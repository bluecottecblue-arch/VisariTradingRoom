"""
Caricamento dati da file CSV, Excel o Parquet.

Supporta mappatura flessibile dei nomi colonne:
il dataframe risultante contiene sempre timestamp/open/high/low/close/volume.
"""
from __future__ import annotations

import io
import base64
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

STANDARD_COLUMNS = ["timestamp", "open", "high", "low", "close", "adjusted_close", "volume"]

_COMMON_ALIASES: dict[str, str] = {
    # timestamp
    "time": "timestamp", "date": "timestamp", "datetime": "timestamp",
    "Date": "timestamp", "Time": "timestamp", "Datetime": "timestamp",
    "DATE": "timestamp", "DATETIME": "timestamp",
    # price
    "Close": "close", "CLOSE": "close",
    "Open": "open", "OPEN": "open",
    "High": "high", "HIGH": "high",
    "Low": "low", "LOW": "low",
    "Adj Close": "adjusted_close", "Adj. Close": "adjusted_close",
    "adjusted_close": "adjusted_close", "AdjClose": "adjusted_close",
    # volume
    "Volume": "volume", "VOLUME": "volume", "vol": "volume",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rinomina le colonne usando gli alias comuni."""
    rename_map = {col: _COMMON_ALIASES[col] for col in df.columns if col in _COMMON_ALIASES}
    return df.rename(columns=rename_map)


def load_from_bytes(raw: bytes, filename: str, column_map: Optional[dict[str, str]] = None) -> pd.DataFrame:
    """
    Carica dati da bytes (es. upload HTTP) in base all'estensione del file.

    :param raw: contenuto del file in bytes
    :param filename: nome del file (usato per determinare il formato)
    :param column_map: mappatura opzionale {nome_originale: nome_standard}
    """
    fname = filename.lower()
    if fname.endswith(".parquet"):
        df = pd.read_parquet(io.BytesIO(raw))
    elif fname.endswith((".xls", ".xlsx")):
        df = pd.read_excel(io.BytesIO(raw))
    else:
        # tenta CSV con più separatori
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(io.BytesIO(raw), sep=sep)
                if len(df.columns) >= 2:
                    break
            except Exception:
                pass
        else:
            raise ValueError("Impossibile parsare il file come CSV.")

    if column_map:
        df = df.rename(columns=column_map)

    df = _normalise_columns(df)

    if "timestamp" not in df.columns:
        raise ValueError(
            "Colonna timestamp non trovata. "
            "Assicurati che esista una colonna 'timestamp', 'date' o 'time'."
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False, errors="coerce")
    invalid_ts = df["timestamp"].isna().sum()
    if invalid_ts > 0:
        logger.warning("Trovati %d timestamp non validi: rimossi.", invalid_ts)
        df = df.dropna(subset=["timestamp"])

    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info("File '%s' caricato: %d righe, colonne=%s", filename, len(df), list(df.columns))
    return df


def load_from_base64(b64: str, filename: str, column_map: Optional[dict[str, str]] = None) -> pd.DataFrame:
    """Carica dati da stringa base64 (usata da upload frontend)."""
    raw = base64.b64decode(b64)
    return load_from_bytes(raw, filename, column_map)
