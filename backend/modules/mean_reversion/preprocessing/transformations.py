"""
Trasformazioni della serie temporale per i test statistici.

NOTA IMPORTANTE sull'uso corretto dei test:
- ADF sul livello del prezzo (o log-prezzo): testa se il PREZZO è stazionario.
  Questo è il test appropriato per valutare mean-reversion del prezzo stesso.
- ADF sui rendimenti: quasi sempre stazionario anche se il prezzo non lo è.
  Applicare ADF ai rendimenti è metodologicamente scorretto per questo scopo.
- Hurst e Variance Ratio: tipicamente applicati al log-prezzo o al prezzo grezzo.
  Il Variance Ratio è definito sui rendimenti del log-prezzo.
- Monte Carlo: usa la distribuzione dei rendimenti per simulare percorsi di prezzo.
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd
from typing import Literal

logger = logging.getLogger(__name__)

SeriesTransform = Literal["price", "log_price", "returns", "log_returns"]


def apply_transform(
    series: pd.Series,
    transform: SeriesTransform,
) -> pd.Series:
    """
    Applica una trasformazione alla serie.

    :param series: serie di prezzi grezzi
    :param transform: 'price' | 'log_price' | 'returns' | 'log_returns'
    :return: serie trasformata (con eventuali NaN rimossi iniziali)
    """
    if transform == "price":
        return series.copy()

    elif transform == "log_price":
        if (series <= 0).any():
            raise ValueError("Impossibile calcolare il log-prezzo: valori <= 0 presenti.")
        return np.log(series)

    elif transform == "returns":
        ret = series.pct_change().dropna()
        return ret

    elif transform == "log_returns":
        if (series <= 0).any():
            raise ValueError("Impossibile calcolare i log-rendimenti: valori <= 0 presenti.")
        lr = np.log(series).diff().dropna()
        return lr

    else:
        raise ValueError(f"Transform '{transform}' non riconosciuto. Usa: price, log_price, returns, log_returns.")


def get_transform_description(transform: SeriesTransform) -> str:
    """Restituisce una descrizione testuale della trasformazione."""
    descriptions = {
        "price": "Prezzo grezzo — adatto a ADF, Hurst, Variance Ratio per analisi di mean-reversion del prezzo.",
        "log_price": "Log-prezzo — trasformazione raccomandata: linearizza la crescita composta, "
                     "adatta per ADF, Hurst, Variance Ratio.",
        "returns": "Rendimenti semplici (variazione %) — spesso stazionari anche se il prezzo non lo è. "
                   "NON usare ADF sui rendimenti per concludere sulla stazionarietà del PREZZO.",
        "log_returns": "Log-rendimenti (differenze prime del log-prezzo) — simile ai rendimenti semplici. "
                       "Adatti per la stima della volatilità e il Monte Carlo.",
    }
    return descriptions.get(transform, "Trasformazione non documentata.")


def validate_series_for_test(series: pd.Series, transform: SeriesTransform, test_name: str) -> list[str]:
    """
    Controlla che la serie trasformata sia adatta per il test specificato.
    Restituisce una lista di avvisi.
    """
    warnings = []

    n = len(series.dropna())
    if n < 30:
        warnings.append(f"{test_name}: serie troppo corta ({n} obs). Minimo consigliato: 50-100.")

    if transform in ("returns", "log_returns") and test_name == "ADF":
        warnings.append(
            "ADF su rendimenti: i rendimenti sono quasi sempre stazionari, "
            "il che NON implica stazionarietà del prezzo. "
            "Applica ADF al log-prezzo per testare la stazionarietà del prezzo."
        )

    if series.dropna().std() == 0:
        warnings.append(f"{test_name}: la serie ha varianza zero — risultati non significativi.")

    if series.dropna().isna().sum() > 0:
        warnings.append(f"{test_name}: la serie contiene {series.isna().sum()} NaN residui.")

    return warnings
