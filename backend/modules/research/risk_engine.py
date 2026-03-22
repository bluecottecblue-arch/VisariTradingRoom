from collections import defaultdict
from typing import Optional


class RiskReviewEngine:
    def evaluate(self, config: dict, metrics: dict, monte_carlo: Optional[dict], statistical: dict) -> dict:
        trades = metrics.get("trades") or []
        risk_pct = float(config.get("risk_per_trade_pct", 1.0) or 1.0)
        max_daily_trades = int(config.get("max_daily_trades", 3) or 3)
        daily_returns = defaultdict(float)
        for trade in trades:
            exit_time = trade.get("exit_time") or trade.get("entry_time")
            if not exit_time:
                continue
            day = str(exit_time)[:10]
            daily_returns[day] += float(trade.get("r_multiple", 0.0)) * risk_pct

        worst_daily_pct = min(daily_returns.values()) if daily_returns else 0.0
        max_drawdown_pct = abs(float(metrics.get("max_drawdown_pct", 0.0)))
        max_consec_losses = int(metrics.get("max_consecutive_losses", 0))
        concentration_pct = risk_pct * max(1, max_daily_trades)
        ruin_proxy = float((monte_carlo or {}).get("prob_ruin", 0.0))
        if not ruin_proxy:
            ruin_proxy = self._fallback_ruin_proxy(metrics, risk_pct)

        sample_status = (statistical.get("sample_rules") or {}).get("status", "TOO_SMALL")
        warnings = []
        if concentration_pct > 6:
            warnings.append("Rischio concentrato: rischio per trade × max trade giornalieri supera il 6% nominale.")
        if ruin_proxy > 0.1:
            warnings.append("Risk of ruin stimato elevato: il capitale è vulnerabile a sequenze avverse.")
        if worst_daily_pct < -4:
            warnings.append("Peggior giornata molto pesante: serve un daily drawdown guard più stretto.")
        if float(metrics.get("expectancy_r", 0.0)) > 0 and float(metrics.get("max_drawdown_pct", 0.0)) < -15:
            warnings.append("Expectancy positiva ma varianza elevata: il profilo rischio/rendimento resta duro da sostenere.")
        if sample_status in {"TOO_SMALL", "LIMITED"}:
            warnings.append("Campione ancora limitato: i guardrail di rischio vanno trattati con prudenza.")

        daily_guard = round(max(2.0, abs(worst_daily_pct) * 1.25, risk_pct * 2.5), 2)
        kill_switch = round(max(8.0, max_drawdown_pct * 1.2, daily_guard * 2.5), 2)
        consec_guard = max(3, max_consec_losses + 1)
        overall_score = max(
            0.0,
            min(
                1.0,
                1.0
                - min(0.5, concentration_pct / 20.0)
                - min(0.35, ruin_proxy * 1.5)
                - min(0.25, max_drawdown_pct / 35.0),
            ),
        )

        return {
            "guards": {
                "daily_drawdown_guard_pct": daily_guard,
                "equity_kill_switch_pct": kill_switch,
                "consecutive_losses_guard": consec_guard,
                "max_exposure_pct": round(concentration_pct, 2),
            },
            "metrics": {
                "worst_daily_return_pct": round(worst_daily_pct, 3),
                "risk_concentration_pct": round(concentration_pct, 3),
                "risk_of_ruin_proxy": round(ruin_proxy, 4),
                "variance_pressure_score": round(min(1.0, max_drawdown_pct / 30.0), 4),
            },
            "warnings": warnings,
            "risk_score": round(overall_score, 4),
        }

    def _fallback_ruin_proxy(self, metrics: dict, risk_pct: float) -> float:
        hit_rate = float(metrics.get("hit_rate", 0.0))
        avg_win = abs(float(metrics.get("avg_win_r", 0.0)))
        avg_loss = abs(float(metrics.get("avg_loss_r", 0.0)))
        expectancy = float(metrics.get("expectancy_r", 0.0))
        if avg_loss == 0:
            return 0.0
        edge_ratio = (hit_rate * avg_win) - ((1 - hit_rate) * avg_loss)
        penalty = max(0.0, risk_pct / 10.0) + max(0.0, -expectancy)
        if edge_ratio <= 0:
            return min(1.0, 0.2 + penalty)
        return max(0.0, min(1.0, 0.12 - edge_ratio * 0.05 + penalty))
