"""
DataFetcher — Scarica e prepara dati storici reali

Supporta:
- Polygon.io: dati OHLC aggregati professionali (richiede API key)
- Dukascopy CSV: tick data gratuiti (scaricati manualmente)
- Demo: dati sintetici per testare il flusso UI

DICHIARAZIONE TRASPARENZA DATI:
- Polygon.io fornisce dati OHLC aggregati (non tick). Qualità alta, non perfetta.
- Dukascopy fornisce tick data storici gratuiti per FX. Ottima qualità per FX.
- I dati demo sono puramente sintetici — NON usarli per decisioni reali.
- Nessun dato può replicare perfettamente il book reale con cui avresti tradato.
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta


class DataFetcher:
    def __init__(self, source: str = "demo"):
        self.source = source
        self.polygon_api_key = os.environ.get("POLYGON_API_KEY")

    async def fetch(self, symbol: str, timeframe: str,
                    date_from: str, date_to: str) -> pd.DataFrame:
        """
        Scarica i dati storici e li restituisce come DataFrame con indice DatetimeIndex.
        
        Colonne: Open, High, Low, Close, Volume (OHLCV)
        Indice: UTC timestamp
        """
        if self.source == "polygon":
            return await self._fetch_polygon(symbol, timeframe, date_from, date_to)
        elif self.source == "dukascopy":
            return self._load_dukascopy_csv(symbol, timeframe, date_from, date_to)
        elif self.source == "demo":
            return self._generate_demo_data(symbol, timeframe, date_from, date_to)
        else:
            raise ValueError(f"Fonte dati non supportata: {self.source}")

    async def _fetch_polygon(self, symbol: str, timeframe: str,
                              date_from: str, date_to: str) -> pd.DataFrame:
        """
        Scarica dati da Polygon.io.
        
        Piano gratuito: 2 anni di dati, rate limited.
        Piano Starter ($29/mese): 10+ anni, unlimited calls.
        
        Documentazione: https://polygon.io/docs/forex/get_v2_aggs_ticker__forexticker__range__multiplier___timespan___from___to
        """
        if not self.polygon_api_key:
            raise ValueError(
                "POLYGON_API_KEY non configurata. "
                "Registrati su https://polygon.io e inserisci la chiave nel file .env"
            )

        # httpx imported lazily
        
        # Converti timeframe in formato Polygon
        tf_map = {
            "M1": ("1", "minute"), "M5": ("5", "minute"),
            "M15": ("15", "minute"), "M30": ("30", "minute"),
            "H1": ("1", "hour"), "H4": ("4", "hour"),
            "D1": ("1", "day"),
        }
        if timeframe not in tf_map:
            raise ValueError(f"Timeframe {timeframe} non supportato da Polygon")

        multiplier, span = tf_map[timeframe]
        
        # Symbol Polygon per Forex: C:EURUSD
        polygon_symbol = f"C:{symbol}" if not symbol.startswith("C:") else symbol

        url = (f"https://api.polygon.io/v2/aggs/ticker/{polygon_symbol}/range/"
               f"{multiplier}/{span}/{date_from}/{date_to}"
               f"?adjusted=false&sort=asc&limit=50000"
               f"&apiKey={self.polygon_api_key}")

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise ValueError(f"Polygon API error {resp.status_code}: {resp.text[:200]}")
            data = resp.json()

        if data.get("resultsCount", 0) == 0:
            raise ValueError(f"Nessun dato trovato per {symbol} da {date_from} a {date_to}")

        results = data.get("results", [])
        df = pd.DataFrame(results)
        df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
        df = df.set_index("timestamp")[["Open", "High", "Low", "Close", "Volume"]]
        df = df.sort_index()
        
        print(f"✅ Polygon: caricati {len(df)} bar per {symbol} {timeframe} ({date_from} → {date_to})")
        return df

    def _load_dukascopy_csv(self, symbol: str, timeframe: str,
                             date_from: str, date_to: str) -> pd.DataFrame:
        """
        Carica dati CSV scaricati da Dukascopy JForex.
        
        Come scaricare i dati da Dukascopy:
        1. Vai su https://www.dukascopy.com/swiss/english/marketwatch/historical/
        2. Seleziona lo strumento e il periodo
        3. Scarica il CSV
        4. Salva in: /data/dukascopy/{SYMBOL}_{TIMEFRAME}.csv
        
        Formato CSV atteso: Time, Open, High, Low, Close, Volume
        """
        duka_path = os.environ.get("DUKASCOPY_PATH", "/data/dukascopy")
        file_path = f"{duka_path}/{symbol}_{timeframe}.csv"
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"File Dukascopy non trovato: {file_path}\n"
                f"Scarica i dati da https://www.dukascopy.com e salvali in {duka_path}/"
            )
        
        df = pd.read_csv(file_path, parse_dates=["Time"])
        df = df.rename(columns={"Time": "timestamp"})
        df = df.set_index("timestamp")
        df.index = pd.to_datetime(df.index, utc=True)
        
        # Filtra per date
        df = df[date_from:date_to]
        df = df.sort_index()
        
        print(f"✅ Dukascopy: caricati {len(df)} bar per {symbol} {timeframe}")
        return df

    def _generate_demo_data(self, symbol: str, timeframe: str,
                             date_from: str, date_to: str) -> pd.DataFrame:
        """
        Genera dati sintetici per demo/test UI.
        
        ⚠️ QUESTI DATI NON HANNO VALORE PER BACKTEST REALI.
        Sono generati con random walk e non replicano nessun mercato reale.
        """
        print("⚠️  DEMO DATA: questi dati sono sintetici e privi di significato analitico")
        
        tf_minutes = {"M1": 1, "M5": 5, "M15": 15, "M30": 30,
                      "H1": 60, "H4": 240, "D1": 1440}
        minutes = tf_minutes.get(timeframe, 60)
        
        start = pd.Timestamp(date_from, tz="UTC")
        end = pd.Timestamp(date_to, tz="UTC")
        timestamps = pd.date_range(start, end, freq=f"{minutes}min")
        
        # Random walk con media e volatilità simulate
        np.random.seed(42)
        n = len(timestamps)
        returns = np.random.normal(0, 0.0003, n)  # Simula FX volatilità
        price = 1.10000  # EURUSD start
        
        closes = [price]
        for r in returns[1:]:
            closes.append(closes[-1] * (1 + r))
        
        closes = np.array(closes)
        highs = closes * (1 + np.abs(np.random.normal(0, 0.0002, n)))
        lows = closes * (1 - np.abs(np.random.normal(0, 0.0002, n)))
        opens = np.roll(closes, 1)
        opens[0] = closes[0]
        
        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows, "Close": closes,
            "Volume": np.random.randint(1000, 10000, n).astype(float)
        }, index=timestamps)
        
        # Rimuovi weekend
        df = df[df.index.dayofweek < 5]
        
        return df
