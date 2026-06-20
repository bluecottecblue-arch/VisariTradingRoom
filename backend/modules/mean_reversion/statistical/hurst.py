"""
Esponente di Hurst — misura della persistenza/anti-persistenza di una serie.

INTERPRETAZIONE:
  H < 0.5  → Anti-persistente / mean-reverting (la serie tende a tornare alla media)
  H ≈ 0.5  → Random walk (moto browniano geometrico)
  H > 0.5  → Persistente / trending (i movimenti tendono a continuare)

METODO: regressione log-log della varianza del range riscalato (R/S) su multipli lag.
È più robusto del semplice metodo RS per serie finanziarie.

LIMITAZIONI:
  - Le stime di Hurst sono rumorose su campioni < 200 osservazioni.
  - Sensibile alla scelta dei lag e alla finestra temporale.
  - Il regime può cambiare nel tempo (usare rolling Hurst per monitorare).
  - Un H < 0.5 non garantisce profitti da strategie mean-reverting.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _compute_hurst_rs(series: np.ndarray, lags: Optional[list[int]] = None) -> tuple[float, dict]:
    """
    Calcola H con metodo R/S (Rescaled Range) via regressione log-log.
    Restituisce (H, dati_diagnostici).
    """
    n = len(series)
    if lags is None:
        # Lag da 10 a n/4, campionati geometricamente
        max_lag = max(n // 4, 20)
        min_lag = max(10, n // 40)
        lags = [int(x) for x in np.unique(
            np.logspace(np.log10(min_lag), np.log10(max_lag), 20).astype(int)
        ) if x >= 5]

    rs_values = []
    valid_lags = []

    for lag in lags:
        if lag < 4 or lag >= n:
            continue
        n_chunks = n // lag
        if n_chunks < 2:
            continue

        rs_list = []
        for i in range(n_chunks):
            chunk = series[i * lag:(i + 1) * lag]
            m = chunk.mean()
            dev = np.cumsum(chunk - m)
            r = dev.max() - dev.min()
            s = chunk.std(ddof=1)
            if s > 0:
                rs_list.append(r / s)

        if rs_list:
            rs_values.append(np.mean(rs_list))
            valid_lags.append(lag)

    if len(valid_lags) < 4:
        raise ValueError(f"Troppo pochi lag validi ({len(valid_lags)}) per stimare H.")

    log_lags = np.log(valid_lags)
    log_rs = np.log(rs_values)
    coeffs = np.polyfit(log_lags, log_rs, 1)
    h = coeffs[0]

    residuals = log_rs - np.polyval(coeffs, log_lags)
    r_squared = 1 - np.var(residuals) / np.var(log_rs)

    return float(h), {
        "lags": valid_lags,
        "rs_values": [round(v, 4) for v in rs_values],
        "log_lags": [round(v, 4) for v in log_lags.tolist()],
        "log_rs": [round(v, 4) for v in log_rs.tolist()],
        "r_squared": round(float(r_squared), 4),
        "intercept": round(float(coeffs[1]), 4),
    }


def _interpret_hurst(h: float) -> tuple[str, str]:
    """Restituisce (descrizione italiana, codice)."""
    if h < 0.40:
        return "Forte anti-persistenza / mean-reverting", "strong_mean_reverting"
    elif h < 0.45:
        return "Moderata anti-persistenza / tendenza mean-reverting", "moderate_mean_reverting"
    elif h < 0.55:
        return "Random walk (processo casuale)", "random_walk"
    elif h < 0.65:
        return "Moderata persistenza / tendenza trending", "moderate_trending"
    else:
        return "Forte persistenza / trending", "strong_trending"


def run_hurst(
    series: pd.Series,
    lags: Optional[list[int]] = None,
    rolling_window: Optional[int] = None,
) -> dict:
    """
    Esegue la stima dell'esponente di Hurst.

    :param series: serie di prezzi o log-prezzi (non rendimenti!)
    :param lags: lista di lag da usare (None = automatico)
    :param rolling_window: finestra per il rolling Hurst (None = disabilitato)
    """
    series = series.dropna()
    n = len(series)

    if n < 30:
        return {"error": f"Serie troppo corta ({n} obs). Minimo 30 per Hurst.", "applicable": False}

    try:
        values = np.array(series.values, dtype=float)
        h, diag = _compute_hurst_rs(values, lags)
    except Exception as exc:
        return {"error": str(exc), "applicable": False}

    description, code = _interpret_hurst(h)

    result: dict = {
        "applicable": True,
        "h": round(h, 4),
        "interpretation": description,
        "interpretation_code": code,
        "r_squared": diag["r_squared"],
        "lags_used": diag["lags"],
        "rs_values": diag["rs_values"],
        "diagnostics": diag,
        "warnings": [
            "L'esponente di Hurst è rumoroso su campioni < 200 osservazioni.",
            "Sensibile alla scelta dei lag: cambia l'intervallo di lag per verificare la robustezza.",
            "H varia nel tempo (regimi): usa il rolling Hurst per monitorare la stabilità.",
            "H < 0.5 è una condizione necessaria ma non sufficiente per una strategia mean-reverting profittabile.",
        ],
    }

    # Rolling Hurst
    if rolling_window is not None and n >= rolling_window * 2:
        rolling_h = []
        rolling_timestamps = []
        for i in range(rolling_window, n):
            window = values[i - rolling_window:i]
            try:
                h_roll, _ = _compute_hurst_rs(window)
                rolling_h.append(round(h_roll, 4))
            except Exception:
                rolling_h.append(None)
            ts = series.index[i]
            rolling_timestamps.append(str(ts)[:10] if hasattr(ts, 'strftime') else str(ts)[:10])

        result["rolling"] = {
            "window": rolling_window,
            "timestamps": rolling_timestamps,
            "h_values": rolling_h,
            "mean_h": round(float(np.nanmean([v for v in rolling_h if v])), 4) if rolling_h else None,
            "std_h": round(float(np.nanstd([v for v in rolling_h if v])), 4) if rolling_h else None,
        }

    return result


def run_hurst_multi_sample(
    full: pd.Series,
    in_sample: Optional[pd.Series],
    out_sample: Optional[pd.Series],
    rolling_window: Optional[int] = None,
    **kwargs,
) -> dict:
    """Esegue Hurst su campione intero, in-sample e out-of-sample."""
    results = {"full": run_hurst(full, rolling_window=rolling_window, **kwargs)}
    if in_sample is not None:
        results["in_sample"] = run_hurst(in_sample, **kwargs)
    if out_sample is not None:
        results["out_of_sample"] = run_hurst(out_sample, **kwargs)

    if (
        in_sample is not None
        and out_sample is not None
        and results["in_sample"].get("applicable")
        and results["out_of_sample"].get("applicable")
    ):
        h_in = results["in_sample"].get("h", 0.5)
        h_out = results["out_of_sample"].get("h", 0.5)
        if h_in < 0.45 and h_out > 0.50:
            results["overfitting_warning"] = (
                "⚠️  H in-sample < 0.5 (mean-reverting) ma H out-of-sample ≥ 0.5 (random walk). "
                "Instabilità di regime: non usare per costruire strategie."
            )

    return results
