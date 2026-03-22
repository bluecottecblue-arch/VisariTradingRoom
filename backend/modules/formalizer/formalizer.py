"""
StrategyFormalizer — Trasforma la strategia risolta in specifica algoritmica formale

Questo modulo prende:
- La struttura dati dal parser
- Le scelte dell'utente per ogni ambiguità
E produce una specifica algoritmica completa con macchina a stati.
"""

from modules.common.anthropic_client import get_anthropic_model, invoke_json
from modules.common.strategy_validation import (
    STATUS_INVALID,
    STATUS_VALID,
    build_formalization_result,
    validate_formal_spec_payload,
    validate_resolutions_for_formalization,
)


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

    async def formalize(self, session_id: str, resolutions: dict) -> dict:
        """
        Produce la specifica algoritmica formale basandosi su:
        - parsed strategy (dal DB/memoria)
        - resolutions: scelte dell'utente per ogni ambiguità
        """
        # In produzione: recupera parsed dal DB
        session_payload = self._sessions.get(session_id)
        if not session_payload:
            return build_formalization_result(
                status=STATUS_INVALID,
                message="Sessione non trovata. Riesegui il parse della strategia.",
            )

        parsed = session_payload.get("parsed", {})
        readiness = validate_resolutions_for_formalization(parsed, resolutions)
        if not readiness["is_ready"]:
            return build_formalization_result(
                status=STATUS_INVALID,
                message=readiness["message"],
                ambiguities=readiness["unresolved_ambiguities"],
                required_inputs=readiness["required_inputs"],
                validation={"ready_for_generation": False},
            )

        llm_result = await invoke_json(
            module="formalize",
            system_prompt=FORMALIZATION_SYSTEM,
            payload=self._build_payload(session_payload, readiness["selected_resolutions"]),
            model=self.model,
            max_tokens=8192,
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

    def _validate_formalization_structure(self, data: dict, session_payload: dict) -> dict:
        data = data if isinstance(data, dict) else {}
        intake = session_payload.get("intake", {})
        formal_spec = data.get("formal_spec") if isinstance(data.get("formal_spec"), dict) else {}
        state_machine = data.get("state_machine") if isinstance(data.get("state_machine"), dict) else {}
        parameters = data.get("parameters") if isinstance(data.get("parameters"), list) else []

        if not formal_spec.get("entry_conditions"):
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

        return {
            "formal_spec": formal_spec,
            "state_machine": state_machine,
            "parameters": parameters,
            "non_optimizable": data.get("non_optimizable") if isinstance(data.get("non_optimizable"), list) else [],
            "assumptions": data.get("assumptions") if isinstance(data.get("assumptions"), list) else [],
        }

    def _build_payload(self, session_payload: dict, selected_resolutions: list) -> dict:
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
                    "additional_notes": intake.get("additional_notes"),
                },
                "parsed_strategy": parsed.get("structured_strategy", {}),
                "codeable_rules": parsed.get("codeable_rules", []),
                "selected_resolutions": selected_resolutions,
            },
        }
