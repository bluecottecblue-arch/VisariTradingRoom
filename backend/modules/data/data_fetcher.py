"""
DataFetcher — Interfaccia unificata per dati storici

Questo modulo è il punto di ingresso per tutti i dati storici.
Astrae le differenze tra provider e gestisce la cache locale.

Provider supportati:
  demo     → dati sintetici (solo per testare il flusso, ZERO valore analitico)
  polygon  → dati OHLC reali via Polygon.io API (richiede API key)
  dukascopy → CSV tick/bid-ask scaricati manualmente da Dukascopy

Qualità dichiarata per ogni provider:
  demo      → nessuna. Generazione random walk. Non usare per decisioni.
  polygon   → buona per H1+, sufficiente per M15-M30, scarsa per M5 e inferiori
  dukascopy → eccellente per FX (tick reale), richiede download manuale
"""
import pandas as pd
import numpy as np
import hashlib
import os
# httpx imported lazily inside _fetch_polygon to avoid hard dependency
from typing import Optional


class DataFetcher:
    """Wrapper unificato per tutti i provider di dati storici."""

    def __init__(self):
        self.polygon_key = os.environ.get("POLYGON_API_KEY")
        self._quality_warnings: list[str] = []
        self._cleaning_stats: dict = {}

    async def fetch(self,
                    provider: str,
                    symbol: str,
                    timeframe: str,
                    date_from: str,
                    date_to: str) -> pd.DataFrame:
        """
        Scarica i dati e ritorna un DataFrame OHLCV ordinato cronologicamente.

        Colonne garantite: Open, High, Low, Close, Volume
        Indice: pd.DatetimeIndex timezone-aware (UTC)
        """
        self._quality_warnings = []

        if provider == "polygon":
            df = await self._fetch_polygon(symbol, timeframe, date_from, date_to)
        elif provider == "dukascopy":
            df = self._load_dukascopy(symbol, timeframe, date_from, date_to)
        else:
            self._quality_warnings.append(
                "⚠️  DATI DEMO SINTETICI — zero valore analitico reale"
            )
            df = self._generate_demo(symbol, timeframe, date_from, date_to)

        # Validazione base
        df, cleaning_stats = self._validate_and_clean(df, symbol, timeframe)
        self._cleaning_stats = cleaning_stats
        return df

    def get_quality_warnings(self) -> list[str]:
        return self._quality_warnings

    def get_cleaning_stats(self) -> dict:
        return self._cleaning_stats

    # ─── Polygon.io ────────────────────────────────────────────────────────────

    async def _fetch_polygon(self, symbol: str, timeframe: str,
                              date_from: str, date_to: str) -> pd.DataFrame:
        if not self.polygon_key:
            raise ValueError(
                "POLYGON_API_KEY non impostata nel file .env\n"
                "Registrati gratis su https://polygon.io per ottenere una chiave."
            )

        tf_map = {
            "M1":  ("1", "minute"),  "M5":  ("5", "minute"),
            "M15": ("15", "minute"), "M30": ("30", "minute"),
            "H1":  ("1", "hour"),    "H4":  ("4", "hour"),
            "D1":  ("1", "day"),     "W1":  ("1", "week"),
        }
        if timeframe not in tf_map:
            raise ValueError(f"Timeframe {timeframe} non supportato da Polygon")

        multiplier, span = tf_map[timeframe]
        poly_sym = f"C:{symbol}" if not symbol.startswith("C:") else symbol

        all_results = []
        url = (f"https://api.polygon.io/v2/aggs/ticker/{poly_sym}/range/"
               f"{multiplier}/{span}/{date_from}/{date_to}"
               f"?adjusted=false&sort=asc&limit=50000&apiKey={self.polygon_key}")

        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            while url:
                resp = await client.get(url)
                if resp.status_code == 403:
                    raise ValueError("Chiave Polygon non valida o piano insufficiente")
                if resp.status_code != 200:
                    raise ValueError(f"Polygon API error {resp.status_code}: {resp.text[:300]}")

                data = resp.json()
                if data.get("status") == "ERROR":
                    raise ValueError(f"Polygon error: {data.get('error', data)}")

                results = data.get("results", [])
                all_results.extend(results)

                # Paginazione
                next_url = data.get("next_url")
                url = f"{next_url}&apiKey={self.polygon_key}" if next_url else None

        if not all_results:
            raise ValueError(
                f"Nessun dato trovato per {symbol} [{timeframe}] "
                f"da {date_from} a {date_to}. "
                "Verifica symbol e date. Il piano gratuito di Polygon limita la storia a 2 anni."
            )

        df = pd.DataFrame(all_results)
        df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low",
                                  "c": "Close", "v": "Volume"})
        df = df.set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]
        df = df.sort_index()

        # Aggiungi quality warnings specifici per Polygon
        if timeframe in ("M1", "M5"):
            self._quality_warnings.append(
                f"Polygon OHLC su {timeframe}: alta aggregazione, tick reali non disponibili. "
                "Usa Dukascopy per strategie di scalping."
            )
        self._quality_warnings.append(
            "Dati Polygon: nessun bid/ask separato. Spread simulato nel backtest."
        )

        return df

    # ─── Dukascopy CSV ─────────────────────────────────────────────────────────

    def _load_dukascopy(self, symbol: str, timeframe: str,
                         date_from: str, date_to: str) -> pd.DataFrame:
        """
        Carica CSV scaricati manualmente da Dukascopy.
        Come scaricare: https://www.dukascopy.com/swiss/english/marketwatch/historical/
        Formato atteso colonne: Gmt time, Open, High, Low, Close, Volume
        Salva in: DUKASCOPY_PATH/{SYMBOL}_{TIMEFRAME}.csv
        """
        path = os.environ.get("DUKASCOPY_PATH", "./data/dukascopy")
        fp = f"{path}/{symbol}_{timeframe}.csv"

        if not os.path.exists(fp):
            raise FileNotFoundError(
                f"File Dukascopy non trovato: {fp}\n"
                f"1. Vai su https://www.dukascopy.com/swiss/english/marketwatch/historical/\n"
                f"2. Seleziona {symbol}, timeframe {timeframe}, esporta CSV\n"
                f"3. Salva il file come: {fp}"
            )

        df = pd.read_csv(fp)
        # Dukascopy usa "Gmt time" come colonna data
        time_col = next((c for c in df.columns if "time" in c.lower() or "date" in c.lower()), None)
        if not time_col:
            raise ValueError("Colonna data non trovata nel CSV Dukascopy")

        df["timestamp"] = pd.to_datetime(df[time_col], utc=True)
        df = df.rename(columns={"Open": "Open", "High": "High", "Low": "Low",
                                  "Close": "Close", "Volume": "Volume"})
        df = df.set_index("timestamp")

        # Filtra date
        df = df.sort_index()
        df = df[date_from:date_to]

        self._quality_warnings.append(
            "Dukascopy CSV: qualità alta, ma verifica che il CSV copra tutto il periodo richiesto."
        )
        return df[["Open", "High", "Low", "Close", "Volume"]]

    # ─── Demo (sintetico) ──────────────────────────────────────────────────────

    def _generate_demo(self, symbol: str, timeframe: str,
                        date_from: str, date_to: str) -> pd.DataFrame:
        """
        Genera dati OHLC sintetici con random walk e regime switching.
        ZERO VALORE ANALITICO — solo per testare il flusso dell'applicazione.
        """
        tf_minutes = {
            "M1": 1, "M5": 5, "M15": 15, "M30": 30,
            "H1": 60, "H4": 240, "D1": 1440, "W1": 10080
        }
        freq = tf_minutes.get(timeframe, 60)

        start = pd.Timestamp(date_from, tz="UTC")
        end = pd.Timestamp(date_to, tz="UTC")
        idx = pd.date_range(start, end, freq=f"{freq}min")

        seed = int(hashlib.md5(f"{symbol}{date_from}".encode()).hexdigest()[:8], 16) % (2**31)
        np.random.seed(seed)
        n = len(idx)

        # Random walk con trend e regime switching
        base_price = 1.1000
        volatility = 0.0003
        drift = 0.00002

        returns = np.random.normal(drift, volatility, n)
        # Regime switching: alterna trend rialzista / ribassista ogni ~200 barre
        regime = np.sin(np.arange(n) / 200) * 0.0001
        returns += regime

        prices = base_price * np.exp(np.cumsum(returns))
        intra_vol = volatility * 0.5

        opens = np.roll(prices, 1)
        opens[0] = base_price
        highs = np.maximum(opens, prices) * (1 + np.abs(np.random.normal(0, intra_vol, n)))
        lows = np.minimum(opens, prices) * (1 - np.abs(np.random.normal(0, intra_vol, n)))
        volumes = np.random.lognormal(8, 1, n)

        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows,
            "Close": prices, "Volume": volumes
        }, index=idx)

        # Rimuovi weekend
        df = df[df.index.dayofweek < 5]
        for i, ts in enumerate(df.index):
            if ts.dayofweek == 0 and i > 0:
                gap = np.random.normal(0, volatility * 3)
                df.iloc[i:, :] = df.iloc[i:, :] * (1 + gap)
        return df

    # ─── Validazione ──────────────────────────────────────────────────────────

    def _validate_and_clean(self, df: pd.DataFrame,
                              symbol: str, timeframe: str) -> tuple[pd.DataFrame, dict]:
        """Validazione e pulizia dei dati con warning espliciti."""
        original_len = len(df)
        duplicate_count = int(df.index.duplicated(keep="first").sum())

        # Rimuovi duplicati
        df = df[~df.index.duplicated(keep="first")]

        # Rimuovi barre con valori impossibili
        bad_mask = (
            (df["High"] < df["Low"]) |
            (df["Open"] > df["High"]) | (df["Open"] < df["Low"]) |
            (df["Close"] > df["High"]) | (df["Close"] < df["Low"]) |
            (df[["Open", "High", "Low", "Close"]] <= 0).any(axis=1)
        )
        bad_count = bad_mask.sum()
        if bad_count > 0:
            self._quality_warnings.append(
                f"Rimosse {bad_count} barre con OHLC incoerente "
                f"({bad_count/original_len*100:.1f}% del totale)"
            )
            df = df[~bad_mask]

        # Ordina cronologicamente
        df = df.sort_index()

        # Check gap temporali anomali
        large_gap_count = 0
        if len(df) > 10:
            diffs = df.index.to_series().diff().dropna()
            median_diff = diffs.median()
            large_gaps = diffs[diffs > median_diff * 10]
            large_gap_count = int(len(large_gaps))
            if len(large_gaps) > 5:
                self._quality_warnings.append(
                    f"Rilevati {len(large_gaps)} gap temporali grandi nei dati. "
                    "Possibili dati mancanti nel periodo. "
                    "Verifica la copertura del provider."
                )

        # Sample size warning
        if len(df) < 200:
            self._quality_warnings.append(
                f"ATTENZIONE: solo {len(df)} barre disponibili. "
                "Insufficiente per backtest statisticamente valido (minimo consigliato: 500+)."
            )

        return df, {
            "rows_original": int(original_len),
            "rows_final": int(len(df)),
            "rows_removed_bad_ohlc": int(bad_count),
            "rows_removed_duplicates": duplicate_count,
            "large_gaps_found": large_gap_count,
        }
