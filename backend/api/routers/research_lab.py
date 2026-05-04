from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from modules.auth.security import AuthContext, require_authenticated
from modules.research_lab.service import ResearchLabService


router = APIRouter()


class UploadDatasetRequest(BaseModel):
    title: str
    csv_text: str
    project_id: Optional[str] = None


class FetchDatasetRequest(BaseModel):
    title: str
    provider: str = "demo"
    symbol: str
    timeframe: str = "H1"
    date_from: str
    date_to: str
    project_id: Optional[str] = None


class TrainModelRequest(BaseModel):
    dataset_id: str
    title: Optional[str] = None
    horizon_bars: int = Field(default=12, ge=2, le=200)
    return_threshold_bps: float = Field(default=8.0, ge=0.0, le=500.0)
    train_ratio: float = Field(default=0.6, gt=0.3, lt=0.85)
    validation_ratio: float = Field(default=0.2, gt=0.05, lt=0.4)
    learning_rate: float = Field(default=0.05, gt=0.001, le=0.5)
    epochs: int = Field(default=600, ge=120, le=4000)
    l2_penalty: float = Field(default=0.002, ge=0.0, le=1.0)


@router.get("/bootstrap")
async def research_bootstrap(context: AuthContext = Depends(require_authenticated)):
    return {
        "ok": True,
        **(await ResearchLabService.bootstrap(context.username)),
    }


@router.post("/datasets/upload")
async def upload_dataset(payload: UploadDatasetRequest, context: AuthContext = Depends(require_authenticated)):
    try:
        dataset = await ResearchLabService.ingest_uploaded_csv(
            owner_username=context.username,
            title=payload.title,
            csv_text=payload.csv_text,
            project_id=payload.project_id,
        )
        return {"ok": True, "dataset": dataset}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/datasets/fetch")
async def fetch_dataset(payload: FetchDatasetRequest, context: AuthContext = Depends(require_authenticated)):
    try:
        dataset = await ResearchLabService.fetch_market_data(
            owner_username=context.username,
            title=payload.title,
            provider=payload.provider,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            date_from=payload.date_from,
            date_to=payload.date_to,
            project_id=payload.project_id,
        )
        return {"ok": True, "dataset": dataset}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/train")
async def train_model(payload: TrainModelRequest, context: AuthContext = Depends(require_authenticated)):
    try:
        run = await ResearchLabService.train_statistical_model(
            owner_username=context.username,
            dataset_id=payload.dataset_id,
            title=payload.title,
            horizon_bars=payload.horizon_bars,
            return_threshold_bps=payload.return_threshold_bps,
            train_ratio=payload.train_ratio,
            validation_ratio=payload.validation_ratio,
            learning_rate=payload.learning_rate,
            epochs=payload.epochs,
            l2_penalty=payload.l2_penalty,
        )
        return {"ok": True, "run": run}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
