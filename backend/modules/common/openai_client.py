"""
OpenAI API Client.
"""
import asyncio
import os
import copy
from typing import Any, Optional
from openai import AsyncOpenAI

from modules.common.anthropic_client import (
    _CACHE, _USAGE_SUMMARY, _build_cache_key, _api_key_fingerprint,
    _record_usage, parse_json_response, get_default_max_tokens,
    compact_json, estimate_tokens_from_chars, _ESTIMATED_SYSTEM_TOKENS
)

_CLIENT = None
_DEFAULT_OPENAI_MODEL = "gpt-4o"

def get_openai_api_key(api_key_override: Optional[str] = None) -> Optional[str]:
    api_key = str(api_key_override or "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    return api_key or None

def get_openai_client(api_key_override: Optional[str] = None):
    global _CLIENT
    api_key = get_openai_api_key(api_key_override)
    if not api_key:
        raise RuntimeError("OpenAI API key mancante.")
    
    if api_key_override:
        return AsyncOpenAI(api_key=api_key)

    if _CLIENT is None:
        _CLIENT = AsyncOpenAI(api_key=api_key)
    return _CLIENT

def _estimate_openai_cost(model: str, inputs: int, outputs: int) -> float:
    # Approx for GPT-4o (2.5 IN, 10.0 OUT per 1M)
    input_cost = 2.5
    output_cost = 10.0
    return (inputs / 1_000_000.0) * input_cost + (outputs / 1_000_000.0) * output_cost

async def invoke_text_openai(
    module: str,
    system_prompt: str,
    payload: Any,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    use_cache: bool = True,
    api_key_override: Optional[str] = None,
) -> dict:
    client = get_openai_client(api_key_override)
    model = model or _DEFAULT_OPENAI_MODEL
    max_tokens = max_tokens or get_default_max_tokens(module)
    system_prompt = system_prompt.strip()
    prompt = compact_json(payload)
    
    cache_key = _build_cache_key("text_openai", module, model, system_prompt, prompt, max_tokens, _api_key_fingerprint(api_key_override))

    if use_cache and cache_key in _CACHE:
        cached = copy.deepcopy(_CACHE[cache_key])
        cached_usage = cached["usage"]
        cached_usage["cache_hit"] = True
        cached_usage["billable"] = False
        cached_usage["estimated_cost_usd"] = 0.0
        _record_usage(module, cached_usage)
        return {"text": cached["raw_text"], "usage": cached_usage, "cache_key": cache_key}

    est_in = estimate_tokens_from_chars(len(prompt) + len(system_prompt))
    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0,
            )
            break
        except Exception as e:
            if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                if attempt < max_retries:
                    await asyncio.sleep(2.0 * (2 ** attempt))
                    continue
            raise e

    text = response.choices[0].message.content or ""
    in_tok = response.usage.prompt_tokens if response.usage else est_in
    out_tok = response.usage.completion_tokens if response.usage else 0
    cost = _estimate_openai_cost(model, in_tok, out_tok)
    
    usage = {
        "module": module,
        "model": model,
        "cache_hit": False,
        "billable": True,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "max_tokens": max_tokens,
        "estimated_cost_usd": round(cost, 6),
    }
    
    result = {"usage": usage, "raw_text": text}
    if use_cache:
        _CACHE[cache_key] = copy.deepcopy(result)
    _record_usage(module, usage)
    
    return {"text": text, "usage": usage, "cache_key": cache_key}

async def invoke_json_openai(
    module: str, system_prompt: str, payload: Any, max_tokens: Optional[int] = None,
    model: Optional[str] = None, use_cache: bool = True, api_key_override: Optional[str] = None,
) -> dict:
    res = await invoke_text_openai(module, system_prompt + "\n\nRESTITUISCI SOLO JSON VALIDO, SENZA COMMENTI FORMATTATI.", payload, max_tokens, model, use_cache, api_key_override)
    parsed = parse_json_response(res["text"])
    return {"data": parsed, "usage": res["usage"], "raw_text": res["text"]}
