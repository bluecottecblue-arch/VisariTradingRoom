"""
Guardrail locali e contratti di risposta per il workflow StrategyForge.

Obiettivi:
- bloccare presto strategie non codificabili senza spendere token
- uniformare i payload restituiti da parser, formalizer e bot generator
- validare che il codice MQL5 generato sia realmente scaricabile/usabile
"""
import re
from typing import Any, Dict, List, Optional


STATUS_VALID = "VALID"
STATUS_NEEDS_INPUT = "NEEDS_INPUT"
STATUS_INVALID = "INVALID"
STATUS_GENERATION_FAILED = "GENERATION_FAILED"

_TECHNICAL_DEFAULT_NOTES = (
    ("account_balance", "account_balance=10000 USD"),
    ("broker_spread", "broker_spread_max=1.5 pips"),
    ("ema_method", "EMA calculation method = exponential moving average on close price"),
)


def empty_usage(module: str) -> dict:
    return {
        "module": module,
        "model": None,
        "cache_hit": False,
        "billable": False,
        "system_chars": 0,
        "prompt_chars": 0,
        "estimated_input_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "max_tokens": 0,
        "estimated_cost_usd": 0.0,
    }


def enrich_intake_with_technical_defaults(intake: dict) -> dict:
    enriched = dict(intake or {})
    raw_notes = str(enriched.get("additional_notes") or "").strip()
    normalized_notes = _normalize(raw_notes)
    additions = []

    for key, note in _TECHNICAL_DEFAULT_NOTES:
        if key == "account_balance" and "account_balance" not in normalized_notes and "account balance" not in normalized_notes:
            additions.append(note)
        elif key == "broker_spread" and "broker_spread" not in normalized_notes and "broker spread" not in normalized_notes and "spread_max" not in normalized_notes:
            additions.append(note)
        elif key == "ema_method" and "ema calculation method" not in normalized_notes and "ema method" not in normalized_notes:
            additions.append(note)

    if additions:
        enriched["additional_notes"] = "; ".join([part for part in [raw_notes, *additions] if part])

    return enriched


def build_required_input(
    req_id: str,
    field: str,
    label: str,
    why: str,
    example: str,
    source_text: str = "",
    blocking: bool = True,
) -> dict:
    return {
        "id": req_id,
        "field": field,
        "label": label,
        "why": why,
        "example": example,
        "source_text": source_text,
        "blocking": blocking,
    }


def build_ambiguity(
    amb_id: str,
    original_text: str,
    why_ambiguous: str,
    severity: str,
    alternatives: Optional[List[dict]] = None,
    field: Optional[str] = None,
    blocking: bool = True,
) -> dict:
    return {
        "id": amb_id,
        "original_text": original_text,
        "why_ambiguous": why_ambiguous,
        "severity": severity,
        "alternatives": alternatives or [],
        "field": field,
        "blocking": blocking,
    }


def build_parse_result(
    status: str,
    message: str,
    structured_strategy: Optional[dict] = None,
    ambiguities: Optional[List[dict]] = None,
    required_inputs: Optional[List[dict]] = None,
    codeable_rules: Optional[List[dict]] = None,
    bias_warnings: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    completeness_score: float = 0.0,
    usage: Optional[dict] = None,
    validation: Optional[dict] = None,
) -> dict:
    ambiguities = ambiguities or []
    required_inputs = required_inputs or []
    codeable_rules = codeable_rules or []
    bias_warnings = bias_warnings or []
    assumptions = assumptions or []
    usage = usage or empty_usage("parse")
    validation = validation or {}
    validation.setdefault("stage", "parse")
    validation.setdefault("blocking_ambiguities", _count_blocking_ambiguities(ambiguities))
    validation.setdefault("blocking_required_inputs", _count_blocking_required_inputs(required_inputs))
    validation.setdefault(
        "blocking_issues",
        validation["blocking_ambiguities"] + validation["blocking_required_inputs"],
    )
    validation.setdefault("llm_reviewed", False)
    validation.setdefault("llm_skipped", not validation["llm_reviewed"])
    validation.setdefault("ready_for_formalization", status == STATUS_VALID)
    validation.setdefault("ready_for_generation", False)

    return {
        "status": status,
        "validation_status": STATUS_VALID if status == STATUS_VALID else STATUS_INVALID,
        "message": message,
        "structured_strategy": structured_strategy or {},
        "ambiguities": ambiguities,
        "required_inputs": required_inputs,
        "codeable_rules": codeable_rules,
        "bias_warnings": bias_warnings,
        "assumptions": assumptions,
        "completeness_score": round(float(completeness_score), 4),
        "can_proceed": status == STATUS_VALID,
        "can_generate_code": False,
        "validation": validation,
        "usage": usage,
    }


def build_formalization_result(
    status: str,
    message: str,
    formal_spec: Optional[dict] = None,
    state_machine: Optional[dict] = None,
    parameters: Optional[List[dict]] = None,
    non_optimizable: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
    ambiguities: Optional[List[dict]] = None,
    required_inputs: Optional[List[dict]] = None,
    usage: Optional[dict] = None,
    validation: Optional[dict] = None,
) -> dict:
    ambiguities = ambiguities or []
    required_inputs = required_inputs or []
    parameters = parameters or []
    non_optimizable = non_optimizable or []
    assumptions = assumptions or []
    usage = usage or empty_usage("formalize")
    validation = validation or {}
    validation.setdefault("stage", "formalize")
    validation.setdefault("blocking_ambiguities", _count_blocking_ambiguities(ambiguities))
    validation.setdefault("blocking_required_inputs", _count_blocking_required_inputs(required_inputs))
    validation.setdefault(
        "blocking_issues",
        validation["blocking_ambiguities"] + validation["blocking_required_inputs"],
    )
    validation.setdefault("ready_for_generation", status == STATUS_VALID)

    return {
        "status": status,
        "validation_status": STATUS_VALID if status == STATUS_VALID else STATUS_INVALID,
        "message": message,
        "formal_spec": formal_spec or {},
        "state_machine": state_machine or {},
        "parameters": parameters,
        "non_optimizable": non_optimizable,
        "assumptions": assumptions,
        "ambiguities": ambiguities,
        "required_inputs": required_inputs,
        "can_generate_code": status == STATUS_VALID,
        "validation": validation,
        "usage": usage,
    }


def build_bot_result(
    status: str,
    message: str,
    mql5_code: str = "",
    documentation: str = "",
    implementation_assumptions: Optional[List[str]] = None,
    limitations_vs_discretionary: Optional[List[str]] = None,
    required_inputs: Optional[List[dict]] = None,
    code_validation: Optional[dict] = None,
    usage: Optional[dict] = None,
    validation: Optional[dict] = None,
) -> dict:
    implementation_assumptions = implementation_assumptions or []
    limitations_vs_discretionary = limitations_vs_discretionary or []
    required_inputs = required_inputs or []
    code_validation = code_validation or validate_mql5_code(mql5_code)
    usage = usage or empty_usage("botgen")
    validation = validation or {}
    validation.setdefault("stage", "botgen")
    validation.setdefault("ready_for_download", status == STATUS_VALID and code_validation["is_valid"])

    return {
        "status": status,
        "validation_status": STATUS_VALID if status == STATUS_VALID else STATUS_INVALID,
        "message": message,
        "mql5_code": mql5_code,
        "documentation": documentation,
        "implementation_assumptions": implementation_assumptions,
        "limitations_vs_discretionary": limitations_vs_discretionary,
        "required_inputs": required_inputs,
        "code_validation": code_validation,
        "download_ready": status == STATUS_VALID and code_validation["is_valid"],
        "can_generate_code": status == STATUS_VALID,
        "validation": validation,
        "usage": usage,
    }


def validate_strategy_intake(intake: dict) -> dict:
    ambiguities: List[dict] = []
    required_inputs: List[dict] = []
    codeable_rules: List[dict] = []
    bias_warnings: List[str] = []
    assumptions: List[str] = []
    seen_keys = set()

    def add_required(field: str, label: str, why: str, example: str, source_text: str = "") -> None:
        key = ("required", field, label)
        if key in seen_keys:
            return
        seen_keys.add(key)
        required_inputs.append(
            build_required_input(
                req_id="req_%03d" % (len(required_inputs) + 1),
                field=field,
                label=label,
                why=why,
                example=example,
                source_text=source_text,
            )
        )

    def add_ambiguity(field: str, source_text: str, why: str, severity: str, alternatives: List[dict]) -> None:
        source_text = (source_text or "").strip()
        if not source_text:
            return
        key = ("ambiguity", field, source_text.lower())
        if key in seen_keys:
            return
        seen_keys.add(key)
        ambiguities.append(
            build_ambiguity(
                amb_id="amb_%03d" % (len(ambiguities) + 1),
                original_text=source_text,
                why_ambiguous=why,
                severity=severity,
                alternatives=alternatives,
                field=field,
                blocking=True,
            )
        )

    required_text_fields = [
        ("name", "Definisci il nome della strategia", "Es. EMA Pullback Quant"),
        ("market", "Definisci il mercato", "Es. EURUSD"),
        ("long_entry", "Definisci il trigger long in modo binario", "Es. close[0] > EMA50 e body >= 6 pips"),
        ("invalidation", "Definisci quando il setup è invalidato", "Es. 1 chiusura M15 oltre EMA200 opposta"),
        ("stop_loss", "Definisci lo stop loss in modo matematico", "Es. low candela ingresso - 2 pips"),
        ("take_profit", "Definisci il take profit", "Es. TP fisso 2R"),
    ]

    for field, label, example in required_text_fields:
        if not str(intake.get(field, "")).strip():
            add_required(
                field=field,
                label=label,
                why="Senza questo dato il bot non puó essere generato in modo deterministico.",
                example=example,
            )

    if not intake.get("trading_days"):
        add_required(
            field="trading_days",
            label="Definisci i giorni operativi",
            why="Serve per evitare assunzioni implicite sulla sessione di trading.",
            example="MON,TUE,WED,THU,FRI",
        )

    if float(intake.get("risk_per_trade_pct", 0) or 0) <= 0:
        add_required(
            field="risk_per_trade_pct",
            label="Definisci un rischio per trade > 0",
            why="La size position richiede un rischio percentuale positivo.",
            example="1.0",
        )

    combined_text = " ".join(
        str(intake.get(field, "") or "")
        for field in (
            "long_entry",
            "short_entry",
            "invalidation",
            "stop_loss",
            "take_profit",
            "trailing_stop",
            "trend_filter",
            "volatility_filter",
            "context_filter",
            "news_management",
            "additional_notes",
        )
    )

    if not _mentions_max_open_positions(combined_text):
        add_required(
            field="additional_notes",
            label="Definisci il numero massimo di posizioni aperte",
            why="Il generatore non deve assumere quante posizioni possano restare aperte insieme.",
            example="max 1 trade aperto alla volta",
        )

    text_fields = [
        "long_entry",
        "short_entry",
        "invalidation",
        "stop_loss",
        "take_profit",
        "trailing_stop",
        "trend_filter",
        "volatility_filter",
        "context_filter",
        "news_management",
        "additional_notes",
    ]

    for field in text_fields:
        text = str(intake.get(field, "") or "").strip()
        if not text:
            continue

        if _is_pullback_ambiguous(text):
            add_ambiguity(
                field,
                _extract_phrase(text, r"(torna[^.]*?ema[^.,;]*|vicin[^.]*?ema[^.,;]*|pullback[^.]*?ema[^.,;]*)"),
                "Non è definita una distanza massima o una regola binaria per il ritorno verso la media/livello.",
                "HIGH",
                _pullback_alternatives(),
            )

        if _is_break_ambiguous(text):
            add_ambiguity(
                field,
                _extract_phrase(text, r"(romp\w+[^.,;]*|rottur\w+[^.,;]*|breakout[^.,;]*)"),
                "Una rottura va definita in modo binario: close oltre livello, wick oltre livello o numero di chiusure consecutive.",
                "HIGH",
                _break_alternatives(),
            )

        if _is_confirmation_ambiguous(text):
            add_ambiguity(
                field,
                _extract_phrase(text, r"(conferm\w+[^.,;]*)"),
                "La parola 'conferma' non definisce da sola un trigger misurabile.",
                "HIGH",
                _confirmation_alternatives(),
            )

        if _is_candle_direction_ambiguous(text):
            add_ambiguity(
                field,
                _extract_phrase(text, r"(candela\s+(bullish|bearish)[^.,;]*)"),
                "Una candela bullish/bearish va definita esplicitamente con open/close, dimensione del corpo o pattern preciso.",
                "MEDIUM",
                _candle_direction_alternatives(),
            )

        if _is_rejection_ambiguous(text):
            add_ambiguity(
                field,
                _extract_phrase(text, r"((rejection|pin ?bar|hammer|engulfing)[^.,;]*)"),
                "Il pattern price action non è definito con rapporti tra corpo e wick o regole di chiusura.",
                "HIGH",
                _rejection_alternatives(),
            )

        if _is_subjective_context(text):
            add_required(
                field=field,
                label="Sostituisci il concetto soggettivo con una regola misurabile",
                why="Espressioni come 'contesto', 'gestione discrezionale' o 'quando ha senso' non sono codificabili.",
                example="Es. operare solo se ADX(14) > 25 e ATR(14) >= 0.0008",
                source_text=text,
            )

    codeable_rules.extend(_build_local_codeable_rules(intake))

    blocking_issues = len(required_inputs) + len(ambiguities)
    if blocking_issues == 0:
        status = STATUS_VALID
        message = "Strategia abbastanza specifica per la revisione AI."
        completeness_score = 1.0
    else:
        status = STATUS_NEEDS_INPUT if ambiguities and not required_inputs else STATUS_INVALID
        message = (
            "Servono dettagli aggiuntivi prima di spendere token su formalizzazione o generazione codice."
        )
        completeness_score = max(0.0, 1.0 - min(0.85, blocking_issues * 0.18))
        bias_warnings.append(
            "Le parti ancora soggettive verrebbero trasformate in assunzioni arbitrarie: il flusso viene bloccato apposta."
        )

    return build_parse_result(
        status=status,
        message=message,
        structured_strategy=_build_local_strategy_skeleton(intake),
        ambiguities=ambiguities,
        required_inputs=required_inputs,
        codeable_rules=codeable_rules,
        bias_warnings=bias_warnings,
        assumptions=assumptions,
        completeness_score=completeness_score,
        validation={
            "stage": "parse",
            "llm_reviewed": False,
            "llm_skipped": True,
        },
    )


def validate_resolutions_for_formalization(parsed: dict, resolutions: dict) -> dict:
    required_inputs = list(parsed.get("required_inputs", []))
    ambiguities = list(parsed.get("ambiguities", []))
    unresolved = []
    selected = []

    for ambiguity in ambiguities:
        alternatives = ambiguity.get("alternatives", [])
        if not alternatives:
            continue

        selected_id = resolutions.get(ambiguity["id"])
        if not selected_id:
            if ambiguity.get("blocking", True):
                unresolved.append(ambiguity)
            continue

        selected_alt = next((alt for alt in alternatives if alt.get("id") == selected_id), None)
        if selected_alt is None:
            unresolved.append(ambiguity)
            continue

        selected.append(
            {
                "ambiguity_id": ambiguity.get("id"),
                "original_text": ambiguity.get("original_text"),
                "selected_id": selected_alt.get("id"),
                "description": selected_alt.get("description"),
                "implementation": selected_alt.get("implementation"),
                "tradeoffs": selected_alt.get("tradeoffs"),
            }
        )

    is_ready = not required_inputs and not unresolved
    if parsed.get("status") == STATUS_VALID:
        is_ready = True

    return {
        "is_ready": is_ready,
        "message": (
            "Specifica pronta per la formalizzazione."
            if is_ready
            else "Mancano ancora dettagli obbligatori prima della formalizzazione."
        ),
        "required_inputs": required_inputs,
        "unresolved_ambiguities": unresolved,
        "selected_resolutions": selected,
    }


def validate_formal_spec_payload(payload: dict) -> dict:
    errors = []
    formal_spec = payload.get("formal_spec") or {}
    state_machine = payload.get("state_machine") or {}
    parameters = payload.get("parameters") or []

    if not formal_spec.get("entry_conditions"):
        errors.append("entry_conditions mancanti")
    else:
        has_long = bool((formal_spec.get("entry_conditions", {}).get("long") or {}).get("conditions"))
        has_short = bool((formal_spec.get("entry_conditions", {}).get("short") or {}).get("conditions"))
        if not has_long and not has_short:
            errors.append("nessuna condizione di ingresso formale")

    if not formal_spec.get("risk_management"):
        errors.append("risk_management mancante")

    if not state_machine.get("states") or not state_machine.get("transitions"):
        errors.append("state_machine incompleta")

    if not parameters:
        errors.append("parameters vuoti")

    return {
        "is_valid": not errors,
        "errors": errors,
    }


def validate_mql5_code(code: str) -> dict:
    normalized = (code or "").strip()
    errors = []
    checks = {
        "non_empty": bool(normalized),
        "length_gt_400": len(normalized) >= 400,
        "has_property": "#property" in normalized,
        "has_on_init": "OnInit(" in normalized,
        "has_on_tick": "OnTick(" in normalized,
        "has_trade_action": any(
            marker in normalized
            for marker in (
                "trade.Buy(",
                "trade.Sell(",
                "OrderSend(",
                "MqlTradeRequest",
                "PositionOpen(",
            )
        ),
        "has_risk_or_exit_logic": any(
            marker in normalized.lower()
            for marker in (
                "stoploss",
                "takeprofit",
                "stop_loss",
                "take_profit",
                "sl =",
                "tp =",
            )
        ),
        "no_placeholders": not any(
            marker in normalized.lower()
            for marker in (
                "todo",
                "placeholder",
                "codice non",
                "non disponibile",
                "da implementare",
                "revisiona manualmente",
            )
        ),
    }

    for key, ok in checks.items():
        if ok:
            continue
        if key == "non_empty":
            errors.append("codice vuoto")
        elif key == "length_gt_400":
            errors.append("codice troppo corto per essere un EA utile")
        elif key == "has_property":
            errors.append("manca il blocco #property")
        elif key == "has_on_init":
            errors.append("manca OnInit()")
        elif key == "has_on_tick":
            errors.append("manca OnTick()")
        elif key == "has_trade_action":
            errors.append("nessuna chiamata di trading rilevata")
        elif key == "has_risk_or_exit_logic":
            errors.append("stop loss / take profit non rilevati")
        elif key == "no_placeholders":
            errors.append("presenti placeholder o TODO")

    return {
        "is_valid": not errors,
        "errors": errors,
        "checks": checks,
        "length": len(normalized),
    }


def extract_llm_parse_issues(payload: dict) -> dict:
    ambiguities = list(payload.get("ambiguities") or [])
    required_inputs = list(payload.get("required_inputs") or [])
    if not ambiguities and not required_inputs:
        return {
            "status": STATUS_VALID,
            "message": "Strategia validata e pronta per il prossimo step.",
        }
    return {
        "status": STATUS_NEEDS_INPUT if ambiguities else STATUS_INVALID,
        "message": "Il parser AI ha rilevato ancora punti da chiarire prima della formalizzazione.",
    }


def count_blocking_issues(payload: dict) -> int:
    return _count_blocking_required_inputs(payload.get("required_inputs", [])) + _count_blocking_ambiguities(
        payload.get("ambiguities", [])
    )


def _count_blocking_required_inputs(items: List[dict]) -> int:
    return sum(1 for item in items if item.get("blocking", True))


def _count_blocking_ambiguities(items: List[dict]) -> int:
    return sum(1 for item in items if item.get("blocking", True))


def _build_local_strategy_skeleton(intake: dict) -> dict:
    days = intake.get("trading_days") or []
    start = intake.get("trading_hours_start")
    end = intake.get("trading_hours_end")
    return {
        "metadata": {
            "strategy_name": intake.get("name", ""),
            "market": intake.get("market", ""),
        },
        "instruments": [intake.get("market")] if intake.get("market") else [],
        "timeframes": {
            "analysis": intake.get("analysis_timeframe"),
            "execution": intake.get("execution_timeframe"),
        },
        "sessions": [f"{start}-{end} UTC"] if start and end else [],
        "raw_rules": {
            "long_entry": intake.get("long_entry"),
            "short_entry": intake.get("short_entry"),
            "invalidation": intake.get("invalidation"),
            "stop_loss": intake.get("stop_loss"),
            "take_profit": intake.get("take_profit"),
            "trailing_stop": intake.get("trailing_stop"),
        },
        "risk_management": {
            "risk_per_trade_pct": intake.get("risk_per_trade_pct"),
            "max_daily_trades": intake.get("max_daily_trades"),
            "trading_days": days,
        },
    }


def _build_local_codeable_rules(intake: dict) -> List[dict]:
    rules = []
    if intake.get("risk_per_trade_pct"):
        rules.append(
            {
                "id": "rule_local_001",
                "description": "Rischio per trade esplicito",
                "condition": "position_size basata su risk_per_trade_pct",
                "parameters": {"risk_per_trade_pct": intake.get("risk_per_trade_pct")},
            }
        )
    if intake.get("max_daily_trades"):
        rules.append(
            {
                "id": "rule_local_002",
                "description": "Numero massimo di trade giornalieri",
                "condition": "daily_trades < max_daily_trades",
                "parameters": {"max_daily_trades": intake.get("max_daily_trades")},
            }
        )
    if intake.get("trading_hours_start") and intake.get("trading_hours_end"):
        rules.append(
            {
                "id": "rule_local_003",
                "description": "Finestra temporale di operatività",
                "condition": "session_start <= now <= session_end",
                "parameters": {
                    "start": intake.get("trading_hours_start"),
                    "end": intake.get("trading_hours_end"),
                    "days": intake.get("trading_days", []),
                },
            }
        )
    return rules


def _mentions_max_open_positions(text: str) -> bool:
    text = _normalize(text)
    return bool(
        re.search(
            r"\b(max|massimo|al massimo|solo)\s+\d+\s+(trade|trades|posizion\w+|operazion\w+)\s+(apert\w+|contemporane\w+)\b",
            text,
        )
        or re.search(r"\b\d+\s+trade\s+apert\w+\b", text)
        or re.search(r"\buna\s+sola\s+posizion\w+\b", text)
    )


def _is_pullback_ambiguous(text: str) -> bool:
    normalized = _normalize(text)
    if not re.search(r"\b(vicin\w+|verso|ritorn\w+|pullback)\b", normalized):
        return False
    if not re.search(r"\b(ema|media|ma\d*|supporto|resistenza|livello)\b", normalized):
        return False
    return not _has_numeric_or_binary_trigger(normalized)


def _is_break_ambiguous(text: str) -> bool:
    normalized = _normalize(text)
    if not re.search(r"\b(romp\w+|rottur\w+|breakout|break)\b", normalized):
        return False
    return not (
        _has_numeric_or_binary_trigger(normalized)
        or re.search(r"\b(chius\w+|close|wick|ombra|2\s+candel\w+|2\s+bar|consecutiv\w+)\b", normalized)
    )


def _is_confirmation_ambiguous(text: str) -> bool:
    normalized = _normalize(text)
    return bool(re.search(r"\bconferm\w+\b", normalized) and not _has_numeric_or_binary_trigger(normalized))


def _is_candle_direction_ambiguous(text: str) -> bool:
    normalized = _normalize(text)
    if not re.search(r"\bcandela\s+(bullish|bearish)\b", normalized):
        return False
    return not re.search(r"\b(open|close|corpo|body|wick|ombra)\b", normalized)


def _is_rejection_ambiguous(text: str) -> bool:
    normalized = _normalize(text)
    if not re.search(r"\b(rejection|pin ?bar|hammer|engulfing|shooting star)\b", normalized):
        return False
    return not re.search(r"\b(wick|ombra|body|corpo|rapporto|close|open|>=|<=)\b", normalized)


def _is_subjective_context(text: str) -> bool:
    normalized = _normalize(text)
    return bool(
        re.search(
            r"\b(discrezional\w*|manual\w*|a occhio|quando ha senso|contesto|setup pulito|sentiment|gestione discrezionale)\b",
            normalized,
        )
    )


def _has_numeric_or_binary_trigger(text: str) -> bool:
    return bool(
        re.search(r"\d+(\.\d+)?\s*(pip|pips|point|points|%|percent|atr|bar|bars|tick|ticks)\b", text)
        or re.search(r"(>=|<=|>|<|==)", text)
        or re.search(r"\b(close|open|high|low|touch|tocc\w+|cross|incroci\w+|chius\w+)\b", text)
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _extract_phrase(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def _pullback_alternatives() -> List[dict]:
    return [
        {
            "id": "alt_pullback_touch",
            "description": "La candela deve toccare la EMA",
            "implementation": "low[0] <= ema50 and close[0] >= ema50 per long; high[0] >= ema50 and close[0] <= ema50 per short",
            "tradeoffs": "Più restrittivo ma completamente binario.",
        },
        {
            "id": "alt_pullback_pips",
            "description": "Distanza massima in pips dalla EMA",
            "implementation": "abs(close[0] - ema50) <= 10 pips",
            "tradeoffs": "Richiede una soglia fissa non adattiva.",
        },
        {
            "id": "alt_pullback_pct",
            "description": "Distanza massima percentuale dalla EMA",
            "implementation": "abs(close[0] - ema50) / ema50 <= 0.001",
            "tradeoffs": "Più adattivo ma meno intuitivo per chi ragiona in pips.",
        },
    ]


def _break_alternatives() -> List[dict]:
    return [
        {
            "id": "alt_break_close",
            "description": "Rottura valida solo a chiusura oltre il livello",
            "implementation": "close[0] > level + buffer per long o close[0] < level - buffer per short",
            "tradeoffs": "Riduce falsi breakout ma entra più tardi.",
        },
        {
            "id": "alt_break_two_closes",
            "description": "Due chiusure consecutive oltre il livello",
            "implementation": "close[0] > level and close[1] > level",
            "tradeoffs": "Molto robusto ma più lento.",
        },
        {
            "id": "alt_break_wick",
            "description": "Rottura valida al superamento intrabar con wick + buffer",
            "implementation": "high[0] >= level + 2 pips o low[0] <= level - 2 pips",
            "tradeoffs": "Più aggressivo e sensibile al rumore.",
        },
    ]


def _confirmation_alternatives() -> List[dict]:
    return [
        {
            "id": "alt_confirmation_close",
            "description": "Conferma = chiusura oltre il trigger",
            "implementation": "close[0] oltre il massimo/minimo della candela setup",
            "tradeoffs": "Semplice e binario.",
        },
        {
            "id": "alt_confirmation_cross",
            "description": "Conferma = cross indicatore specifico",
            "implementation": "ema_fast crosses above ema_slow per long / sotto per short",
            "tradeoffs": "Più meccanico ma cambia la logica originale.",
        },
        {
            "id": "alt_confirmation_body",
            "description": "Conferma = candela con corpo minimo",
            "implementation": "abs(close[0]-open[0]) >= 6 pips nella direzione del trade",
            "tradeoffs": "Filtra rumore ma introduce un parametro in più.",
        },
    ]


def _candle_direction_alternatives() -> List[dict]:
    return [
        {
            "id": "alt_candle_close_open",
            "description": "Candela direzionale base",
            "implementation": "close[0] > open[0] per bullish; close[0] < open[0] per bearish",
            "tradeoffs": "Molto semplice ma non filtra candele deboli.",
        },
        {
            "id": "alt_candle_body_min",
            "description": "Candela con corpo minimo",
            "implementation": "close[0] > open[0] e abs(close[0]-open[0]) >= 6 pips",
            "tradeoffs": "Più robusta ma dipende da una soglia fissa.",
        },
        {
            "id": "alt_candle_engulfing",
            "description": "Pattern engulfing",
            "implementation": "bullish engulfing / bearish engulfing sulle ultime 2 candele",
            "tradeoffs": "Molto selettivo, riduce il numero di trade.",
        },
    ]


def _rejection_alternatives() -> List[dict]:
    return [
        {
            "id": "alt_rejection_wick",
            "description": "Wick almeno 2x del corpo",
            "implementation": "lower_wick >= 2 * body e close nella metà alta della candela",
            "tradeoffs": "Buon compromesso tra chiarezza e fedeltà.",
        },
        {
            "id": "alt_rejection_pinbar",
            "description": "Pin bar classica",
            "implementation": "wick dominante >= 66% range totale e body <= 34% range",
            "tradeoffs": "Molto precisa ma più rigida.",
        },
        {
            "id": "alt_rejection_engulfing",
            "description": "Sostituisci con engulfing",
            "implementation": "candela corrente engulfing della precedente nella direzione del trade",
            "tradeoffs": "Più facile da codificare ma meno fedele alla rejection pura.",
        },
    ]
