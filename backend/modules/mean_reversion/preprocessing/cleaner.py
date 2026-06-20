"""
Validazione e pulizia dei dati di mercato.

Gestisce: timestamp duplicati, valori mancanti, range di prezzi non validi,
timezone, gap nelle serie temporali, bias di sopravvivenza (avvisi).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataQualityReport:
    """Raccoglie tutti gli avvisi e le statistiche di qualità dei dati."""

    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.info: list[str] = []
        self.n_original: int = 0
        self.n_after_clean: int = 0
        self.n_duplicates_removed: int = 0
        self.n_missing_filled: int = 0
        self.n_missing_dropped: int = 0
        self.n_invalid_prices: int = 0
        self.timezone_note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "n_original": self.n_original,
            "n_after_clean": self.n_after_clean,
            "n_duplicates_removed": self.n_duplicates_removed,
            "n_missing_filled": self.n_missing_filled,
            "n_missing_dropped": self.n_missing_dropped,
            "n_invalid_prices": self.n_invalid_prices,
            "timezone_note": self.timezone_note,
            "warnings": self.warnings,
            "info": self.info,
        }


def clean_ohlcv(
    df: pd.DataFrame,
    price_column: str = "close",
    fill_method: Optional[str] = None,
    drop_na: bool = True,
    asset_type: str = "equity",
) -> tuple[pd.DataFrame, DataQualityReport]:
    """
    Pulizia completa di un DataFrame OHLCV.

    :param df: DataFrame grezzo con almeno timestamp e price_column
    :param price_column: colonna prezzo da analizzare
    :param fill_method: 'ffill', 'bfill' o None (default: drop)
    :param drop_na: se True, rimuove le righe con NaN residui
    :param asset_type: 'equity', 'fx', 'crypto' — influenza gli avvisi
    :return: (DataFrame pulito, DataQualityReport)
    """
    report = DataQualityReport()
    df = df.copy()
    report.n_original = len(df)

    # 1. Timezone handling
    if hasattr(df["timestamp"].dtype, "tz") and df["timestamp"].dt.tz is not None:
        report.timezone_note = f"Timezone rimossa (UTC→naive): {df['timestamp'].dt.tz}"
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
    else:
        report.timezone_note = "Nessuna timezone rilevata (dati naive)."

    # 2. Ordinamento per timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 3. Rimozione duplicati (mantieni il primo)
    dupes = df.duplicated(subset=["timestamp"], keep="first").sum()
    if dupes > 0:
        report.warnings.append(
            f"Trovati {dupes} timestamp duplicati: rimosso il secondo occorrenza."
        )
        df = df.drop_duplicates(subset=["timestamp"], keep="first").reset_index(drop=True)
    report.n_duplicates_removed = dupes

    # 4. Conversione numerica della colonna prezzo
    if price_column in df.columns:
        df[price_column] = pd.to_numeric(df[price_column], errors="coerce")

    # 5. Validazione prezzi: valori <= 0 impostati a NaN
    if price_column in df.columns:
        invalid = (df[price_column] <= 0).sum()
        if invalid > 0:
            report.warnings.append(
                f"Trovati {invalid} valori non validi (<= 0) in '{price_column}': sostituiti con NaN."
            )
            df.loc[df[price_column] <= 0, price_column] = np.nan
        report.n_invalid_prices = int(invalid)

    # 6. Gestione valori mancanti
    na_count = df[price_column].isna().sum() if price_column in df.columns else 0
    if na_count > 0:
        if fill_method == "ffill":
            df[price_column] = df[price_column].fillna(method="ffill")
            report.n_missing_filled = int(na_count)
            report.warnings.append(
                f"Forward fill applicato a {na_count} valori mancanti in '{price_column}'. "
                "Attenzione: può introdurre look-ahead bias se i dati non sono stati allineati correttamente."
            )
        elif fill_method == "bfill":
            df[price_column] = df[price_column].fillna(method="bfill")
            report.n_missing_filled = int(na_count)
            report.warnings.append(
                f"Backward fill applicato a {na_count} valori mancanti in '{price_column}'."
            )
        elif drop_na:
            df = df.dropna(subset=[price_column]).reset_index(drop=True)
            report.n_missing_dropped = int(na_count)
            report.info.append(f"Rimosse {na_count} righe con valori mancanti in '{price_column}'.")

    # 7. Avvisi specifici per asset class
    if asset_type == "equity":
        if "adjusted_close" not in df.columns:
            report.warnings.append(
                "⚠️  DATI EQUITY: colonna 'adjusted_close' non presente. "
                "Per analisi corrette su equity, usa prezzi aggiustati per split e dividendi. "
                "I prezzi non adjusted possono generare false discontinuità che alterano i test di stazionarietà."
            )
        else:
            report.info.append(
                "Colonna 'adjusted_close' presente. "
                "Considera di selezionare 'adjusted_close' come colonna di analisi per evitare distorsioni da split/dividendi."
            )
    elif asset_type in ("fx", "forex"):
        report.info.append(
            "FX: nessun aggiustamento per dividendi/split necessario. "
            "Attenzione a possibili differenze di liquidità tra sessioni (Asia/Europa/USA) "
            "e gap weekend che possono influenzare i test su dati intraday."
        )
    elif asset_type == "crypto":
        report.info.append(
            "Crypto: nessun aggiustamento per split/dividendi. "
            "Attenzione a possibili hard fork, listing/delisting, differenze tra exchange. "
            "I dati aggregati (es. CCXT) possono avere inconsistenze di volume."
        )

    # 8. Avviso gap (date mancanti non consecutive)
    if len(df) > 1:
        ts_diff = df["timestamp"].diff().dropna()
        most_common_diff = ts_diff.mode()[0] if not ts_diff.empty else None
        if most_common_diff is not None:
            gaps = (ts_diff > most_common_diff * 3).sum()
            if gaps > 0:
                report.warnings.append(
                    f"Rilevati {gaps} gap significativi nella serie temporale "
                    f"(intervallo atteso: {most_common_diff}). "
                    "Possono essere giorni non di trading, dati mancanti o periodi di halt. "
                    "Verificare prima di procedere con i test."
                )

    report.n_after_clean = len(df)

    if report.n_after_clean < 30:
        report.warnings.append(
            f"⚠️  Solo {report.n_after_clean} osservazioni disponibili dopo la pulizia. "
            "I test statistici richiedono almeno 50-100 osservazioni per risultati affidabili."
        )

    report.info.append(
        f"Dataset finale: {report.n_after_clean} osservazioni "
        f"(rimossi: {report.n_original - report.n_after_clean} su {report.n_original})."
    )

    return df, report
