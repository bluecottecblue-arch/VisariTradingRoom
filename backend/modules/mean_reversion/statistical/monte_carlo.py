"""
Analisi Monte Carlo — confronto con distribuzione nulla (random walk).

SCOPO: verificare se le statistiche osservate (H, VR, ADF) sono più estreme
di quanto ci si aspetterebbe da un puro random walk con stessa media e volatilità.

TRE METODI:
A. GBM (Geometric Brownian Motion): simula percorsi random walk con drift e volatilità
   stimati dai dati reali. Il prezzo finale si distribuisce come log-normale.
B. Bootstrap: ricampiona i rendimenti con rimpiazzo. Preserva la distribuzione
   marginale ma distrugge la struttura seriale. Adatto per testare dipendenza temporale.
C. Permutation: mescola i rendimenti casualmente. Equivalente al bootstrap ma senza rimpiazzo.
   Conserva esattamente la distribuzione dei rendimenti.

INTERPRETAZIONE:
  Il test non dice "stazionario" o "non stazionario".
  Dice: "l'evidenza osservata è più forte di quella attesa da un random walk?"
  p-value empirico < 0.05 → l'evidenza è atipicamente forte rispetto al modello nullo.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SimMethod = Literal["gbm", "bootstrap", "permutation"]


def _simulate_paths(
    returns: np.ndarray,
    n_sims: int,
    method: SimMethod,
    start_price: float,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Genera n_sims percorsi simulati. Shape: (n_sims, len(returns)+1)."""
    rng = np.random.default_rng(seed)
    n = len(returns)

    if method == "gbm":
        mu = returns.mean()
        sigma = returns.std(ddof=1)
        noise = rng.normal(mu, sigma, size=(n_sims, n))
        paths = np.exp(np.cumsum(noise, axis=1))
        paths = np.hstack([np.ones((n_sims, 1)), paths]) * start_price

    elif method == "bootstrap":
        paths = np.empty((n_sims, n + 1))
        paths[:, 0] = start_price
        for i in range(n_sims):
            sampled = rng.choice(returns, size=n, replace=True)
            paths[i, 1:] = start_price * np.exp(np.cumsum(sampled))

    elif method == "permutation":
        paths = np.empty((n_sims, n + 1))
        paths[:, 0] = start_price
        for i in range(n_sims):
            shuffled = rng.permutation(returns)
            paths[i, 1:] = start_price * np.exp(np.cumsum(shuffled))

    else:
        raise ValueError(f"Metodo '{method}' non riconosciuto. Usa: gbm, bootstrap, permutation.")

    return paths


def _compute_hurst_simple(values: np.ndarray) -> Optional[float]:
    """Stima rapida H per uso in loop Monte Carlo."""
    n = len(values)
    if n < 30:
        return None
    lags = [max(5, n // 20), max(10, n // 10), max(20, n // 5)]
    lags = [lag for lag in lags if lag < n // 2]
    if len(lags) < 2:
        return None

    rs_vals, lag_vals = [], []
    for lag in lags:
        n_chunks = n // lag
        if n_chunks < 2:
            continue
        rs_list = []
        for i in range(n_chunks):
            chunk = values[i * lag:(i + 1) * lag]
            m = chunk.mean()
            dev = np.cumsum(chunk - m)
            r = dev.max() - dev.min()
            s = chunk.std(ddof=1)
            if s > 0:
                rs_list.append(r / s)
        if rs_list:
            rs_vals.append(np.mean(rs_list))
            lag_vals.append(lag)

    if len(lag_vals) < 2:
        return None
    h = np.polyfit(np.log(lag_vals), np.log(rs_vals), 1)[0]
    return float(h)


def run_monte_carlo(
    series: pd.Series,
    n_sims: int = 500,
    method: SimMethod = "bootstrap",
    seed: Optional[int] = 42,
    compute_hurst: bool = True,
    compute_adf: bool = True,
    compute_vr: bool = True,
    vr_lag: int = 10,
    significance: float = 0.05,
) -> dict:
    """
    Esegue l'analisi Monte Carlo.

    :param series: serie del log-prezzo (o prezzo)
    :param n_sims: numero di simulazioni (default 500, max 2000 per performance)
    :param method: 'gbm', 'bootstrap' o 'permutation'
    :param seed: seed per riproducibilità
    :param significance: soglia per p-value empirico
    """
    try:
        from scipy.stats import norm as scipy_norm
        from statsmodels.tsa.stattools import adfuller
    except ImportError:
        raise ImportError("scipy e statsmodels richiesti.")

    series = series.dropna()
    n = len(series)

    if n < 30:
        return {"error": f"Serie troppo corta ({n} obs).", "applicable": False}

    n_sims = min(n_sims, 2000)

    # Log-rendimenti della serie originale
    log_series = np.log(np.array(series.values, dtype=float))
    returns = np.diff(log_series)
    start_price = float(series.iloc[0])

    # Statistiche osservate
    obs_stats: dict = {}
    if compute_adf:
        try:
            adf_res = adfuller(series.values, regression="c", autolag="AIC")
            obs_stats["adf_stat"] = float(adf_res[0])
        except Exception:
            obs_stats["adf_stat"] = None

    if compute_hurst:
        h_obs = _compute_hurst_simple(series.values)
        obs_stats["hurst"] = h_obs

    if compute_vr and vr_lag < n // 2:
        returns_obs = np.diff(np.log(series.values))
        n_vr = len(returns_obs)
        mu = returns_obs.mean()
        var1 = ((returns_obs - mu) ** 2).sum() / (n_vr - 1)
        returns_q = np.array([returns_obs[i:i + vr_lag].sum() for i in range(n_vr - vr_lag + 1)])
        mu_q = returns_q.mean()
        var_q = ((returns_q - mu_q) ** 2).sum() / (len(returns_q) - 1)
        obs_stats["vr"] = float(var_q / (vr_lag * var1)) if var1 > 0 else None

    # Simulazioni
    paths = _simulate_paths(returns, n_sims, method, start_price, seed)

    sim_adf, sim_hurst, sim_vr = [], [], []

    for i in range(n_sims):
        path = paths[i]

        if compute_adf:
            try:
                res = adfuller(path, regression="c", autolag="AIC")
                sim_adf.append(float(res[0]))
            except Exception:
                pass

        if compute_hurst:
            h = _compute_hurst_simple(path)
            if h is not None:
                sim_hurst.append(h)

        if compute_vr and vr_lag < len(path) // 2:
            try:
                rets = np.diff(np.log(path))
                n_v = len(rets)
                mu = rets.mean()
                v1 = ((rets - mu) ** 2).sum() / (n_v - 1)
                r_q = np.array([rets[j:j + vr_lag].sum() for j in range(n_v - vr_lag + 1)])
                mu_q = r_q.mean()
                v_q = ((r_q - mu_q) ** 2).sum() / (len(r_q) - 1)
                if v1 > 0:
                    sim_vr.append(float(v_q / (vr_lag * v1)))
            except Exception:
                pass

    def emp_pvalue_lower(obs, sim_list):
        """Proporzione di simulazioni con statistica <= osservata (per ADF: più negativo = più evidence)."""
        if obs is None or not sim_list:
            return None
        return round(float(np.mean(np.array(sim_list) <= obs)), 4)

    def emp_pvalue_lower_hurst(obs, sim_list):
        """Per Hurst: p-value = proporzione con H <= osservato (mean-reverting = H < 0.5)."""
        if obs is None or not sim_list:
            return None
        return round(float(np.mean(np.array(sim_list) <= obs)), 4)

    def emp_pvalue_lower_vr(obs, sim_list):
        """Per VR: p-value = proporzione con VR <= osservato (mean-reverting = VR < 1)."""
        if obs is None or not sim_list:
            return None
        return round(float(np.mean(np.array(sim_list) <= obs)), 4)

    def percentile_info(sim_list):
        if not sim_list:
            return {}
        arr = np.array(sim_list)
        return {
            "mean": round(float(arr.mean()), 4),
            "std": round(float(arr.std()), 4),
            "p5": round(float(np.percentile(arr, 5)), 4),
            "p25": round(float(np.percentile(arr, 25)), 4),
            "p50": round(float(np.percentile(arr, 50)), 4),
            "p75": round(float(np.percentile(arr, 75)), 4),
            "p95": round(float(np.percentile(arr, 95)), 4),
        }

    result: dict = {
        "applicable": True,
        "n_simulations": n_sims,
        "method": method,
        "seed": seed,
        "observed": obs_stats,
    }

    if sim_adf and obs_stats.get("adf_stat") is not None:
        pv = emp_pvalue_lower(obs_stats["adf_stat"], sim_adf)
        result["adf"] = {
            "observed_stat": round(obs_stats["adf_stat"], 4),
            "empirical_pvalue": pv,
            "significant": pv < significance if pv is not None else None,
            "distribution": percentile_info(sim_adf),
            "n_sim_values": len(sim_adf),
            "interpretation": (
                f"La statistica ADF osservata ({obs_stats['adf_stat']:.4f}) è più negativa del "
                f"{round((1 - pv) * 100, 1) if pv else '?'}% delle simulazioni random walk. "
                + ("Evidenza atipicamente forte di stazionarietà." if pv and pv < significance
                   else "Compatibile con un random walk.")
            ),
        }

    if sim_hurst and obs_stats.get("hurst") is not None:
        pv = emp_pvalue_lower_hurst(obs_stats["hurst"], sim_hurst)
        result["hurst"] = {
            "observed_h": round(obs_stats["hurst"], 4),
            "empirical_pvalue": pv,
            "significant": pv < significance if pv is not None else None,
            "distribution": percentile_info(sim_hurst),
            "n_sim_values": len(sim_hurst),
            "interpretation": (
                f"H osservato ({obs_stats['hurst']:.4f}) è inferiore al "
                f"{round(pv * 100, 1) if pv else '?'}% degli H simulati sotto random walk. "
                + ("Mean-reversion significativamente più forte del caso." if pv and pv < significance
                   else "Compatibile con un random walk.")
            ),
        }

    if sim_vr and obs_stats.get("vr") is not None:
        pv = emp_pvalue_lower_vr(obs_stats["vr"], sim_vr)
        result["variance_ratio"] = {
            "observed_vr": round(obs_stats["vr"], 4),
            "vr_lag": vr_lag,
            "empirical_pvalue": pv,
            "significant": pv < significance if pv is not None else None,
            "distribution": percentile_info(sim_vr),
            "n_sim_values": len(sim_vr),
            "interpretation": (
                f"VR osservato ({obs_stats['vr']:.4f}) è inferiore al "
                f"{round(pv * 100, 1) if pv else '?'}% dei VR simulati sotto random walk. "
                + ("Mean-reversion significativamente più forte del caso." if pv and pv < significance
                   else "Compatibile con un random walk.")
            ),
        }

    # Conteggio segnali significativi
    sig_count = sum(1 for k in ["adf", "hurst", "variance_ratio"]
                    if result.get(k, {}).get("significant"))
    total = sum(1 for k in ["adf", "hurst", "variance_ratio"] if k in result)

    if total == 0:
        overall = "Nessuna statistica calcolabile"
    elif sig_count == 0:
        overall = "Nessuna evidenza di mean-reversion superiore al random walk atteso"
    elif sig_count == 1:
        overall = "Debole evidenza Monte Carlo di mean-reversion (1 su {} test significativo)".format(total)
    elif sig_count == 2:
        overall = "Moderata evidenza Monte Carlo di mean-reversion (2 su {} test significativi)".format(total)
    else:
        overall = "Forte evidenza Monte Carlo di mean-reversion (tutti i test significativi)"

    result["overall_interpretation"] = overall
    result["warnings"] = [
        "Il Monte Carlo testa rispetto a un modello nullo GBM/bootstrap, non alla realtà dei mercati.",
        "Un p-value empirico basso non garantisce profittabilità: richiede signal design e risk management.",
        "Aumenta n_sims per stime più stabili (raccomandato: ≥ 1000).",
        "La scelta del metodo di simulazione (gbm vs bootstrap vs permutation) può influenzare i risultati.",
    ]

    return result
