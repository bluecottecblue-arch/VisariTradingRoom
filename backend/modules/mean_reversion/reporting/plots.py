"""
Generazione di grafici per il report di stazionarietà.
Restituisce immagini come base64 PNG per embedding nel JSON/HTML.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_STYLE = {
    "bg": "#0f172a",
    "surface": "#1e293b",
    "text": "#e2e8f0",
    "muted": "#64748b",
    "primary": "#f59e0b",
    "green": "#22c55e",
    "red": "#ef4444",
    "blue": "#60a5fa",
    "purple": "#a78bfa",
    "grid": "#1e293b",
}


def _fig_to_b64(fig) -> str:
    """Converte una figure matplotlib in stringa base64 PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=_STYLE["bg"], edgecolor="none")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    return encoded


def plot_price_series(
    series: pd.Series,
    title: str = "Serie storica",
    in_sample_end: Optional[str] = None,
) -> Optional[str]:
    """Grafico della serie temporale con marcatura in-sample/out-of-sample."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        fig, ax = plt.subplots(figsize=(12, 4))
        fig.patch.set_facecolor(_STYLE["bg"])
        ax.set_facecolor(_STYLE["bg"])

        dates = series.index
        values = series.values

        if in_sample_end:
            cut = pd.Timestamp(in_sample_end)
            mask_in = dates <= cut
            mask_out = dates > cut
            if mask_in.any():
                ax.plot(dates[mask_in], values[mask_in], color=_STYLE["blue"],
                        linewidth=1.0, label="In-sample")
            if mask_out.any():
                ax.plot(dates[mask_out], values[mask_out], color=_STYLE["primary"],
                        linewidth=1.0, label="Out-of-sample")
            if mask_in.any():
                ax.axvline(cut, color=_STYLE["red"], linestyle="--", alpha=0.7, label="Split")
            ax.legend(facecolor=_STYLE["surface"], labelcolor=_STYLE["text"],
                      framealpha=0.8, fontsize=9)
        else:
            ax.plot(dates, values, color=_STYLE["blue"], linewidth=1.0)

        ax.set_title(title, color=_STYLE["text"], fontsize=12, pad=10)
        ax.tick_params(colors=_STYLE["muted"], labelsize=8)
        ax.spines[:].set_color(_STYLE["surface"])
        ax.grid(True, color=_STYLE["surface"], linewidth=0.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate()

        result = _fig_to_b64(fig)
        plt.close(fig)
        return result
    except Exception as exc:
        logger.warning("plot_price_series failed: %s", exc)
        return None


def plot_rolling_hurst(rolling: dict) -> Optional[str]:
    """Grafico del rolling Hurst nel tempo."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        timestamps = rolling.get("timestamps", [])
        h_values = rolling.get("h_values", [])
        window = rolling.get("window", "?")

        if not timestamps or not h_values:
            return None

        ts = pd.to_datetime(timestamps, errors="coerce")
        h_arr = np.array([v if v is not None else np.nan for v in h_values], dtype=float)

        fig, ax = plt.subplots(figsize=(12, 4))
        fig.patch.set_facecolor(_STYLE["bg"])
        ax.set_facecolor(_STYLE["bg"])

        ax.plot(ts, h_arr, color=_STYLE["purple"], linewidth=1.2, label=f"H rolling ({window})")
        ax.axhline(0.5, color=_STYLE["muted"], linestyle="--", linewidth=0.8, label="H=0.5 (random walk)")
        ax.axhspan(0, 0.5, alpha=0.05, color=_STYLE["green"], label="Zona mean-reverting (H<0.5)")
        ax.axhspan(0.5, 1.0, alpha=0.05, color=_STYLE["red"], label="Zona trending (H>0.5)")
        ax.set_ylim(0, 1)
        ax.set_title(f"Rolling Hurst (finestra={window})", color=_STYLE["text"], fontsize=12)
        ax.tick_params(colors=_STYLE["muted"], labelsize=8)
        ax.spines[:].set_color(_STYLE["surface"])
        ax.grid(True, color=_STYLE["surface"], linewidth=0.5)
        ax.legend(facecolor=_STYLE["surface"], labelcolor=_STYLE["text"],
                  framealpha=0.8, fontsize=8, loc="upper right")

        result = _fig_to_b64(fig)
        plt.close(fig)
        return result
    except Exception as exc:
        logger.warning("plot_rolling_hurst failed: %s", exc)
        return None


def plot_vr_table(lags_data: list[dict]) -> Optional[str]:
    """Grafico a barre dei Variance Ratio per diversi lag."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        qs = [r["q"] for r in lags_data if r.get("variance_ratio") is not None]
        vrs = [r["variance_ratio"] for r in lags_data if r.get("variance_ratio") is not None]
        rejects = [r.get("reject_h0", False) for r in lags_data if r.get("variance_ratio") is not None]

        if not qs:
            return None

        colors = [_STYLE["primary"] if rj else _STYLE["muted"] for rj in rejects]

        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor(_STYLE["bg"])
        ax.set_facecolor(_STYLE["bg"])

        bars = ax.bar([str(q) for q in qs], vrs, color=colors, width=0.5, edgecolor=_STYLE["surface"])
        ax.axhline(1.0, color=_STYLE["muted"], linestyle="--", linewidth=1.0, label="VR=1 (random walk)")

        for bar, vr in zip(bars, vrs):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{vr:.3f}", ha="center", va="bottom", color=_STYLE["text"], fontsize=9)

        ax.set_xlabel("Holding period q", color=_STYLE["muted"], fontsize=10)
        ax.set_ylabel("Variance Ratio", color=_STYLE["muted"], fontsize=10)
        ax.set_title("Variance Ratio per holding period", color=_STYLE["text"], fontsize=12)
        ax.tick_params(colors=_STYLE["muted"], labelsize=9)
        ax.spines[:].set_color(_STYLE["surface"])
        ax.grid(True, color=_STYLE["surface"], linewidth=0.5, axis="y")
        ax.legend(facecolor=_STYLE["surface"], labelcolor=_STYLE["text"], framealpha=0.8, fontsize=9)

        result = _fig_to_b64(fig)
        plt.close(fig)
        return result
    except Exception as exc:
        logger.warning("plot_vr_table failed: %s", exc)
        return None


def plot_mc_distribution(mc_result: dict, stat_key: str) -> Optional[str]:
    """Istogramma della distribuzione Monte Carlo con statistica osservata."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch

        stat_data = mc_result.get(stat_key)
        if not stat_data:
            return None

        dist = stat_data.get("distribution", {})
        if not dist:
            return None

        obs = stat_data.get(
            "observed_stat" if stat_key == "adf" else
            "observed_h" if stat_key == "hurst" else
            "observed_vr"
        )
        pv = stat_data.get("empirical_pvalue")
        n_sim = stat_data.get("n_sim_values", 0)

        # Genera dati per l'istogramma usando i percentili
        # (non abbiamo i valori raw, quindi usiamo la distribuzione riassuntiva)
        # Ricostruiamo approssimativamente da mean/std
        mean = dist.get("mean", 0)
        std = dist.get("std", 1)
        p5 = dist.get("p5")
        p95 = dist.get("p95")

        rng = np.random.default_rng(42)
        sim_approx = rng.normal(mean, std, 1000)
        if p5 and p95:
            sim_approx = sim_approx.clip(p5 - std, p95 + std)

        labels = {
            "adf": "Statistica ADF", "hurst": "H (Hurst)", "variance_ratio": "Variance Ratio"
        }

        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor(_STYLE["bg"])
        ax.set_facecolor(_STYLE["bg"])

        ax.hist(sim_approx, bins=40, color=_STYLE["blue"], alpha=0.7,
                edgecolor=_STYLE["surface"], label=f"Distribuzione simulata (n≈{n_sim})")

        if obs is not None:
            ax.axvline(obs, color=_STYLE["primary"], linewidth=2,
                       label=f"Osservato = {obs:.4f}")

        pv_label = f"p-value empirico = {pv:.3f}" if pv is not None else ""
        ax.set_title(
            f"Monte Carlo — {labels.get(stat_key, stat_key)}   {pv_label}",
            color=_STYLE["text"], fontsize=11
        )
        ax.set_xlabel(labels.get(stat_key, stat_key), color=_STYLE["muted"], fontsize=10)
        ax.set_ylabel("Frequenza simulazioni", color=_STYLE["muted"], fontsize=10)
        ax.tick_params(colors=_STYLE["muted"], labelsize=8)
        ax.spines[:].set_color(_STYLE["surface"])
        ax.grid(True, color=_STYLE["surface"], linewidth=0.5, axis="y")
        ax.legend(facecolor=_STYLE["surface"], labelcolor=_STYLE["text"],
                  framealpha=0.8, fontsize=9)

        result = _fig_to_b64(fig)
        plt.close(fig)
        return result
    except Exception as exc:
        logger.warning("plot_mc_distribution(%s) failed: %s", stat_key, exc)
        return None
