"""
Provider Stooq — gratuito, no API key, equity e indici globali.

Dati giornalieri per la maggior parte dei ticker.
Non include dividendi/split adjustment: usare con cautela per equity.
Ottimo per: indici (SP500, FTSE, DAX), FX spot, commodities.

URL: https://stooq.com
"""
from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from ..provider_base import DataProviderBase

logger = logging.getLogger(__name__)


class StooqProvider(DataProviderBase):
    """
    Stooq — provider gratuito senza API key.
    Solo dati giornalieri (timeframe 1d). Nessun aggiustamento automatico.
    AVVERTENZA: i prezzi equity non sono adjusted per dividendi/split.
    """

    name = "stooq"
    BASE_URL = "https://stooq.com/q/d/l/"

    def fetch_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        self._validate_dates(start, end)

        if timeframe not in ("1d", "1D", "d", "D"):
            raise ValueError("Stooq supporta solo dati giornalieri (timeframe=1d).")

        s = start.replace("-", "")
        e = end.replace("-", "")

        url = f"{self.BASE_URL}?s={symbol.lower()}&d1={s}&d2={e}&i=d"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)

        if "No data" in resp.text or len(resp.text.strip()) < 50:
            raise ValueError(
                f"Simbolo '{symbol}' non trovato su Stooq. "
                f"Esempi validi: ^SPX (S&P 500), ^NDX (Nasdaq), EURUSD (EUR/USD), "
                f"AAPL.US (Apple), MSFT.US (Microsoft), GC.F (Gold futures)."
            )

        df = pd.read_csv(io.StringIO(resp.text))
        if df.empty or len(df.columns) < 3:
            raise ValueError(
                f"Dati non validi per '{symbol}' su Stooq. Verifica il simbolo. "
                f"Esempi: ^SPX, ^NDX, EURUSD, AAPL.US, GC.F"
            )
        df.columns = [c.lower().strip() for c in df.columns]
        df = df.rename(columns={"date": "timestamp", "vol": "volume"})
        if "timestamp" not in df.columns:
            raise ValueError(
                f"Formato dati inatteso per '{symbol}'. Colonne ricevute: {list(df.columns)}. "
                f"Prova con un simbolo diverso (es. ^SPX, EURUSD)."
            )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "volume" not in df.columns:
            df["volume"] = 0.0

        logger.info("Stooq: scaricati %d bar per %s", len(df), symbol)
        return df
