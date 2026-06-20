"""
Provider Polygon.io — dati equity, FX, crypto.

Documentazione: https://polygon.io/docs
API key richiesta. Piano gratuito: dati storici end-of-day (EOD) con ritardo 15 minuti.
Piano a pagamento: intraday senza ritardo.

Variabile .env: POLYGON_API_KEY
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import requests

from ..provider_base import DataProviderBase

logger = logging.getLogger(__name__)

_TIMEFRAME_MAP = {
    "1m": ("minute", 1),
    "5m": ("minute", 5),
    "15m": ("minute", 15),
    "30m": ("minute", 30),
    "1h": ("hour", 1),
    "4h": ("hour", 4),
    "1d": ("day", 1),
    "1w": ("week", 1),
}


class PolygonProvider(DataProviderBase):
    """
    Polygon.io — provider affidabile per equity USA, FX, crypto.
    Prezzi equity: adjusted di default (split + dividendi).
    FX/Crypto: nessun aggiustamento, ma possibili differenze di liquidità tra broker.
    """

    name = "polygon"
    BASE_URL = "https://api.polygon.io"

    def fetch_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        self._validate_dates(start, end)
        if not self.api_key:
            raise ValueError("POLYGON_API_KEY non impostata nel file .env")

        tf_info = _TIMEFRAME_MAP.get(timeframe.lower())
        if tf_info is None:
            raise ValueError(f"Timeframe '{timeframe}' non supportato da Polygon. Usa: {list(_TIMEFRAME_MAP.keys())}")

        span, multiplier = tf_info
        url = f"{self.BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/{multiplier}/{span}/{start}/{end}"

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.api_key,
        }

        rows = []
        while url:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 403:
                raise ValueError("Polygon API key non valida o piano insufficiente per questo dato.")
            resp.raise_for_status()
            data = resp.json()

            if data.get("resultsCount", 0) == 0:
                break

            for r in data.get("results", []):
                rows.append({
                    "timestamp": pd.Timestamp(r["t"], unit="ms", tz="UTC"),
                    "open": r["o"],
                    "high": r["h"],
                    "low": r["l"],
                    "close": r["c"],
                    "volume": r.get("v", 0),
                })

            url = data.get("next_url")
            params = {"apiKey": self.api_key} if url else {}

        if not rows:
            raise ValueError(f"Nessun dato trovato per {symbol} ({start} → {end}).")

        df = pd.DataFrame(rows)
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        logger.info("Polygon: scaricati %d bar per %s", len(df), symbol)
        return df
