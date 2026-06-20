"""
Variance Ratio Test — Lo-MacKinlay (1988).

INTERPRETAZIONE:
  VR ≈ 1  → Random walk (nessuna autocorrelazione seriale)
  VR < 1  → Correlazione negativa / mean-reverting
  VR > 1  → Correlazione positiva / trending

Il test usa il rapporto tra la varianza dei rendimenti a q periodi
e q volte la varianza dei rendimenti a 1 periodo.
Sotto il random walk: Var(r_q) = q * Var(r_1).

Supporta la versione robusta all'eteroschedasticità (Wild Bootstrap / z*).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _vr_stat(returns: np.ndarray, q: int, use_robust: bool = True) -> tuple[float, float, float]:
    """
    Calcola VR, z-stat e p-value per un dato holding period q.

    :param returns: serie di log-rendimenti
    :param q: holding period
    :param use_robust: se True, usa lo z* robusto all'eteroschedasticità
    :return: (variance_ratio, z_stat, p_value)
    """
    from scipy import stats as scipy_stats

    n = len(returns)
    mu = returns.mean()

    # Var(1) — varianza dei rendimenti a 1 periodo (bias-corrected)
    var1 = ((returns - mu) ** 2).sum() / (n - 1)

    # Var(q) — varianza dei rendimenti a q periodi
    returns_q = np.array([
        returns[i:i + q].sum()
        for i in range(n - q + 1)
    ])
    mu_q = returns_q.mean()
    var_q = ((returns_q - mu_q) ** 2).sum() / (len(returns_q) - 1)

    if var1 <= 0:
        return float("nan"), float("nan"), float("nan")

    vr = var_q / (q * var1)

    if use_robust:
        # z* robusto (Lo-MacKinlay, heteroskedasticity-consistent)
        delta = np.zeros(q - 1)
        for k in range(1, q):
            numer = ((returns[k:] - mu) ** 2 * (returns[:-k] - mu) ** 2).sum()
            denom = ((returns - mu) ** 2).sum() ** 2 / n
            delta[k - 1] = numer / denom

        weights = np.array([
            2 * (q - k) / q
            for k in range(1, q)
        ]) ** 2

        theta = (weights * delta).sum()
        z_stat = (vr - 1) / np.sqrt(theta / n) if theta > 0 else float("nan")
    else:
        # z-stat sotto omoscedasticità
        theta = 2 * (2 * q - 1) * (q - 1) / (3 * q * n)
        z_stat = (vr - 1) / np.sqrt(theta)

    from scipy.stats import norm
    p_value = 2 * (1 - norm.cdf(abs(z_stat)))

    return float(vr), float(z_stat), float(p_value)


def _interpret_vr(vr: float, p_value: float, significance: float = 0.05) -> tuple[str, str]:
    """Restituisce (interpretazione italiana, codice)."""
    if np.isnan(vr):
        return "Non calcolabile", "na"

    reject = not np.isnan(p_value) and p_value < significance

    if not reject:
        return f"VR={vr:.3f} — Compatibile con random walk (H0 non rifiutata)", "random_walk"

    if vr < 1.0:
        if vr < 0.85:
            return f"VR={vr:.3f} — Forte evidenza di autocorrelazione negativa / mean-reversion", "strong_mean_reverting"
        return f"VR={vr:.3f} — Moderata evidenza di mean-reversion", "moderate_mean_reverting"
    else:
        if vr > 1.15:
            return f"VR={vr:.3f} — Forte evidenza di momentum / trending", "strong_trending"
        return f"VR={vr:.3f} — Moderata evidenza di trending", "moderate_trending"


def run_variance_ratio(
    series: pd.Series,
    lags: Optional[list[int]] = None,
    use_returns: bool = True,
    robust: bool = True,
    significance: float = 0.05,
) -> dict:
    """
    Esegue il Variance Ratio Test per multipli lag.

    :param series: serie di prezzi o log-prezzi
    :param lags: holding period da testare (default: [2, 5, 10, 20, 60])
    :param use_returns: se True calcola i log-rendimenti; se False usa la serie come è
    :param robust: se True usa lo z* robusto all'eteroschedasticità (raccomandato)
    :param significance: livello di significatività
    """
    try:
        from scipy.stats import norm
    except ImportError:
        raise ImportError("scipy richiesto: pip install scipy")

    series = series.dropna()
    n = len(series)

    if n < 30:
        return {"error": f"Serie troppo corta ({n} obs). Minimo 30 per Variance Ratio.", "applicable": False}

    if lags is None:
        lags = [2, 5, 10, 20, 60]

    # Calcola log-rendimenti dal log-prezzo (o usa la serie direttamente)
    if use_returns:
        try:
            returns = np.log(series.values / np.roll(series.values, 1))[1:]
        except Exception:
            returns = series.diff().dropna().values
    else:
        returns = series.values

    results_per_lag = []
    for q in lags:
        if q >= len(returns) // 2:
            continue
        vr, z, pv = _vr_stat(returns, q, use_robust=robust)
        interp, code = _interpret_vr(vr, pv, significance)
        results_per_lag.append({
            "q": q,
            "variance_ratio": round(vr, 4) if not np.isnan(vr) else None,
            "z_statistic": round(z, 4) if not np.isnan(z) else None,
            "p_value": round(pv, 4) if not np.isnan(pv) else None,
            "reject_h0": bool(not np.isnan(pv) and pv < significance),
            "interpretation": interp,
            "interpretation_code": code,
        })

    if not results_per_lag:
        return {"error": "Nessun lag valido calcolabile con il dataset fornito.", "applicable": False}

    # Sommario globale
    codes = [r["interpretation_code"] for r in results_per_lag if r["interpretation_code"] != "random_walk"]
    if not codes:
        overall = "Compatibile con random walk in tutti i lag testati"
        overall_code = "random_walk"
    elif sum(1 for c in codes if "mean_reverting" in c) > sum(1 for c in codes if "trending" in c):
        overall = "Tendenza mean-reverting (VR < 1 prevalente)"
        overall_code = "mean_reverting"
    else:
        overall = "Tendenza trending/momentum (VR > 1 prevalente)"
        overall_code = "trending"

    return {
        "applicable": True,
        "robust": robust,
        "n_observations": n,
        "lags": results_per_lag,
        "overall_interpretation": overall,
        "overall_code": overall_code,
        "warnings": [
            "Il VR test è valido sotto ipotesi di omoscedasticità (o usa versione robusta).",
            "Con molti lag, attenzione alla molteplicità dei test.",
            "VR < 1 non implica automaticamente profittabilità di una strategia mean-reverting.",
        ],
    }


def run_vr_multi_sample(
    full: pd.Series,
    in_sample: Optional[pd.Series],
    out_sample: Optional[pd.Series],
    **kwargs,
) -> dict:
    """Esegue VR Test su campione intero, in-sample e out-of-sample."""
    results = {"full": run_variance_ratio(full, **kwargs)}
    if in_sample is not None:
        results["in_sample"] = run_variance_ratio(in_sample, **kwargs)
    if out_sample is not None:
        results["out_of_sample"] = run_variance_ratio(out_sample, **kwargs)
    return results
