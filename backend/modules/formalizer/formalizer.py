"""
StrategyFormalizer — Trasforma la strategia risolta in specifica algoritmica formale

Questo modulo prende:
- La struttura dati dal parser
- Le scelte dell'utente per ogni ambiguità
E produce una specifica algoritmica completa con macchina a stati.
"""
import re

from modules.common.anthropic_client import get_anthropic_model
from modules.common.llm_client import invoke_json
from modules.common.strategy_validation import (
    STATUS_INVALID,
    STATUS_VALID,
    build_formalization_result,
    empty_usage,
    normalize_claude_access,
    validate_formal_spec_payload,
    validate_resolutions_for_formalization,
)
from modules.fundamentals.economic_calendar import normalize_macro_news_config


FORMALIZATION_SYSTEM = """Sei un quant developer.
Return ONLY raw JSON. No markdown fences, no explanation, no preamble.
Start your response with { and end with }.
Restituisci SOLO JSON con chiavi:
formal_spec, state_machine, parameters, non_optimizable, assumptions.
Regole:
- nessuna regola soggettiva
- condizioni in forma binaria e implementabile
- testi brevi
- nessun markdown"""


class StrategyFormalizer:
    def __init__(self):
        self.model = get_anthropic_model("formalize")
        # In produzione: recupera da DB usando session_id
        self._sessions: dict = {}

    def store_parsed(self, session_id: str, parsed: dict, intake: dict):
        """Salva i risultati del parsing per questa sessione"""
        self._sessions[session_id] = {"parsed": parsed, "intake": intake}

    async def formalize(self, session_id: str, resolutions: dict, missing_inputs: dict = None) -> dict:
        """
        Produce la specifica algoritmica formale basandosi su:
        - parsed strategy (dal DB/memoria)
        - resolutions: scelte dell'utente per ogni ambiguità
        - missing_inputs: testi manuali forniti per input mancanti
        """
        # In produzione: recupera parsed dal DB
        session_payload = self._sessions.get(session_id)
        if not session_payload:
            return build_formalization_result(
                status=STATUS_INVALID,
                message="Sessione non trovata. Riesegui il parse della strategia.",
            )
        claude_access = normalize_claude_access(session_payload.get("intake", {}).get("claude_access"))

        parsed = session_payload.get("parsed", {})
        readiness = validate_resolutions_for_formalization(parsed, resolutions, missing_inputs)
        if not readiness["is_ready"]:
            return build_formalization_result(
                status=STATUS_INVALID,
                message=readiness["message"],
                ambiguities=readiness["unresolved_ambiguities"],
                required_inputs=readiness["required_inputs"],
                validation={"ready_for_generation": False},
            )

        local_candidate = self._build_local_formalization(
            session_payload,
            readiness["selected_resolutions"],
        )
        data = self._validate_formalization_structure(local_candidate, session_payload)
        payload_validation = validate_formal_spec_payload(data)
        if payload_validation["is_valid"]:
            return build_formalization_result(
                status=STATUS_VALID,
                message="Specifica formale pronta per il backtest e per la generazione del bot.",
                formal_spec=data.get("formal_spec") or {},
                state_machine=data.get("state_machine") or {},
                parameters=data.get("parameters") or [],
                non_optimizable=data.get("non_optimizable") or [],
                assumptions=data.get("assumptions") or [],
                usage=empty_usage("formalize"),
                validation={
                    "ready_for_generation": True,
                    "llm_reviewed": False,
                    "llm_skipped": True,
                    "formalized_locally": True,
                },
            )

        llm_result = await invoke_json(
            module="formalize",
            system_prompt=FORMALIZATION_SYSTEM,
            payload=self._build_payload(session_payload, readiness["selected_resolutions"], missing_inputs),
            model=self.model,
            ai_credentials=claude_access,
        )
        data = self._validate_formalization_structure(llm_result["data"], session_payload)
        payload_validation = validate_formal_spec_payload(data)
        if not payload_validation["is_valid"]:
            return build_formalization_result(
                status=STATUS_INVALID,
                message="Specifica formale incompleta: %s" % ", ".join(payload_validation["errors"]),
                formal_spec=data.get("formal_spec") or {},
                state_machine=data.get("state_machine") or {},
                parameters=data.get("parameters") or [],
                non_optimizable=data.get("non_optimizable") or [],
                assumptions=data.get("assumptions") or [],
                usage=llm_result["usage"],
                validation={"ready_for_generation": False, "errors": payload_validation["errors"]},
            )

        return build_formalization_result(
            status=STATUS_VALID,
            message="Specifica formale pronta per il backtest e per la generazione del bot.",
            formal_spec=data.get("formal_spec") or {},
            state_machine=data.get("state_machine") or {},
            parameters=data.get("parameters") or [],
            non_optimizable=data.get("non_optimizable") or [],
            assumptions=data.get("assumptions") or [],
            usage=llm_result["usage"],
            validation={"ready_for_generation": True},
        )

    def _build_local_formalization(self, session_payload: dict, selected_resolutions: list) -> dict:
        parsed = session_payload.get("parsed", {}) or {}
        intake = session_payload.get("intake", {}) or {}
        structured = parsed.get("structured_strategy") or {}
        indicators = structured.get("indicators") or {}
        entry_conditions = structured.get("entry_conditions") or structured.get("entries") or {}
        risk_management = structured.get("risk_management") or {}

        return {
            "formal_spec": {
                "symbol": intake.get("market") or structured.get("market"),
                "market": intake.get("market") or structured.get("market"),
                "strategy_style": self._infer_strategy_style(structured, intake),
                "timeframes": structured.get("timeframes") or {
                    "trend": intake.get("analysis_timeframe"),
                    "entry": intake.get("execution_timeframe"),
                },
                "session_filter": structured.get("session") or {
                    "days": intake.get("trading_days", []),
                    "start_time": intake.get("trading_hours_start"),
                    "end_time": intake.get("trading_hours_end"),
                },
                "indicators": self._normalize_indicator_specs(indicators),
                "entry_conditions": self._normalize_entry_conditions(entry_conditions),
                "invalidation": structured.get("invalidation") or {
                    "long": intake.get("invalidation"),
                    "short": intake.get("invalidation"),
                },
                "stop_loss": self._normalize_stop_loss(structured, intake),
                "take_profit": self._normalize_take_profit(structured, intake),
                "risk_management": {
                    "risk_per_trade_pct": self._parse_percentage(
                        risk_management.get("risk_per_trade"),
                        intake.get("risk_per_trade_pct", 1.0),
                    ),
                    "max_daily_trades": int(
                        risk_management.get("max_daily_trades")
                        or intake.get("max_daily_trades")
                        or 1
                    ),
                    "max_positions": int(
                        risk_management.get("max_concurrent_trades") or 1
                    ),
                },
            },
            "state_machine": {},
            "parameters": [],
            "non_optimizable": [],
            "assumptions": [
                "Formalizzazione locale derivata dalla struttura già estratta dal parser.",
                *[
                    "Risoluzione applicata: %s" % resolution
                    for resolution in selected_resolutions
                    if resolution
                ],
            ],
        }

    def _infer_strategy_style(self, structured: dict, intake: dict) -> str:
        text = " ".join(
            str(part or "")
            for part in (
                intake.get("long_entry"),
                intake.get("short_entry"),
                structured.get("market"),
            )
        ).lower()
        if "breakout" in text:
            return "breakout"
        if "mean reversion" in text or "reversion" in text:
            return "mean_reversion"
        return "trend_following"

    def _normalize_indicator_specs(self, indicators) -> list:
        specs = []
        if not isinstance(indicators, dict):
            return specs
        for indicator_id, config in indicators.items():
            raw_id = str(indicator_id or "indicator")
            indicator_type = raw_id.split("_", 1)[0].upper() or "CUSTOM"
            params = {}
            timeframe = None
            if isinstance(config, dict):
                if config.get("period") is not None:
                    params["period"] = config.get("period")
                if config.get("source"):
                    params["source"] = config.get("source")
                timeframe = config.get("timeframe")
            elif isinstance(config, str):
                match = re.search(r"(\d+)", config)
                if match:
                    params["period"] = int(match.group(1))
                if "close" in config.lower():
                    params["source"] = "close"
            specs.append(
                {
                    "id": raw_id,
                    "type": indicator_type,
                    "params": params,
                    "timeframe": timeframe,
                }
            )
        return specs

    def _normalize_entry_conditions(self, entry_conditions) -> dict:
        normalized = {}
        if isinstance(entry_conditions, list):
            entry_conditions = {
                "long": [str(item) for item in entry_conditions if str(item).strip()],
                "short": [],
            }
        if not isinstance(entry_conditions, dict):
            entry_conditions = {}
        for direction in ("long", "short"):
            raw_conditions = entry_conditions.get(direction) or []
            if isinstance(raw_conditions, dict):
                conditions = raw_conditions.get("signal_conditions") or raw_conditions.get("conditions") or []
                trend_condition = raw_conditions.get("trend_condition")
                entry_timing = raw_conditions.get("entry_timing")
                if trend_condition:
                    conditions = [trend_condition] + list(conditions)
                if entry_timing:
                    conditions = list(conditions) + ["entry_timing: %s" % entry_timing]
            elif isinstance(raw_conditions, str):
                conditions = [raw_conditions]
            else:
                conditions = raw_conditions
            normalized[direction] = {
                "logic": "AND",
                "conditions": [
                    {
                        "id": "%s_%s" % (direction, idx),
                        "description": str(condition),
                        "mql5_expression": str(condition),
                    }
                    for idx, condition in enumerate(conditions, start=1)
                    if str(condition).strip()
                ],
            }
        return normalized

    def _normalize_stop_loss(self, structured: dict, intake: dict) -> dict:
        rule = (structured.get("exit_conditions") or {}).get("stop_loss") or intake.get("stop_loss")
        return {
            "type": "rule_text",
            "rule": rule,
        }

    def _normalize_take_profit(self, structured: dict, intake: dict) -> dict:
        rule = (structured.get("exit_conditions") or {}).get("take_profit") or intake.get("take_profit")
        rr_ratio = self._extract_first_number(rule, 2.0)
        return {
            "type": "rr_ratio",
            "rr_ratio": rr_ratio,
            "rule": rule,
        }

    def _parse_percentage(self, raw_value, default: float) -> float:
        if raw_value is None:
            return float(default)
        text = str(raw_value).strip().replace("%", "")
        try:
            return float(text)
        except Exception:
            return float(default)

    def _extract_first_number(self, raw_value, default: float) -> float:
        text = str(raw_value or "")
        for token in text.replace(",", ".").split():
            try:
                return float(token.replace("R", "").replace("r", ""))
            except Exception:
                continue
        return float(default)

    def _validate_formalization_structure(self, data: dict, session_payload: dict) -> dict:
        data = data if isinstance(data, dict) else {}
        intake = session_payload.get("intake", {})
        formal_spec = data.get("formal_spec") if isinstance(data.get("formal_spec"), dict) else {}
        state_machine = data.get("state_machine") if isinstance(data.get("state_machine"), dict) else {}
        parameters = data.get("parameters") if isinstance(data.get("parameters"), list) else []
        macro_news = normalize_macro_news_config(intake.get("macro_news") or intake.get("fundamental_filters"))

        formal_spec["entry_conditions"] = self._normalize_entry_conditions(formal_spec.get("entry_conditions"))
        normalized_entry_conditions = formal_spec.get("entry_conditions") or {}
        has_long_conditions = bool(
            ((normalized_entry_conditions.get("long") or {}).get("conditions") or [])
        )
        has_short_conditions = bool(
            ((normalized_entry_conditions.get("short") or {}).get("conditions") or [])
        )

        if not has_long_conditions and not has_short_conditions:
            long_expr = formal_spec.get("entry_long")
            short_expr = formal_spec.get("entry_short")
            formal_spec["entry_conditions"] = {
                "long": {
                    "logic": "AND",
                    "conditions": [{"id": "long_1", "description": "Entry long", "mql5_expression": long_expr}] if long_expr else [],
                },
                "short": {
                    "logic": "AND",
                    "conditions": [{"id": "short_1", "description": "Entry short", "mql5_expression": short_expr}] if short_expr else [],
                },
            }

        if not formal_spec.get("risk_management"):
            formal_spec["risk_management"] = {
                "risk_per_trade_pct": intake.get("risk_per_trade_pct"),
                "max_daily_trades": intake.get("max_daily_trades"),
                "position_size": formal_spec.get("position_size"),
                "daily_limit": formal_spec.get("daily_limit"),
                "max_positions": formal_spec.get("max_positions"),
            }

        formal_spec["macro_news"] = macro_news
        formal_spec["fundamental_filters"] = {
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
        }

        transitions = state_machine.get("transitions")
        if isinstance(transitions, dict):
            flat_transitions = []
            for from_state, mapping in transitions.items():
                if not isinstance(mapping, dict):
                    continue
                for to_state, condition in mapping.items():
                    flat_transitions.append(
                        {
                            "from": from_state,
                            "to": to_state.replace("to_", ""),
                            "condition": condition,
                        }
                    )
            state_machine["transitions"] = flat_transitions

        if not state_machine.get("states"):
            state_machine["states"] = [
                "FLAT",
                "SETUP_PENDING",
                "IN_POSITION_LONG",
                "IN_POSITION_SHORT",
            ]

        if not state_machine.get("transitions"):
            state_machine["transitions"] = [
                {
                    "from": "FLAT",
                    "to": "SETUP_PENDING",
                    "condition": "entry context valido e filtri di sessione/rischio soddisfatti",
                },
                {
                    "from": "SETUP_PENDING",
                    "to": "IN_POSITION_LONG",
                    "condition": "condizioni long vere e ordine eseguito",
                },
                {
                    "from": "SETUP_PENDING",
                    "to": "IN_POSITION_SHORT",
                    "condition": "condizioni short vere e ordine eseguito",
                },
                {
                    "from": "IN_POSITION_LONG",
                    "to": "FLAT",
                    "condition": "take profit, stop loss o invalidazione",
                },
                {
                    "from": "IN_POSITION_SHORT",
                    "to": "FLAT",
                    "condition": "take profit, stop loss o invalidazione",
                },
            ]

        if not parameters:
            parameters = [
                {
                    "id": "risk_per_trade_pct",
                    "name": "RiskPerTradePct",
                    "description": "Percentuale di rischio per trade",
                    "type": "double",
                    "default_value": intake.get("risk_per_trade_pct", 1.0),
                    "optimize": False,
                    "why_not_optimize": "Parametro di risk management deciso dall'utente",
                },
                {
                    "id": "max_daily_trades",
                    "name": "MaxDailyTrades",
                    "description": "Numero massimo di trade al giorno",
                    "type": "int",
                    "default_value": intake.get("max_daily_trades", 1),
                    "optimize": False,
                    "why_not_optimize": "Vincolo operativo deciso dall'utente",
                },
            ]

        if macro_news.get("enabled"):
            parameters.extend(
                [
                    {
                        "id": "macro_news_enabled",
                        "name": "UseMacroNewsFilter",
                        "description": "Abilita il filtro macro/news live nel bot finale",
                        "type": "bool",
                        "default_value": True,
                        "optimize": False,
                        "why_not_optimize": "È una scelta di architettura del bot, non un parametro da ottimizzare.",
                    },
                    {
                        "id": "macro_news_pre_block",
                        "name": "MacroNewsPreBlockMinutes",
                        "description": "Minuti di blocco prima dell'evento macro",
                        "type": "int",
                        "default_value": macro_news.get("pre_event_block_minutes", 30),
                        "optimize": False,
                        "why_not_optimize": "Vincolo operativo deciso dall'utente.",
                    },
                    {
                        "id": "macro_news_post_block",
                        "name": "MacroNewsPostBlockMinutes",
                        "description": "Minuti di blocco dopo l'evento macro",
                        "type": "int",
                        "default_value": macro_news.get("post_event_block_minutes", 30),
                        "optimize": False,
                        "why_not_optimize": "Vincolo operativo deciso dall'utente.",
                    },
                ]
            )

        non_optimizable = data.get("non_optimizable") if isinstance(data.get("non_optimizable"), list) else []
        if macro_news.get("enabled") and "macro_news" not in non_optimizable:
            non_optimizable.append("macro_news")

        return {
            "formal_spec": formal_spec,
            "state_machine": state_machine,
            "parameters": parameters,
            "non_optimizable": non_optimizable,
            "assumptions": data.get("assumptions") if isinstance(data.get("assumptions"), list) else [],
        }

    def _build_payload(self, session_payload: dict, selected_resolutions: list, missing_inputs: dict = None) -> dict:
        parsed = session_payload.get("parsed", {})
        intake = session_payload.get("intake", {})
        return {
            "task": "formalize_strategy",
            "strategy": {
                "name": intake.get("name"),
                "market": intake.get("market"),
                "intake": {
                    "long_entry": intake.get("long_entry"),
                    "short_entry": intake.get("short_entry"),
                    "invalidation": intake.get("invalidation"),
                    "stop_loss": intake.get("stop_loss"),
                    "take_profit": intake.get("take_profit"),
                    "trailing_stop": intake.get("trailing_stop"),
                    "risk_per_trade_pct": intake.get("risk_per_trade_pct"),
                    "max_daily_trades": intake.get("max_daily_trades"),
                    "trading_hours_start": intake.get("trading_hours_start"),
                    "trading_hours_end": intake.get("trading_hours_end"),
                    "trading_days": intake.get("trading_days", []),
                    "macro_news": normalize_macro_news_config(intake.get("macro_news") or intake.get("fundamental_filters")),
                    "additional_notes": intake.get("additional_notes"),
                },
                "parsed_strategy": parsed.get("structured_strategy", {}),
                "codeable_rules": parsed.get("codeable_rules", []),
                "selected_resolutions": selected_resolutions,
                "provided_missing_inputs": missing_inputs or {},
            },
        }
