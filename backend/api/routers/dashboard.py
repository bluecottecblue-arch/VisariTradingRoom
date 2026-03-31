from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from modules.auth.security import AuthContext, require_authenticated
from modules.dashboard.service import DashboardService
from modules.projects.store import ProjectStore


router = APIRouter()


class LiveSignalIn(BaseModel):
    timestamp: str
    symbol: str
    side: str
    status: str
    price: float = 0.0
    reason: str = ""


class LivePositionIn(BaseModel):
    id: str
    symbol: str
    side: str
    size: float
    entry: float
    pnl: float
    stop: float = 0.0
    take_profit: float = 0.0
    status: str = "OPEN"


class LiveMonitorIngestRequest(BaseModel):
    project_id: str
    monitor_token: str
    timestamp: Optional[str] = None
    bot_label: Optional[str] = None
    equity: float
    balance: Optional[float] = None
    available_cash: Optional[float] = None
    today_pnl_pct: float = 0.0
    risk_usage_pct: float = 0.0
    var_proxy_pct: float = 0.0
    leverage_proxy: float = 1.0
    exposure_pct: float = 0.0
    daily_loss_used_pct: float = 0.0
    kill_switch_status: str = "NOMINAL"
    max_drawdown_pct: float = 0.0
    regime: str = "Unknown"
    volatility: str = "Unknown"
    news_risk_active: bool = False
    news_provider: str = "none"
    news_events: int = 0
    macro_filter_status: str = "Inactive"
    directional_bias: str = "Neutral"
    data_provider: str = "mt5_bridge"
    data_feed_status: str = "Live"
    engine_status: str = "Running"
    provider_status: str = "Connected"
    export_status: str = "Package ready"
    latency_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    equity_curve: list[float] = Field(default_factory=list)
    recent_signals: list[LiveSignalIn] = Field(default_factory=list)
    open_positions: list[LivePositionIn] = Field(default_factory=list)


@router.get("/command-center")
async def get_command_center(
    project_id: Optional[str] = Query(default=None),
    timeframe: str = Query(default="30D"),
    source: Literal["auto", "live", "real", "demo"] = Query(default="auto"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    context: AuthContext = Depends(require_authenticated),
):
    payload = await DashboardService.get_command_center(
        owner_username=context.username,
        project_id=project_id,
        timeframe=timeframe,
        source=source,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "ok": True,
        "dashboard": payload,
    }


@router.post("/live-monitor-ingest")
async def ingest_live_monitor(payload: LiveMonitorIngestRequest):
    project = await ProjectStore.get_project_unscoped(payload.project_id)
    if not project:
      raise HTTPException(status_code=404, detail="Progetto non trovato")

    token = str((project.get("metadata") or {}).get("live_monitor_token") or "").strip()
    if not token or token != payload.monitor_token:
        raise HTTPException(status_code=403, detail="Token live monitor non valido")

    snapshot = payload.model_dump()
    snapshot["owner_username"] = project.get("owner_username")
    version = await ProjectStore.add_version(
        project_id=payload.project_id,
        session_id=project.get("active_session_id"),
        version_kind="live_monitor_snapshot",
        status="live",
        payload=snapshot,
        summary={
            "mode": "live",
            "equity": payload.equity,
            "positions": len(payload.open_positions),
            "signals": len(payload.recent_signals),
            "latency_ms": payload.latency_ms,
        },
    )
    await ProjectStore.update_project(
        payload.project_id,
        metadata={
            "last_live_ingest_at": payload.timestamp or version.get("created_at"),
        },
    )
    return {
        "ok": True,
        "version_id": version["version_id"],
    }
