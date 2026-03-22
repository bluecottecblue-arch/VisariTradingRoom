"""
DataProvider — Fornisce dati storici reali per il backtest

FONTI SUPPORTATE:
1. Polygon.io    — OHLC aggregato, piano free (2 anni) o Starter (15+ anni)
2. Dukascopy     — Tick + Bid/Ask per Forex (download locale richiesto)
3. Demo          — Dati sintetici SOLO per test UI (non usare per decisioni reali)

DICHIARAZIONE DI QUALITÀ OBBLIGATORIA:
Ogni dataset viene accompagnato da una dichiarazione esplicita della qualità
e dei limiti. L'utente deve sapere cosa sta backtestando.
"""
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import requests


class DataProvider:
    def __init__(self):
        self.polygon_key = os.environ.get("POLYGON_API_KEY", "")
        self.storage_path = Path(os.environ.get("STORAGE_PATH", "./storage"))
        self.storage_path.mkdir(exist_ok=True)

    def get_ohlc(
        self,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
        provider: str = "polygon"
    ) -> dict:
        """
        Recupera dati OHLC e ritorna DataFrame + metadata di qualità.

        Returns:
            {
                "data": pd.DataFrame con colonne [Open, High, Low, Close, Volume],
                "quality": dict con info sulla qualità dei dati,
                "warnings": list di avvertenze,
            }
        """
        if provider == "demo":
            return self._generate_demo_data(symbol, timeframe, date_from, date_to)
        elif provider == "polygon":
            return self._fetch_polygon(symbol, timeframe, date_from, date_to)
        elif provider == "dukascopy":
            return self._load_dukascopy(symbol, timeframe, date_from, date_to)
        else:
            raise ValueError(f"Provider non supportato: {provider}")

    # ─── Polygon.io ───────────────────────────────────────────────────────────

    def _fetch_polygon(self, symbol: str, timeframe: str, date_from: str, date_to: str) -> dict:
        """
        Scarica dati OHLC da Polygon.io.

        Piano gratuito: dati con 15-min delay, limite 2 anni.
        Piano Starter ($29/mese): real-time, 15+ anni di storia.
        Consigliato per backtest seri.
        """
        if not self.polygon_key:
            return self._generate_demo_data(
                symbol, timeframe, date_from, date_to,
                warning="API key Polygon.io non configurata. Usando dati demo."
            )

        # Mappa timeframe in formato Polygon
        tf_map = {
            "M1": ("1", "minute"), "M5": ("5", "minute"), "M15": ("15", "minute"),
            "M30": ("30", "minute"), "H1": ("1", "hour"), "H4": ("4", "hour"),
            "D1": ("1", "day"), "W1": ("1", "week"),
        }
        multiplier, span = tf_map.get(timeframe, ("1", "hour"))

        # Polygon usa ticker diversi: EURUSD → C:EURUSD per Forex
        ticker = self._normalize_ticker_polygon(symbol)

        cache_file = self.storage_path / f"polygon_{ticker}_{timeframe}_{date_from}_{date_to}.parquet"
        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            return self._wrap_result(df, "polygon", "cached", [])

        url = (f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/"
               f"{multiplier}/{span}/{date_from}/{date_to}")
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.polygon_key
        }

        all_results = []
        while url:
            try:
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                return self._generate_demo_data(
                    symbol, timeframe, date_from, date_to,
                    warning=f"Errore Polygon.io: {e}. Fallback su dati demo."
                )

            results = data.get("results", [])
            all_results.extend(results)

            # Paginazione
            url = data.get("next_url")
            params = {"apiKey": self.polygon_key} if url else {}

        if not all_results:
            return self._generate_demo_data(
                symbol, timeframe, date_from, date_to,
                warning=f"Nessun dato Polygon.io per {symbol} {timeframe}. Fallback demo."
            )

        df = pd.DataFrame(all_results)
        df.index = pd.to_datetime(df["t"], unit="ms", utc=True)
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
        df = df[["Open", "High", "Low", "Close", "Volume"]].sort_index()

        # Verifica integrità
        warnings = self._check_data_integrity(df)

        # Cache su disco
        df.to_parquet(cache_file)

        return self._wrap_result(
            df, "polygon", "live",
            warnings,
            notes=[
                "Dati OHLC aggregati da tick reali",
                "Bid/Ask non disponibili — spread simulato con costante",
                f"Periodo: {date_from} → {date_to}",
                "Piano gratuito: max 2 anni. Considera piano Starter per backtest più lunghi."
            ]
        )

    def _normalize_ticker_polygon(self, symbol: str) -> str:
        """Converte simbolo in formato Polygon"""
        forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
                       "NZDUSD", "EURGBP", "EURJPY", "XAUUSD"]
        if symbol.upper() in forex_pairs:
            return f"C:{symbol.upper()}"
        # Indices, stocks, etc.
        return symbol.upper()

    # ─── Dukascopy ────────────────────────────────────────────────────────────

    def _load_dukascopy(self, symbol: str, timeframe: str, date_from: str, date_to: str) -> dict:
        """
        Carica dati Dukascopy da file locale.

        Dukascopy fornisce tick data gratuiti ma richiede download manuale
        tramite JForex History Center o dukascopy-client open source.

        ISTRUZIONI:
        1. Vai su https://www.dukascopy.com/trading-tools/widgets/tools/historical-data-feed/
        2. Seleziona strumento e periodo
        3. Esporta come CSV
        4. Metti il file in: storage/dukascopy/{SYMBOL}_{TIMEFRAME}.csv
        """
        duka_path = self.storage_path / "dukascopy" / f"{symbol}_{timeframe}.csv"

        if not duka_path.exists():
            return self._generate_demo_data(
                symbol, timeframe, date_from, date_to,
                warning=(
                    f"File Dukascopy non trovato: {duka_path}. "
                    "Scarica i dati manualmente da Dukascopy e metti il CSV in storage/dukascopy/. "
                    "Usando dati demo come fallback."
                )
            )

        try:
            df = pd.read_csv(duka_path, index_col=0, parse_dates=True)
            df.columns = [c.title() for c in df.columns]
            required = ["Open", "High", "Low", "Close"]
            if not all(c in df.columns for c in required):
                raise ValueError("Colonne OHLC mancanti nel file Dukascopy")

            # Filtra per date
            df = df.loc[date_from:date_to]
            warnings = self._check_data_integrity(df)

            return self._wrap_result(
                df, "dukascopy", "local_file",
                warnings,
                notes=[
                    "Dati tick aggregati a OHLC — qualità superiore a OHLC aggregati",
                    "Bid/Ask disponibili se esportati — consigliato per backtest precisi",
                    f"File locale: {duka_path}",
                ]
            )
        except Exception as e:
            return self._generate_demo_data(
                symbol, timeframe, date_from, date_to,
                warning=f"Errore lettura Dukascopy: {e}. Usando dati demo."
            )

    # ─── Demo data ────────────────────────────────────────────────────────────

    def _generate_demo_data(
        self,
        symbol: str,
        timeframe: str,
        date_from: str,
        date_to: str,
        warning: str = ""
    ) -> dict:
        """
        Genera OHLC sintetici per test UI.

        ⚠️ ATTENZIONE: Questi dati NON rappresentano mercati reali.
        Sono generati con random walk — non hanno struttura di mercato.
        Non usare MAI per decisioni di trading.
        """
        freq_map = {
            "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
            "H1": "1H", "H4": "4H", "D1": "1D", "W1": "1W"
        }
        freq = freq_map.get(timeframe, "1H")

        dates = pd.date_range(start=date_from, end=date_to, freq=freq)
        n = len(dates)

        # Random walk semplice (NON realistico)
        np.random.seed(42)
        returns = np.random.normal(0.0001, 0.002, n)
        close = 1.1 * np.exp(np.cumsum(returns))
        high = close * (1 + np.abs(np.random.normal(0, 0.001, n)))
        low = close * (1 - np.abs(np.random.normal(0, 0.001, n)))
        open_ = np.roll(close, 1)
        open_[0] = close[0]
        volume = np.random.randint(100, 10000, n).astype(float)

        df = pd.DataFrame({
            "Open": open_, "High": high, "Low": low,
            "Close": close, "Volume": volume
        }, index=dates)

        warnings = [
            "⚠️ DATI SINTETICI — non rappresentano mercati reali",
            "⚠️ NON usare per decisioni di trading",
            "Generati con random walk — nessuna struttura di mercato",
        ]
        if warning:
            warnings.insert(0, warning)

        return self._wrap_result(
            df, "demo", "synthetic",
            warnings,
            notes=["Dati generati per test UI esclusivamente"]
        )

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _check_data_integrity(self, df: pd.DataFrame) -> list[str]:
        """Controlla integrità OHLC e ritorna lista di warning"""
        warnings = []

        # Barre con OHLC incoerente
        bad = df[(df["High"] < df["Low"]) |
                 (df["Open"] > df["High"]) |
                 (df["Open"] < df["Low"]) |
                 (df["Close"] > df["High"]) |
                 (df["Close"] < df["Low"])]
        if len(bad) > 0:
            pct = len(bad) / len(df) * 100
            warnings.append(f"{len(bad)} barre con OHLC incoerente ({pct:.1f}%). Rimuovere prima del backtest.")

        # Gaps temporali anomali
        if hasattr(df.index, "freq") and df.index.freq:
            expected_diff = pd.tseries.frequencies.to_offset(df.index.freq)
            actual_diffs = df.index.to_series().diff().dropna()
            gaps = actual_diffs[actual_diffs > expected_diff * 3]
            if len(gaps) > 10:
                warnings.append(f"{len(gaps)} gap temporali rilevati. Potrebbero essere sessioni chiuse o dati mancanti.")

        # Prezzi zero o negativi
        zero_prices = (df[["Open", "High", "Low", "Close"]] <= 0).any(axis=1).sum()
        if zero_prices > 0:
            warnings.append(f"{zero_prices} barre con prezzi zero o negativi — dati corrotti.")

        return warnings

    def _wrap_result(
        self,
        df: pd.DataFrame,
        provider: str,
        source: str,
        warnings: list,
        notes: Optional[list] = None
    ) -> dict:
        return {
            "data": df,
            "quality": {
                "provider": provider,
                "source": source,
                "rows": len(df),
                "date_from": str(df.index[0]) if len(df) > 0 else None,
                "date_to": str(df.index[-1]) if len(df) > 0 else None,
                "notes": notes or [],
            },
            "warnings": warnings
        }
