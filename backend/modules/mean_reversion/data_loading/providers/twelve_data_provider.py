"""
Provider Twelve Data — equity, FX, ETF, crypto, indici.

Documentazione: https://twelvedata.com/docs
API key richiesta. Piano gratuito: 8 req/min, dati storici limitati.

Variabile .env: TWELVE_DATA_API_KEY
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import requests

from ..provider_base import DataProviderBase

logger = logging.getLogger(__name__)

_TIMEFRAME_MAP = {
    "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h",
    "1d": "1day", "1w": "1week",
}


class TwelveDataProvider(DataProviderBase):
    """
    Twelve Data — buona copertura globale. Prezzi equity non sempre adjusted.
    Attenzione: verifica se i dati equity includono aggiustamento dividendi/split
    prima di usare il close grezzo per l'analisi di stazionarietà.
    """

    name = "twelve_data"
    BASE_URL = "https://api.twelvedata.com"

    def fetch_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        self._validate_dates(start, end)
        if not self.api_key:
            raise ValueError("TWELVE_DATA_API_KEY non impostata nel file .env")

        tf = _TIMEFRAME_MAP.get(timeframe.lower())
        if tf is None:
            raise ValueError(f"Timeframe '{timeframe}' non supportato. Usa: {list(_TIMEFRAME_MAP.keys())}")

        url = f"{self.BASE_URL}/time_series"
        params = {
            "symbol": symbol.upper(),
            "interval": tf,
            "start_date": start,
            "end_date": end,
            "outputsize": 5000,
            "format": "JSON",
            "apikey": self.api_key,
        }

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if "code" in data and data["code"] != 200:
            raise ValueError(f"Twelve Data errore: {data.get('message', data)}")

        values = data.get("values", [])
        if not values:
            raise ValueError(f"Nessun dato trovato per {symbol} ({start} → {end}).")

        rows = []
        for r in values:
            rows.append({
                "timestamp": pd.Timestamp(r["datetime"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r.get("volume") or 0),
            })

        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        logger.info("TwelveData: scaricati %d bar per %s", len(df), symbol)
        return df
