"""
Suddivisione in-sample / out-of-sample della serie temporale.

Tre modalità:
- 'ratio': split per proporzione (es. 70/30)
- 'date':  split per data (tutto prima X = in-sample)
- 'none':  nessuno split (usa solo il campione completo)

IMPORTANTE: evitare look-ahead bias — la divisione deve essere temporale,
mai random, per rispettare l'ordine cronologico dei dati.
"""
from __future__ import annotations

from typing import Literal, Optional, Tuple

import pandas as pd

SplitMethod = Literal["ratio", "date", "none"]


def split_series(
    series: pd.Series,
    method: SplitMethod,
    ratio: float = 0.7,
    split_date: Optional[str] = None,
) -> Tuple[pd.Series, Optional[pd.Series]]:
    """
    Divide la serie in in-sample e out-of-sample.

    :param series: serie temporale indicizzata per timestamp (pd.DatetimeIndex)
    :param method: 'ratio', 'date' o 'none'
    :param ratio: proporzione in-sample (usata solo se method='ratio')
    :param split_date: data di split ISO YYYY-MM-DD (usata solo se method='date')
    :return: (in_sample, out_of_sample) — out_of_sample è None se method='none'
    """
    series = series.dropna().sort_index()
    n = len(series)

    if method == "none":
        return series, None

    if method == "ratio":
        if not 0.1 < ratio < 0.99:
            raise ValueError("Il ratio deve essere tra 0.10 e 0.99")
        split_idx = int(n * ratio)
        if split_idx < 20:
            raise ValueError(
                f"In-sample troppo corto dopo lo split ({split_idx} obs). "
                "Aumenta il ratio o usa un dataset più lungo."
            )
        if n - split_idx < 10:
            raise ValueError(
                f"Out-of-sample troppo corto dopo lo split ({n - split_idx} obs). "
                "Riduci il ratio o usa un dataset più lungo."
            )
        return series.iloc[:split_idx], series.iloc[split_idx:]

    if method == "date":
        if split_date is None:
            raise ValueError("split_date è obbligatorio quando method='date'")
        cut = pd.Timestamp(split_date)
        in_sample = series[series.index <= cut]
        out_sample = series[series.index > cut]
        if len(in_sample) < 20:
            raise ValueError(f"In-sample troppo corto ({len(in_sample)} obs) con split_date={split_date}.")
        if len(out_sample) < 10:
            raise ValueError(f"Out-of-sample troppo corto ({len(out_sample)} obs) con split_date={split_date}.")
        return in_sample, out_sample

    raise ValueError(f"Metodo di split '{method}' non riconosciuto. Usa: ratio, date, none.")


def get_split_info(in_sample: pd.Series, out_sample: Optional[pd.Series]) -> dict:
    """Restituisce metadati sullo split per il report."""
    info = {
        "in_sample_n": len(in_sample),
        "in_sample_start": str(in_sample.index[0])[:10] if len(in_sample) else None,
        "in_sample_end": str(in_sample.index[-1])[:10] if len(in_sample) else None,
        "out_sample_n": len(out_sample) if out_sample is not None else 0,
        "out_sample_start": str(out_sample.index[0])[:10] if (out_sample is not None and len(out_sample)) else None,
        "out_sample_end": str(out_sample.index[-1])[:10] if (out_sample is not None and len(out_sample)) else None,
    }
    return info
