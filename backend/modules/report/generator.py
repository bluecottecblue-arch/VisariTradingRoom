"""
ReportGenerator — Genera report HTML/JSON del backtest

Produce un report completo con:
- Metriche in-sample e out-of-sample
- Walk-forward results
- Monte Carlo distribution
- Bias check con spiegazioni
- Equity curve ASCII (per debug)
- Raccomandazione finale onesta

Il report è progettato per essere leggibile sia da un utente non tecnico
(spiegazioni in italiano chiaro) che da un analista (metriche complete).
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class ReportGenerator:
    def __init__(self, storage_path: str = "./storage"):
        self.storage = Path(storage_path)
        self.storage.mkdir(exist_ok=True)

    def generate(self, session_id: str, data: dict) -> dict:
        """
        Genera il report completo e lo salva su disco.
        Ritorna paths ai file generati.
        """
        # Salva JSON raw
        json_path = self.storage / f"{session_id}_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({**data, "session_id": session_id,
                       "generated_at": datetime.utcnow().isoformat()}, f,
                      ensure_ascii=False, indent=2, default=str)

        # Genera HTML
        html_path = self.storage / f"{session_id}_report.html"
        html = self._render_html(session_id, data)
        html_path.write_text(html, encoding="utf-8")

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
        intake = data.get("intake", {})

        def fmt(v, decimals=2, suffix="", prefix=""):
            if v is None:
                return "N/A"
            try:
                return f"{prefix}{float(v):.{decimals}f}{suffix}"
            except Exception:
                return str(v)

        def color_class(v, good, bad):
            try:
                fv = float(v)
                if fv >= good:
                    return "#34d399"
                if fv <= bad:
                    return "#f87171"
                return "#fbbf24"
            except Exception:
                return "#a8a29e"

        def metric_row(label, value, color="#e7e5e4"):
            return (
                f'<tr>'
                f'<td style="color:#9ca3af;padding:5px 12px;font-size:13px">{label}</td>'
                f'<td style="color:{color};padding:5px 12px;font-weight:bold;font-size:14px">{value}</td>'
                f'</tr>'
            )

        bias_sections = ""
        for w in bias.get("warnings", []):
            sev = w.get("severity", "LOW")
            bg = {"CRITICAL": "#450a0a", "HIGH": "#451a03", "MEDIUM": "#1c1917", "LOW": "#0c0a09"}
            border = {"CRITICAL": "#7f1d1d", "HIGH": "#7c2d12", "MEDIUM": "#44403c", "LOW": "#292524"}
            color = {"CRITICAL": "#fca5a5", "HIGH": "#fcd34d", "MEDIUM": "#a8a29e", "LOW": "#57534e"}
            bias_sections += f"""
<div style="background:{bg[sev]};border:1px solid {border[sev]};border-radius:6px;padding:12px;margin:8px 0">
  <div style="color:{color[sev]};font-size:12px;font-weight:bold">[{sev}] {w.get('type','').replace('_',' ')}</div>
  <div style="color:#d4d4d4;font-size:13px;margin:4px 0">{w.get('description','')}</div>
  <div style="color:#a8a29e;font-size:12px">{w.get('what_it_means','')}</div>
  <div style="color:#78716c;font-size:12px;margin-top:4px">💡 {w.get('how_to_mitigate','')}</div>
</div>"""

        wf_section = ""
        if wf.get("aggregated"):
            agg = wf["aggregated"]
            wf_section = f"""
<h2 style="color:#a8a29e;font-size:12px;text-transform:uppercase;letter-spacing:2px;border-bottom:1px solid #292524;padding-bottom:6px;margin-top:32px">Walk-Forward Analysis</h2>
<table style="border-collapse:collapse;width:100%;max-width:600px">
  {metric_row("Sharpe medio OOS", fmt(agg.get('avg_sharpe_oos')), color_class(agg.get('avg_sharpe_oos',0), 0.8, 0.3))}
  {metric_row("Rendimento medio OOS", fmt(agg.get('avg_return_oos'), suffix='%'), color_class(agg.get('avg_return_oos',0), 5, 0))}
  {metric_row("% periodi profittevoli", fmt((agg.get('pct_profitable_periods',0)*100), suffix='%'), color_class(agg.get('pct_profitable_periods',0), 0.65, 0.4))}
  {metric_row("WF Efficiency", fmt(wf.get('wf_efficiency')), color_class(wf.get('wf_efficiency',0), 0.5, 0.2))}
</table>
<p style="color:#57534e;font-size:12px;margin-top:8px">{wf.get('interpretation','')}</p>"""

        mc_section = ""
        if mc.get("final_capital"):
            fc = mc["final_capital"]
            dd = mc.get("max_drawdown", {})
            mc_section = f"""
<h2 style="color:#a8a29e;font-size:12px;text-transform:uppercase;letter-spacing:2px;border-bottom:1px solid #292524;padding-bottom:6px;margin-top:32px">Monte Carlo ({mc.get('n_simulations', 1000)} simulazioni)</h2>
<table style="border-collapse:collapse;width:100%;max-width:600px">
  {metric_row("Capitale P5 (pessimista)", fmt(fc.get('p5'), prefix='$', decimals=0), '#f87171')}
  {metric_row("Capitale mediano", fmt(fc.get('median'), prefix='$', decimals=0))}
  {metric_row("Capitale P95 (ottimista)", fmt(fc.get('p95'), prefix='$', decimals=0), '#34d399')}
  {metric_row("Prob. profitto", fmt(mc.get('prob_profit',0)*100, suffix='%'), color_class(mc.get('prob_profit',0), 0.65, 0.45))}
  {metric_row("Prob. rovina (−50%)", fmt(mc.get('prob_ruin',0)*100, suffix='%'))}
  {metric_row("Max DD mediano", fmt(dd.get('p50',0)*100, suffix='%'))}
</table>
<p style="color:#57534e;font-size:12px;margin-top:8px">{mc.get('interpretation','')}</p>"""

        strategy_name = intake.get("name", "N/A")
        market = intake.get("market", "N/A")
        generated_at = datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")

        return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VisariTradingRoom Report — {strategy_name}</title>
<style>
  body {{ font-family: 'Courier New', monospace; background:#0c0a09; color:#e7e5e4; margin:0; padding:32px; line-height:1.6; max-width:900px; }}
  h1 {{ color:#fbbf24; font-size:22px; margin-bottom:4px; }}
  h2 {{ color:#a8a29e; font-size:11px; text-transform:uppercase; letter-spacing:2px; margin-top:32px; border-bottom:1px solid #292524; padding-bottom:6px; }}
  table {{ border-collapse:collapse; width:100%; max-width:600px; }}
  .card {{ background:#1c1917; border:1px solid #292524; border-radius:8px; padding:16px; margin:12px 0; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold; }}
  footer {{ margin-top:48px; color:#57534e; font-size:11px; border-top:1px solid #292524; padding-top:16px; }}
  @media print {{ body {{ background:white; color:#111; }} }}
</style>
</head>
<body>

<h1>VISARITRADINGROOM — REPORT BACKTEST</h1>
<p style="color:#57534e;font-size:12px">{strategy_name} · {market} · {generated_at} · Sessione: {session_id[:8]}</p>

<div class="card" style="background:#1a1200;border-color:#854d0e;margin-top:24px">
  <strong style="color:#fbbf24">⚠️ AVVERTENZA METODOLOGICA</strong>
  <p style="color:#a8a29e;font-size:13px;margin:8px 0 0">
  Un backtest positivo NON garantisce performance future. I mercati cambiano regime.
  Il codice MQL5 va revisionato da un developer prima del deploy in live.
  Parti discrezionali della strategia non codificabili sono state approssimate.
  </p>
</div>

<h2>Affidabilità metodologica</h2>
<div class="card" style="background:{'#1a0000' if bias.get('critical_count',0)>0 else '#1a1000' if bias.get('high_count',0)>0 else '#001a00'};border-color:{'#7f1d1d' if bias.get('critical_count',0)>0 else '#7c2d12' if bias.get('high_count',0)>0 else '#14532d'}">
  <strong style="color:{'#f87171' if bias.get('critical_count',0)>0 else '#fcd34d' if bias.get('high_count',0)>0 else '#34d399'}">{bias.get('overall_reliability','N/A')}</strong>
  <p style="color:#a8a29e;font-size:13px;margin:8px 0 0">{bias.get('recommendation','')}</p>
</div>
{bias_sections}

<h2>Risultati out-of-sample ★ (i numeri che contano)</h2>
<p style="color:#57534e;font-size:11px">Dati non visti durante lo sviluppo della strategia.</p>
<table>
  {metric_row("Trade totali", fmt(oos.get('total_trades'), decimals=0))}
  {metric_row("Hit rate", fmt(oos.get('hit_rate',0)*100, suffix='%'))}
  {metric_row("Expectancy (R)", fmt(oos.get('expectancy_r')), color_class(oos.get('expectancy_r',0), 0.2, 0))}
  {metric_row("Profit Factor", fmt(oos.get('profit_factor')), color_class(oos.get('profit_factor',0), 1.5, 1.0))}
  {metric_row("Sharpe Ratio", fmt(oos.get('sharpe_ratio')), color_class(oos.get('sharpe_ratio',0), 1.0, 0.3))}
  {metric_row("Sortino Ratio", fmt(oos.get('sortino_ratio')), color_class(oos.get('sortino_ratio',0), 1.5, 0.5))}
  {metric_row("Calmar Ratio", fmt(oos.get('calmar_ratio')), color_class(oos.get('calmar_ratio',0), 1.0, 0.3))}
  {metric_row("Max Drawdown", fmt(oos.get('max_drawdown_pct'), suffix='%'), color_class(-(oos.get('max_drawdown_pct',0) or 0), -5, -25))}
  {metric_row("Max perd. consecutive", fmt(oos.get('max_consecutive_losses'), decimals=0))}
  {metric_row("Rendimento totale", fmt(oos.get('total_return_pct'), suffix='%'), color_class(oos.get('total_return_pct',0), 10, 0))}
  {metric_row("Capitale finale", fmt(oos.get('final_capital'), prefix='$', decimals=0))}
</table>

<h2>Risultati in-sample (solo confronto)</h2>
<p style="color:#57534e;font-size:11px">⚠ Attesi migliori del OOS. Non usare per valutare la strategia.</p>
<table>
  {metric_row("Sharpe IS", fmt(is_r.get('sharpe_ratio')))}
  {metric_row("Rendimento IS", fmt(is_r.get('total_return_pct'), suffix='%'))}
  {metric_row("Max DD IS", fmt(is_r.get('max_drawdown_pct'), suffix='%'))}
  {metric_row("Trade IS", fmt(is_r.get('total_trades'), decimals=0))}
</table>

{wf_section}
{mc_section}

<h2>Avvertenze qualità dati</h2>
{"".join(f'<p style="color:#57534e;font-size:12px">• {w}</p>' for w in oos.get('data_quality_warnings', []))}
<p style="color:#57534e;font-size:12px">• Backtest su OHLC: ordine High/Low nella stessa candela non è noto</p>
<p style="color:#57534e;font-size:12px">• Slippage simulato con costante — non tick reale</p>

<footer>
  VisariTradingRoom · Report generato automaticamente · Non costituisce consulenza finanziaria
  <br>Per supporto: revisiona con un trader/developer esperto prima di qualsiasi decisione reale.
</footer>
</body>
</html>"""
