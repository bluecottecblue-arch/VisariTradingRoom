from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from db.database import AsyncSessionLocal, InMemorySessionStore, is_db_available

try:
    from sqlalchemy import select
    from db.models import AcademyLessonProgress, AcademyProfile
except Exception:  # pragma: no cover
    AcademyLessonProgress = AcademyProfile = None  # type: ignore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcademyStore:
    _ROOT = "__academy__"

    @classmethod
    def _state(cls) -> dict[str, Any]:
        state = InMemorySessionStore.get(cls._ROOT, "state")
        if not state:
            state = {
                "profiles": {},
                "progress": {},
            }
            InMemorySessionStore.save(cls._ROOT, "state", state)
        return state

    @classmethod
    async def get_profile(cls, username: str) -> Optional[dict[str, Any]]:
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    row = (await db.execute(select(AcademyProfile).where(AcademyProfile.username == username))).scalar_one_or_none()
                    if row:
                        return {
                            "username": row.username,
                            "level_input": row.level_input,
                            "detected_level": row.detected_level,
                            "freeform_background": row.freeform_background,
                            "recommended_module_id": row.recommended_module_id,
                            "recommendation_reason": row.recommendation_reason,
                            "last_viewed_module_id": row.last_viewed_module_id,
                            "last_viewed_lesson_id": row.last_viewed_lesson_id,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                        }
            except Exception:
                pass

        return dict(cls._state()["profiles"].get(username) or {}) or None

    @classmethod
    async def upsert_profile(
        cls,
        *,
        username: str,
        level_input: Optional[str] = None,
        detected_level: Optional[str] = None,
        freeform_background: Optional[str] = None,
        recommended_module_id: Optional[str] = None,
        recommendation_reason: Optional[str] = None,
        last_viewed_module_id: Optional[str] = None,
        last_viewed_lesson_id: Optional[str] = None,
    ) -> dict[str, Any]:
        existing = await cls.get_profile(username) or {}
        payload = {
            "username": username,
            "level_input": level_input if level_input is not None else existing.get("level_input"),
            "detected_level": detected_level if detected_level is not None else existing.get("detected_level") or "beginner",
            "freeform_background": freeform_background if freeform_background is not None else existing.get("freeform_background"),
            "recommended_module_id": recommended_module_id if recommended_module_id is not None else existing.get("recommended_module_id"),
            "recommendation_reason": recommendation_reason if recommendation_reason is not None else existing.get("recommendation_reason"),
            "last_viewed_module_id": last_viewed_module_id if last_viewed_module_id is not None else existing.get("last_viewed_module_id"),
            "last_viewed_lesson_id": last_viewed_lesson_id if last_viewed_lesson_id is not None else existing.get("last_viewed_lesson_id"),
        }

        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    row = (await db.execute(select(AcademyProfile).where(AcademyProfile.username == username))).scalar_one_or_none()
                    if not row:
                        row = AcademyProfile(username=username)  # type: ignore[call-arg]
                        db.add(row)
                    row.level_input = payload["level_input"]
                    row.detected_level = payload["detected_level"]
                    row.freeform_background = payload["freeform_background"]
                    row.recommended_module_id = payload["recommended_module_id"]
                    row.recommendation_reason = payload["recommendation_reason"]
                    row.last_viewed_module_id = payload["last_viewed_module_id"]
                    row.last_viewed_lesson_id = payload["last_viewed_lesson_id"]
                    await db.commit()
                    await db.refresh(row)
                    return {
                        **payload,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
            except Exception:
                pass

        state = cls._state()
        memory_payload = {
            **payload,
            "created_at": existing.get("created_at") or _utc_now().isoformat(),
            "updated_at": _utc_now().isoformat(),
        }
        state["profiles"][username] = memory_payload
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return memory_payload

    @classmethod
    async def list_progress(cls, username: str) -> list[dict[str, Any]]:
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    rows = (
                        await db.execute(
                            select(AcademyLessonProgress)
                            .where(AcademyLessonProgress.username == username)
                            .order_by(AcademyLessonProgress.updated_at.desc(), AcademyLessonProgress.created_at.desc())
                        )
                    ).scalars().all()
                    return [
                        {
                            "id": row.id,
                            "username": row.username,
                            "module_id": row.module_id,
                            "lesson_id": row.lesson_id,
                            "completed": bool(row.completed),
                            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                            "last_viewed_at": row.last_viewed_at.isoformat() if row.last_viewed_at else None,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                        }
                        for row in rows
                    ]
            except Exception:
                pass

        state = cls._state()
        return list((state["progress"].get(username) or {}).values())

    @classmethod
    async def mark_lesson_viewed(cls, *, username: str, module_id: str, lesson_id: str) -> dict[str, Any]:
        return await cls._upsert_progress_record(
            username=username,
            module_id=module_id,
            lesson_id=lesson_id,
            completed=None,
            viewed=True,
        )

    @classmethod
    async def set_lesson_completed(
        cls,
        *,
        username: str,
        module_id: str,
        lesson_id: str,
        completed: bool,
    ) -> dict[str, Any]:
        return await cls._upsert_progress_record(
            username=username,
            module_id=module_id,
            lesson_id=lesson_id,
            completed=completed,
            viewed=True,
        )

    @classmethod
    async def _upsert_progress_record(
        cls,
        *,
        username: str,
        module_id: str,
        lesson_id: str,
        completed: Optional[bool],
        viewed: bool,
    ) -> dict[str, Any]:
        now = _utc_now()
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    row = (
                        await db.execute(
                            select(AcademyLessonProgress).where(
                                AcademyLessonProgress.username == username,
                                AcademyLessonProgress.lesson_id == lesson_id,
                            )
                        )
                    ).scalar_one_or_none()
                    if not row:
                        row = AcademyLessonProgress(  # type: ignore[call-arg]
                            id=str(uuid.uuid4()),
                            username=username,
                            module_id=module_id,
                            lesson_id=lesson_id,
                        )
                        db.add(row)
                    row.module_id = module_id
                    if viewed:
                        row.last_viewed_at = now
                    if completed is not None:
                        row.completed = completed
                        row.completed_at = now if completed else None
                    await db.commit()
                    await db.refresh(row)
                    return {
                        "id": row.id,
                        "username": row.username,
                        "module_id": row.module_id,
                        "lesson_id": row.lesson_id,
                        "completed": bool(row.completed),
                        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                        "last_viewed_at": row.last_viewed_at.isoformat() if row.last_viewed_at else None,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
            except Exception:
                pass

        state = cls._state()
        user_progress = state["progress"].setdefault(username, {})
        record = dict(user_progress.get(lesson_id) or {})
        record.update(
            {
                "id": record.get("id") or str(uuid.uuid4()),
                "username": username,
                "module_id": module_id,
                "lesson_id": lesson_id,
                "completed": record.get("completed", False),
                "completed_at": record.get("completed_at"),
                "last_viewed_at": record.get("last_viewed_at"),
                "created_at": record.get("created_at") or now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        if viewed:
            record["last_viewed_at"] = now.isoformat()
        if completed is not None:
            record["completed"] = completed
            record["completed_at"] = now.isoformat() if completed else None
        user_progress[lesson_id] = record
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return record
