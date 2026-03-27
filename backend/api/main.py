"""
VisariTradingRoom — Backend principale (FastAPI)
"""
import os
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import traceback
import logging
from contextlib import asynccontextmanager

from api.routers import auth, strategy, backtest, export, guide, botlab, projects, dashboard
from modules.auth.security import require_authenticated
from db.database import DATABASE_URL, init_db, is_db_available, resolve_storage_root


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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return response

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"], dependencies=[Depends(require_authenticated)])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"], dependencies=[Depends(require_authenticated)])
app.include_router(strategy.router, prefix="/api/strategy", tags=["Strategy"], dependencies=[Depends(require_authenticated)])
app.include_router(backtest.router, prefix="/api/backtest", tags=["Backtest"], dependencies=[Depends(require_authenticated)])
app.include_router(botlab.router, prefix="/api/bot-lab", tags=["Bot Lab"], dependencies=[Depends(require_authenticated)])
app.include_router(export.router, prefix="/api/export", tags=["Export"], dependencies=[Depends(require_authenticated)])
app.include_router(guide.router, prefix="/api/guide", tags=["Guide"], dependencies=[Depends(require_authenticated)])

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Errore non gestito: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Si è verificato un errore interno al server. Riprova tra qualche istante."},
    )


@app.get("/health")
async def health():
    storage_root = str(resolve_storage_root())
    return {
        "status": "ok",
        "service": "VisariTradingRoom",
        "persistence": {
            "db_available": is_db_available(),
            "db_mode": "postgres" if "postgresql+asyncpg://" in DATABASE_URL else "sqlite",
            "storage_mode": "persistent_candidate"
            if (
                "PERSISTENT_STORAGE_PATH" in os.environ
                or "RENDER_DISK_ROOT" in os.environ
                or storage_root.startswith("/var/data/")
            )
            else "local_storage",
        },
    }
