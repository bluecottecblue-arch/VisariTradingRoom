"""
ReportGenerator — genera report HTML/JSON leggibili sia per l'utente sia per review research.
"""
import json
from datetime import datetime
from pathlib import Path


class ReportGenerator:
    def __init__(self, storage_path: str = "./storage"):
        self.storage = Path(storage_path)
        self.storage.mkdir(exist_ok=True)

    def generate(self, session_id: str, data: dict) -> dict:
        json_path = self.storage / f"{session_id}_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {**data, "session_id": session_id, "generated_at": datetime.utcnow().isoformat()},
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        html_path = self.storage / f"{session_id}_report.html"
        html_path.write_text(self._render_html(session_id, data), encoding="utf-8")

        return {
            "json_path": str(json_path),
            "html_path": str(html_path),
            "html_url": f"/api/export/report/{session_id}",
        }

    def _render_html(self, session_id: str, data: dict) -> str:
        oos = data.get("out_of_sample", {})
        is_r = data.get("in_sample", {})
        wf = data.get("walk_forward") or {}
        mc = data.get("monte_carlo") or {}
        bias = data.get("bias_check", {})
        statistical = data.get("statistical_validation", {})
        robustness = data.get("robustness_suite", {})
        regime = data.get("regime_analysis", {})
        risk = data.get("risk_review", {})
        final_decision = data.get("final_decision", {})
        governance = data.get("research_governance", {})
        data_info = data.get("data_info", {})
        generated_at = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

        def fmt(v, decimals=2, suffix="", prefix="", positive_green=False):
            if v is None:
                return "N/A"
            try:
                fv = float(v)
                formatted = f"{prefix}{fv:.{decimals}f}{suffix}"
                if positive_green:
                    color = "#34d399" if fv > 0 else "#f87171" if fv < 0 else "#a8a29e"
                    return f'<span style="color:{color}">{formatted}</span>'
                return formatted
            except Exception:
                return str(v)

        def metric_row(label, value, color="#e7e5e4"):
            return (
                f'<tr>'
                f'<td style="color:#9ca3af;padding:6px 12px;font-size:13px">{label}</td>'
                f'<td style="color:{color};padding:6px 12px;font-weight:bold;font-size:14px">{value}</td>'
                f"</tr>"
            )

        def severity_colors(level: str) -> tuple[str, str]:
            mapping = {
                "CRITICAL": ("#450a0a", "#fca5a5"),
                "HIGH": ("#451a03", "#fcd34d"),
                "MEDIUM": ("#1c1917", "#d6d3d1"),
                "LOW": ("#0c0a09", "#a8a29e"),
            }
            return mapping.get(level, ("#1c1917", "#d6d3d1"))

        def verdict_color(verdict: str) -> str:
            return {
                "REJECT": "#f87171",
                "NEEDS_RESEARCH": "#fbbf24",
                "PAPER_TRADE_ONLY": "#f59e0b",
                "LIMITED_LIVE_TEST": "#60a5fa",
                "PRODUCTION_CANDIDATE": "#34d399",
            }.get(verdict, "#d6d3d1")

        def render_badges(items, color="#fbbf24"):
            if not items:
                return '<p style="color:#57534e;font-size:12px">Nessuno.</p>'
            return "".join(
                f'<div style="background:#1c1917;border:1px solid #292524;border-radius:6px;padding:10px;margin:8px 0;color:{color};font-size:13px">{item}</div>'
                for item in items
            )

        def render_equity_curve_svg(equity: list) -> str:
            if not equity or len(equity) < 2:
                return ""
            w, h = 760, 160
            mn, mx = min(equity), max(equity)
            rng = mx - mn or 1
            pts = []
            for i, value in enumerate(equity):
                x = int(i / (len(equity) - 1) * w)
                y = int(h - (value - mn) / rng * h)
                pts.append(f"{x},{y}")
            color = "#34d399" if equity[-1] >= equity[0] else "#f87171"
            return (
                f'<svg width="100%" viewBox="0 0 {w} {h}" style="display:block;background:#0c0a09;border:1px solid #292524;border-radius:8px">'
                f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/>'
                f"</svg>"
            )

        bias_sections = ""
        for warning in bias.get("warnings", []):
            bg, color = severity_colors(warning.get("severity", "LOW"))
            bias_sections += f"""
<div style="background:{bg};border:1px solid #292524;border-radius:8px;padding:12px;margin:10px 0">
  <div style="color:{color};font-size:12px;font-weight:bold">{warning.get('severity','LOW')} · {warning.get('type','').replace('_', ' ')}</div>
  <div style="color:#e7e5e4;font-size:13px;margin-top:4px">{warning.get('description','')}</div>
  <div style="color:#a8a29e;font-size:12px;margin-top:4px">{warning.get('what_it_means','')}</div>
  <div style="color:#78716c;font-size:12px;margin-top:6px">Mitigazione: {warning.get('how_to_mitigate','')}</div>
</div>"""

        stress_rows = "".join(
            metric_row(
                scenario.get("label", "scenario"),
                (
                    f"ret {fmt(scenario.get('total_return_pct'), suffix='%', positive_green=True)} · "
                    f"exp {fmt(scenario.get('expectancy_r'))}R · "
                    f"dd {fmt(scenario.get('max_drawdown_pct'), suffix='%')}"
                ),
            )
            for scenario in robustness.get("stress_scenarios", [])
        )

        regime_rows = "".join(
            metric_row(
                item.get("regime", "N/A"),
                (
                    f"{item.get('trade_count', 0)} trade · "
                    f"exp {fmt(item.get('expectancy_r'))}R · "
                    f"win {fmt(item.get('win_rate', 0) * 100, suffix='%')} · "
                    f"contrib {fmt(item.get('contribution_to_total_r_pct'), suffix='%')}"
                ),
            )
            for item in regime.get("by_regime", [])
        )

        score_rows = "".join(
            metric_row(key.replace("_", " ").title(), fmt(value * 100, suffix="%"))
            for key, value in (final_decision.get("score_breakdown") or {}).items()
        )

        return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VisariTradingRoom Research Report — {session_id[:8]}</title>
<style>
  body {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background:#0c0a09; color:#e7e5e4; margin:0; padding:32px; line-height:1.55; max-width:980px; }}
  h1 {{ color:#fbbf24; font-size:22px; margin-bottom:4px; }}
  h2 {{ color:#a8a29e; font-size:12px; text-transform:uppercase; letter-spacing:2px; margin-top:32px; border-bottom:1px solid #292524; padding-bottom:8px; }}
  table {{ border-collapse:collapse; width:100%; max-width:780px; }}
  .card {{ background:#1c1917; border:1px solid #292524; border-radius:10px; padding:16px; margin:12px 0; }}
  .grid {{ display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); }}
  footer {{ margin-top:48px; color:#78716c; font-size:11px; border-top:1px solid #292524; padding-top:16px; }}
  @media print {{ body {{ background:white; color:#111; }} .card {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<h1>VISARITRADINGROOM — RESEARCH REPORT</h1>
<p style="color:#78716c;font-size:12px">Sessione {session_id[:8]} · {data_info.get('symbol','N/A')} {data_info.get('timeframe','')} · provider {data_info.get('provider','N/A')} · {generated_at}</p>

<div class="card" style="background:#1a1200;border-color:#854d0e">
  <strong style="color:#fbbf24">Avvertenza metodologica</strong>
  <p style="color:#d6d3d1;font-size:13px;margin:8px 0 0">
    Questa pipeline è molto più rigorosa di un semplice backtest, ma non replica ancora un'infrastruttura istituzionale completa.
    Il codice MQL5 resta un artefatto di ricerca e non va portato live senza review umana e test esterni.
  </p>
</div>

<h2>Final Decision Engine</h2>
<div class="card" style="border-color:{verdict_color(final_decision.get('verdict',''))};background:#111827">
  <div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap">
    <div>
      <div style="color:{verdict_color(final_decision.get('verdict',''))};font-size:22px;font-weight:bold">{final_decision.get('verdict','N/A')}</div>
      <div style="color:#a8a29e;font-size:12px;margin-top:4px">confidence {final_decision.get('confidence_label','N/A')}</div>
    </div>
    <div style="text-align:right">
      <div style="color:#e7e5e4;font-size:13px">overall score</div>
      <div style="font-size:24px;color:#f8fafc;font-weight:bold">{fmt((final_decision.get('overall_score') or 0) * 100, suffix='%')}</div>
    </div>
  </div>
  <div class="grid" style="margin-top:16px">
    <div>
      <div style="color:#a8a29e;font-size:12px;margin-bottom:6px">Reasons</div>
      {render_badges(final_decision.get("reasons") or [], "#e7e5e4")}
    </div>
    <div>
      <div style="color:#a8a29e;font-size:12px;margin-bottom:6px">Blockers</div>
      {render_badges(final_decision.get("blockers") or [], "#fca5a5")}
    </div>
    <div>
      <div style="color:#a8a29e;font-size:12px;margin-bottom:6px">Warnings</div>
      {render_badges(final_decision.get("warnings") or [], "#fcd34d")}
    </div>
  </div>
</div>

<h2>Score Breakdown</h2>
<table>{score_rows}</table>

<h2>Out-of-Sample Core</h2>
<table>
  {metric_row("Trade OOS", fmt(oos.get('total_trades'), decimals=0))}
  {metric_row("Hit rate", fmt(oos.get('hit_rate', 0) * 100, suffix='%'))}
  {metric_row("Expectancy", fmt(oos.get('expectancy_r')), "#34d399" if (oos.get('expectancy_r') or 0) > 0 else "#f87171")}
  {metric_row("Sharpe", fmt(oos.get('sharpe_ratio')))}
  {metric_row("Profit factor", fmt(oos.get('profit_factor')))}
  {metric_row("Max drawdown", fmt(oos.get('max_drawdown_pct'), suffix='%'))}
  {metric_row("Total return", fmt(oos.get('total_return_pct'), suffix='%', positive_green=True))}
  {metric_row("Final capital", fmt(oos.get('final_capital'), prefix='$', decimals=0))}
</table>
<div style="margin-top:14px">{render_equity_curve_svg(oos.get('equity_curve') or [])}</div>

<h2>Statistical Validation</h2>
<table>
  {metric_row("Sample status", (statistical.get('sample_rules') or {}).get('status', 'N/A'))}
  {metric_row("Trade count", fmt((statistical.get('sample_rules') or {}).get('trade_count'), decimals=0))}
  {metric_row("Expectancy CI95", f"{fmt(((statistical.get('confidence_intervals') or {}).get('expectancy_r') or {}).get('ci_95_low'))} .. {fmt(((statistical.get('confidence_intervals') or {}).get('expectancy_r') or {}).get('ci_95_high'))}")}
  {metric_row("Hit rate CI95", f"{fmt((((statistical.get('confidence_intervals') or {}).get('hit_rate') or {}).get('ci_95_low') or 0) * 100, suffix='%')} .. {fmt((((statistical.get('confidence_intervals') or {}).get('hit_rate') or {}).get('ci_95_high') or 0) * 100, suffix='%')}")}
  {metric_row("Bootstrap positive expectancy", fmt((((statistical.get('bootstrap') or {}).get('positive_expectancy_probability') or 0) * 100), suffix='%'))}
  {metric_row("Subperiod stability", fmt(((statistical.get('subperiod_stability') or {}).get('stability_score') or 0) * 100, suffix='%'))}
  {metric_row("Skew", fmt(((statistical.get('distribution_diagnostics') or {}).get('skew'))))}
  {metric_row("Excess kurtosis", fmt(((statistical.get('distribution_diagnostics') or {}).get('kurtosis_excess'))))}
</table>
{render_badges(statistical.get("warnings") or [], "#fcd34d")}

<h2>Robustness Suite</h2>
<table>
  {metric_row("Robustness score", fmt((robustness.get('robustness_score') or 0) * 100, suffix='%'))}
  {metric_row("Cost robustness", fmt((robustness.get('cost_robustness_score') or 0) * 100, suffix='%'))}
  {metric_row("Parameter fragility", fmt((robustness.get('parameter_fragility_score') or 0) * 100, suffix='%'))}
  {metric_row("OOS degradation", fmt((robustness.get('oos_degradation_score') or 0) * 100, suffix='%'))}
  {metric_row("Overfit suspicion", fmt((robustness.get('overfit_suspicion_score') or 0) * 100, suffix='%'))}
</table>
<p style="color:#a8a29e;font-size:13px">{robustness.get('summary', '')}</p>
<table>{stress_rows or metric_row("Stress scenarios", "Nessuno")}</table>

<h2>Regime Analysis</h2>
<table>
  {metric_row("Dependence score", fmt((regime.get('dependence_score') or 0) * 100, suffix='%'))}
  {metric_row("Warning", regime.get('warning', 'Nessun warning specifico'))}
</table>
<table>{regime_rows or metric_row("Regimes", "Nessun trade OOS sufficiente per segmentazione")}</table>

<h2>Risk Review</h2>
<table>
  {metric_row("Risk score", fmt((risk.get('risk_score') or 0) * 100, suffix='%'))}
  {metric_row("Risk of ruin proxy", fmt((((risk.get('metrics') or {}).get('risk_of_ruin_proxy') or 0) * 100), suffix='%'))}
  {metric_row("Worst daily return", fmt((risk.get('metrics') or {}).get('worst_daily_return_pct'), suffix='%'))}
  {metric_row("Risk concentration", fmt((risk.get('metrics') or {}).get('risk_concentration_pct'), suffix='%'))}
  {metric_row("Consecutive losses guard", fmt(((risk.get('guards') or {}).get('consecutive_losses_guard')), decimals=0))}
</table>
{render_badges(risk.get("warnings") or [], "#fcd34d")}

<h2>Bias Review</h2>
<div class="card" style="background:{'#1a0000' if bias.get('critical_count', 0) > 0 else '#1a1000' if bias.get('high_count', 0) > 0 else '#001a00'}">
  <strong style="color:{'#f87171' if bias.get('critical_count', 0) > 0 else '#fcd34d' if bias.get('high_count', 0) > 0 else '#34d399'}">{bias.get('overall_reliability', 'N/A')}</strong>
  <p style="color:#d6d3d1;font-size:13px;margin-top:8px">{bias.get('recommendation', '')}</p>
</div>
{bias_sections}

<h2>Walk-Forward e Monte Carlo</h2>
<table>
  {metric_row("WF efficiency", fmt(wf.get('wf_efficiency')))}
  {metric_row("WF avg OOS sharpe", fmt(((wf.get('aggregated') or {}).get('avg_sharpe_oos'))))}
  {metric_row("Monte Carlo prob. profit", fmt(((mc.get('prob_profit') or 0) * 100), suffix='%'))}
  {metric_row("Monte Carlo prob. ruin", fmt(((mc.get('prob_ruin') or 0) * 100), suffix='%'))}
</table>

<h2>Research Governance</h2>
<table>
  {metric_row("Strategy ID", governance.get('strategy_id', session_id))}
  {metric_row("Version", fmt(governance.get('strategy_version'), decimals=0))}
  {metric_row("Analysis timestamp", governance.get('analysis_timestamp', 'N/A'))}
  {metric_row("Final verdict", governance.get('final_verdict', 'N/A'))}
  {metric_row("Provider", data_info.get('provider', 'N/A'))}
  {metric_row("Symbol", data_info.get('symbol', 'N/A'))}
  {metric_row("Timeframe", data_info.get('timeframe', 'N/A'))}
</table>

<h2>In-Sample Reference</h2>
<table>
  {metric_row("Trade IS", fmt(is_r.get('total_trades'), decimals=0))}
  {metric_row("Expectancy IS", fmt(is_r.get('expectancy_r')))}
  {metric_row("Sharpe IS", fmt(is_r.get('sharpe_ratio')))}
  {metric_row("Return IS", fmt(is_r.get('total_return_pct'), suffix='%'))}
</table>

<footer>
  VisariTradingRoom · Research report locale · Non costituisce consulenza finanziaria.
  <br>Il workflow è più vicino a una desk pipeline, ma non sostituisce portfolio construction, execution modelling e live governance.
</footer>
</body>
</html>"""
