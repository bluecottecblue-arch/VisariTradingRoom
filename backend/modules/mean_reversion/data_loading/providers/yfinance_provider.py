"""
Provider yfinance — fallback gratuito, dati Yahoo Finance.

ATTENZIONE — AFFIDABILITÀ LIMITATA:
- I dati possono avere gap, duplicati o errori silenti.
- Gli aggiustamenti split/dividendi vengono applicati retroattivamente e
  possono causare valori negativi o discontinuità nei dati storici vecchi.
- Non usare per ricerche critiche senza validazione incrociata con altra fonte.
- Usare solo come fallback quando non si ha accesso ad altri provider.

Richiede: pip install yfinance
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from ..provider_base import DataProviderBase

logger = logging.getLogger(__name__)

_TIMEFRAME_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "1d": "1d", "1w": "1wk", "1mo": "1mo",
}


class YfinanceProvider(DataProviderBase):
    """
    yfinance — SOLO FALLBACK. Dati Yahoo Finance non garantiti.
    Vedi docstring del modulo per le limitazioni.
    """

    name = "yfinance"

    def fetch_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        self._validate_dates(start, end)

        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("Installa yfinance: pip install yfinance")

        tf = _TIMEFRAME_MAP.get(timeframe.lower(), "1d")
        logger.warning(
            "yfinance: provider non affidabile usato come fallback. "
            "Verificare i dati prima di usarli in analisi statistiche."
        )

        ticker = yf.Ticker(symbol)
        raw = ticker.history(
            start=start,
            end=end,
            interval=tf,
            auto_adjust=True,
            actions=False,
        )

        if raw.empty:
            raise ValueError(f"Nessun dato trovato per {symbol} ({start} → {end}) su yfinance.")

        raw = raw.reset_index()
        date_col = "Datetime" if "Datetime" in raw.columns else "Date"
        raw["timestamp"] = pd.to_datetime(raw[date_col]).dt.tz_localize(None)

        df = raw.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })[["timestamp", "open", "high", "low", "close", "volume"]]

        df = df.sort_values("timestamp").reset_index(drop=True)
        logger.info("yfinance: scaricati %d bar per %s (adjusted=True)", len(df), symbol)
        return df
