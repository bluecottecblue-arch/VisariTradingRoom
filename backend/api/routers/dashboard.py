from __future__ import annotations

import traceback
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from modules.auth.security import AuthContext, require_authenticated
from modules.dashboard.service import DashboardService


router = APIRouter()


@router.get("/command-center")
async def get_command_center(
    project_id: Optional[str] = Query(default=None),
    timeframe: str = Query(default="30D"),
    source: Literal["auto", "real", "demo"] = Query(default="auto"),
    context: AuthContext = Depends(require_authenticated),
):
    try:
        payload = await DashboardService.get_command_center(
            owner_username=context.username,
            project_id=project_id,
            timeframe=timeframe,
            source=source,
        )
        return {
            "ok": True,
            "dashboard": payload,
        }
    except Exception as exc:
        tb = traceback.format_exc()
        return JSONResponse(status_code=500, content={"error": str(exc), "traceback": tb})
