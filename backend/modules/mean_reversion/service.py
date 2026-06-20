"""
Mean Reversion Lab — Service principale.

Orchestra: caricamento dati → preprocessing → split → test statistici → plotting → report.
"""
from __future__ import annotations

import logging
import os
from typing import Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SplitMethod = Literal["ratio", "date", "none"]
SeriesTransform = Literal["price", "log_price", "returns", "log_returns"]
SimMethod = Literal["gbm", "bootstrap", "permutation"]


class MeanReversionService:

    @staticmethod
    def _final_verdict(adf: dict, hurst: dict, vr: dict, mc: dict) -> dict:
        """Sintetizza tutti i risultati in un verdetto finale."""
        signals = []

        # ADF
        adf_full = adf.get("full", {})
        if adf_full.get("reject_h0"):
            p = adf_full.get("p_value", 1)
            signals.append(("adf", "mean_reverting", 1 - p))
        elif adf_full.get("applicable"):
            signals.append(("adf", "non_stationary", 0.0))

        # Hurst
        h_full = hurst.get("full", {})
        if h_full.get("applicable"):
            h = h_full.get("h", 0.5)
            if h < 0.45:
                signals.append(("hurst", "mean_reverting", 0.5 - h))
            elif h > 0.55:
                signals.append(("hurst", "trending", h - 0.5))
            else:
                signals.append(("hurst", "random_walk", 0.0))

        # VR
        vr_full = vr.get("full", {})
        if vr_full.get("applicable"):
            code = vr_full.get("overall_code", "")
            if "mean_reverting" in code:
                signals.append(("vr", "mean_reverting", 0.3))
            elif "trending" in code:
                signals.append(("vr", "trending", 0.3))
            else:
                signals.append(("vr", "random_walk", 0.0))

        # Monte Carlo
        if mc.get("applicable"):
            mc_sigs = sum(1 for k in ["adf", "hurst", "variance_ratio"]
                          if mc.get(k, {}).get("significant"))
            mc_total = sum(1 for k in ["adf", "hurst", "variance_ratio"] if k in mc)
            if mc_total > 0 and mc_sigs / mc_total >= 0.67:
                signals.append(("mc", "mean_reverting", mc_sigs / mc_total))

        mr_count = sum(1 for _, label, _ in signals if label == "mean_reverting")
        trend_count = sum(1 for _, label, _ in signals if label == "trending")
        rw_count = sum(1 for _, label, _ in signals if label in ("random_walk", "non_stationary"))

        if mr_count >= 3:
            verdict = "Forte evidenza di stazionarietà / mean-reversion"
            code = "strong_mean_reverting"
            color = "green"
        elif mr_count == 2:
            verdict = "Moderata evidenza di mean-reversion"
            code = "moderate_mean_reverting"
            color = "yellow"
        elif mr_count == 1:
            verdict = "Evidenza debole o instabile"
            code = "weak"
            color = "orange"
        elif trend_count >= 2:
            verdict = "Tendenza trending / persistente"
            code = "trending"
            color = "blue"
        elif rw_count >= 2:
            verdict = "Random-walk-like (nessuna evidence di mean-reversion)"
            code = "random_walk"
            color = "red"
        else:
            verdict = "Inconcludente"
            code = "inconclusive"
            color = "gray"

        # Check overfitting: in-sample vs out-of-sample
        oos_warning = None
        if (
            adf.get("overfitting_warning")
            or hurst.get("overfitting_warning")
        ):
            oos_warning = (
                "⚠️  ATTENZIONE OOS: evidenza trovata in-sample ma non out-of-sample. "
                "Possibile instabilità di regime o overfitting."
            )

        return {
            "verdict": verdict,
            "verdict_code": code,
            "color": color,
            "signals_summary": [
                {"test": t, "signal": s, "strength": round(float(w), 3)}
                for t, s, w in signals
            ],
            "overfitting_warning": oos_warning,
            "disclaimer": (
                "⚠️  DISCLAIMER: questi test sono strumenti diagnostici, non una strategia completa. "
                "Una strategia profittabile richiede: design del segnale, costi di transazione, "
                "slippage, gestione del rischio, assunzioni di esecuzione e validazione out-of-sample robusta."
            ),
        }

    @staticmethod
    def run_from_dataframe(
        df: pd.DataFrame,
        price_column: str = "close",
        series_transform: SeriesTransform = "log_price",
        split_method: SplitMethod = "ratio",
        split_ratio: float = 0.7,
        split_date: Optional[str] = None,
        asset_type: str = "equity",
        fill_method: Optional[str] = None,
        # ADF
        adf_regression: str = "c",
        adf_autolag: Optional[str] = "AIC",
        adf_maxlag: Optional[int] = None,
        # Hurst
        hurst_lags: Optional[list[int]] = None,
        rolling_window: Optional[int] = 60,
        # VR
        vr_lags: Optional[list[int]] = None,
        # Monte Carlo
        mc_n_sims: int = 500,
        mc_method: SimMethod = "bootstrap",
        mc_seed: int = 42,
        mc_vr_lag: int = 10,
    ) -> dict:
        """
        Esegue l'analisi completa di mean-reversion su un DataFrame esistente.
        """
        from .preprocessing.cleaner import clean_ohlcv
        from .preprocessing.transformations import apply_transform, get_transform_description, validate_series_for_test
        from .preprocessing.splitter import split_series, get_split_info
        from .statistical.adf_test import run_adf_multi_sample
        from .statistical.hurst import run_hurst_multi_sample
        from .statistical.variance_ratio import run_vr_multi_sample
        from .statistical.monte_carlo import run_monte_carlo
        from .reporting.plots import (
            plot_price_series, plot_rolling_hurst, plot_vr_table, plot_mc_distribution
        )

        # 1. Verifica colonna
        if price_column not in df.columns:
            available = [c for c in df.columns if c != "timestamp"]
            raise ValueError(
                f"Colonna '{price_column}' non trovata. "
                f"Colonne disponibili: {available}"
            )

        # 2. Pulizia
        df_clean, quality = clean_ohlcv(
            df, price_column=price_column,
            fill_method=fill_method, drop_na=True,
            asset_type=asset_type,
        )

        if "timestamp" in df_clean.columns and not isinstance(df_clean.index, pd.DatetimeIndex):
            df_clean = df_clean.set_index("timestamp")

        raw_series = df_clean[price_column]
        raw_series.index = pd.to_datetime(raw_series.index)

        # 3. Trasformazione
        try:
            series = apply_transform(raw_series, series_transform)
        except Exception as exc:
            raise ValueError(f"Errore nella trasformazione '{series_transform}': {exc}")

        transform_desc = get_transform_description(series_transform)

        # 4. Split
        from .preprocessing.splitter import split_series, get_split_info
        in_sample, out_sample = split_series(
            series, method=split_method,
            ratio=split_ratio, split_date=split_date,
        )
        split_info = get_split_info(in_sample, out_sample)

        # 5. Validazione pre-test
        pre_warnings = []
        for test_name in ["ADF", "Hurst", "VR"]:
            pre_warnings.extend(validate_series_for_test(series, series_transform, test_name))
        pre_warnings = list(dict.fromkeys(pre_warnings))

        # 6. Test statistici
        adf_results = run_adf_multi_sample(
            series, in_sample, out_sample,
            regression=adf_regression,
            autolag=adf_autolag,
            maxlag=adf_maxlag,
        )

        hurst_results = run_hurst_multi_sample(
            series, in_sample, out_sample,
            lags=hurst_lags,
            rolling_window=rolling_window,
        )

        vr_results = run_vr_multi_sample(
            series, in_sample, out_sample,
            lags=vr_lags,
        )

        mc_result = run_monte_carlo(
            raw_series,  # Monte Carlo usa sempre i prezzi grezzi
            n_sims=mc_n_sims,
            method=mc_method,
            seed=mc_seed,
            vr_lag=mc_vr_lag,
        )

        # 7. Grafici
        in_sample_end = split_info.get("in_sample_end") if split_method != "none" else None
        plots = {}

        plots["price"] = plot_price_series(
            raw_series,
            title=f"Serie storica — {price_column}",
            in_sample_end=in_sample_end,
        )

        hurst_rolling = hurst_results.get("full", {}).get("rolling")
        if hurst_rolling:
            plots["rolling_hurst"] = plot_rolling_hurst(hurst_rolling)

        vr_lags_data = vr_results.get("full", {}).get("lags")
        if vr_lags_data:
            plots["variance_ratio"] = plot_vr_table(vr_lags_data)

        if mc_result.get("applicable"):
            for key in ["adf", "hurst", "variance_ratio"]:
                if key in mc_result:
                    plots[f"mc_{key}"] = plot_mc_distribution(mc_result, key)

        # 8. Verdetto finale
        verdict = MeanReversionService._final_verdict(
            adf_results, hurst_results, vr_results, mc_result
        )

        # 9. Metadata
        metadata = {
            "n_observations_total": len(raw_series),
            "date_range_start": str(raw_series.index[0])[:10],
            "date_range_end": str(raw_series.index[-1])[:10],
            "price_column": price_column,
            "series_transform": series_transform,
            "transform_description": transform_desc,
            "asset_type": asset_type,
        }

        return {
            "ok": True,
            "metadata": metadata,
            "quality_report": quality.to_dict(),
            "split_info": split_info,
            "pre_warnings": pre_warnings,
            "adf": adf_results,
            "hurst": hurst_results,
            "variance_ratio": vr_results,
            "monte_carlo": mc_result,
            "verdict": verdict,
            "plots": plots,
        }

    @staticmethod
    def available_columns(df: pd.DataFrame) -> list[str]:
        """Restituisce le colonne numeriche disponibili per l'analisi."""
        return [
            col for col in df.columns
            if col != "timestamp" and pd.api.types.is_numeric_dtype(df[col])
        ]
