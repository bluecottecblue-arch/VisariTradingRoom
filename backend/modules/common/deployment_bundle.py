"""
Helper per readiness del bot ed export bundle operativo.

Obiettivo pragmatico:
- far uscire dall'app un deliverable più vicino a un handoff professionale
- rendere espliciti setup live, dipendenze runtime e blocker
- evitare claim ingenui: export pronto != live senza controlli
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


TRADING_ECONOMICS_CALENDAR_URL = "https://api.tradingeconomics.com/calendar"


def _build_launch_pack(*, readiness: dict, research_summary: Optional[dict], macro_enabled: bool) -> dict:
    research_summary = research_summary or {}
    verdict = str(research_summary.get("verdict") or "").strip().upper()
    readiness_status = str(readiness.get("status") or "").strip().upper()
    warnings = list(readiness.get("warnings") or [])
    blockers = list(readiness.get("live_blockers") or [])
    runtime_requirements = list(readiness.get("runtime_requirements") or [])

    mode = "DEMO_ONLY"
    summary = (
        "La build è pronta per un setup controllato ma deve ancora essere osservata in demo o paper "
        "prima di qualsiasi uso con capitale reale."
    )

    if readiness_status == "BLOCKED" or verdict in {"REJECT", "NEEDS_RESEARCH"}:
        mode = "RESEARCH_ONLY"
        summary = (
            "Non portare questo bot in ambiente operativo. Chiudi i blocker, migliora il verdict research "
            "e rigenera il pacchetto prima di pensare al deploy."
        )
    elif verdict == "PAPER_TRADE_ONLY":
        mode = "PAPER_TRADE"
        summary = (
            "Il sistema è adatto a demo/paper trading controllato, ma non ha ancora sufficiente robustezza "
            "per giustificare un uso live."
        )
    elif verdict == "LIMITED_LIVE_TEST" and readiness_status == "READY_FOR_EXPORT":
        mode = "LIMITED_LIVE"
        summary = (
            "La build supporta un test live limitato con size ridotta, un solo ambiente broker e supervisione quotidiana."
        )
    elif verdict == "PRODUCTION_CANDIDATE" and readiness_status == "READY_FOR_EXPORT":
        mode = "CONTROLLED_LIVE"
        summary = (
            "Il pacchetto è adatto a un rollout live controllato, ma resta necessario un presidio operativo e un ramp-up graduale."
        )

    first_week_protocol = [
        (
            "Se non sei in LIMITED_LIVE o CONTROLLED_LIVE, mantieni il bot in demo/paper fino a quando il comportamento "
            "non combacia con la validazione."
        ),
        "Controlla a fine giornata Journal MT5, trade aperti/chiusi e rispetto delle regole della strategia.",
        "Verifica ogni giorno sizing, sessioni, spread e parametri runtime prima dell'apertura del mercato.",
        "Metti in pausa il bot immediatamente se vedi entry inattese, uscite mancanti o errori runtime.",
    ]
    if mode in {"LIMITED_LIVE", "CONTROLLED_LIVE"}:
        first_week_protocol[0] = "Avvia con size ridotta, un solo simbolo e supervisione umana quotidiana."
    if macro_enabled:
        first_week_protocol.append(
            "Verifica ogni giorno API key macro, whitelist WebRequest e aggiornamento del calendario live."
        )

    operator_brief: List[str] = [str(readiness.get("recommended_next_action") or "").strip()]
    operator_brief.extend(blockers[:2])
    operator_brief.extend(warnings[:2])
    operator_brief.extend(
        f"{item.get('label')}: {item.get('value')}"
        for item in runtime_requirements
        if item.get("required")
    )

    return {
        "mode": mode,
        "summary": summary,
        "first_week_protocol": first_week_protocol,
        "operator_brief": [item for item in operator_brief if item][:5],
        "deliverables": [
            "Strategy Specification",
            "Validation Report",
            "Risk Assessment",
            "MQL5 Bot",
            "Deployment Guide",
        ],
    }


def build_deployment_readiness(*, code: str, spec: Optional[dict], code_validation: dict) -> dict:
    spec = spec or {}
    formal_spec = dict(spec.get("formal_spec") or {})
    macro_news = dict(formal_spec.get("macro_news") or {})
    parameters = spec.get("parameters") or []

    parameter_names = {
        str(item.get("name") or item.get("id") or "").strip().lower()
        for item in parameters
        if isinstance(item, dict)
    }
    macro_enabled = bool(macro_news.get("enabled"))
    macro_provider = str(macro_news.get("provider") or "none").strip() or "none"
    market = str(formal_spec.get("market") or formal_spec.get("symbol") or "").strip()
    timeframe = str(
        formal_spec.get("execution_timeframe")
        or formal_spec.get("timeframe")
        or formal_spec.get("entry_timeframe")
        or ""
    ).strip()

    has_oninit = "OnInit(" in code
    has_ontick = "OnTick(" in code
    has_session_gate = "IsSessionActive(" in code
    has_spread_gate = "IsSpreadOk(" in code
    has_lot_size = "CalcLotSize(" in code
    has_macro_inputs = all(token in code for token in ("UseMacroNewsFilter", "MacroNewsProvider", "MacroNewsApiKey"))
    has_macro_refresh = "RefreshMacroCalendarIfNeeded(" in code
    has_macro_blackout = "IsMacroTradingBlocked(" in code
    has_macro_bias = "MacroBiasAllowsTrade(" in code
    has_web_request = "WebRequest(" in code
    risk_defined = (
        bool(formal_spec.get("risk_management"))
        or any(token in parameter_names for token in {"riskpercent", "risk_percent", "risk_per_trade_pct", "max_daily_trades"})
    )

    live_blockers: List[str] = []
    warnings: List[str] = []
    setup_steps: List[str] = [
        "Compila il file .mq5 in MetaEditor per ottenere il file .ex5 distribuibile.",
        "Carica l'EA sul grafico corretto in MT5 e verifica che timeframe e simbolo coincidano con la strategia.",
        "Esegui almeno una fase demo controllata prima di qualunque uso live.",
    ]
    runtime_requirements: List[Dict[str, Any]] = [
        {
            "id": "mt5_compile",
            "label": "Compilazione MetaEditor",
            "value": "Richiesta: converti il .mq5 in .ex5 prima del deploy operativo.",
            "required": True,
            "category": "platform",
        },
        {
            "id": "mt5_autotrading",
            "label": "Permessi MT5",
            "value": "AutoTrading attivo e parametri EA verificati sul terminale.",
            "required": True,
            "category": "platform",
        },
    ]
    mt5_checklist = [
        "MetaEditor: compile riuscita senza errori bloccanti.",
        "MT5: AutoTrading attivo sul terminale e sull'EA.",
        "Grafico corretto aperto con simbolo e timeframe previsti.",
        "Parametri di rischio, sessione e spread coerenti con il broker.",
    ]

    if market:
        runtime_requirements.append(
            {
                "id": "symbol",
                "label": "Simbolo operativo",
                "value": market,
                "required": True,
                "category": "runtime",
            }
        )
    if timeframe:
        runtime_requirements.append(
            {
                "id": "timeframe",
                "label": "Timeframe esecuzione",
                "value": timeframe,
                "required": True,
                "category": "runtime",
            }
        )

    if not code_validation.get("is_valid"):
        live_blockers.extend(code_validation.get("errors") or ["Il codice MQL5 non supera la validazione minima."])
    if not has_oninit:
        live_blockers.append("Manca OnInit(): il bot non ha un bootstrap operativo completo.")
    if not has_ontick:
        live_blockers.append("Manca OnTick(): il bot non ha un loop operativo eseguibile.")
    if not has_lot_size:
        warnings.append("CalcLotSize() non rilevato: verifica il position sizing nel codice generato.")
    if not has_session_gate:
        warnings.append("Filtro sessione non rilevato: il bot potrebbe tradare fuori finestra.")
    if not has_spread_gate:
        warnings.append("Filtro spread non rilevato: verifica la protezione execution-side.")
    if not risk_defined:
        warnings.append("Specifica rischio non completamente esplicita: ricontrolla gli input di sizing.")

    if macro_enabled:
        runtime_requirements.extend(
            [
                {
                    "id": "macro_provider",
                    "label": "Provider macro live",
                    "value": macro_provider,
                    "required": True,
                    "category": "macro",
                },
                {
                    "id": "macro_api_key",
                    "label": "API key macro runtime",
                    "value": "Da inserire nei parametri dell'EA al momento del deploy.",
                    "required": True,
                    "category": "macro",
                },
            ]
        )
        mt5_checklist.append("MT5: aggiungi il dominio del provider macro nelle URL consentite di WebRequest.")
        setup_steps.insert(
            1,
            "Imposta MacroNewsApiKey e MacroNewsProvider negli input dell'EA prima dell'avvio operativo.",
        )
        if macro_provider == "trading_economics":
            runtime_requirements.append(
                {
                    "id": "macro_webrequest",
                    "label": "WebRequest whitelist",
                    "value": TRADING_ECONOMICS_CALENDAR_URL,
                    "required": True,
                    "category": "macro",
                }
            )
            setup_steps.insert(
                2,
                "In MT5 > Strumenti > Opzioni > Expert Advisors, abilita WebRequest per https://api.tradingeconomics.com.",
            )
        if not has_macro_inputs:
            live_blockers.append("Macro news attivo ma mancano gli input runtime UseMacroNewsFilter/MacroNewsProvider/MacroNewsApiKey.")
        if not has_macro_refresh:
            live_blockers.append("Macro news attivo ma manca RefreshMacroCalendarIfNeeded().")
        if not has_macro_blackout:
            live_blockers.append("Macro news attivo ma manca IsMacroTradingBlocked().")
        if not has_macro_bias:
            warnings.append("MacroBiasAllowsTrade() non rilevato: verifica la parte di conferma direzionale.")
        if not has_web_request:
            live_blockers.append("Macro news attivo ma manca WebRequest verso il provider live.")
    else:
        warnings.append("Confluenza macro live disattivata: il bot opera solo su logica tecnica/prezzo.")

    score = 0
    score += 45 if code_validation.get("is_valid") else 0
    score += 10 if has_oninit else 0
    score += 10 if has_ontick else 0
    score += 10 if has_session_gate else 0
    score += 10 if has_spread_gate else 0
    score += 10 if has_lot_size else 0
    if macro_enabled:
        score += 5 if has_macro_inputs else 0
        score += 5 if has_macro_refresh else 0
        score += 5 if has_macro_blackout else 0
        score += 5 if has_web_request else 0
    else:
        score += 10
    score = min(100, score)

    if live_blockers:
        status = "BLOCKED"
        summary = "Il codice esiste ma non supera ancora il livello minimo per un handoff operativo pulito."
        next_action = "Rigenera il bot o correggi i blocker prima dell'export operativo."
    elif score >= 85:
        status = "READY_FOR_EXPORT"
        summary = "Build operativa pronta per export e setup finale su MT5."
        next_action = "Scarica il bundle operativo, compila in .ex5 e completa il setup runtime su demo."
    else:
        status = "REQUIRES_SETUP"
        summary = "Il bot è generato correttamente ma richiede ancora setup operativo e verifiche guidate."
        next_action = "Completa i requisiti runtime e valida il comportamento su demo prima del live."

    return {
        "status": status,
        "score": score,
        "summary": summary,
        "live_blockers": live_blockers,
        "warnings": warnings,
        "setup_steps": setup_steps,
        "runtime_requirements": runtime_requirements,
        "mt5_checklist": mt5_checklist,
        "recommended_next_action": next_action,
    }


def build_export_manifest(
    *,
    session_id: str,
    code: str,
    file_size_bytes: int,
    backtest_results: Optional[dict] = None,
    deployment_readiness: Optional[dict] = None,
) -> dict:
    backtest_results = backtest_results or {}
    final_decision = (backtest_results.get("final_decision") or {})
    data_info = (backtest_results.get("data_info") or {})
    calendar_context = data_info.get("calendar_context") or {}
    macro_enabled = "UseMacroNewsFilter" in code or "MacroNewsProvider" in code
    provider_hint = calendar_context.get("provider") or ("trading_economics" if "tradingeconomics.com" in code.lower() else "none")
    readiness = deployment_readiness or {}
    launch_pack = _build_launch_pack(
        readiness=readiness,
        research_summary=final_decision,
        macro_enabled=macro_enabled,
    )

    return {
        "session_id": session_id,
        "app_name": "VisariTradingRoom",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "mq5_filename": f"VisariTradingRoom_{session_id[:8]}.mq5",
            "file_size_bytes": file_size_bytes,
        },
        "research_summary": {
            "verdict": final_decision.get("verdict"),
            "overall_score": final_decision.get("overall_score"),
            "export_allowed": final_decision.get("export_allowed", True),
            "reasons": final_decision.get("reasons") or [],
            "blockers": final_decision.get("blockers") or [],
        },
        "macro_news": {
            "enabled": macro_enabled,
            "provider_hint": provider_hint,
            "events_used": calendar_context.get("events_used"),
            "warnings": calendar_context.get("warnings") or [],
            "webrequest_url": TRADING_ECONOMICS_CALENDAR_URL if provider_hint == "trading_economics" else None,
        },
        "deployment_readiness": readiness,
        "launch_pack": launch_pack,
        "recommended_workflow": [
            "Compila il .mq5 in .ex5 dentro MetaEditor.",
            "Imposta gli input runtime dell'EA su simbolo, rischio, sessione e provider macro.",
            "Testa il comportamento su demo prima di qualunque live deployment.",
            "Usa il report research come riferimento per aspettative, rischi e blocker residui.",
        ],
    }


def build_setup_text(manifest: dict) -> str:
    readiness = manifest.get("deployment_readiness") or {}
    launch_pack = manifest.get("launch_pack") or {}
    macro = manifest.get("macro_news") or {}
    research = manifest.get("research_summary") or {}

    lines = [
        "VISARITRADINGROOM — DEPLOYMENT SETUP GUIDE",
        "",
        f"Sessione: {manifest.get('session_id', '')}",
        f"File MQ5: {(manifest.get('artifacts') or {}).get('mq5_filename', '')}",
        "",
        "1. Stato export",
        f"- Verdict research: {research.get('verdict') or 'N/A'}",
        f"- Export allowed: {research.get('export_allowed')}",
        f"- Deployment readiness: {readiness.get('status') or 'N/A'} ({readiness.get('score') or 0}/100)",
        "",
        "2. Modalità di lancio consigliata",
        f"- Launch mode: {launch_pack.get('mode') or 'DEMO_ONLY'}",
        f"- Summary: {launch_pack.get('summary') or 'Valida il comportamento del bot in demo prima del live.'}",
        "",
        "3. Setup operativo minimo",
    ]

    for step in readiness.get("setup_steps") or []:
        lines.append(f"- {step}")

    if launch_pack.get("first_week_protocol"):
        lines.extend(["", "4. Protocollo prima settimana"])
        for item in launch_pack.get("first_week_protocol") or []:
            lines.append(f"- {item}")

    if launch_pack.get("operator_brief"):
        lines.extend(["", "5. Handoff operativo"])
        for item in launch_pack.get("operator_brief") or []:
            lines.append(f"- {item}")

    lines.extend(["", "6. Requisiti runtime"])
    for item in readiness.get("runtime_requirements") or []:
        required = "required" if item.get("required") else "optional"
        lines.append(f"- {item.get('label')}: {item.get('value')} [{required}]")

    if macro.get("enabled"):
        lines.extend(
            [
                "",
                "7. Macro news live",
                f"- Provider hint: {macro.get('provider_hint') or 'N/A'}",
            ]
        )
        if macro.get("webrequest_url"):
            lines.append(f"- WebRequest URL da consentire in MT5: {macro.get('webrequest_url')}")
        lines.append("- Inserisci sempre la tua API key macro negli input dell'EA al runtime.")
    else:
        lines.extend(["", "7. Macro news live", "- Non attivo in questa build."])

    warnings = list(readiness.get("warnings") or []) + list(macro.get("warnings") or [])
    lines.extend(["", "8. Warning"])
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- Nessun warning operativo aggiuntivo.")

    lines.extend(["", "9. Checklist MT5"])
    for item in readiness.get("mt5_checklist") or []:
        lines.append(f"- {item}")

    if launch_pack.get("deliverables"):
        lines.extend(["", "10. Deliverable inclusi"])
        for item in launch_pack.get("deliverables") or []:
            lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "11. Next action",
            f"- {readiness.get('recommended_next_action') or 'Compila, configura e valida in demo.'}",
            "",
        ]
    )
    return "\n".join(lines)
