"""
Bootstrap condiviso per Anthropic.

Carica in modo affidabile la .env del progetto e uniforma la creazione del client
tra parser, formalizer e bot generator.
"""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import os
import re
from typing import Any, Dict, Optional

from dotenv import load_dotenv


_ENV_LOADED = False
_CLIENT = None
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_CANDIDATES = (
    _PROJECT_ROOT / ".env",
    _PROJECT_ROOT / "backend" / ".env",
)
_CACHE: Dict[str, dict] = {}
_USAGE_SUMMARY: Dict[str, dict] = {
    "overall": {
        "calls": 0,
        "billable_calls": 0,
        "cache_hits": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
    },
    "by_module": {},
}

_DEFAULT_MAX_TOKENS = {
    "parse": 4096,
    "formalize": 4096,
    "botgen": 7168,
    "botlab_modify": 7168,
}

_DEFAULT_COSTS_PER_MILLION = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
}

_ESTIMATED_SYSTEM_TOKENS = {
    "parse": 650,
    "formalize": 900,
    "botgen": 1200,
    "botlab_modify": 900,
}


def _load_project_env() -> None:
    global _ENV_LOADED

    if _ENV_LOADED:
        return

    for env_path in _ENV_CANDIDATES:
        if env_path.exists():
            load_dotenv(env_path, override=True)

    _ENV_LOADED = True


def get_anthropic_api_key(api_key_override: Optional[str] = None) -> Optional[str]:
    _load_project_env()
    api_key = str(api_key_override or "").strip() or os.getenv("ANTHROPIC_API_KEY", "").strip()
    return api_key or None


def get_anthropic_model(module: Optional[str] = None) -> str:
    _load_project_env()
    if module:
        module_specific = os.getenv("ANTHROPIC_MODEL_%s" % module.upper(), "").strip()
        if module_specific:
            return module_specific
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def get_anthropic_client(api_key_override: Optional[str] = None):
    global _CLIENT
    import anthropic

    api_key = get_anthropic_api_key(api_key_override)
    if not api_key:
        raise RuntimeError(
            "Claude API key mancante. Configura ANTHROPIC_API_KEY nel backend oppure passa una chiave personale dalla UI."
        )

    if api_key_override:
        return anthropic.Anthropic(api_key=api_key)

    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic(api_key=api_key)

    return _CLIENT


def compact_json(payload: Any) -> str:
    payload = prune_payload(payload)
    if isinstance(payload, str):
        return payload.strip()
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def prune_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned = {}
        for key, value in payload.items():
            pruned = prune_payload(value)
            if pruned in (None, "", [], {}):
                continue
            cleaned[key] = pruned
        return cleaned
    if isinstance(payload, list):
        cleaned = [prune_payload(item) for item in payload]
        return [item for item in cleaned if item not in (None, "", [], {})]
    if isinstance(payload, str):
        stripped = payload.strip()
        return stripped or None
    return payload


def get_default_max_tokens(module: str) -> int:
    _load_project_env()
    override = os.getenv("ANTHROPIC_MAX_TOKENS_%s" % module.upper(), "").strip()
    if override.isdigit():
        return int(override)
    return _DEFAULT_MAX_TOKENS.get(module, 2048)


def estimate_tokens_from_chars(chars: int) -> int:
    return max(1, int(round(max(0, chars) / 4.0)))


def estimate_stage_budget(module: str, payload: Any, expected_output_ratio: float = 0.6) -> dict:
    model = get_anthropic_model(module)
    prompt = compact_json(payload)
    input_tokens = estimate_tokens_from_chars(len(prompt)) + _ESTIMATED_SYSTEM_TOKENS.get(module, 500)
    max_tokens = get_default_max_tokens(module)
    output_tokens = max(256, min(max_tokens, int(max_tokens * expected_output_ratio)))
    return {
        "module": module,
        "model": model,
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "max_tokens": max_tokens,
        "estimated_cost_usd": round(_estimate_cost_usd(model, input_tokens, output_tokens), 6),
    }


async def invoke_text(
    module: str,
    system_prompt: str,
    payload: Any,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    use_cache: bool = True,
    api_key_override: Optional[str] = None,
) -> dict:
    client = get_anthropic_client(api_key_override)
    model = model or get_anthropic_model(module)
    max_tokens = max_tokens or get_default_max_tokens(module)
    system_prompt = system_prompt.strip()
    prompt = compact_json(payload)
    cache_key = _build_cache_key(
        "text",
        module,
        model,
        system_prompt,
        prompt,
        max_tokens,
        _api_key_fingerprint(api_key_override),
    )

    if use_cache and cache_key in _CACHE:
        cached = copy.deepcopy(_CACHE[cache_key])
        cached_usage = cached["usage"]
        cached_usage["cache_hit"] = True
        cached_usage["billable"] = False
        cached_usage["estimated_cost_usd"] = 0.0
        _record_usage(module, cached_usage)
        print(
            "[LLM:%s] cache hit model=%s in=%s out=%s"
            % (
                module,
                model,
                cached_usage.get("input_tokens", 0),
                cached_usage.get("output_tokens", 0),
            )
        )
        return {"text": cached["raw_text"], "usage": cached_usage}

    estimated_input_tokens = client.count_tokens(system_prompt) + client.count_tokens(prompt)
    loop = asyncio.get_running_loop()
    message = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        ),
    )

    text = extract_text(message)
    usage = {
        "module": module,
        "model": model,
        "cache_hit": False,
        "billable": True,
        "system_chars": len(system_prompt),
        "prompt_chars": len(prompt),
        "estimated_input_tokens": estimated_input_tokens,
        "input_tokens": getattr(message.usage, "input_tokens", 0),
        "output_tokens": getattr(message.usage, "output_tokens", 0),
        "max_tokens": max_tokens,
        "estimated_cost_usd": round(
            _estimate_cost_usd(
                model,
                getattr(message.usage, "input_tokens", 0),
                getattr(message.usage, "output_tokens", 0),
            ),
            6,
        ),
    }
    result = {"usage": usage, "raw_text": text}
    if use_cache:
        _CACHE[cache_key] = copy.deepcopy(result)
    _record_usage(module, usage)
    print(
        "[LLM:%s] model=%s chars=%s tok(in=%s,out=%s) cost~$%.6f"
        % (
            module,
            model,
            len(prompt),
            usage["input_tokens"],
            usage["output_tokens"],
            usage["estimated_cost_usd"],
        )
    )
    return {"text": text, "usage": usage}


async def invoke_json(
    module: str,
    system_prompt: str,
    payload: Any,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    use_cache: bool = True,
    api_key_override: Optional[str] = None,
) -> dict:
    llm_result = await invoke_text(
        module=module,
        system_prompt=system_prompt,
        payload=payload,
        max_tokens=max_tokens,
        model=model,
        use_cache=use_cache,
        api_key_override=api_key_override,
    )
    parsed = parse_json_response(llm_result["text"])
    return {"data": parsed, "usage": llm_result["usage"], "raw_text": llm_result["text"]}


def parse_json_response(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = _strip_fences(cleaned)
    if not cleaned:
        raise ValueError("Risposta LLM vuota")

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None
        for candidate in _find_json_candidates(cleaned):
            try:
                parsed = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if parsed is None:
            print("[LLM] JSON parse failure. Raw response preview:", cleaned[:1200])
            raise ValueError("Risposta LLM non valida: JSON assente o malformato")

    if not isinstance(parsed, dict):
        raise ValueError("Risposta LLM non valida: oggetto JSON atteso")
    return parsed


def extract_text(message: Any) -> str:
    chunks = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            chunks.append(getattr(block, "text", ""))
    return "\n".join(chunks).strip()


def get_usage_summary() -> dict:
    return copy.deepcopy(_USAGE_SUMMARY)


def _build_cache_key(
    kind: str,
    module: str,
    model: str,
    system_prompt: str,
    prompt: str,
    max_tokens: int,
    api_key_fingerprint: str,
) -> str:
    payload = "%s|%s|%s|%s|%s|%s|%s" % (
        kind,
        module,
        model,
        max_tokens,
        system_prompt,
        prompt,
        api_key_fingerprint,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _api_key_fingerprint(api_key_override: Optional[str]) -> str:
    raw = str(api_key_override or "").strip()
    if not raw:
        return "integrated"
    return "personal:%s" % hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    _load_project_env()
    default_input, default_output = _DEFAULT_COSTS_PER_MILLION.get(model, (0.0, 0.0))
    input_per_million = float(os.getenv("ANTHROPIC_INPUT_COST_PER_MTOK", default_input) or 0.0)
    output_per_million = float(os.getenv("ANTHROPIC_OUTPUT_COST_PER_MTOK", default_output) or 0.0)
    return (input_tokens / 1_000_000.0) * input_per_million + (
        output_tokens / 1_000_000.0
    ) * output_per_million


def _record_usage(module: str, usage: dict) -> None:
    _USAGE_SUMMARY["overall"]["calls"] += 1
    if usage.get("cache_hit"):
        _USAGE_SUMMARY["overall"]["cache_hits"] += 1
    if usage.get("billable"):
        _USAGE_SUMMARY["overall"]["billable_calls"] += 1
        _USAGE_SUMMARY["overall"]["input_tokens"] += usage.get("input_tokens", 0)
        _USAGE_SUMMARY["overall"]["output_tokens"] += usage.get("output_tokens", 0)
        _USAGE_SUMMARY["overall"]["estimated_cost_usd"] += usage.get("estimated_cost_usd", 0.0)

    module_stats = _USAGE_SUMMARY["by_module"].setdefault(
        module,
        {
            "calls": 0,
            "billable_calls": 0,
            "cache_hits": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
        },
    )
    module_stats["calls"] += 1
    if usage.get("cache_hit"):
        module_stats["cache_hits"] += 1
    if usage.get("billable"):
        module_stats["billable_calls"] += 1
        module_stats["input_tokens"] += usage.get("input_tokens", 0)
        module_stats["output_tokens"] += usage.get("output_tokens", 0)
        module_stats["estimated_cost_usd"] += usage.get("estimated_cost_usd", 0.0)


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    fence_match = re.search(r"```(?:json|javascript|js|python|text)?\s*([\s\S]*?)\s*```", stripped, re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _find_json_candidates(text: str) -> list[str]:
    candidates = []
    patterns = [
        r"(\{[\s\S]*\})",
        r"```(?:json)?\s*(\{[\s\S]*\})\s*```",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidate = _strip_fences(match.group(1) if match.groups() else match.group(0))
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    if not candidates:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start:end + 1])
    return candidates
