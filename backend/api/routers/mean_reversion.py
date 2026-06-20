"""
Router FastAPI per il Mean Reversion Lab.

Endpoints:
  POST /api/mean-reversion/analyze-file   — analisi da CSV/Excel/Parquet caricato come base64
  POST /api/mean-reversion/analyze-api    — analisi da provider dati
  GET  /api/mean-reversion/providers      — lista provider disponibili
"""
from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from modules.auth.security import AuthContext, require_authenticated

logger = logging.getLogger(__name__)
router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=2)

# --- Schemi Pydantic ---

class AnalysisConfig(BaseModel):
    """Parametri comuni a tutti i tipi di analisi."""
    price_column: str = "close"
    series_transform: Literal["price", "log_price", "returns", "log_returns"] = "log_price"
    asset_type: Literal["equity", "fx", "crypto", "index"] = "equity"
    fill_method: Optional[Literal["ffill", "bfill"]] = None
    # Split
    split_method: Literal["ratio", "date", "none"] = "ratio"
    split_ratio: float = Field(default=0.7, ge=0.1, le=0.95)
    split_date: Optional[str] = None
    # ADF
    adf_regression: Literal["c", "ct", "ctt", "n"] = "c"
    adf_autolag: Optional[Literal["AIC", "BIC", "t-stat"]] = "AIC"
    adf_maxlag: Optional[int] = Field(default=None, ge=1, le=50)
    # Hurst
    rolling_window: Optional[int] = Field(default=60, ge=20, le=500)
    # VR
    vr_lags: Optional[list[int]] = None
    # Monte Carlo
    mc_n_sims: int = Field(default=500, ge=50, le=2000)
    mc_method: Literal["gbm", "bootstrap", "permutation"] = "bootstrap"
    mc_seed: int = 42
    mc_vr_lag: int = Field(default=10, ge=2, le=60)


class AnalyzeFileRequest(BaseModel):
    """Richiesta analisi da file caricato come base64."""
    filename: str
    file_base64: str
    column_map: Optional[dict[str, str]] = None
    config: AnalysisConfig = Field(default_factory=AnalysisConfig)


class AnalyzeApiRequest(BaseModel):
    """Richiesta analisi da provider API."""
    provider: str
    symbol: str
    timeframe: str = "1d"
    start: str
    end: str
    api_key: Optional[str] = None
    config: AnalysisConfig = Field(default_factory=AnalysisConfig)


# --- Helper ---

def _get_api_key(provider: str, override: Optional[str]) -> Optional[str]:
    """Cerca la chiave API: prima nell'override, poi nell'env."""
    if override:
        return override
    key_map = {
        "polygon": "POLYGON_API_KEY",
        "twelve_data": "TWELVE_DATA_API_KEY",
        "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
    }
    env_key = key_map.get(provider.lower())
    return os.environ.get(env_key) if env_key else None


def _run_analysis_sync(df, config: AnalysisConfig) -> dict:
    """Esegue l'analisi in thread separato (CPU-bound)."""
    from modules.mean_reversion.service import MeanReversionService
    return MeanReversionService.run_from_dataframe(
        df=df,
        price_column=config.price_column,
        series_transform=config.series_transform,
        split_method=config.split_method,
        split_ratio=config.split_ratio,
        split_date=config.split_date,
        asset_type=config.asset_type,
        fill_method=config.fill_method,
        adf_regression=config.adf_regression,
        adf_autolag=config.adf_autolag,
        adf_maxlag=config.adf_maxlag,
        rolling_window=config.rolling_window,
        vr_lags=config.vr_lags,
        mc_n_sims=config.mc_n_sims,
        mc_method=config.mc_method,
        mc_seed=config.mc_seed,
        mc_vr_lag=config.mc_vr_lag,
    )


# --- Endpoints ---

@router.get("/providers")
async def list_providers(_: AuthContext = Depends(require_authenticated)):
    """Lista dei provider dati disponibili."""
    from modules.mean_reversion.data_loading.provider_base import list_providers
    providers = list_providers()
    return {
        "ok": True,
        "providers": providers,
        "note": (
            "yfinance è disponibile come fallback non affidabile. "
            "stooq è gratuito e senza API key (solo dati giornalieri). "
            "polygon, twelve_data, alpha_vantage richiedono API key nel file .env."
        ),
    }


@router.post("/analyze-file")
async def analyze_file(
    payload: AnalyzeFileRequest,
    context: AuthContext = Depends(require_authenticated),
):
    """
    Analisi di mean-reversion da file caricato (CSV, Excel, Parquet) in base64.
    Restituisce i risultati completi inclusi grafici come base64 PNG.
    """
    try:
        from modules.mean_reversion.data_loading.file_loader import load_from_base64
        df = load_from_base64(payload.file_base64, payload.filename, payload.column_map)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Errore caricamento file: {exc}")

    if len(df) < 20:
        raise HTTPException(status_code=400, detail="Dataset troppo piccolo (< 20 righe).")

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor, _run_analysis_sync, df, payload.config
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Errore analisi mean-reversion (file): %s", exc)
        raise HTTPException(status_code=500, detail=f"Errore interno: {exc}")

    return result


@router.post("/analyze-api")
async def analyze_api(
    payload: AnalyzeApiRequest,
    context: AuthContext = Depends(require_authenticated),
):
    """
    Analisi di mean-reversion scaricando dati dal provider specificato.
    """
    api_key = _get_api_key(payload.provider, payload.api_key)

    try:
        from modules.mean_reversion.data_loading.provider_base import get_provider
        provider = get_provider(payload.provider, api_key=api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    loop = asyncio.get_event_loop()

    def _fetch_and_analyze():
        df = provider.fetch_ohlcv(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            start=payload.start,
            end=payload.end,
        )
        if len(df) < 20:
            raise ValueError(f"Dataset scaricato troppo piccolo ({len(df)} righe).")
        return _run_analysis_sync(df, payload.config)

    try:
        result = await loop.run_in_executor(_executor, _fetch_and_analyze)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Errore analisi mean-reversion (API %s): %s", payload.provider, exc)
        raise HTTPException(status_code=500, detail=f"Errore scaricamento/analisi: {exc}")

    return {
        **result,
        "data_source": {
            "provider": payload.provider,
            "symbol": payload.symbol,
            "timeframe": payload.timeframe,
            "start": payload.start,
            "end": payload.end,
        },
    }
