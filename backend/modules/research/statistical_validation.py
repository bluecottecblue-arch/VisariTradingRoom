import math
from typing import Iterable

import numpy as np


def _safe_array(values: Iterable[float]) -> np.ndarray:
    return np.array([float(v) for v in values], dtype=float)


def _safe_percentile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.percentile(values, q))


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    phat = successes / total
    denom = 1 + (z * z / total)
    center = (phat + z * z / (2 * total)) / denom
    margin = (
        z
        * math.sqrt((phat * (1 - phat) / total) + (z * z / (4 * total * total)))
        / denom
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _mean_confidence_interval(values: np.ndarray, z: float = 1.96) -> tuple[float, float]:
    if values.size == 0:
        return 0.0, 0.0
    if values.size == 1:
        mean = float(values[0])
        return mean, mean
    std = float(np.std(values, ddof=1))
    margin = z * std / math.sqrt(values.size)
    mean = float(np.mean(values))
    return mean - margin, mean + margin


def _skew(values: np.ndarray) -> float:
    if values.size < 3:
        return 0.0
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=0))
    if std == 0:
        return 0.0
    centered = (values - mean) / std
    return float(np.mean(centered ** 3))


def _kurtosis(values: np.ndarray) -> float:
    if values.size < 4:
        return 0.0
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=0))
    if std == 0:
        return 0.0
    centered = (values - mean) / std
    return float(np.mean(centered ** 4) - 3.0)


class StatisticalValidationSuite:
    def __init__(self, bootstrap_samples: int = 400):
        self.bootstrap_samples = bootstrap_samples

    def evaluate(self, metrics: dict) -> dict:
        trades = metrics.get("trades") or []
        r_values = _safe_array(t.get("r_multiple", 0.0) for t in trades)
        wins = int(np.sum(r_values > 0))
        total = int(r_values.size)
        hit_rate = float(wins / total) if total else 0.0
        hit_ci = _wilson_interval(wins, total)
        mean_r = float(np.mean(r_values)) if total else 0.0
        mean_ci = _mean_confidence_interval(r_values)
        equity = _safe_array(metrics.get("equity_curve") or [])
        equity_returns = np.diff(equity) / equity[:-1] if equity.size > 1 else np.array([])
        sharpe_like = (
            float(np.mean(equity_returns) / np.std(equity_returns, ddof=1) * math.sqrt(252))
            if equity_returns.size > 2 and float(np.std(equity_returns, ddof=1)) > 0
            else 0.0
        )
        bootstrap = self._bootstrap_r_values(r_values)
        subperiod = self._subperiod_stability(trades)
        warnings = []

        if total < 30:
            warnings.append("Campione troppo piccolo per inferenze robuste: meno di 30 trade.")
        elif total < 100:
            warnings.append("Campione ancora limitato: le metriche restano instabili sotto 100 trade.")

        if total and abs(mean_r) < 0.05:
            warnings.append("Expectancy vicina a zero: il margine statistico è sottile.")

        if total and bootstrap["positive_expectancy_probability"] < 0.6:
            warnings.append("Il bootstrap non mostra una confidenza sufficiente su expectancy positiva.")

        t_stat_like = self._t_stat_like(r_values)
        p_value_proxy = self._p_value_proxy(t_stat_like, total)

        return {
            "sample_rules": {
                "trade_count": total,
                "hard_minimum_trades": 30,
                "recommended_trades": 100,
                "strong_trades": 200,
                "status": self._sample_status(total),
            },
            "confidence_intervals": {
                "mean_return_per_trade_r": {
                    "estimate": mean_r,
                    "ci_95_low": float(mean_ci[0]),
                    "ci_95_high": float(mean_ci[1]),
                },
                "hit_rate": {
                    "estimate": hit_rate,
                    "ci_95_low": float(hit_ci[0]),
                    "ci_95_high": float(hit_ci[1]),
                },
                "expectancy_r": {
                    "estimate": mean_r,
                    "ci_95_low": float(mean_ci[0]),
                    "ci_95_high": float(mean_ci[1]),
                },
                "sharpe_like": {
                    "estimate": sharpe_like,
                    "ci_95_low": bootstrap["sharpe_like"]["p5"],
                    "ci_95_high": bootstrap["sharpe_like"]["p95"],
                },
            },
            "bootstrap": bootstrap,
            "distribution_diagnostics": {
                "skew": _skew(r_values),
                "kurtosis_excess": _kurtosis(r_values),
                "tail_concentration": self._tail_concentration(r_values),
                "median_r": float(np.median(r_values)) if total else 0.0,
                "std_r": float(np.std(r_values, ddof=1)) if total > 1 else 0.0,
            },
            "subperiod_stability": subperiod,
            "significance_proxy": {
                "t_stat_like": t_stat_like,
                "p_value_proxy": p_value_proxy,
                "confidence_label": self._confidence_label(total, bootstrap["positive_expectancy_probability"], p_value_proxy),
                "note": "Proxy statistico umile: non sostituisce una validazione accademica né una vera inferenza su processi non stazionari.",
            },
            "warnings": warnings,
        }

    def _bootstrap_r_values(self, r_values: np.ndarray) -> dict:
        if r_values.size == 0:
            return {
                "n_bootstrap": 0,
                "mean_r": {"p5": 0.0, "p50": 0.0, "p95": 0.0},
                "hit_rate": {"p5": 0.0, "p50": 0.0, "p95": 0.0},
                "sharpe_like": {"p5": 0.0, "p50": 0.0, "p95": 0.0},
                "positive_expectancy_probability": 0.0,
            }

        draws = min(self.bootstrap_samples, max(120, r_values.size * 6))
        rng = np.random.default_rng(42)
        means = []
        hit_rates = []
        sharpes = []
        for _ in range(draws):
            sample = rng.choice(r_values, size=r_values.size, replace=True)
            means.append(float(np.mean(sample)))
            hit_rates.append(float(np.mean(sample > 0)))
            std = float(np.std(sample, ddof=1)) if sample.size > 1 else 0.0
            sharpes.append(float(np.mean(sample) / std) if std > 0 else 0.0)

        means_arr = np.array(means, dtype=float)
        hit_arr = np.array(hit_rates, dtype=float)
        sharpe_arr = np.array(sharpes, dtype=float)
        return {
            "n_bootstrap": int(draws),
            "mean_r": {
                "p5": _safe_percentile(means_arr, 5),
                "p50": _safe_percentile(means_arr, 50),
                "p95": _safe_percentile(means_arr, 95),
            },
            "hit_rate": {
                "p5": _safe_percentile(hit_arr, 5),
                "p50": _safe_percentile(hit_arr, 50),
                "p95": _safe_percentile(hit_arr, 95),
            },
            "sharpe_like": {
                "p5": _safe_percentile(sharpe_arr, 5),
                "p50": _safe_percentile(sharpe_arr, 50),
                "p95": _safe_percentile(sharpe_arr, 95),
            },
            "positive_expectancy_probability": float(np.mean(means_arr > 0)),
        }

    def _subperiod_stability(self, trades: list[dict]) -> dict:
        total = len(trades)
        if total == 0:
            return {"periods": [], "stability_score": 0.0}

        buckets = min(4, max(1, total // 15))
        chunk_size = max(1, math.ceil(total / buckets))
        periods = []
        expectancies = []

        for idx in range(0, total, chunk_size):
            chunk = trades[idx:idx + chunk_size]
            if not chunk:
                continue
            r_values = _safe_array(t.get("r_multiple", 0.0) for t in chunk)
            expectancy = float(np.mean(r_values)) if r_values.size else 0.0
            expectancies.append(expectancy)
            periods.append(
                {
                    "label": "P%d" % (len(periods) + 1),
                    "trade_count": len(chunk),
                    "expectancy_r": expectancy,
                    "hit_rate": float(np.mean(r_values > 0)) if r_values.size else 0.0,
                    "total_r": float(np.sum(r_values)) if r_values.size else 0.0,
                }
            )

        if len(expectancies) < 2:
            return {"periods": periods, "stability_score": 0.0}

        mean_abs = max(abs(float(np.mean(expectancies))), 0.05)
        dispersion = float(np.std(expectancies)) / mean_abs
        return {
            "periods": periods,
            "stability_score": float(max(0.0, min(1.0, 1.0 - dispersion / 2.0))),
        }

    def _tail_concentration(self, r_values: np.ndarray) -> float:
        if r_values.size == 0:
            return 0.0
        total_abs = float(np.sum(np.abs(r_values)))
        if total_abs == 0:
            return 0.0
        top_tail = np.sort(np.abs(r_values))[-max(1, int(math.ceil(r_values.size * 0.1))):]
        return float(np.sum(top_tail) / total_abs)

    def _t_stat_like(self, r_values: np.ndarray) -> float:
        if r_values.size < 2:
            return 0.0
        std = float(np.std(r_values, ddof=1))
        if std == 0:
            return 0.0
        return float(np.mean(r_values) / (std / math.sqrt(r_values.size)))

    def _p_value_proxy(self, t_stat_like: float, sample_size: int) -> float:
        if sample_size < 30:
            return 1.0
        return float(max(0.0, min(1.0, math.erfc(abs(t_stat_like) / math.sqrt(2)))))

    def _sample_status(self, total: int) -> str:
        if total < 30:
            return "TOO_SMALL"
        if total < 100:
            return "LIMITED"
        if total < 200:
            return "ADEQUATE"
        return "STRONG"

    def _confidence_label(self, total: int, positive_prob: float, p_value_proxy: float) -> str:
        if total < 30:
            return "LOW_CONFIDENCE"
        if positive_prob >= 0.8 and p_value_proxy <= 0.1:
            return "PROMISING"
        if positive_prob >= 0.65:
            return "TENTATIVE"
        return "WEAK"
