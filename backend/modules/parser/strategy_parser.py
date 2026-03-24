"""
StrategyParser — Modulo core di parsing con Claude API

Questo è il traduttore principale. Prende la strategia in linguaggio naturale
e la trasforma in strutture dati codificabili.

Principio fondamentale: essere onesti sulle limitazioni.
Se una parte della strategia non è oggettivamente codificabile, lo diciamo.
"""

from modules.common.anthropic_client import get_anthropic_model, invoke_json
from modules.common.strategy_validation import (
    STATUS_VALID,
    build_ambiguity,
    build_parse_result,
    build_required_input,
    count_blocking_issues,
    extract_llm_parse_issues,
    normalize_claude_access,
    validate_strategy_intake,
)


SYSTEM_PROMPT = """Sei un quant developer.
Return ONLY raw JSON. No markdown fences, no explanation, no preamble.
Start your response with { and end with }.
Restituisci SOLO JSON con chiavi:
structured_strategy, ambiguities, required_inputs, codeable_rules, bias_warnings, assumptions.
Regole:
- usa solo condizioni misurabili
- non inventare valori mancanti
- se qualcosa è ancora soggettivo, aggiungilo in ambiguities con alternative corte e binarie
- required_inputs solo per dati impossibili da inferire
- testo breve, niente markdown, niente spiegazioni extra"""


class StrategyParser:
    def __init__(self):
        self.model = get_anthropic_model("parse")

    async def parse(self, session_id: str, intake: dict) -> dict:
        """
        Analizza la strategia con Claude e restituisce la struttura dati completa.
        """
        local_result = validate_strategy_intake(intake)
        if local_result["status"] != STATUS_VALID:
            return local_result
        claude_access = normalize_claude_access(intake.get("claude_access"))

        llm_result = await invoke_json(
            module="parse",
            system_prompt=SYSTEM_PROMPT,
            payload=self._build_payload(intake),
            model=self.model,
            api_key_override=claude_access.get("api_key") or None,
        )
        parsed = self._validate_parsed_structure(llm_result["data"])
        parsed["required_inputs"] = self._filter_satisfied_required_inputs(
            parsed.get("required_inputs") or [],
            intake,
        )
        issues = extract_llm_parse_issues(parsed)

        ambiguities = parsed.get("ambiguities") or []
        required_inputs = parsed.get("required_inputs") or []
        merged_rules = self._merge_codeable_rules(
            local_result.get("codeable_rules", []),
            parsed.get("codeable_rules") or [],
        )
        completeness_score = self._calculate_completeness(
            ambiguities=ambiguities,
            required_inputs=required_inputs,
            codeable_rules=merged_rules,
        )

        message = issues["message"]
        if issues["status"] == STATUS_VALID:
            message = "Strategia validata e pronta per la formalizzazione."
        else:
            message = (
                "La revisione AI ha trovato ancora %s punto/i da chiarire. "
                "Il flusso resta bloccato finché non li risolvi."
            ) % count_blocking_issues(
                {"ambiguities": ambiguities, "required_inputs": required_inputs}
            )

        return build_parse_result(
            status=issues["status"],
            message=message,
            structured_strategy=parsed.get("structured_strategy") or local_result["structured_strategy"],
            ambiguities=ambiguities,
            required_inputs=required_inputs,
            codeable_rules=merged_rules,
            bias_warnings=parsed.get("bias_warnings") or local_result.get("bias_warnings", []),
            assumptions=parsed.get("assumptions") or [],
            completeness_score=completeness_score,
            usage=llm_result["usage"],
            validation={
                "stage": "parse",
                "llm_reviewed": True,
                "llm_skipped": False,
            },
        )

    def _validate_parsed_structure(self, parsed: dict) -> dict:
        parsed = parsed if isinstance(parsed, dict) else {}
        normalized = {
            "structured_strategy": parsed.get("structured_strategy") if isinstance(parsed.get("structured_strategy"), dict) else {},
            "ambiguities": self._normalize_ambiguities(parsed.get("ambiguities")),
            "required_inputs": self._normalize_required_inputs(parsed.get("required_inputs")),
            "codeable_rules": self._normalize_codeable_rules(parsed.get("codeable_rules")),
            "bias_warnings": parsed.get("bias_warnings") if isinstance(parsed.get("bias_warnings"), list) else [],
            "assumptions": parsed.get("assumptions") if isinstance(parsed.get("assumptions"), list) else [],
        }
        return normalized

    def _normalize_ambiguities(self, items) -> list:
        if not isinstance(items, list):
            return []
        normalized = []
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                original_text = item.get("original_text") or item.get("text") or item.get("label") or ""
                alternatives = item.get("alternatives") if isinstance(item.get("alternatives"), list) else []
                if not original_text and not alternatives:
                    continue
                normalized.append(
                    build_ambiguity(
                        amb_id=item.get("id") or f"amb_llm_{idx:03d}",
                        original_text=original_text,
                        why_ambiguous=item.get("why_ambiguous") or item.get("reason") or "Concetto da chiarire",
                        severity=item.get("severity") or "MEDIUM",
                        alternatives=alternatives,
                        field=item.get("field"),
                        blocking=item.get("blocking", True),
                    )
                )
            elif isinstance(item, str):
                if not item.strip():
                    continue
                normalized.append(
                    build_ambiguity(
                        amb_id=f"amb_llm_{idx:03d}",
                        original_text=item,
                        why_ambiguous="Concetto espresso in modo non ancora binario o matematico.",
                        severity="MEDIUM",
                        alternatives=[],
                    )
                )
        return normalized

    def _normalize_required_inputs(self, items) -> list:
        if not isinstance(items, list):
            return []
        normalized = []
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                label = item.get("label") or item.get("name") or "Input richiesto"
                if not self._is_relevant_required_input(label):
                    continue
                normalized.append(
                    build_required_input(
                        req_id=item.get("id") or f"req_llm_{idx:03d}",
                        field=item.get("field") or "additional_notes",
                        label=label,
                        why=item.get("why") or item.get("reason") or "Dettaglio necessario per codificare la strategia.",
                        example=item.get("example") or "Specifica il dato in modo binario",
                        source_text=item.get("source_text", ""),
                        blocking=item.get("blocking", True),
                    )
                )
            elif isinstance(item, str):
                if not self._is_relevant_required_input(item):
                    continue
                normalized.append(
                    build_required_input(
                        req_id=f"req_llm_{idx:03d}",
                        field="additional_notes",
                        label=item,
                        why="Dettaglio necessario per codificare la strategia.",
                        example="Specifica il dato in modo binario",
                    )
                )
        return normalized

    def _filter_satisfied_required_inputs(self, items: list, intake: dict) -> list:
        if not items:
            return []

        normalized_notes = " ".join(
            str(intake.get(field) or "").strip().lower()
            for field in ("additional_notes", "news_management", "long_entry", "short_entry")
        )
        macro_news = intake.get("macro_news") or intake.get("fundamental_filters") or {}
        macro_provider = str(macro_news.get("provider") or "").strip().lower()
        macro_api_key = str(macro_news.get("api_key") or "").strip()

        filtered = []
        for item in items:
            label = str(item.get("label") or "").strip().lower()
            why = str(item.get("why") or "").strip().lower()
            combined = f"{label} {why}".strip()

            if any(marker in combined for marker in (
                "news feed api",
                "news api",
                "provider api key",
                "economic calendar api",
                "trading economics api",
                "real-time news feed",
                "historical news event",
                "news event timestamp",
                "event timestamps",
                "price data feed",
                "real-time price data",
                "historical price data",
            )):
                if macro_provider == "trading_economics" and macro_api_key:
                    continue
                if "price data" in combined:
                    continue

            if any(marker in combined for marker in (
                "ema calculation method",
                "moving average method",
                "exact_ema_calculation_method",
            )):
                if "exponential moving average" in normalized_notes and "close price" in normalized_notes:
                    continue

            filtered.append(item)
        return filtered

    def _is_relevant_required_input(self, label: str) -> bool:
        text = (label or "").strip().lower()
        if not text:
            return False
        ignored_markers = (
            "account_balance",
            "account balance",
            "broker_spread",
            "broker spread",
            "spread max",
            "max spread",
            "ema calculation method",
            "ema method",
            "moving average method",
            "pip_value",
            "pip value",
            "slippage",
            "commission",
            "timezone",
            "period confirmation",
            "session timezone",
            "news_api_credentials",
            "news api credentials",
            "news provider api key",
            "trading_economics_api_key",
            "trading economics api key",
            "macro news api key",
            "macro provider api key",
            "provider api key",
            "economic calendar api key",
        )
        return not any(marker in text for marker in ignored_markers)

    def _normalize_codeable_rules(self, items) -> list:
        if not isinstance(items, list):
            return []
        normalized = []
        for idx, item in enumerate(items, start=1):
            if isinstance(item, dict):
                normalized.append(
                    {
                        "id": item.get("id") or f"rule_llm_{idx:03d}",
                        "description": item.get("description") or item.get("label") or "Regola codificabile",
                        "condition": item.get("condition") or item.get("expression") or item.get("description") or "",
                        "parameters": item.get("parameters") if isinstance(item.get("parameters"), dict) else {},
                    }
                )
            elif isinstance(item, str):
                normalized.append(
                    {
                        "id": f"rule_llm_{idx:03d}",
                        "description": item,
                        "condition": item,
                        "parameters": {},
                    }
                )
        return normalized

    def _build_payload(self, intake: dict) -> dict:
        return {
            "task": "review_strategy_for_algo_trading",
            "strategy": {
                "name": intake.get("name"),
                "market": intake.get("market"),
                "timeframes": {
                    "analysis": intake.get("analysis_timeframe"),
                    "execution": intake.get("execution_timeframe"),
                },
                "entries": {
                    "long": intake.get("long_entry"),
                    "short": intake.get("short_entry"),
                },
                "invalidation": intake.get("invalidation"),
                "stop_loss": intake.get("stop_loss"),
                "take_profit": intake.get("take_profit"),
                "trailing_stop": intake.get("trailing_stop"),
                "risk_management": {
                    "risk_per_trade_pct": intake.get("risk_per_trade_pct"),
                    "max_daily_trades": intake.get("max_daily_trades"),
                },
                "session": {
                    "start": intake.get("trading_hours_start"),
                    "end": intake.get("trading_hours_end"),
                    "days": intake.get("trading_days", []),
                },
                "filters": {
                    "volatility": intake.get("volatility_filter"),
                    "trend": intake.get("trend_filter"),
                    "context": intake.get("context_filter"),
                    "news": intake.get("news_management"),
                },
                "macro_news": intake.get("macro_news") or intake.get("fundamental_filters") or {},
                "notes": intake.get("additional_notes"),
            },
        }

    def _merge_codeable_rules(self, local_rules: list, llm_rules: list) -> list:
        merged = []
        seen = set()
        for rule in list(local_rules) + list(llm_rules):
            key = "%s|%s" % (rule.get("description"), rule.get("condition"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(rule)
        return merged

    def _calculate_completeness(
        self,
        ambiguities: list,
        required_inputs: list,
        codeable_rules: list,
    ) -> float:
        if not ambiguities and not required_inputs:
            return 1.0

        total_items = len(codeable_rules) + len(ambiguities) + len(required_inputs)
        if total_items == 0:
            return 0.0

        high_amb = sum(1 for item in ambiguities if item.get("severity") == "HIGH")
        medium_amb = sum(1 for item in ambiguities if item.get("severity") == "MEDIUM")
        penalty = len(required_inputs) * 0.25 + high_amb * 0.18 + medium_amb * 0.08
        base = len(codeable_rules) / float(total_items)
        return max(0.0, min(1.0, base - penalty))
