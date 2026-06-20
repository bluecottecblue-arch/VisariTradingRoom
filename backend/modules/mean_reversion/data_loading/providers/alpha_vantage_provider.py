"""
Provider Alpha Vantage — equity, FX, crypto, indici.

Documentazione: https://www.alphavantage.co/documentation/
API key gratuita: 25 req/giorno, dati EOD.

Variabile .env: ALPHA_VANTAGE_API_KEY
"""
from __future__ import annotations

import logging
import pandas as pd
import requests

from ..provider_base import DataProviderBase

logger = logging.getLogger(__name__)


class AlphaVantageProvider(DataProviderBase):
    """
    Alpha Vantage — dati equity con adjusted close disponibile.
    Per equity: usare la funzione TIME_SERIES_DAILY_ADJUSTED per avere i prezzi
    aggiustati per split e dividendi (campo 'adjusted_close').
    Per FX/Crypto: nessun aggiustamento disponibile né necessario.
    """

    name = "alpha_vantage"
    BASE_URL = "https://www.alphavantage.co/query"

    def fetch_ohlcv(self, symbol: str, timeframe: str, start: str, end: str) -> pd.DataFrame:
        self._validate_dates(start, end)
        if not self.api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY non impostata nel file .env")

        # Rileva asset class per scegliere la funzione corretta
        sym = symbol.upper()
        if "/" in sym or len(sym) == 6 and sym.isalpha():
            function = "FX_DAILY"
        else:
            function = "TIME_SERIES_DAILY_ADJUSTED"

        params = {
            "function": function,
            "symbol": sym,
            "outputsize": "full",
            "apikey": self.api_key,
        }

        if function == "FX_DAILY":
            params["from_symbol"] = sym[:3]
            params["to_symbol"] = sym[3:]
            del params["symbol"]

        resp = requests.get(self.BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Individua la chiave dei dati temporali
        ts_key = next((k for k in data if "Time Series" in k), None)
        if ts_key is None:
            raise ValueError(f"Alpha Vantage errore: {data.get('Information', data.get('Note', str(data)[:200]))}")

        ts = data[ts_key]
        rows = []
        for date_str, values in ts.items():
            dt = pd.Timestamp(date_str)
            if dt < pd.Timestamp(start) or dt > pd.Timestamp(end):
                continue
            row = {
                "timestamp": dt,
                "open": float(values.get("1. open", values.get("1. open (USD)", 0))),
                "high": float(values.get("2. high", values.get("2. high (USD)", 0))),
                "low": float(values.get("3. low", values.get("3. low (USD)", 0))),
                "close": float(values.get("4. close", values.get("4. close (USD)", 0))),
                "volume": float(values.get("6. volume", 0)),
            }
            adj = values.get("5. adjusted close")
            if adj:
                row["adjusted_close"] = float(adj)
            rows.append(row)

        if not rows:
            raise ValueError(f"Nessun dato trovato per {symbol} ({start} → {end}).")

        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        logger.info("AlphaVantage: scaricati %d bar per %s", len(df), symbol)
        return df
