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
            raise ValueError(f"Nessun dato trovato per {symbol} su Stooq.")

        df = pd.read_csv(io.StringIO(resp.text))
        df.columns = [c.lower().strip() for c in df.columns]
        df = df.rename(columns={"date": "timestamp", "vol": "volume"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)

        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "volume" not in df.columns:
            df["volume"] = 0.0

        logger.info("Stooq: scaricati %d bar per %s", len(df), symbol)
        return df
