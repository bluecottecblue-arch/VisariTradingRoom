"""
Unified LLM Facade for Anthropic, OpenAI and Google Gemini.
"""
from typing import Any, Optional

from modules.common.anthropic_client import invoke_text as anthropic_text, invoke_json as anthropic_json
from modules.common.openai_client import invoke_text_openai as openai_text, invoke_json_openai as openai_json
from modules.common.gemini_client import invoke_text_gemini as gemini_text, invoke_json_gemini as gemini_json

async def invoke_text(
    module: str,
    system_prompt: str,
    payload: Any,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    use_cache: bool = True,
    ai_credentials: Optional[dict] = None,
) -> dict:
    creds = ai_credentials or {}
    provider = creds.get("provider", "anthropic")
    key = creds.get("api_key")
    
    if provider == "openai":
        return await openai_text(module, system_prompt, payload, max_tokens, model, use_cache, key)
    elif provider == "google":
        return await gemini_text(module, system_prompt, payload, max_tokens, model, use_cache, key)
    else:
        return await anthropic_text(module, system_prompt, payload, max_tokens, model, use_cache, key)

async def invoke_json(
    module: str,
    system_prompt: str,
    payload: Any,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    use_cache: bool = True,
    ai_credentials: Optional[dict] = None,
) -> dict:
    creds = ai_credentials or {}
    provider = creds.get("provider", "anthropic")
    key = creds.get("api_key")
    
    if provider == "openai":
        return await openai_json(module, system_prompt, payload, max_tokens, model, use_cache, key)
    elif provider == "google":
        return await gemini_json(module, system_prompt, payload, max_tokens, model, use_cache, key)
    else:
        return await anthropic_json(module, system_prompt, payload, max_tokens, model, use_cache, key)
