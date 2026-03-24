from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from db.database import AsyncSessionLocal, InMemorySessionStore

try:
    import greenlet  # noqa: F401
    from sqlalchemy import select
    from db.models import JobRun, Project, ProjectArtifact, ProjectVersion
    _DB_AVAILABLE = AsyncSessionLocal is not None
except Exception:  # pragma: no cover
    JobRun = Project = ProjectArtifact = ProjectVersion = None  # type: ignore
    _DB_AVAILABLE = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ProjectStore:
    _MEMORY_ROOT = "__projects__"

    @classmethod
    def _memory(cls) -> dict[str, Any]:
        memory = InMemorySessionStore.get(cls._MEMORY_ROOT) or {}
        if not memory:
            memory = {
                "projects": {},
                "versions": {},
                "artifacts": {},
                "jobs": {},
            }
            InMemorySessionStore.save(cls._MEMORY_ROOT, "state", memory)
        return memory

    @classmethod
    def _memory_state(cls) -> dict[str, Any]:
        state = InMemorySessionStore.get(cls._MEMORY_ROOT, "state")
        if not state:
            state = {
                "projects": {},
                "versions": {},
                "artifacts": {},
                "jobs": {},
            }
            InMemorySessionStore.save(cls._MEMORY_ROOT, "state", state)
        return state

    @classmethod
    async def create_project(cls, *, owner_username: str, title: str, mode: str = "strategy") -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        now = _utc_now()
        project = {
            "project_id": project_id,
            "owner_username": owner_username,
            "title": (title or "Untitled Project").strip() or "Untitled Project",
            "mode": mode,
            "status": "active",
            "active_session_id": None,
            "latest_verdict": None,
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                row = Project(
                    id=project_id,
                    owner_username=project["owner_username"],
                    title=project["title"],
                    mode=project["mode"],
                    status=project["status"],
                    metadata_json={},
                )
                db.add(row)
                await db.commit()
            return project

        state = cls._memory_state()
        state["projects"][project_id] = project
        InMemorySessionStore.save(cls._MEMORY_ROOT, "state", state)
        return project

    @classmethod
    async def list_projects(cls, owner_username: str) -> list[dict[str, Any]]:
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                stmt = (
                    select(Project)
                    .where(Project.owner_username == owner_username)
                    .order_by(Project.updated_at.desc(), Project.created_at.desc())
                )
                rows = (await db.execute(stmt)).scalars().all()
                return [
                    {
                        "project_id": row.id,
                        "owner_username": row.owner_username,
                        "title": row.title,
                        "mode": row.mode,
                        "status": row.status,
                        "active_session_id": row.active_session_id,
                        "latest_verdict": row.latest_verdict,
                        "metadata": row.metadata_json or {},
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
                    for row in rows
                ]

        state = cls._memory_state()
        projects = [
            value for value in state["projects"].values()
            if value.get("owner_username") == owner_username
        ]
        return sorted(projects, key=lambda item: item.get("updated_at") or "", reverse=True)

    @classmethod
    async def get_project(cls, owner_username: str, project_id: str) -> Optional[dict[str, Any]]:
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                stmt = select(Project).where(Project.id == project_id, Project.owner_username == owner_username)
                row = (await db.execute(stmt)).scalar_one_or_none()
                if not row:
                    return None
                versions = await cls.list_versions(project_id)
                artifacts = await cls.list_artifacts(project_id)
                jobs = await cls.list_jobs(project_id)
                return {
                    "project_id": row.id,
                    "owner_username": row.owner_username,
                    "title": row.title,
                    "mode": row.mode,
                    "status": row.status,
                    "active_session_id": row.active_session_id,
                    "latest_verdict": row.latest_verdict,
                    "metadata": row.metadata_json or {},
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "versions": versions,
                    "artifacts": artifacts,
                    "jobs": jobs,
                }

        state = cls._memory_state()
        project = state["projects"].get(project_id)
        if not project or project.get("owner_username") != owner_username:
            return None
        return {
            **project,
            "versions": state["versions"].get(project_id, []),
            "artifacts": state["artifacts"].get(project_id, []),
            "jobs": state["jobs"].get(project_id, []),
        }

    @classmethod
    async def update_project(cls, project_id: str, **changes: Any) -> None:
        allowed = {"title", "mode", "status", "active_session_id", "latest_verdict", "metadata"}
        filtered = {key: value for key, value in changes.items() if key in allowed}
        if not filtered:
            return
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                row = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
                if not row:
                    return
                for key, value in filtered.items():
                    if key == "metadata":
                        merged = dict(row.metadata_json or {})
                        merged.update(value or {})
                        row.metadata_json = merged
                    else:
                        setattr(row, key, value)
                await db.commit()
            return

        state = cls._memory_state()
        project = state["projects"].get(project_id)
        if not project:
            return
        if "metadata" in filtered:
            merged = dict(project.get("metadata") or {})
            merged.update(filtered.pop("metadata") or {})
            project["metadata"] = merged
        project.update(filtered)
        project["updated_at"] = _utc_now()
        InMemorySessionStore.save(cls._MEMORY_ROOT, "state", state)

    @classmethod
    async def add_version(
        cls,
        *,
        project_id: str,
        session_id: Optional[str],
        version_kind: str,
        status: str,
        payload: Any,
        summary: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        version_id = str(uuid.uuid4())
        item = {
            "version_id": version_id,
            "project_id": project_id,
            "session_id": session_id,
            "version_kind": version_kind,
            "status": status,
            "summary": summary or {},
            "payload": payload,
            "fingerprint": _fingerprint(payload),
            "created_at": _utc_now(),
        }
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                db.add(
                    ProjectVersion(
                        id=version_id,
                        project_id=project_id,
                        session_id=session_id,
                        version_kind=version_kind,
                        status=status,
                        summary=item["summary"],
                        payload=payload,
                        fingerprint=item["fingerprint"],
                    )
                )
                await db.commit()
            return item

        state = cls._memory_state()
        state["versions"].setdefault(project_id, []).append(item)
        InMemorySessionStore.save(cls._MEMORY_ROOT, "state", state)
        return item

    @classmethod
    async def list_versions(cls, project_id: str) -> list[dict[str, Any]]:
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                rows = (
                    await db.execute(
                        select(ProjectVersion)
                        .where(ProjectVersion.project_id == project_id)
                        .order_by(ProjectVersion.created_at.desc())
                    )
                ).scalars().all()
                return [
                    {
                        "version_id": row.id,
                        "project_id": row.project_id,
                        "session_id": row.session_id,
                        "version_kind": row.version_kind,
                        "status": row.status,
                        "summary": row.summary or {},
                        "fingerprint": row.fingerprint,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in rows
                ]

        state = cls._memory_state()
        return list(reversed(state["versions"].get(project_id, [])))

    @classmethod
    async def add_artifact(
        cls,
        *,
        project_id: str,
        session_id: Optional[str],
        artifact_type: str,
        label: str,
        storage_path: Optional[str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        artifact_id = str(uuid.uuid4())
        item = {
            "artifact_id": artifact_id,
            "project_id": project_id,
            "session_id": session_id,
            "artifact_type": artifact_type,
            "label": label,
            "storage_path": storage_path,
            "metadata": metadata or {},
            "created_at": _utc_now(),
        }
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                db.add(
                    ProjectArtifact(
                        id=artifact_id,
                        project_id=project_id,
                        session_id=session_id,
                        artifact_type=artifact_type,
                        label=label,
                        storage_path=storage_path,
                        metadata_json=item["metadata"],
                    )
                )
                await db.commit()
            return item

        state = cls._memory_state()
        state["artifacts"].setdefault(project_id, []).append(item)
        InMemorySessionStore.save(cls._MEMORY_ROOT, "state", state)
        return item

    @classmethod
    async def list_artifacts(cls, project_id: str) -> list[dict[str, Any]]:
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                rows = (
                    await db.execute(
                        select(ProjectArtifact)
                        .where(ProjectArtifact.project_id == project_id)
                        .order_by(ProjectArtifact.created_at.desc())
                    )
                ).scalars().all()
                return [
                    {
                        "artifact_id": row.id,
                        "project_id": row.project_id,
                        "session_id": row.session_id,
                        "artifact_type": row.artifact_type,
                        "label": row.label,
                        "storage_path": row.storage_path,
                        "metadata": row.metadata_json or {},
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in rows
                ]

        state = cls._memory_state()
        return list(reversed(state["artifacts"].get(project_id, [])))

    @classmethod
    async def create_job(
        cls,
        *,
        project_id: Optional[str],
        session_id: Optional[str],
        job_type: str,
        payload: Optional[dict[str, Any]] = None,
        status: str = "queued",
    ) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        item = {
            "job_id": job_id,
            "project_id": project_id,
            "session_id": session_id,
            "job_type": job_type,
            "status": status,
            "error": None,
            "payload": payload or {},
            "result_summary": {},
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                db.add(
                    JobRun(
                        id=job_id,
                        project_id=project_id,
                        session_id=session_id,
                        job_type=job_type,
                        status=status,
                        payload=item["payload"],
                        result_summary={},
                    )
                )
                await db.commit()
            return item

        state = cls._memory_state()
        state["jobs"].setdefault(project_id or "__orphan__", []).append(item)
        InMemorySessionStore.save(cls._MEMORY_ROOT, "state", state)
        return item

    @classmethod
    async def update_job(
        cls,
        job_id: str,
        *,
        status: str,
        error: Optional[str] = None,
        result_summary: Optional[dict[str, Any]] = None,
    ) -> None:
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                row = (await db.execute(select(JobRun).where(JobRun.id == job_id))).scalar_one_or_none()
                if not row:
                    return
                row.status = status
                row.error = error
                if result_summary is not None:
                    row.result_summary = result_summary
                await db.commit()
            return

        state = cls._memory_state()
        for items in state["jobs"].values():
            for item in items:
                if item["job_id"] == job_id:
                    item["status"] = status
                    item["error"] = error
                    if result_summary is not None:
                        item["result_summary"] = result_summary
                    item["updated_at"] = _utc_now()
                    InMemorySessionStore.save(cls._MEMORY_ROOT, "state", state)
                    return

    @classmethod
    async def list_jobs(cls, project_id: str) -> list[dict[str, Any]]:
        if _DB_AVAILABLE:
            async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                rows = (
                    await db.execute(
                        select(JobRun)
                        .where(JobRun.project_id == project_id)
                        .order_by(JobRun.created_at.desc())
                    )
                ).scalars().all()
                return [
                    {
                        "job_id": row.id,
                        "project_id": row.project_id,
                        "session_id": row.session_id,
                        "job_type": row.job_type,
                        "status": row.status,
                        "error": row.error,
                        "payload": row.payload or {},
                        "result_summary": row.result_summary or {},
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
                    for row in rows
                ]

        state = cls._memory_state()
        return list(reversed(state["jobs"].get(project_id, [])))
