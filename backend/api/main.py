"""
VisariTradingRoom — Backend principale (FastAPI)
"""
import os
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routers import auth, strategy, backtest, export, guide
from modules.auth.security import require_authenticated
from db.database import init_db


def _load_cors_origins() -> list[str]:
    raw = os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="VisariTradingRoom API",
    description="Traduttore da strategia discrezionale a bot algoritmico MT5",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
    allow_origin_regex=os.environ.get("CORS_ALLOW_ORIGIN_REGEX"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(strategy.router, prefix="/api/strategy", tags=["Strategy"], dependencies=[Depends(require_authenticated)])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"], dependencies=[Depends(require_authenticated)])
app.include_router(export.router, prefix="/api/export", tags=["Export"], dependencies=[Depends(require_authenticated)])
app.include_router(guide.router, prefix="/api/guide", tags=["Guide"], dependencies=[Depends(require_authenticated)])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "VisariTradingRoom"}
