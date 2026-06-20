"""
Test ADF (Augmented Dickey-Fuller) per la stazionarietà delle serie finanziarie.

IPOTESI NULLA: la serie ha una radice unitaria (è non-stazionaria / random walk).
IPOTESI ALTERNATIVA: la serie è stazionaria (o trend-stazionaria).

COME INTERPRETARE:
  p-value < 0.05  → Rifiuta H0 → Evidenza di stazionarietà
  p-value >= 0.05 → Non rifiuta H0 → Nessuna evidenza di stazionarietà

LIMITAZIONI (da comunicare sempre):
  1. Bassa potenza: il test fatica a rilevare mean-reversion in serie corte.
  2. Sensibile alla scelta dei lag: risultati diversi con AIC vs BIC vs t-stat.
  3. Sensibile alle rotture strutturali: un cambiamento di regime può far sembrare
     non-stazionaria una serie che in realtà è stazionaria per tratti.
  4. Stazionarietà ≠ profittabilità: una serie stazionaria non garantisce
     guadagni netti dopo costi, slippage e rischio di esecuzione.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RegressionType = Literal["c", "ct", "ctt", "n"]
AutolagMethod = Literal["AIC", "BIC", "t-stat"]


def run_adf(
    series: pd.Series,
    regression: RegressionType = "c",
    autolag: Optional[AutolagMethod] = "AIC",
    maxlag: Optional[int] = None,
    significance: float = 0.05,
) -> dict:
    """
    Esegue il test ADF e restituisce i risultati in un dizionario strutturato.

    :param series: serie temporale (prezzo o log-prezzo — NON rendimenti per test di stazionarietà)
    :param regression: 'c'=costante, 'ct'=costante+trend, 'ctt'=costante+trend quadratico, 'n'=nessuno
    :param autolag: metodo per la selezione automatica dei lag ('AIC', 'BIC', 't-stat') o None
    :param maxlag: numero massimo di lag da considerare (None = auto)
    :param significance: livello di significatività per l'interpretazione (default 5%)
    :return: dizionario con statistica, p-value, lag, valori critici, interpretazione
    """
    try:
        from statsmodels.tsa.stattools import adfuller
    except ImportError:
        raise ImportError("statsmodels richiesto: pip install statsmodels")

    series = series.dropna()
    n = len(series)

    if n < 15:
        return {
            "error": f"Serie troppo corta ({n} osservazioni). Minimo 15 per ADF.",
            "applicable": False,
        }

    try:
        result = adfuller(
            series.values,
            regression=regression,
            autolag=autolag,
            maxlag=maxlag,
        )
    except Exception as exc:
        return {"error": str(exc), "applicable": False}

    stat, pvalue, lags_used, nobs = result[0], result[1], result[2], result[3]
    critical_values = result[4]

    reject_h0 = pvalue < significance

    # Interpretazione in italiano
    if reject_h0:
        if pvalue < 0.01:
            verdict = "Forte evidenza di stazionarietà"
            verdict_en = "strong_stationarity"
        else:
            verdict = "Evidenza moderata di stazionarietà"
            verdict_en = "moderate_stationarity"
    else:
        if pvalue > 0.10:
            verdict = "Nessuna evidenza di stazionarietà (random walk probabile)"
            verdict_en = "non_stationary"
        else:
            verdict = "Evidenza debole / inconcludente"
            verdict_en = "inconclusive"

    regression_descriptions = {
        "c": "Costante (intercetta)",
        "ct": "Costante + trend lineare",
        "ctt": "Costante + trend quadratico",
        "n": "Nessuna costante/trend",
    }

    warnings = [
        "L'ADF ha bassa potenza su serie corte: risultati su < 100 osservazioni sono meno affidabili.",
        "La scelta dei lag influenza il risultato: valuta diversi metodi (AIC, BIC, t-stat).",
        "Rotture strutturali (cambi di regime) possono invalidare il test.",
        "Stazionarietà statistica ≠ strategia profittabile. Richiede signal design, costi, rischio.",
    ]

    return {
        "applicable": True,
        "test_statistic": round(float(stat), 6),
        "p_value": round(float(pvalue), 6),
        "lags_used": int(lags_used),
        "n_observations": int(nobs),
        "critical_values": {k: round(v, 4) for k, v in critical_values.items()},
        "regression_type": regression,
        "regression_description": regression_descriptions.get(regression, regression),
        "autolag_method": autolag or "Nessuno (specifico)",
        "reject_h0": reject_h0,
        "significance_level": significance,
        "verdict": verdict,
        "verdict_code": verdict_en,
        "null_hypothesis": "La serie ha una radice unitaria (non-stazionaria)",
        "alternative_hypothesis": "La serie è stazionaria",
        "warnings": warnings,
    }


def run_adf_multi_sample(
    full: pd.Series,
    in_sample: Optional[pd.Series],
    out_sample: Optional[pd.Series],
    **kwargs,
) -> dict:
    """Esegue ADF su campione intero, in-sample e out-of-sample."""
    results = {"full": run_adf(full, **kwargs)}
    if in_sample is not None:
        results["in_sample"] = run_adf(in_sample, **kwargs)
    if out_sample is not None:
        results["out_of_sample"] = run_adf(out_sample, **kwargs)

    # Avviso se mean-reversion trovata solo in-sample
    if (
        in_sample is not None
        and out_sample is not None
        and results["in_sample"].get("reject_h0")
        and not results["out_of_sample"].get("reject_h0")
    ):
        results["overfitting_warning"] = (
            "⚠️  ATTENZIONE: evidenza di stazionarietà rilevata in-sample ma NON out-of-sample. "
            "Questo è un segnale classico di overfitting o instabilità di regime. "
            "Non usare questo risultato per costruire strategie di trading."
        )

    return results
