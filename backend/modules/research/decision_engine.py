import os


VERDICT_REJECT = "REJECT"
VERDICT_NEEDS_RESEARCH = "NEEDS_RESEARCH"
VERDICT_PAPER_TRADE_ONLY = "PAPER_TRADE_ONLY"
VERDICT_LIMITED_LIVE_TEST = "LIMITED_LIVE_TEST"
VERDICT_PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"

PROMOTED_VERDICTS = {
    VERDICT_PAPER_TRADE_ONLY,
    VERDICT_LIMITED_LIVE_TEST,
    VERDICT_PRODUCTION_CANDIDATE,
}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def is_promoted_verdict(verdict: str) -> bool:
    return verdict in PROMOTED_VERDICTS


class DecisionEngine:
    def __init__(self) -> None:
        self.paper_trade_threshold = _env_float("RESEARCH_SCORE_PAPER_TRADE", 0.45)
        self.limited_live_threshold = _env_float("RESEARCH_SCORE_LIMITED_LIVE", 0.65)
        self.production_threshold = _env_float("RESEARCH_SCORE_PRODUCTION", 0.82)
        self.max_live_overfit_score = _env_float("RESEARCH_MAX_LIVE_OVERFIT", 0.8)
        self.min_live_implementation_score = _env_float("RESEARCH_MIN_LIVE_IMPLEMENTATION", 0.6)
        self.max_live_risk_of_ruin = _env_float("RESEARCH_MAX_LIVE_RISK_OF_RUIN", 0.18)
        self.min_live_oos_trades = _env_int("RESEARCH_MIN_LIVE_OOS_TRADES", 80)

    def evaluate(
        self,
        *,
        codifiability_status: str,
        formal_status: str,
        implementation_context: dict,
        in_sample: dict,
        out_of_sample: dict,
        bias_check: dict,
        statistical: dict,
        robustness: dict,
        regime: dict,
        risk: dict,
        data_info=None,
    ) -> dict:
        data_info = data_info or {}
        sample_status = (statistical.get("sample_rules") or {}).get("status", "TOO_SMALL")
        sample_count = int((statistical.get("sample_rules") or {}).get("trade_count", 0))
        implementation_score = float(implementation_context.get("completeness", 0.45))
        regime_dependence = float(regime.get("dependence_score", 0.0))
        robustness_score = float(robustness.get("robustness_score", 0.0))
        risk_score = float(risk.get("risk_score", 0.0))
        oos_quality = self._oos_quality_score(out_of_sample)
        sample_score = self._sample_score(sample_status, sample_count)
        codifiability_score = 1.0 if codifiability_status == "VALID" and formal_status == "VALID" else 0.0
        drawdown_score = self._drawdown_score(out_of_sample)

        score_breakdown = {
            "codifiability": round(codifiability_score, 4),
            "sample_size": round(sample_score, 4),
            "oos_quality": round(oos_quality, 4),
            "robustness": round(robustness_score, 4),
            "regime_independence": round(max(0.0, 1.0 - regime_dependence), 4),
            "drawdown_quality": round(drawdown_score, 4),
            "implementation_completeness": round(implementation_score, 4),
            "risk_quality": round(risk_score, 4),
        }
        overall = round(
            0.12 * score_breakdown["codifiability"]
            + 0.12 * score_breakdown["sample_size"]
            + 0.20 * score_breakdown["oos_quality"]
            + 0.16 * score_breakdown["robustness"]
            + 0.10 * score_breakdown["regime_independence"]
            + 0.10 * score_breakdown["drawdown_quality"]
            + 0.08 * score_breakdown["implementation_completeness"]
            + 0.12 * score_breakdown["risk_quality"],
            4,
        )

        blockers = []
        reasons = []
        warnings = []
        critical = int(bias_check.get("critical_count", 0))
        high = int(bias_check.get("high_count", 0))

        if critical > 0:
            blockers.append("Bias critici rilevati nel backtest.")
        if codifiability_score == 0:
            blockers.append("La strategia non è completamente codificabile.")
        if sample_status == "TOO_SMALL":
            blockers.append("Campione OOS troppo piccolo per un giudizio serio.")
        if float(out_of_sample.get("expectancy_r", 0.0)) <= 0:
            warnings.append("Expectancy OOS non positiva.")
        if regime.get("warning"):
            warnings.append(regime["warning"])
        if risk.get("warnings"):
            warnings.extend(risk["warnings"][:2])
        if high > 1:
            warnings.append("Multipli warning di alta severità nella bias review.")
        if float(robustness.get("overfit_suspicion_score", 0.0)) > 0.65:
            warnings.append("Overfit suspicion elevato.")

        provider = str(data_info.get("provider", "")).lower()
        if provider == "demo":
            warnings.append("Provider demo: la decisione vale solo per workflow interno, non per ricerca reale.")

        verdict = VERDICT_REJECT
        if blockers:
            verdict = VERDICT_REJECT
            reasons.extend(blockers)
        elif overall < self.paper_trade_threshold:
            verdict = VERDICT_NEEDS_RESEARCH
            reasons.append("Il punteggio complessivo è insufficiente per promuovere la strategia.")
        elif overall < self.limited_live_threshold:
            verdict = VERDICT_PAPER_TRADE_ONLY
            reasons.append("La strategia mostra segnali interessanti ma richiede ancora cautela operativa.")
        elif overall < self.production_threshold:
            verdict = VERDICT_LIMITED_LIVE_TEST
            reasons.append("La strategia supera i controlli principali ma resta adatta solo a test live limitati.")
        else:
            verdict = VERDICT_PRODUCTION_CANDIDATE
            reasons.append("La strategia supera in modo convincente i controlli locali disponibili.")

        if provider == "demo" and verdict in {VERDICT_LIMITED_LIVE_TEST, VERDICT_PRODUCTION_CANDIDATE}:
            verdict = VERDICT_PAPER_TRADE_ONLY
            reasons.append("I dati demo impediscono qualunque promozione oltre paper trade.")

        if implementation_score < self.min_live_implementation_score and verdict in {VERDICT_LIMITED_LIVE_TEST, VERDICT_PRODUCTION_CANDIDATE}:
            verdict = VERDICT_PAPER_TRADE_ONLY
            reasons.append("La strategia è ancora testata tramite un adapter backtest semplificato.")

        if float(robustness.get("overfit_suspicion_score", 0.0)) > self.max_live_overfit_score and verdict != VERDICT_REJECT:
            verdict = VERDICT_NEEDS_RESEARCH
            reasons.append("Il rischio di overfitting resta troppo alto.")

        ruin_proxy = float((risk.get("metrics") or {}).get("risk_of_ruin_proxy", 0.0))
        if ruin_proxy > self.max_live_risk_of_ruin and verdict in {VERDICT_LIMITED_LIVE_TEST, VERDICT_PRODUCTION_CANDIDATE}:
            verdict = VERDICT_PAPER_TRADE_ONLY
            reasons.append("Il risk of ruin stimato è troppo alto per promuovere oltre paper trade.")

        if sample_count < self.min_live_oos_trades and verdict in {VERDICT_LIMITED_LIVE_TEST, VERDICT_PRODUCTION_CANDIDATE}:
            verdict = VERDICT_PAPER_TRADE_ONLY
            reasons.append("Il campione OOS resta troppo piccolo per un test live credibile.")

        return {
            "verdict": verdict,
            "overall_score": overall,
            "score_breakdown": score_breakdown,
            "reasons": reasons,
            "blockers": blockers,
            "warnings": warnings,
            "generate_bot_allowed": is_promoted_verdict(verdict),
            "export_allowed": is_promoted_verdict(verdict),
            "confidence_label": self._confidence_label(overall, sample_status, provider),
            "policy_snapshot": {
                "paper_trade_threshold": self.paper_trade_threshold,
                "limited_live_threshold": self.limited_live_threshold,
                "production_threshold": self.production_threshold,
                "max_live_overfit_score": self.max_live_overfit_score,
                "min_live_implementation_score": self.min_live_implementation_score,
                "max_live_risk_of_ruin": self.max_live_risk_of_ruin,
                "min_live_oos_trades": self.min_live_oos_trades,
            },
        }

    def _sample_score(self, sample_status: str, sample_count: int) -> float:
        if sample_status == "TOO_SMALL":
            return 0.15
        if sample_status == "LIMITED":
            return min(0.55, 0.3 + sample_count / 250.0)
        if sample_status == "ADEQUATE":
            return 0.72
        return 0.9

    def _oos_quality_score(self, out_of_sample: dict) -> float:
        sharpe = float(out_of_sample.get("sharpe_ratio", 0.0))
        expectancy = float(out_of_sample.get("expectancy_r", 0.0))
        profit_factor = float(out_of_sample.get("profit_factor", 0.0))
        total_return = float(out_of_sample.get("total_return_pct", 0.0))
        return max(
            0.0,
            min(
                1.0,
                0.35 * min(1.0, max(0.0, sharpe) / 1.5)
                + 0.25 * min(1.0, max(0.0, expectancy + 0.1) / 0.4)
                + 0.20 * min(1.0, max(0.0, profit_factor - 1.0) / 1.0)
                + 0.20 * min(1.0, max(0.0, total_return) / 20.0),
            ),
        )

    def _drawdown_score(self, out_of_sample: dict) -> float:
        dd = abs(float(out_of_sample.get("max_drawdown_pct", 0.0)))
        if dd <= 5:
            return 0.95
        if dd <= 10:
            return 0.8
        if dd <= 20:
            return 0.55
        if dd <= 30:
            return 0.35
        return 0.15

    def _confidence_label(self, overall: float, sample_status: str, provider: str) -> str:
        if provider == "demo":
            return "WORKFLOW_ONLY"
        if sample_status == "TOO_SMALL":
            return "LOW_CONFIDENCE"
        if overall >= 0.8:
            return "HIGH_CONFIDENCE"
        if overall >= 0.6:
            return "MODERATE_CONFIDENCE"
        return "LOW_CONFIDENCE"
