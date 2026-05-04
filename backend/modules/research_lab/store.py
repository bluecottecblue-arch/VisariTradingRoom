from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from db.database import AsyncSessionLocal, InMemorySessionStore, is_db_available

try:
    from sqlalchemy import select
    from db.models import ResearchDataset, ResearchModelRun
except Exception:  # pragma: no cover
    ResearchDataset = ResearchModelRun = None  # type: ignore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchLabStore:
    _ROOT = "__research_lab__"

    @classmethod
    def _state(cls) -> dict[str, Any]:
        state = InMemorySessionStore.get(cls._ROOT, "state")
        if not state:
            state = {"datasets": {}, "runs": {}}
            InMemorySessionStore.save(cls._ROOT, "state", state)
        return state

    @classmethod
    async def create_dataset(
        cls,
        *,
        owner_username: str,
        project_id: Optional[str],
        title: str,
        source: str,
        symbol: Optional[str],
        timeframe: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        row_count: int,
        quality: dict[str, Any],
        metadata: dict[str, Any],
        storage_path: str,
    ) -> dict[str, Any]:
        dataset_id = str(uuid.uuid4())
        payload = {
            "dataset_id": dataset_id,
            "owner_username": owner_username,
            "project_id": project_id,
            "title": title,
            "source": source,
            "symbol": symbol,
            "timeframe": timeframe,
            "date_from": date_from,
            "date_to": date_to,
            "row_count": int(row_count),
            "quality": quality or {},
            "metadata": metadata or {},
            "storage_path": storage_path,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    db.add(
                        ResearchDataset(
                            id=dataset_id,
                            owner_username=owner_username,
                            project_id=project_id,
                            title=title,
                            source=source,
                            symbol=symbol,
                            timeframe=timeframe,
                            date_from=date_from,
                            date_to=date_to,
                            row_count=int(row_count),
                            quality_json=quality or {},
                            metadata_json=metadata or {},
                            storage_path=storage_path,
                        )
                    )
                    await db.commit()
                return payload
            except Exception:
                pass
        state = cls._state()
        state["datasets"][dataset_id] = payload
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return payload

    @classmethod
    async def list_datasets(cls, owner_username: str) -> list[dict[str, Any]]:
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    rows = (
                        await db.execute(
                            select(ResearchDataset)
                            .where(ResearchDataset.owner_username == owner_username)
                            .order_by(ResearchDataset.updated_at.desc(), ResearchDataset.created_at.desc())
                        )
                    ).scalars().all()
                    return [
                        {
                            "dataset_id": row.id,
                            "owner_username": row.owner_username,
                            "project_id": row.project_id,
                            "title": row.title,
                            "source": row.source,
                            "symbol": row.symbol,
                            "timeframe": row.timeframe,
                            "date_from": row.date_from,
                            "date_to": row.date_to,
                            "row_count": row.row_count,
                            "quality": row.quality_json or {},
                            "metadata": row.metadata_json or {},
                            "storage_path": row.storage_path,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                        }
                        for row in rows
                    ]
            except Exception:
                pass
        state = cls._state()
        return sorted(
            [item for item in state["datasets"].values() if item.get("owner_username") == owner_username],
            key=lambda item: item.get("updated_at") or "",
            reverse=True,
        )

    @classmethod
    async def get_dataset(cls, owner_username: str, dataset_id: str) -> Optional[dict[str, Any]]:
        datasets = await cls.list_datasets(owner_username)
        return next((item for item in datasets if item["dataset_id"] == dataset_id), None)

    @classmethod
    async def update_dataset(cls, owner_username: str, dataset_id: str, **changes: Any) -> Optional[dict[str, Any]]:
        dataset = await cls.get_dataset(owner_username, dataset_id)
        if not dataset:
            return None
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    row = (
                        await db.execute(
                            select(ResearchDataset).where(
                                ResearchDataset.id == dataset_id,
                                ResearchDataset.owner_username == owner_username,
                            )
                        )
                    ).scalar_one_or_none()
                    if not row:
                        return None
                    for key, value in changes.items():
                        if key == "quality":
                            row.quality_json = value or {}
                        elif key == "metadata":
                            row.metadata_json = value or {}
                        elif key == "row_count":
                            row.row_count = int(value or 0)
                        elif key == "storage_path":
                            row.storage_path = value
                        elif key in {"title", "source", "symbol", "timeframe", "date_from", "date_to", "project_id"}:
                            setattr(row, key, value)
                    await db.commit()
                return await cls.get_dataset(owner_username, dataset_id)
            except Exception:
                pass
        state = cls._state()
        item = state["datasets"].get(dataset_id)
        if not item:
            return None
        item.update(changes)
        item["updated_at"] = _utc_now()
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return item

    @classmethod
    async def create_run(
        cls,
        *,
        dataset_id: str,
        owner_username: str,
        project_id: Optional[str],
        title: str,
        model_type: str,
        config: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        payload = {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "owner_username": owner_username,
            "project_id": project_id,
            "title": title,
            "model_type": model_type,
            "config": config or {},
            "result": result or {},
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    db.add(
                        ResearchModelRun(
                            id=run_id,
                            dataset_id=dataset_id,
                            owner_username=owner_username,
                            project_id=project_id,
                            title=title,
                            model_type=model_type,
                            config_json=config or {},
                            result_json=result or {},
                        )
                    )
                    await db.commit()
                return payload
            except Exception:
                pass
        state = cls._state()
        state["runs"][run_id] = payload
        InMemorySessionStore.save(cls._ROOT, "state", state)
        return payload

    @classmethod
    async def list_runs(cls, owner_username: str) -> list[dict[str, Any]]:
        if is_db_available():
            try:
                async with AsyncSessionLocal() as db:  # type: ignore[arg-type]
                    rows = (
                        await db.execute(
                            select(ResearchModelRun)
                            .where(ResearchModelRun.owner_username == owner_username)
                            .order_by(ResearchModelRun.updated_at.desc(), ResearchModelRun.created_at.desc())
                        )
                    ).scalars().all()
                    return [
                        {
                            "run_id": row.id,
                            "dataset_id": row.dataset_id,
                            "owner_username": row.owner_username,
                            "project_id": row.project_id,
                            "title": row.title,
                            "model_type": row.model_type,
                            "config": row.config_json or {},
                            "result": row.result_json or {},
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                        }
                        for row in rows
                    ]
            except Exception:
                pass
        state = cls._state()
        return sorted(
            [item for item in state["runs"].values() if item.get("owner_username") == owner_username],
            key=lambda item: item.get("updated_at") or "",
            reverse=True,
        )
