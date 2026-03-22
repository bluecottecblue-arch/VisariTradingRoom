from dataclasses import replace
from typing import Optional

import numpy as np

from modules.backtest.engine import BacktestConfig, BacktestEngine


class RobustnessAnalyzer:
    def evaluate(
        self,
        base_config: BacktestConfig,
        oos_data,
        strategy_fn,
        in_sample: dict,
        out_of_sample: dict,
        walk_forward: Optional[dict],
    ) -> dict:
        analysis_data = oos_data.tail(4000) if len(oos_data) > 4000 else oos_data
        scenarios = [
            ("base", 1.0, 1.0, 1.0),
            ("spread_x1_5", 1.5, 1.0, 1.0),
            ("spread_x2", 2.0, 1.0, 1.0),
            ("slippage_x2", 1.0, 2.0, 1.0),
            ("combined_stress", 2.0, 3.0, 1.5),
        ]
        scenario_results = []
        for label, spread_mult, slip_mult, comm_mult in scenarios:
            cfg = replace(
                base_config,
                spread_pips=base_config.spread_pips * spread_mult,
                slippage_pips=base_config.slippage_pips * slip_mult,
                commission_per_lot=base_config.commission_per_lot * comm_mult,
            )
            engine = BacktestEngine(cfg)
            result = engine.run(analysis_data, strategy_fn)
            scenario_results.append(
                {
                    "label": label,
                    "spread_multiplier": spread_mult,
                    "slippage_multiplier": slip_mult,
                    "commission_multiplier": comm_mult,
                    "total_return_pct": float(result.get("total_return_pct", 0.0)),
                    "expectancy_r": float(result.get("expectancy_r", 0.0)),
                    "max_drawdown_pct": float(result.get("max_drawdown_pct", 0.0)),
                    "sharpe_ratio": float(result.get("sharpe_ratio", 0.0)),
                    "trade_count": int(result.get("total_trades", 0)),
                }
            )

        heatmap = self._build_heatmap(base_config, oos_data, strategy_fn)
        expectancies = np.array([item["expectancy_r"] for item in scenario_results], dtype=float)
        returns = np.array([item["total_return_pct"] for item in scenario_results], dtype=float)
        positive_ratio = float(
            np.mean(
                [
                    item["expectancy_r"] > 0 and item["total_return_pct"] >= 0
                    for item in scenario_results
                ]
            )
        )
        base_expectancy = max(abs(float(out_of_sample.get("expectancy_r", 0.0))), 0.05)
        fragility = float(min(1.0, np.std(expectancies) / base_expectancy / 2.5))
        base_sharpe = float(out_of_sample.get("sharpe_ratio", 0.0))
        is_sharpe = max(float(in_sample.get("sharpe_ratio", 0.0)), 0.01)
        wf_eff = float((walk_forward or {}).get("wf_efficiency", 0.0))
        degradation = self._oos_degradation(in_sample, out_of_sample)
        overfit = max(
            0.0,
            min(
                1.0,
                0.35 * max(0.0, 1.0 - min(1.0, max(base_sharpe, 0.0) / is_sharpe))
                + 0.35 * (1.0 - min(1.0, wf_eff if wf_eff > 0 else 0.0))
                + 0.30 * fragility,
            ),
        )
        robustness_score = max(
            0.0,
            min(
                1.0,
                0.45 * positive_ratio
                + 0.25 * max(0.0, 1.0 - fragility)
                + 0.30 * max(0.0, 1.0 - degradation),
            ),
        )
        return {
            "analysis_bars": int(len(analysis_data)),
            "stress_scenarios": scenario_results,
            "heatmap": heatmap,
            "cost_robustness_score": round(positive_ratio, 4),
            "parameter_fragility_score": round(fragility, 4),
            "overfit_suspicion_score": round(overfit, 4),
            "oos_degradation_score": round(degradation, 4),
            "robustness_score": round(robustness_score, 4),
            "summary": self._build_summary(scenario_results, robustness_score, overfit),
        }

    def _build_heatmap(self, base_config: BacktestConfig, oos_data, strategy_fn) -> list[dict]:
        analysis_data = oos_data.tail(2500) if len(oos_data) > 2500 else oos_data
        spread_mults = [1.0, 1.5, 2.0]
        slip_mults = [1.0, 2.0]
        rows = []
        for spread_mult in spread_mults:
            cells = []
            for slip_mult in slip_mults:
                cfg = replace(
                    base_config,
                    spread_pips=base_config.spread_pips * spread_mult,
                    slippage_pips=base_config.slippage_pips * slip_mult,
                )
                engine = BacktestEngine(cfg)
                result = engine.run(analysis_data, strategy_fn)
                cells.append(
                    {
                        "slippage_multiplier": slip_mult,
                        "total_return_pct": float(result.get("total_return_pct", 0.0)),
                        "expectancy_r": float(result.get("expectancy_r", 0.0)),
                    }
                )
            rows.append({"spread_multiplier": spread_mult, "cells": cells})
        return rows

    def _oos_degradation(self, in_sample: dict, out_of_sample: dict) -> float:
        is_sharpe = max(float(in_sample.get("sharpe_ratio", 0.0)), 0.01)
        oos_sharpe = max(float(out_of_sample.get("sharpe_ratio", 0.0)), 0.0)
        is_return = float(in_sample.get("total_return_pct", 0.0))
        oos_return = float(out_of_sample.get("total_return_pct", 0.0))
        sharpe_drop = max(0.0, 1.0 - min(1.0, oos_sharpe / is_sharpe))
        return_drop = max(0.0, 1.0 - min(1.0, (oos_return + 1.0) / (is_return + 1.0))) if is_return > -1 else 1.0
        return float(max(0.0, min(1.0, 0.6 * sharpe_drop + 0.4 * return_drop)))

    def _build_summary(self, scenario_results: list[dict], robustness_score: float, overfit: float) -> str:
        profitable = sum(1 for item in scenario_results if item["total_return_pct"] > 0)
        total = len(scenario_results)
        if robustness_score >= 0.7 and overfit <= 0.35:
            return f"Robustezza buona: {profitable}/{total} scenari stress restano profittevoli."
        if robustness_score >= 0.45:
            return f"Robustezza intermedia: {profitable}/{total} scenari stress restano profittevoli."
        return f"Robustezza debole: solo {profitable}/{total} scenari stress restano profittevoli."
