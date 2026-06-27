from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from modules.auth.security import AuthContext, require_authenticated

router = APIRouter()


class SubmitEntry(BaseModel):
    display_name: Optional[str] = None
    country: str = "IT"
    bot_name: Optional[str] = None
    performance_pct: float = Field(..., ge=-100, le=10000)
    period: str = "ytd"  # ytd | monthly | alltime


def _period_label(p: str) -> str:
    return {"ytd": "Anno in corso", "monthly": "Ultimo mese", "alltime": "All time"}.get(p, p)


async def _get_entries(country: Optional[str] = None, limit: int = 20) -> list[dict]:
    try:
        from db.database import AsyncSessionLocal, is_db_available
        from db.models import LeaderboardEntry
        from sqlalchemy import select, desc

        if not is_db_available():
            return []

        async with AsyncSessionLocal() as session:
            q = select(LeaderboardEntry).where(LeaderboardEntry.is_public == True)
            if country:
                q = q.where(LeaderboardEntry.country == country.upper())
            q = q.order_by(desc(LeaderboardEntry.performance_pct)).limit(limit)
            result = await session.execute(q)
            entries = result.scalars().all()
            return [_entry_to_dict(e, rank=i + 1) for i, e in enumerate(entries)]
    except Exception:
        return []


def _entry_to_dict(e, rank: int = 0) -> dict:
    return {
        "rank": rank,
        "username": e.username,
        "display_name": e.display_name or e.username,
        "country": e.country or "IT",
        "bot_name": e.bot_name,
        "performance_pct": round(float(e.performance_pct), 2),
        "period": e.period,
        "period_label": _period_label(e.period),
        "verified": bool(e.verified),
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@router.get("/global")
async def leaderboard_global(limit: int = 20):
    entries = await _get_entries(limit=min(limit, 50))
    return {"ok": True, "scope": "global", "entries": entries}


@router.get("/national")
async def leaderboard_national(country: str = "IT", limit: int = 20):
    entries = await _get_entries(country=country, limit=min(limit, 50))
    return {"ok": True, "scope": "national", "country": country.upper(), "entries": entries}


@router.get("/me")
async def leaderboard_me(context: AuthContext = Depends(require_authenticated)):
    try:
        from db.database import AsyncSessionLocal, is_db_available
        from db.models import LeaderboardEntry

        if not is_db_available():
            return {"ok": True, "entry": None}

        async with AsyncSessionLocal() as session:
            entry = await session.get(LeaderboardEntry, context.username)
            return {"ok": True, "entry": _entry_to_dict(entry) if entry else None}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/me")
async def leaderboard_submit(payload: SubmitEntry, context: AuthContext = Depends(require_authenticated)):
    try:
        from db.database import AsyncSessionLocal, is_db_available
        from db.models import LeaderboardEntry
        from datetime import datetime, timezone

        if not is_db_available():
            raise HTTPException(status_code=503, detail="Database non disponibile")

        valid_periods = {"ytd", "monthly", "alltime"}
        if payload.period not in valid_periods:
            raise HTTPException(status_code=400, detail="Period non valido")

        async with AsyncSessionLocal() as session:
            entry = await session.get(LeaderboardEntry, context.username)
            if entry:
                entry.display_name = payload.display_name
                entry.country = payload.country.upper()[:2]
                entry.bot_name = payload.bot_name
                entry.performance_pct = payload.performance_pct
                entry.period = payload.period
                entry.is_public = True
                entry.updated_at = datetime.now(timezone.utc)
            else:
                entry = LeaderboardEntry(
                    username=context.username,
                    display_name=payload.display_name,
                    country=payload.country.upper()[:2],
                    bot_name=payload.bot_name,
                    performance_pct=payload.performance_pct,
                    period=payload.period,
                    is_public=True,
                )
                session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return {"ok": True, "entry": _entry_to_dict(entry)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/me")
async def leaderboard_remove(context: AuthContext = Depends(require_authenticated)):
    try:
        from db.database import AsyncSessionLocal, is_db_available
        from db.models import LeaderboardEntry

        if not is_db_available():
            raise HTTPException(status_code=503, detail="Database non disponibile")

        async with AsyncSessionLocal() as session:
            entry = await session.get(LeaderboardEntry, context.username)
            if entry:
                await session.delete(entry)
                await session.commit()
        return {"ok": True, "removed": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
