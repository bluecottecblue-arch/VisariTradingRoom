"""
Modification pipeline per Bot Lab.

Flusso:
original bot -> local analysis -> prompt validation -> optional LLM rewrite ->
local re-analysis -> compare summary
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from modules.common.anthropic_client import get_anthropic_model
from modules.common.llm_client import invoke_json
from modules.common.strategy_validation import (
    STATUS_INVALID,
    STATUS_VALID,
    empty_usage,
    normalize_claude_access,
    validate_mql5_code,
)


MODIFIER_SYSTEM_PROMPT = """You modify existing trading bots with minimal, precise edits.
Return ONLY raw JSON. No markdown fences, no explanation.
Return exactly these keys:
- modified_code: string
- change_summary: array of short strings
- conceptual_diff: array of short strings
- implementation_notes: array of short strings
- assumptions: array of short strings
- limitations: array of short strings

Rules:
1. Keep the existing architecture and naming style when possible.
2. Do not rewrite unrelated parts.
3. If the request adds fundamentals/news logic, implement explicit blackout windows or directional confirmation logic. No placeholders.
4. For MQL5 code, preserve OnInit/OnDeinit/OnTick and return compilable-looking code.
5. Output valid JSON only."""


class BotModifier:
    def __init__(self) -> None:
        self.model = get_anthropic_model("botlab_modify")

    def validate_prompt(self, prompt: str, fundamental_filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        text = (prompt or "").strip()
        if len(text) < 8:
            return {
                "status": STATUS_INVALID,
                "message": "La richiesta di modifica è troppo corta per essere codificabile.",
                "ambiguities": ["Richiesta troppo generica."],
                "resolved_actions": [],
                "usage": empty_usage("botlab_modify"),
            }

        lowered = text.lower()
        resolved_actions = []
        ambiguities = []

        mapping = [
            ("trailing_stop", ["trailing stop", "trailing", "breakeven"]),
            ("rsi_confirmation", ["rsi", "conferma rsi"]),
            ("atr_stop", ["atr", "atr-based", "atr based"]),
            ("session_filter", ["sessione", "londra", "new york", "london", "new york"]),
            ("news_safe_mode", ["news", "high impact", "rosso", "fomc", "cpi", "nfp"]),
            ("conservative_mode", ["conservativo", "conservative"]),
            ("aggressive_mode", ["aggressivo", "aggressive"]),
            ("reduce_entries", ["riduci numero di ingressi", "meno ingressi", "riduci gli ingressi"]),
        ]
        for action_id, tokens in mapping:
            if any(token in lowered for token in tokens):
                resolved_actions.append(action_id)

        if "miglior" in lowered and not resolved_actions:
            ambiguities.append(
                "La richiesta 'migliora il bot' da sola è troppo generica: serve un criterio tipo conservative mode, news-safe mode, trailing stop o riduzione ingressi."
            )
        if "modifica" in lowered and not resolved_actions and len(text.split()) < 5:
            ambiguities.append("La modifica richiesta non descrive quale parte del bot cambiare.")
        if fundamental_filters and fundamental_filters.get("enabled"):
            resolved_actions.append("fundamental_filters")

        resolved_actions = sorted(set(resolved_actions))
        if ambiguities:
            return {
                "status": STATUS_INVALID,
                "message": "La richiesta va chiarita prima di spendere token sulla modifica del codice.",
                "ambiguities": ambiguities,
                "resolved_actions": resolved_actions,
                "usage": empty_usage("botlab_modify"),
            }

        if not resolved_actions and len(text.split()) < 4:
            return {
                "status": STATUS_INVALID,
                "message": "La richiesta non è abbastanza specifica per modificare il bot in modo affidabile.",
                "ambiguities": ["Specifica il tipo di modifica desiderata."],
                "resolved_actions": [],
                "usage": empty_usage("botlab_modify"),
            }

        return {
            "status": STATUS_VALID,
            "message": "Richiesta chiara abbastanza per tentare una modifica mirata del bot.",
            "ambiguities": [],
            "resolved_actions": resolved_actions,
            "usage": empty_usage("botlab_modify"),
        }

    async def modify(
        self,
        *,
        original_code: str,
        original_analysis: dict[str, Any],
        prompt: str,
        claude_access: Optional[Dict[str, Any]] = None,
        fundamental_filters: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized_access = normalize_claude_access(claude_access)
        if not normalized_access.get("api_key"):
            return {
                "status": STATUS_INVALID,
                "message": "Serve una Claude API key valida: usa la tua key personale oppure quella assegnata al tuo account.",
                "modified_code": "",
                "change_summary": [],
                "conceptual_diff": [],
                "implementation_notes": [],
                "assumptions": [],
                "limitations": [],
                "code_validation": validate_uploaded_code(
                    language=((original_analysis.get("file_info") or {}).get("language") or "mql5"),
                    code="",
                ),
                "usage": empty_usage("botlab_modify"),
            }
        llm_result = await invoke_json(
            module="botlab_modify",
            system_prompt=MODIFIER_SYSTEM_PROMPT,
            payload={
                "task": "modify_existing_bot",
                "app_name": "VisariTradingRoom",
                "language": ((original_analysis.get("file_info") or {}).get("language") or "mql5"),
                "platform": ((original_analysis.get("file_info") or {}).get("platform") or "MetaTrader 5"),
                "requested_change": prompt.strip(),
                "resolved_actions": (original_analysis.get("modification_preflight") or {}).get("resolved_actions", []),
                "fundamental_filters": fundamental_filters or {},
                "original_bot_profile": original_analysis.get("bot_profile", {}),
                "original_code_summary": original_analysis.get("code_summary", {}),
                "original_code": original_code,
            },
            ai_credentials=normalized_access,
        )
        data = llm_result["data"]
        modified_code = str(data.get("modified_code") or "").strip()
        code_validation = validate_uploaded_code(
            language=((original_analysis.get("file_info") or {}).get("language") or "mql5"),
            code=modified_code,
        )
        return {
            "status": STATUS_VALID if code_validation["is_valid"] else STATUS_INVALID,
            "message": (
                "Versione modificata pronta per analisi, backtest e confronto."
                if code_validation["is_valid"]
                else "Il modello ha restituito codice modificato non valido."
            ),
            "modified_code": modified_code,
            "change_summary": _ensure_list(data.get("change_summary")),
            "conceptual_diff": _ensure_list(data.get("conceptual_diff")),
            "implementation_notes": _ensure_list(data.get("implementation_notes")),
            "assumptions": _ensure_list(data.get("assumptions")),
            "limitations": _ensure_list(data.get("limitations")),
            "code_validation": code_validation,
            "usage": llm_result["usage"],
        }


def validate_uploaded_code(language: str, code: str) -> dict[str, Any]:
    if language == "mql5":
        return validate_mql5_code(code)
    normalized = (code or "").strip()
    errors = []
    if not normalized:
        errors.append("codice vuoto")
    if len(normalized) < 80:
        errors.append("codice troppo corto per essere utile")
    if "todo" in normalized.lower() or "placeholder" in normalized.lower():
        errors.append("presenti placeholder o TODO")
    return {
        "is_valid": not errors,
        "errors": errors,
        "checks": {
            "non_empty": bool(normalized),
            "length_gt_80": len(normalized) >= 80,
            "no_placeholders": not any(token in normalized.lower() for token in ("todo", "placeholder")),
        },
        "length": len(normalized),
    }


def _ensure_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
