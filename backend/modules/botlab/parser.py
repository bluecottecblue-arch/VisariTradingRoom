"""
Parser locale per Bot Lab.

Obiettivi:
- identificare file/language supportati senza spendere token
- estrarre una logica operativa approssimata ma utile
- derivare un formal_spec_bundle compatibile con la pipeline research esistente
- produrre un health check leggibile da trader non tecnici
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Dict, List, Optional

from modules.common.strategy_validation import STATUS_INVALID, STATUS_VALID
from modules.fundamentals.economic_calendar import normalize_macro_news_config


SUPPORTED_EXTENSIONS = {
    ".mq5": ("mql5", "MetaTrader 5"),
    ".txt": ("text", "Generic text/code"),
    ".py": ("python", "Python"),
}

_INPUT_RE = re.compile(
    r"^\s*(input|extern)\s+(?P<type>\w+)\s+(?P<name>\w+)\s*=\s*(?P<value>[^;]+);",
    re.MULTILINE,
)
_PY_ASSIGN_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>[-+\"'A-Za-z0-9_., ]+)$",
    re.MULTILINE,
)
_FUNC_RE = re.compile(r"\b(?:void|int|double|bool|string|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_IMA_RE = re.compile(r"iMA\s*\(([^)]*)\)", re.IGNORECASE)
_IRSI_RE = re.compile(r"iRSI\s*\(([^)]*)\)", re.IGNORECASE)
_IATR_RE = re.compile(r"iATR\s*\(([^)]*)\)", re.IGNORECASE)
_IADX_RE = re.compile(r"iADX\s*\(([^)]*)\)", re.IGNORECASE)


@dataclass
class BotFileInfo:
    filename: str
    language: str
    platform: str
    extension: str
    size_chars: int
    line_count: int
    sha256_short: str
    source_origin: str


def analyze_bot_code(
    *,
    filename: str,
    content: str,
    source_origin: str = "user",
    platform_hint: Optional[str] = None,
    fundamental_filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return {
            "status": STATUS_INVALID,
            "message": "Il file caricato è vuoto o contiene solo spazi.",
            "file_info": {},
            "code_summary": {},
            "bot_profile": {},
            "explanation": {},
            "health_check": {
                "score": 0.0,
                "strengths": [],
                "warnings": ["Il codice caricato è vuoto."],
                "likely_issues": ["Nessuna logica analizzabile."],
            },
            "formal_spec_bundle": {
                "status": STATUS_INVALID,
                "formal_spec": {},
                "state_machine": {},
                "parameters": [],
                "non_optimizable": [],
                "assumptions": [],
                "required_inputs": [
                    {
                        "id": "req_bot_file",
                        "field": "content",
                        "label": "Carica un file non vuoto",
                        "why": "Serve codice reale per analizzare, modificare o backtestare il bot.",
                        "example": "Carica un file .mq5 completo oppure incolla il codice nel box.",
                        "blocking": True,
                    }
                ],
            },
            "backtest_ready": False,
            "compare_ready": False,
            "supported_actions": [],
            "token_saved": True,
        }

    file_info = _detect_file_info(filename, normalized, source_origin, platform_hint)
    if file_info.language == "unsupported":
        return {
            "status": STATUS_INVALID,
            "message": "Formato file non supportato. Carica .mq5, .txt o .py.",
            "file_info": file_info.__dict__,
            "code_summary": {},
            "bot_profile": {},
            "explanation": {},
            "health_check": {
                "score": 0.0,
                "strengths": [],
                "warnings": ["Formato non supportato."],
                "likely_issues": ["La piattaforma accetta .mq5, .txt o .py."],
            },
            "formal_spec_bundle": {
                "status": STATUS_INVALID,
                "formal_spec": {},
                "state_machine": {},
                "parameters": [],
                "non_optimizable": [],
                "assumptions": [],
                "required_inputs": [
                    {
                        "id": "req_bot_format",
                        "field": "filename",
                        "label": "Carica un formato supportato",
                        "why": "Il parser locale al momento supporta .mq5, .txt e .py.",
                        "example": "example_bot.mq5",
                        "blocking": True,
                    }
                ],
            },
            "backtest_ready": False,
            "compare_ready": False,
            "supported_actions": [],
            "token_saved": True,
        }

    parameters = _extract_parameters(file_info.language, normalized)
    functions = _extract_functions(normalized)
    indicators = _extract_indicators(normalized)
    trade_actions = _extract_trade_actions(normalized)
    protections = _extract_protections(normalized)
    sessions = _extract_sessions(normalized)
    fundamental_flags = _extract_fundamental_flags(normalized, fundamental_filters)
    inferred_logic = _infer_logic(normalized, indicators, trade_actions, protections)
    health_check = _build_health_check(
        functions=functions,
        indicators=indicators,
        trade_actions=trade_actions,
        protections=protections,
        parameters=parameters,
        language=file_info.language,
        fundamental_flags=fundamental_flags,
    )
    formal_spec_bundle = _build_formal_spec_bundle(
        file_info=file_info,
        parameters=parameters,
        indicators=indicators,
        protections=protections,
        sessions=sessions,
        inferred_logic=inferred_logic,
        fundamental_flags=fundamental_flags,
        configured_macro_news=fundamental_filters or {},
    )
    explanation = _build_explanation(
        file_info=file_info,
        inferred_logic=inferred_logic,
        indicators=indicators,
        protections=protections,
        fundamental_flags=fundamental_flags,
        parameters=parameters,
    )

    return {
        "status": STATUS_VALID,
        "message": "Bot analizzato localmente senza usare token.",
        "file_info": file_info.__dict__,
        "code_summary": {
            "functions": functions,
            "indicators": indicators,
            "trade_actions": trade_actions,
            "protections": protections,
            "sessions": sessions,
            "fundamental_flags": fundamental_flags,
            "lines_of_code": file_info.line_count,
            "parameter_count": len(parameters),
        },
        "bot_profile": {
            "language": file_info.language,
            "platform": file_info.platform,
            "strategy_style": inferred_logic["strategy_style"],
            "entry_logic": inferred_logic["entry_logic"],
            "exit_logic": inferred_logic["exit_logic"],
            "risk_model": inferred_logic["risk_model"],
            "technical_features": indicators,
            "fundamental_features": fundamental_flags,
            "supports_modification": file_info.language in {"mql5", "python", "text"},
        },
        "explanation": explanation,
        "health_check": health_check,
        "formal_spec_bundle": formal_spec_bundle,
        "backtest_ready": formal_spec_bundle.get("status") == STATUS_VALID,
        "compare_ready": True,
        "supported_actions": [
            "analyze",
            "explain",
            "modify",
            "improve",
            "backtest",
            "validate",
            "compare",
        ],
        "token_saved": True,
    }


def summarize_bot_diff(original: dict[str, Any], modified: dict[str, Any]) -> dict[str, Any]:
    original_profile = original.get("bot_profile") or {}
    modified_profile = modified.get("bot_profile") or {}
    original_summary = original.get("code_summary") or {}
    modified_summary = modified.get("code_summary") or {}

    original_inds = {item.get("type") for item in original_summary.get("indicators", [])}
    modified_inds = {item.get("type") for item in modified_summary.get("indicators", [])}
    original_protections = set(original_summary.get("protections", []))
    modified_protections = set(modified_summary.get("protections", []))

    return {
        "strategy_style": {
            "original": original_profile.get("strategy_style"),
            "modified": modified_profile.get("strategy_style"),
        },
        "new_indicators": sorted(ind for ind in modified_inds - original_inds if ind),
        "removed_indicators": sorted(ind for ind in original_inds - modified_inds if ind),
        "new_protections": sorted(modified_protections - original_protections),
        "removed_protections": sorted(original_protections - modified_protections),
        "parameter_count_delta": int(modified_summary.get("parameter_count", 0)) - int(original_summary.get("parameter_count", 0)),
        "fundamental_filter_added": bool(
            (modified_summary.get("fundamental_flags") or {}).get("enabled")
            and not (original_summary.get("fundamental_flags") or {}).get("enabled")
        ),
    }


def _detect_file_info(filename: str, content: str, source_origin: str, platform_hint: Optional[str]) -> BotFileInfo:
    raw_name = (filename or "uploaded_bot").strip() or "uploaded_bot"
    extension = ""
    if "." in raw_name:
        extension = "." + raw_name.split(".")[-1].lower()
    language, platform = SUPPORTED_EXTENSIONS.get(extension, ("unsupported", "Unsupported"))

    if language == "unsupported":
        lowered = content.lower()
        if "oninit(" in lowered and "ontick(" in lowered:
            language, platform, extension = "mql5", "MetaTrader 5", ".mq5"
        elif "def " in lowered and ("pandas" in lowered or "backtrader" in lowered or "ccxt" in lowered):
            language, platform, extension = "python", "Python", ".py"
        elif platform_hint:
            platform = platform_hint

    return BotFileInfo(
        filename=raw_name,
        language=language,
        platform=platform if platform_hint is None else platform_hint,
        extension=extension or "n/a",
        size_chars=len(content),
        line_count=max(1, len(content.splitlines())),
        sha256_short=hashlib.sha256(content.encode("utf-8")).hexdigest()[:12],
        source_origin=(source_origin or "user").strip() or "user",
    )


def _extract_parameters(language: str, content: str) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    if language == "mql5":
        for match in _INPUT_RE.finditer(content):
            params.append(
                {
                    "name": match.group("name"),
                    "type": match.group("type").lower(),
                    "default": match.group("value").strip(),
                }
            )
    elif language == "python":
        for match in _PY_ASSIGN_RE.finditer(content):
            name = match.group("name")
            if name.isupper() or any(token in name.lower() for token in ("period", "risk", "sl", "tp", "session", "spread", "atr", "rsi", "ema", "sma")):
                params.append({"name": name, "type": "python_var", "default": match.group("value").strip()})
    return params[:40]


def _extract_functions(content: str) -> list[str]:
    functions = []
    for fn in _FUNC_RE.findall(content):
        if fn not in functions:
            functions.append(fn)
    return functions[:30]


def _extract_indicators(content: str) -> list[dict[str, Any]]:
    indicators: list[dict[str, Any]] = []
    indicators.extend(_extract_call_based_indicator("EMA", _IMA_RE, content, default_mode="MODE_EMA"))
    indicators.extend(_extract_call_based_indicator("RSI", _IRSI_RE, content))
    indicators.extend(_extract_call_based_indicator("ATR", _IATR_RE, content))
    indicators.extend(_extract_call_based_indicator("ADX", _IADX_RE, content))

    marker_map = {
        "MACD": ["macd", "iMACD("],
        "BOLLINGER": ["bollinger", "ibands("],
        "STOCHASTIC": ["stochastic", "istochastic("],
    }
    lowered = content.lower()
    for indicator_type, markers in marker_map.items():
        if any(marker.lower() in lowered for marker in markers):
            indicators.append({"type": indicator_type, "period_ref": None, "raw": indicator_type})

    deduped = []
    seen = set()
    for item in indicators:
        key = (item.get("type"), item.get("period_ref"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:12]


def _extract_call_based_indicator(indicator_type: str, pattern: re.Pattern[str], content: str, default_mode: Optional[str] = None) -> List[Dict[str, Any]]:
    items = []
    for match in pattern.findall(content):
        args = [part.strip() for part in match.split(",")]
        period_ref = None
        if indicator_type == "EMA" and len(args) >= 3:
            mode = args[4].upper() if len(args) >= 5 else ""
            if default_mode and default_mode not in mode:
                continue
            period_ref = args[2]
        elif len(args) >= 3:
            period_ref = args[2]
        elif len(args) >= 1:
            period_ref = args[-1]
        items.append({"type": indicator_type, "period_ref": period_ref, "raw": match})
    return items


def _extract_trade_actions(content: str) -> list[str]:
    markers = {
        "open_long": ["trade.buy(", "ordersend(", "positionopen(", "order_type_buy"],
        "open_short": ["trade.sell(", "ordersend(", "positionopen(", "order_type_sell"],
        "close_position": ["positionclose(", "trade.positionclose(", "closeall", "closeposition"],
        "modify_position": ["positionmodify(", "ordermodify(", "trailing"],
    }
    lowered = content.lower()
    actions = []
    for action, tokens in markers.items():
        if any(token in lowered for token in tokens):
            actions.append(action)
    return actions


def _extract_protections(content: str) -> list[str]:
    lowered = content.lower()
    protections = []
    if any(token in lowered for token in ("stoploss", "stop_loss", "sl =")):
        protections.append("stop_loss")
    if any(token in lowered for token in ("takeprofit", "take_profit", "tp =")):
        protections.append("take_profit")
    if any(token in lowered for token in ("trailing", "breakeven", "break_even")):
        protections.append("trailing_stop")
    if "symbol_spread" in lowered or "spread" in lowered:
        protections.append("spread_filter")
    if any(token in lowered for token in ("session", "timecurrent", "hour", "tradinghours")):
        protections.append("session_filter")
    if any(token in lowered for token in ("maxdailytrades", "daily_trades", "max trades")):
        protections.append("daily_trade_limit")
    if any(token in lowered for token in ("account_balance", "riskpercent", "calc lotsize", "lot_size", "position sizing")):
        protections.append("position_sizing")
    return protections


def _extract_sessions(content: str) -> list[str]:
    lowered = content.lower()
    sessions = []
    if "london" in lowered:
        sessions.append("London")
    if "new york" in lowered or "newyork" in lowered or "ny session" in lowered:
        sessions.append("New York")
    if "asia" in lowered or "asian session" in lowered:
        sessions.append("Asia")
    if not sessions and ("sessionstart" in lowered or "sessionend" in lowered):
        sessions.append("Custom session window")
    return sessions


def _extract_fundamental_flags(content: str, configured_filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    lowered = content.lower()
    flags = {
        "enabled": False,
        "has_news_blackout": False,
        "has_directional_bias": False,
        "has_post_event_rule": False,
        "keywords": [],
    }
    keyword_map = {
        "news": ["news", "calendar", "economic event", "high impact", "low impact", "medium impact"],
        "usd": ["usd", "dollar", "fomc", "cpi", "nfp"],
        "eur": ["eur", "ecb", "eurozone", "germany cpi"],
        "gbp": ["gbp", "boe", "uk cpi", "cable"],
    }
    for label, tokens in keyword_map.items():
        if any(token in lowered for token in tokens):
            flags["keywords"].append(label)

    if any(token in lowered for token in ("news", "calendar", "fomc", "cpi", "nfp")):
        flags["enabled"] = True
    if any(token in lowered for token in ("no trade during news", "high impact", "blackout", "before news", "after news")):
        flags["has_news_blackout"] = True
    if any(token in lowered for token in ("bias", "bullish usd", "bearish usd", "macro bias")):
        flags["has_directional_bias"] = True
    if any(token in lowered for token in ("after event", "post-news", "wait 15 minutes", "breakout after")):
        flags["has_post_event_rule"] = True

    cfg = configured_filters or {}
    if cfg.get("enabled"):
        flags["enabled"] = True
        flags["has_news_blackout"] = bool(cfg.get("blackout_before_min") or cfg.get("blackout_after_min"))
        flags["has_directional_bias"] = cfg.get("bias_mode") == "confirm_with_bias"
        flags["has_post_event_rule"] = cfg.get("bias_mode") == "post_event_trigger"
    return flags


def _infer_logic(content: str, indicators: list[dict[str, Any]], trade_actions: list[str], protections: list[str]) -> dict[str, Any]:
    lowered = content.lower()
    strategy_style = "rule_based"
    if any(item.get("type") == "EMA" for item in indicators):
        strategy_style = "trend_following"
    if any(item.get("type") == "RSI" for item in indicators):
        strategy_style = "hybrid_trend_momentum"
    if "breakout" in lowered or "highest" in lowered or "lowest" in lowered:
        strategy_style = "breakout"
    if "mean reversion" in lowered or "oversold" in lowered or "overbought" in lowered:
        strategy_style = "mean_reversion"

    entry_logic = []
    if any(item.get("type") == "EMA" for item in indicators):
        entry_logic.append("usa medie mobili per definire direzione o trigger")
    if any(item.get("type") == "RSI" for item in indicators):
        entry_logic.append("usa RSI come conferma o filtro")
    if "candlestick" in lowered or "bullish" in lowered or "bearish" in lowered:
        entry_logic.append("usa conferme price action")
    if not entry_logic and trade_actions:
        entry_logic.append("apre posizioni in base a regole interne non completamente inferite")

    exit_logic = []
    if "stop_loss" in protections:
        exit_logic.append("stop loss presente")
    if "take_profit" in protections:
        exit_logic.append("take profit presente")
    if "trailing_stop" in protections:
        exit_logic.append("gestione dinamica del profitto")
    if not exit_logic:
        exit_logic.append("uscita non chiaramente inferita dal parser locale")

    risk_model = []
    if "position_sizing" in protections:
        risk_model.append("dimensionamento posizione presente")
    if "daily_trade_limit" in protections:
        risk_model.append("limite giornaliero presente")
    if "spread_filter" in protections:
        risk_model.append("controllo spread presente")
    if not risk_model:
        risk_model.append("rischio operativo poco esplicito")

    return {
        "strategy_style": strategy_style,
        "entry_logic": entry_logic,
        "exit_logic": exit_logic,
        "risk_model": risk_model,
    }


def _build_health_check(
    *,
    functions: list[str],
    indicators: list[dict[str, Any]],
    trade_actions: list[str],
    protections: list[str],
    parameters: list[dict[str, Any]],
    language: str,
    fundamental_flags: dict[str, Any],
) -> dict[str, Any]:
    score = 48.0
    strengths = []
    warnings = []
    likely_issues = []

    if language == "mql5" and "OnTick" in functions:
        score += 8
        strengths.append("Struttura EA riconosciuta con OnTick().")
    else:
        warnings.append("La struttura del bot non espone chiaramente un loop operativo stile EA.")

    if trade_actions:
        score += 10
        strengths.append("Sono state rilevate azioni di trading concrete.")
    else:
        warnings.append("Nessuna chiamata di trading chiara: analisi e backtest saranno più fragili.")
        likely_issues.append("entry/exit non ricostruibili con certezza")

    if indicators:
        score += 8
        strengths.append("Il bot usa indicatori tecnici leggibili localmente.")
    else:
        warnings.append("Il bot non espone indicatori standard facilmente inferibili.")

    if "stop_loss" in protections:
        score += 8
    else:
        warnings.append("Stop loss non rilevato: rischio operativo elevato.")
        likely_issues.append("assenza di protezione loss evidente")

    if "position_sizing" in protections:
        score += 6
    else:
        likely_issues.append("position sizing non chiaro")

    if "spread_filter" not in protections:
        warnings.append("Filtro spread non rilevato.")
    if "session_filter" not in protections:
        warnings.append("Filtro sessione non rilevato.")
    if not parameters:
        warnings.append("Pochi input modificabili: tuning e explainability limitati.")
    if fundamental_flags.get("enabled") and not fundamental_flags.get("has_news_blackout"):
        warnings.append("Ci sono riferimenti macro/news ma non un blackout chiaro intorno agli eventi.")

    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "strengths": strengths,
        "warnings": warnings,
        "likely_issues": likely_issues,
    }


def _build_formal_spec_bundle(
    *,
    file_info: BotFileInfo,
    parameters: list[dict[str, Any]],
    indicators: list[dict[str, Any]],
    protections: list[str],
    sessions: list[str],
    inferred_logic: dict[str, Any],
    fundamental_flags: dict[str, Any],
    configured_macro_news: dict[str, Any],
) -> dict[str, Any]:
    if not parameters:
        parameters = [
            {"name": "RiskPercent", "type": "double", "default": "1.0"},
            {"name": "MaxDailyTrades", "type": "int", "default": "3"},
        ]

    ema_periods = [item.get("period_ref") for item in indicators if item.get("type") == "EMA"]
    rsi_periods = [item.get("period_ref") for item in indicators if item.get("type") == "RSI"]
    atr_periods = [item.get("period_ref") for item in indicators if item.get("type") == "ATR"]

    fast_ema = _parse_period(ema_periods[0]) if ema_periods else 20
    slow_ema = _parse_period(ema_periods[1]) if len(ema_periods) > 1 else 50
    rsi_period = _parse_period(rsi_periods[0]) if rsi_periods else None
    atr_period = _parse_period(atr_periods[0]) if atr_periods else 14

    entry_conditions = {
        "long": {"conditions": [{"mql5_expression": f"ema_fast({fast_ema}) > ema_slow({slow_ema})"}], "logic": "AND"},
        "short": {"conditions": [{"mql5_expression": f"ema_fast({fast_ema}) < ema_slow({slow_ema})"}], "logic": "AND"},
    }
    if rsi_period:
        entry_conditions["long"]["conditions"].append({"mql5_expression": f"rsi({rsi_period}) > 52"})
        entry_conditions["short"]["conditions"].append({"mql5_expression": f"rsi({rsi_period}) < 48"})

    risk_management = {
        "risk_per_trade_pct": _guess_numeric_param(parameters, ["risk", "riskpercent"], 1.0),
        "max_daily_trades": int(_guess_numeric_param(parameters, ["maxdailytrades", "daily_trades"], 3)),
        "sessions": sessions or ["Inferred session"],
        "protections": protections,
    }
    if "spread_filter" in protections:
        risk_management["spread_guard_enabled"] = True
    macro_news = normalize_macro_news_config(configured_macro_news)

    formal_spec = {
        "source": "uploaded_bot",
        "language": file_info.language,
        "platform": file_info.platform,
        "strategy_style": inferred_logic["strategy_style"],
        "indicators": indicators,
        "entry_conditions": entry_conditions,
        "stop_loss": {
            "type": "atr_multiple" if "ATR" in {item.get("type") for item in indicators} else "inferred_protective_stop",
            "atr_period": atr_period,
            "atr_multiplier": 1.5,
        },
        "take_profit": {"type": "rr_ratio", "rr_ratio": 2.0},
        "risk_management": risk_management,
        "macro_news": macro_news,
        "fundamental_filters": {
            "enabled": macro_news.get("enabled", False),
            "provider": macro_news.get("provider", "none"),
            "api_key": macro_news.get("api_key", ""),
            "currencies": macro_news.get("currencies", []),
            "impacts": macro_news.get("impacts", []),
            "blackout_before_min": macro_news.get("pre_event_block_minutes", 30),
            "blackout_after_min": macro_news.get("post_event_block_minutes", 30),
            "post_event_wait_min": macro_news.get("post_event_wait_minutes", 15),
            "bias_mode": macro_news.get("bias_mode", "exclude_only"),
            "directional_bias": macro_news.get("directional_bias", ""),
            "notes": macro_news.get("notes", ""),
            "manual_events": macro_news.get("manual_events", []),
            "has_news_blackout": fundamental_flags.get("has_news_blackout", False),
            "has_directional_bias": fundamental_flags.get("has_directional_bias", False),
            "has_post_event_rule": fundamental_flags.get("has_post_event_rule", False),
        },
    }
    state_machine = {
        "states": ["IDLE", "SETUP", "IN_POSITION"],
        "transitions": [
            {"from": "IDLE", "to": "SETUP", "condition": "technical_filters_pass"},
            {"from": "SETUP", "to": "IN_POSITION", "condition": "entry_signal_confirmed"},
            {"from": "IN_POSITION", "to": "IDLE", "condition": "stop_loss_or_take_profit_or_exit_rule"},
        ],
    }
    assumptions = [
        "Il formal spec del Bot Lab è inferito localmente dal codice e resta una proxy representation.",
        "Se il bot originale usa funzioni custom non standard, alcune regole vengono riassunte in modo conservativo.",
    ]

    backtest_ready = bool(indicators and parameters)
    status = STATUS_VALID if backtest_ready else STATUS_INVALID
    required_inputs = []
    if not backtest_ready:
        required_inputs.append(
            {
                "id": "req_bot_backtest",
                "field": "code",
                "label": "Il bot non è interpretabile abbastanza per un backtest proxy credibile",
                "why": "Mancano indicatori standard, parametri o uscite chiaramente inferibili.",
                "example": "Usa un EA MQL5 con input espliciti e logica tecnica riconoscibile.",
                "blocking": True,
            }
        )

    return {
        "status": status,
        "formal_spec": formal_spec,
        "state_machine": state_machine,
        "parameters": [
            {
                "id": f"bot_param_{idx+1:03d}",
                "name": item.get("name"),
                "description": f"Parametro inferito dal bot caricato: {item.get('name')}",
                "type": _map_param_type(item.get("type")),
                "default_value": item.get("default"),
                "optimize": True,
            }
            for idx, item in enumerate(parameters[:20])
        ],
        "non_optimizable": ["fundamental_filters", "compliance_guards"],
        "assumptions": assumptions,
        "ambiguities": [],
        "required_inputs": required_inputs,
        "validation_status": STATUS_VALID if status == STATUS_VALID else STATUS_INVALID,
    }


def _build_explanation(
    *,
    file_info: BotFileInfo,
    inferred_logic: dict[str, Any],
    indicators: list[dict[str, Any]],
    protections: list[str],
    fundamental_flags: dict[str, Any],
    parameters: list[dict[str, Any]],
) -> dict[str, Any]:
    technicals = ", ".join(sorted({item.get("type") for item in indicators if item.get("type")})) or "nessun indicatore standard chiaro"
    protections_text = ", ".join(protections) or "poche protezioni operative esplicite"
    fundamentals = []
    if fundamental_flags.get("enabled"):
        if fundamental_flags.get("has_news_blackout"):
            fundamentals.append("blackout news")
        if fundamental_flags.get("has_directional_bias"):
            fundamentals.append("bias direzionale macro")
        if fundamental_flags.get("has_post_event_rule"):
            fundamentals.append("trigger post-evento")
    fundamental_text = ", ".join(fundamentals) or "nessun filtro fondamentale esplicito"

    plain = (
        f"Il bot caricato è stato riconosciuto come {file_info.platform} con stile prevalente "
        f"{inferred_logic['strategy_style']}. Usa {technicals}. "
        f"Le protezioni operative rilevate sono: {protections_text}. "
        f"Sul fronte macro/fondamentale il parser vede: {fundamental_text}. "
        f"I parametri editabili rilevati sono {len(parameters)}."
    )
    return {
        "plain_language": plain,
        "key_rules": inferred_logic["entry_logic"] + inferred_logic["exit_logic"],
        "beginner_safe_report": [
            "Cosa fa: apre e chiude trade seguendo regole tecniche inferite localmente.",
            f"Cosa controlla: {technicals}.",
            f"Quanto è protetto: {protections_text}.",
            f"Parte macro/fondamentale: {fundamental_text}.",
        ],
        "improvement_opportunities": [
            "aggiungere blackout news",
            "aggiungere filtro spread o sessione se assenti",
            "rendere più espliciti stop loss e take profit",
            "aumentare la leggibilità con input ben nominati",
        ],
    }


def _guess_numeric_param(parameters: list[dict[str, Any]], name_markers: list[str], fallback: float) -> float:
    for item in parameters:
        name = str(item.get("name") or "").lower()
        if not any(marker in name for marker in name_markers):
            continue
        raw = str(item.get("default") or "").strip().strip('"').strip("'")
        try:
            return float(raw)
        except ValueError:
            continue
    return float(fallback)


def _parse_period(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    match = re.search(r"(\d+)", str(raw))
    if not match:
        return None
    return int(match.group(1))


def _map_param_type(raw_type: Any) -> str:
    normalized = str(raw_type or "").lower()
    if normalized in {"int", "long"}:
        return "int"
    if normalized in {"double", "float"}:
        return "double"
    if normalized in {"bool", "boolean"}:
        return "bool"
    return "string"
