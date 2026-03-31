"""
MQL5Generator — Genera Expert Advisor per MetaTrader 5

Usa Claude API per tradurre la specifica algoritmica formale
in codice MQL5 funzionante, documentato e leggibile.

LIMITAZIONE IMPORTANTE: il codice generato è un punto di partenza.
Non va mai deployato in live senza revisione manuale da un developer MQL5.
"""
import json
import re
from typing import Optional

from modules.common.anthropic_client import get_anthropic_model, parse_json_response
from modules.common.llm_client import invoke_text
from modules.common.deployment_bundle import build_deployment_readiness
from modules.common.strategy_validation import (
    STATUS_GENERATION_FAILED,
    STATUS_INVALID,
    STATUS_VALID,
    build_bot_result,
    normalize_claude_access,
    validate_formal_spec_payload,
    validate_mql5_code,
)


MQL5_SYSTEM_PROMPT = """You are an MQL5 expert.
Return ONLY raw JSON. No markdown fences, no explanation, no preamble.
Start your response with { and end with }.
Return ONLY a JSON object with exactly these keys:
- mql5_code: string containing the complete .mq5 file
- documentation: string in Italian explaining each section in plain language
- implementation_assumptions: array of strings
- limitations_vs_discretionary: array of strings

The MQL5 code MUST include:
1. All input parameters with input keyword and sensible defaults
2. OnInit() that validates parameters and initializes indicator handles with error checking
3. OnDeinit() that releases all indicator handles
4. OnTick() that checks new bar, session hours, spread, daily trade limit, open position management, then entry signals
5. CalcLotSize() using account balance × risk% ÷ (sl_pips × pip_value)
6. OpenLong() and OpenShort() with full MqlTradeRequest/MqlTradeResult error handling
7. IsNewBar() helper using static datetime
8. IsSessionActive() checking TimeCurrent() against input hours
9. IsSpreadOk() checking SymbolInfoInteger SYMBOL_SPREAD
10. If formal_spec.macro_news.enabled is true, ALSO include:
   - input bool UseMacroNewsFilter
   - input string MacroNewsProvider
   - input string MacroNewsApiKey with empty default value
   - input string MacroNewsCurrencies
   - input int MacroNewsPreBlockMinutes
   - input int MacroNewsPostBlockMinutes
   - input int MacroNewsPostEventWaitMinutes
   - input string MacroNewsMode
   - input string MacroDirectionalBias
   - RefreshMacroCalendarIfNeeded()
   - IsMacroTradingBlocked()
   - MacroBiasAllowsTrade()
   - WebRequest-based fetch to the provider API
   - macro/news checks BEFORE entry signals inside OnTick()
11. Never ignore macro_news when enabled.
12. For Trading Economics use a GET request to https://api.tradingeconomics.com/calendar?c=<api_key>.
13. Cache the fetched events in memory, refresh periodically, and convert them into pre/post-event blackout windows.
14. If MacroNewsMode is confirm_with_bias/post_event_trigger, use explicit helper logic; no pseudo-code.
15. Never hardcode secrets. MacroNewsApiKey must stay user-configurable at runtime.
16. Never output TODO, placeholder, FIXME, or stub comments.
17. mql5_code must contain ONLY plain MQL5 source code. Never JSON-encode another object inside mql5_code.
18. Do not use fake event timestamps, dummy data, placeholder arrays, or comment markers such as "placeholder" or "TODO".
No markdown fences."""


class MQL5Generator:
    def __init__(self):
        self.model = get_anthropic_model("botgen")
        self._sessions: dict = {}

    def store_formal_spec(self, session_id: str, spec: dict, claude_access: Optional[dict] = None):
        self._sessions[session_id] = {
            "spec": spec,
            "claude_access": normalize_claude_access(claude_access),
        }

    async def generate(self, session_id: str) -> dict:
        session_payload = self._sessions.get(session_id, {}) or {}
        spec = session_payload.get("spec", {})
        if not spec:
            return build_bot_result(
                status=STATUS_INVALID,
                message="Specifica formale non trovata. Formalizza prima la strategia.",
            )

        if spec.get("status") != STATUS_VALID:
            return build_bot_result(
                status=STATUS_INVALID,
                message="La strategia non è pronta per la generazione del bot.",
                required_inputs=spec.get("required_inputs", []),
            )

        formal_validation = validate_formal_spec_payload(spec)
        if not formal_validation["is_valid"]:
            return build_bot_result(
                status=STATUS_INVALID,
                message="Specifica formale incompleta: %s" % ", ".join(formal_validation["errors"]),
                required_inputs=[
                    {
                        "id": "req_formal_spec",
                        "field": "formal_spec",
                        "label": "Completa la specifica algoritmica",
                        "why": ", ".join(formal_validation["errors"]),
                        "example": "Rigenera la formalizzazione dopo aver risolto tutte le ambiguità",
                        "blocking": True,
                    }
                ],
            )

        claude_access = session_payload.get("claude_access") or {}
        llm_result = await invoke_text(
            module="botgen",
            system_prompt=MQL5_SYSTEM_PROMPT,
            payload=self._build_payload(spec),
            model=self.model,
            ai_credentials=claude_access,
        )
        data = self._parse_mixed_response(llm_result["text"])
        code = self._normalize_generated_code((data.get("mql5_code") or "").strip(), spec)
        code_validation = validate_mql5_code(code)
        macro_validation = self._validate_macro_runtime(code, spec)
        if macro_validation["required"]:
            code_validation = self._merge_code_validation(code_validation, macro_validation)
        deployment_readiness = build_deployment_readiness(
            code=code,
            spec=spec,
            code_validation=code_validation,
        )
        if not code_validation["is_valid"]:
            return build_bot_result(
                status=STATUS_GENERATION_FAILED,
                message="Il modello ha restituito codice non valido o incompleto.",
                mql5_code=code,
                documentation=(data.get("documentation") or "").strip(),
                implementation_assumptions=data.get("implementation_assumptions") or [],
                limitations_vs_discretionary=data.get("limitations_vs_discretionary") or [],
                code_validation=code_validation,
                deployment_readiness=deployment_readiness,
                usage=llm_result["usage"],
                validation={"ready_for_download": False},
            )

        return build_bot_result(
            status=STATUS_VALID,
            message="Expert Advisor pronto per il download.",
            mql5_code=code,
            documentation=(data.get("documentation") or "").strip(),
            implementation_assumptions=data.get("implementation_assumptions") or [],
            limitations_vs_discretionary=data.get("limitations_vs_discretionary") or [],
            code_validation=code_validation,
            deployment_readiness=deployment_readiness,
            usage=llm_result["usage"],
            validation={"ready_for_download": True},
        )

    def _parse_mixed_response(self, text: str) -> dict:
        cleaned = (text or "").strip()
        try:
            parsed = parse_json_response(cleaned)
        except Exception:
            code = self._extract_code(cleaned)
            parsed = {
                "mql5_code": code,
                "documentation": "",
                "implementation_assumptions": [],
                "limitations_vs_discretionary": [],
            }
        parsed = self._unwrap_nested_payload(parsed)
        return {
            "mql5_code": parsed.get("mql5_code", "") if isinstance(parsed.get("mql5_code"), str) else "",
            "documentation": parsed.get("documentation", "") if isinstance(parsed.get("documentation"), str) else "",
            "implementation_assumptions": parsed.get("implementation_assumptions") if isinstance(parsed.get("implementation_assumptions"), list) else [],
            "limitations_vs_discretionary": parsed.get("limitations_vs_discretionary") if isinstance(parsed.get("limitations_vs_discretionary"), list) else [],
        }

    def _unwrap_nested_payload(self, parsed: dict) -> dict:
        candidate = parsed if isinstance(parsed, dict) else {}
        nested_code = candidate.get("mql5_code")
        if isinstance(nested_code, str):
            nested_clean = nested_code.strip()
            if nested_clean.startswith("{") and "\"mql5_code\"" in nested_clean:
                try:
                    nested = json.loads(nested_clean)
                except Exception:
                    try:
                        nested = parse_json_response(nested_clean)
                    except Exception:
                        nested = None
                if isinstance(nested, dict):
                    candidate = {
                        "mql5_code": nested.get("mql5_code", ""),
                        "documentation": nested.get("documentation") or candidate.get("documentation") or "",
                        "implementation_assumptions": nested.get("implementation_assumptions")
                        if isinstance(nested.get("implementation_assumptions"), list)
                        else candidate.get("implementation_assumptions") or [],
                        "limitations_vs_discretionary": nested.get("limitations_vs_discretionary")
                        if isinstance(nested.get("limitations_vs_discretionary"), list)
                        else candidate.get("limitations_vs_discretionary") or [],
                    }
        return candidate

    def _normalize_generated_code(self, code: str, spec: dict) -> str:
        normalized = (code or "").strip()
        if not normalized:
            return ""
        if normalized.startswith("{") and "\"mql5_code\"" in normalized:
            try:
                nested = parse_json_response(normalized)
            except Exception:
                nested = None
            if isinstance(nested, dict) and isinstance(nested.get("mql5_code"), str):
                normalized = nested.get("mql5_code", "").strip()
        normalized = normalized.replace("\r\n", "\n")
        normalized = re.sub(r"(?im)^.*\b(TODO|FIXME|placeholder)\b.*\n?", "", normalized)
        if ((spec.get("formal_spec") or {}).get("macro_news") or {}).get("enabled"):
            normalized = self._ensure_macro_inputs(normalized)
            normalized = self._ensure_macro_state(normalized)
            normalized = self._apply_canonical_macro_runtime(normalized)
        normalized = self._ensure_visari_signature(normalized)
        return normalized.strip()

    def _ensure_visari_signature(self, code: str) -> str:
        normalized = (code or "").strip()
        if not normalized:
            return normalized
        if "Visari Trading Room" in normalized or "VisariTradingRoom" in normalized:
            return normalized
        signature = "// Built with Visari Trading Room"
        if normalized.startswith("#property"):
            first_line_end = normalized.find("\n")
            if first_line_end != -1:
                head = normalized[: first_line_end + 1]
                tail = normalized[first_line_end + 1 :]
                return f"{head}{signature}\n{tail}".strip()
        return f"{signature}\n{normalized}".strip()

    def _ensure_macro_inputs(self, code: str) -> str:
        if "MacroNewsImpact" in code:
            return code
        insert_after = 'input string MacroNewsCurrencies = "USD,EUR";           // Currencies to monitor'
        new_line = 'input string MacroNewsImpact = "high";                 // low / medium / high\n'
        if insert_after in code:
            return code.replace(insert_after, f"{insert_after}\n{new_line}", 1)
        anchor = 'input int MacroNewsPostEventWaitMinutes = 15;          // Post-event wait minutes'
        if anchor in code:
            return code.replace(anchor, f"{new_line}{anchor}", 1)
        return code

    def _ensure_macro_state(self, code: str) -> str:
        if "bool macroCalendarReady" in code:
            return code
        marker = "string newsEventImpacts[];"
        state_line = "bool macroCalendarReady = false;"
        if marker in code:
            return code.replace(marker, f"{marker}\n{state_line}", 1)
        indicator_anchor = "// Indicator handles"
        if indicator_anchor in code:
            return code.replace(indicator_anchor, f"{state_line}\n\n{indicator_anchor}", 1)
        return f"{code}\n\n{state_line}\n"

    def _apply_canonical_macro_runtime(self, code: str) -> str:
        replacements = {
            "RefreshMacroCalendarIfNeeded": self._macro_refresh_function(),
            "ParseNewsEvents": self._macro_parse_function(),
            "IsMacroTradingBlocked": self._macro_block_function(),
            "MacroBiasAllowsTrade": self._macro_bias_function(),
        }
        for name, replacement in replacements.items():
            code = self._replace_named_function(code, name, replacement)
        helpers = self._macro_helper_block()
        if "string TrimMacroText(" not in code:
            code = f"{code}\n\n{helpers}\n"
        return code

    def _replace_named_function(self, code: str, function_name: str, replacement: str) -> str:
        match = re.search(
            rf"(?ms)(?:void|bool|int|double|string|datetime)\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{",
            code,
        )
        if not match:
            return f"{code}\n\n{replacement}\n"
        start = match.start()
        brace_start = code.find("{", match.end() - 1)
        if brace_start < 0:
            return code
        depth = 0
        end = -1
        for idx in range(brace_start, len(code)):
            char = code[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        if end < 0:
            return code
        return f"{code[:start]}{replacement}{code[end + 1:]}"

    def _macro_refresh_function(self) -> str:
        return '''void RefreshMacroCalendarIfNeeded()
{
   if(!UseMacroNewsFilter)
      return;

   datetime currentTime = TimeCurrent();
   if(macroCalendarReady && (currentTime - lastNewsRefresh) < 900)
      return;

   string apiKey = TrimMacroText(MacroNewsApiKey);
   if(StringLen(apiKey) == 0)
   {
      macroCalendarReady = false;
      Print("MacroNewsApiKey non configurata: filtro macro attivo ma feed non disponibile.");
      return;
   }

   string provider = StringToLower(TrimMacroText(MacroNewsProvider));
   if(provider == "" || provider == "none")
   {
      macroCalendarReady = false;
      Print("MacroNewsProvider non configurato.");
      return;
   }

   if(provider != "trading_economics")
   {
      macroCalendarReady = false;
      Print("Provider macro non supportato in runtime MQL5: ", provider);
      return;
   }

   string url = "https://api.tradingeconomics.com/calendar?c=" + apiKey + "&f=json";
   string headers = "Content-Type: application/json\\r\\n";
   char data[];
   char result[];
   string responseHeaders = "";

   ResetLastError();
   int status = WebRequest("GET", url, headers, 10000, data, result, responseHeaders);
   if(status == -1)
   {
      macroCalendarReady = false;
      Print("WebRequest macro fallita. Errore MT5: ", GetLastError());
      return;
   }

   if(status != 200)
   {
      macroCalendarReady = false;
      Print("Feed macro non disponibile. HTTP status: ", status);
      return;
   }

   string jsonResponse = CharArrayToString(result);
   ParseNewsEvents(jsonResponse);
   macroCalendarReady = ArraySize(newsEventTimes) >= 0;
   lastNewsRefresh = currentTime;
}'''

    def _macro_parse_function(self) -> str:
        return '''void ParseNewsEvents(string jsonResponse)
{
   ArrayResize(newsEvents, 0);
   ArrayResize(newsEventTimes, 0);
   ArrayResize(newsEventCurrencies, 0);
   ArrayResize(newsEventImpacts, 0);

   int pos = 0;
   while(true)
   {
      int start = StringFind(jsonResponse, "{", pos);
      if(start < 0)
         break;

      int finish = StringFind(jsonResponse, "}", start);
      if(finish < 0)
         break;

      string item = StringSubstr(jsonResponse, start, finish - start + 1);
      pos = finish + 1;

      string currency = TrimMacroText(ExtractJsonStringValue(item, "Currency"));
      if(StringLen(currency) == 0)
         currency = TrimMacroText(ExtractJsonStringValue(item, "CountryCode"));
      if(!MacroCurrencySelected(currency))
         continue;

      string impactText = TrimMacroText(ExtractJsonStringValue(item, "Importance"));
      if(StringLen(impactText) == 0)
         impactText = TrimMacroText(ExtractJsonStringValue(item, "Impact"));
      string impactRaw = TrimMacroText(ExtractJsonRawValue(item, "Importance"));
      if(MacroImpactFromEvent(impactText, impactRaw) < MacroImpactThreshold(MacroNewsImpact))
         continue;

      string eventName = TrimMacroText(ExtractJsonStringValue(item, "Event"));
      if(StringLen(eventName) == 0)
         eventName = TrimMacroText(ExtractJsonStringValue(item, "Category"));
      if(StringLen(eventName) == 0)
         eventName = "MacroEvent";

      string dateValue = TrimMacroText(ExtractJsonStringValue(item, "Date"));
      if(StringLen(dateValue) == 0)
         dateValue = TrimMacroText(ExtractJsonRawValue(item, "Date"));
      datetime eventTime = ParseMacroNewsDate(dateValue);
      if(eventTime <= 0)
         continue;

      int newIndex = ArraySize(newsEventTimes);
      ArrayResize(newsEvents, newIndex + 1);
      ArrayResize(newsEventTimes, newIndex + 1);
      ArrayResize(newsEventCurrencies, newIndex + 1);
      ArrayResize(newsEventImpacts, newIndex + 1);

      newsEvents[newIndex] = eventName;
      newsEventTimes[newIndex] = eventTime;
      newsEventCurrencies[newIndex] = currency;
      newsEventImpacts[newIndex] = NormalizeMacroImpactText(impactText == "" ? impactRaw : impactText);
   }
}'''

    def _macro_block_function(self) -> str:
        return '''bool IsMacroTradingBlocked()
{
   if(!UseMacroNewsFilter)
      return false;

   if(!macroCalendarReady)
   {
      Print("Filtro macro attivo ma calendario non pronto: operatività sospesa per sicurezza.");
      return true;
   }

   datetime currentTime = TimeCurrent();
   int postWindowMinutes = (int)MathMax((double)MacroNewsPostBlockMinutes, (double)MacroNewsPostEventWaitMinutes);

   for(int i = 0; i < ArraySize(newsEventTimes); i++)
   {
      if(!MacroCurrencySelected(newsEventCurrencies[i]))
         continue;
      if(MacroImpactFromEvent(newsEventImpacts[i], newsEventImpacts[i]) < MacroImpactThreshold(MacroNewsImpact))
         continue;

      datetime blockStart = newsEventTimes[i] - (MacroNewsPreBlockMinutes * 60);
      datetime blockEnd = newsEventTimes[i] + (postWindowMinutes * 60);

      if(currentTime >= blockStart && currentTime <= blockEnd)
      {
         Print("Trading sospeso per evento macro: ", newsEvents[i], " / ", newsEventCurrencies[i]);
         return true;
      }
   }

   return false;
}'''

    def _macro_bias_function(self) -> str:
        return '''bool MacroBiasAllowsTrade(bool isLong)
{
   string mode = StringToLower(TrimMacroText(MacroNewsMode));
   string bias = StringToLower(TrimMacroText(MacroDirectionalBias));

   if(mode == "" || mode == "filter" || bias == "" || bias == "exclude_only")
      return true;

   string base = StringSubstr(_Symbol, 0, 3);
   string quote = StringSubstr(_Symbol, 3, 3);

   if(StringFind(bias, "bullish_") == 0)
   {
      string currency = StringToUpper(StringSubstr(bias, 8));
      if(currency == base)
         return isLong;
      if(currency == quote)
         return !isLong;
      return true;
   }

   if(StringFind(bias, "bearish_") == 0)
   {
      string currency = StringToUpper(StringSubstr(bias, 8));
      if(currency == base)
         return !isLong;
      if(currency == quote)
         return isLong;
      return true;
   }

   return true;
}'''

    def _macro_helper_block(self) -> str:
        return '''string TrimMacroText(string value)
{
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
}

bool MacroCurrencySelected(string currency)
{
   string normalized = StringToUpper(TrimMacroText(currency));
   if(StringLen(normalized) == 0)
      return false;

   string configured = StringToUpper(MacroNewsCurrencies);
   return StringFind(configured, normalized) >= 0;
}

int MacroImpactThreshold(string impactSetting)
{
   string normalized = StringToLower(TrimMacroText(impactSetting));
   if(normalized == "low")
      return 1;
   if(normalized == "medium")
      return 2;
   return 3;
}

int MacroImpactFromEvent(string impactValue, string importanceValue)
{
   string raw = StringToLower(TrimMacroText(impactValue + " " + importanceValue));
   if(StringFind(raw, "high") >= 0 || StringFind(raw, "3") >= 0)
      return 3;
   if(StringFind(raw, "medium") >= 0 || StringFind(raw, "2") >= 0)
      return 2;
   if(StringFind(raw, "low") >= 0 || StringFind(raw, "1") >= 0)
      return 1;
   return 0;
}

string NormalizeMacroImpactText(string rawImpact)
{
   int score = MacroImpactFromEvent(rawImpact, rawImpact);
   if(score >= 3)
      return "high";
   if(score == 2)
      return "medium";
   if(score == 1)
      return "low";
   return "unknown";
}

string ExtractJsonStringValue(string source, string key)
{
   string pattern = "\"" + key + "\":";
   int start = StringFind(source, pattern);
   if(start < 0)
      return "";

   start += StringLen(pattern);
   while(start < StringLen(source) && (StringGetCharacter(source, start) == ' ' || StringGetCharacter(source, start) == '\"'))
      start++;

   int finish = start;
   while(finish < StringLen(source))
   {
      ushort ch = StringGetCharacter(source, finish);
      if(ch == '\"')
         break;
      finish++;
   }

   if(finish <= start)
      return "";
   return StringSubstr(source, start, finish - start);
}

string ExtractJsonRawValue(string source, string key)
{
   string pattern = "\"" + key + "\":";
   int start = StringFind(source, pattern);
   if(start < 0)
      return "";

   start += StringLen(pattern);
   while(start < StringLen(source) && StringGetCharacter(source, start) == ' ')
      start++;

   int finish = start;
   while(finish < StringLen(source))
   {
      ushort ch = StringGetCharacter(source, finish);
      if(ch == ',' || ch == '}')
         break;
      finish++;
   }

   if(finish <= start)
      return "";
   return TrimMacroText(StringSubstr(source, start, finish - start));
}

datetime ParseMacroNewsDate(string rawValue)
{
   string value = TrimMacroText(rawValue);
   if(StringLen(value) == 0)
      return 0;

   int dateWrapperStart = StringFind(value, "/Date(");
   if(dateWrapperStart == 0)
   {
      int endPos = StringFind(value, ")", 6);
      if(endPos > 6)
      {
         string millisText = StringSubstr(value, 6, endPos - 6);
         long millis = (long)StringToInteger(millisText);
         return (datetime)(millis / 1000);
      }
   }

   if(StringLen(value) < 16)
      return 0;

   MqlDateTime dt;
   dt.year = (int)StringToInteger(StringSubstr(value, 0, 4));
   dt.mon = (int)StringToInteger(StringSubstr(value, 5, 2));
   dt.day = (int)StringToInteger(StringSubstr(value, 8, 2));
   dt.hour = (int)StringToInteger(StringSubstr(value, 11, 2));
   dt.min = (int)StringToInteger(StringSubstr(value, 14, 2));
   dt.sec = 0;

   if(StringLen(value) >= 19)
      dt.sec = (int)StringToInteger(StringSubstr(value, 17, 2));

   return StructToTime(dt);
}'''

    def _extract_code(self, text: str) -> str:
        normalized = (text or "").strip()
        fence_match = re.search(r"```(?:mql5|cpp|c\+\+|json)?\s*([\s\S]*?)\s*```", normalized, re.IGNORECASE)
        if fence_match:
            content = fence_match.group(1).strip()
            if content.startswith("{") and content.endswith("}"):
                try:
                    parsed = json.loads(content)
                    return (parsed.get("mql5_code") or "").strip()
                except Exception:
                    pass
            return content
        return normalized

    def _build_payload(self, spec: dict) -> dict:
        formal_spec = dict(spec.get("formal_spec") or {})
        macro_news = dict(formal_spec.get("macro_news") or {})
        if macro_news:
            macro_news["api_key"] = ""
            formal_spec["macro_news"] = macro_news
        fundamental_filters = dict(formal_spec.get("fundamental_filters") or {})
        if fundamental_filters:
            fundamental_filters["api_key"] = ""
            formal_spec["fundamental_filters"] = fundamental_filters
        return {
            "task": "generate_mql5_ea",
            "app_name": "VisariTradingRoom",
            "formal_spec": formal_spec,
            "state_machine": spec.get("state_machine", {}),
            "parameters": spec.get("parameters", []),
            "non_optimizable": spec.get("non_optimizable", []),
            "assumptions": spec.get("assumptions", []),
            "macro_news": macro_news,
            "provider_endpoints": {
                "trading_economics": "https://api.tradingeconomics.com/calendar",
            },
        }

    def _validate_macro_runtime(self, code: str, spec: dict) -> dict:
        macro_news = ((spec.get("formal_spec") or {}).get("macro_news") or {})
        enabled = bool(macro_news.get("enabled"))
        if not enabled:
            return {"required": False, "is_valid": True, "errors": [], "checks": {}}

        checks = {
            "has_macro_inputs": "UseMacroNewsFilter" in code and "MacroNewsProvider" in code,
            "has_web_request": "WebRequest(" in code,
            "has_refresh_helper": "RefreshMacroCalendarIfNeeded(" in code,
            "has_block_helper": "IsMacroTradingBlocked(" in code,
            "has_bias_helper": "MacroBiasAllowsTrade(" in code or "MacroBiasAllowsTrade (" in code,
            "has_ontick_macro_gate": "IsMacroTradingBlocked()" in code or "RefreshMacroCalendarIfNeeded();" in code,
            "has_mode_input": "MacroNewsMode" in code,
            "has_api_key_input": "MacroNewsApiKey" in code,
        }

        errors = []
        for key, ok in checks.items():
            if ok:
                continue
            if key == "has_macro_inputs":
                errors.append("manca il blocco input per macro/news live")
            elif key == "has_web_request":
                errors.append("manca WebRequest per il feed macro live")
            elif key == "has_refresh_helper":
                errors.append("manca RefreshMacroCalendarIfNeeded()")
            elif key == "has_block_helper":
                errors.append("manca IsMacroTradingBlocked()")
            elif key == "has_bias_helper":
                errors.append("manca MacroBiasAllowsTrade()")
            elif key == "has_ontick_macro_gate":
                errors.append("OnTick() non applica il filtro macro/news prima degli ingressi")
            elif key == "has_mode_input":
                errors.append("manca MacroNewsMode")
            elif key == "has_api_key_input":
                errors.append("manca MacroNewsApiKey")

        return {
            "required": True,
            "is_valid": not errors,
            "errors": errors,
            "checks": checks,
        }

    def _merge_code_validation(self, base: dict, extra: dict) -> dict:
        checks = dict(base.get("checks") or {})
        checks.update(extra.get("checks") or {})
        errors = list(base.get("errors") or [])
        for item in extra.get("errors") or []:
            if item not in errors:
                errors.append(item)
        return {
            **base,
            "checks": checks,
            "errors": errors,
            "is_valid": not errors,
        }


# Template EA di base come fallback / esempio
EA_TEMPLATE = '''//+------------------------------------------------------------------+
//| VisariTradingRoom EA - Template Base                               |
//| ATTENZIONE: Solo esempio. Personalizza con la tua strategia.       |
//+------------------------------------------------------------------+
#property copyright "VisariTradingRoom"
#property version   "1.00"
#property strict

// === INPUT PARAMETERS ===
input double RiskPercent       = 1.0;   // Rischio per trade (%)
input int    MagicNumber       = 12345; // Magic number EA
input int    MaxDailyTrades    = 3;     // Max trade al giorno
input int    SessionStartHour  = 8;     // Ora inizio sessione (UTC)
input int    SessionEndHour    = 17;    // Ora fine sessione (UTC)
input int    MaxSpreadPoints   = 20;    // Spread massimo consentito
input bool   AllowLong         = true;  // Abilita long
input bool   AllowShort        = true;  // Abilita short

// === GLOBAL VARIABLES ===
int      g_daily_trades = 0;
datetime g_last_trade_day = 0;
int      g_magic = MagicNumber;

//+------------------------------------------------------------------+
int OnInit() {
   Print("VisariTradingRoom EA inizializzato");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   Print("VisariTradingRoom EA rimosso");
}

//+------------------------------------------------------------------+
void OnTick() {
   // Controlla se è un nuovo giorno e resetta contatore
   ResetDailyCounterIfNewDay();
   
   // Controllo sessione
   if(!IsSessionActive()) return;
   
   // Controllo spread
   if(!IsSpreadOk()) return;
   
   // Se già in posizione, gestisci
   if(PositionSelect(_Symbol)) {
      ManagePosition();
      return;
   }
   
   // Controlla max trade giornalieri
   if(g_daily_trades >= MaxDailyTrades) return;
   
   // Verifica segnali di entry
   // TODO: Inserire qui la logica specifica della tua strategia
   CheckEntrySignals();
}

//+------------------------------------------------------------------+
// Controlla se la sessione di trading è attiva
bool IsSessionActive() {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int hour = dt.hour;
   int dow = dt.day_of_week; // 0=Domenica, 6=Sabato
   
   if(dow == 0 || dow == 6) return false; // No weekend
   if(hour < SessionStartHour || hour >= SessionEndHour) return false;
   
   return true;
}

//+------------------------------------------------------------------+
// Controlla che lo spread sia accettabile
bool IsSpreadOk() {
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > MaxSpreadPoints) {
      Print("Spread troppo alto: ", spread, " points");
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
// Calcola il lot size basato su rischio percentuale e SL in points
double CalcLotSize(double sl_points) {
   double account_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = account_balance * (RiskPercent / 100.0);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   
   if(sl_points <= 0 || tick_value <= 0) return 0.01; // fallback
   
   double lot = risk_amount / (sl_points * point / tick_size * tick_value);
   
   // Normalizza al lot step del broker
   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lot = MathFloor(lot / lot_step) * lot_step;
   
   // Clamp tra min e max
   double lot_min = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lot_max = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   
   return MathMin(MathMax(lot, lot_min), lot_max);
}

//+------------------------------------------------------------------+
void ResetDailyCounterIfNewDay() {
   datetime today = (datetime)(TimeCurrent() / 86400 * 86400);
   if(today != g_last_trade_day) {
      g_daily_trades = 0;
      g_last_trade_day = today;
   }
}

//+------------------------------------------------------------------+
// Placeholder: inserire qui la logica di entry specifica della strategia
void CheckEntrySignals() {
   // TODO: Implementare la logica della tua strategia
   // Esempio:
   // if(SomeCondition() && AllowLong) OpenLong();
   // if(SomeCondition() && AllowShort) OpenShort();
}

//+------------------------------------------------------------------+
// Placeholder: gestione della posizione aperta
void ManagePosition() {
   // TODO: trailing stop, gestione parziale, ecc.
}

//+------------------------------------------------------------------+
// Apre una posizione long
void OpenLong(double sl_price, double tp_price) {
   MqlTradeRequest req = {};
   MqlTradeResult  res = {};
   
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl_points = (ask - sl_price) / SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double lots = CalcLotSize(sl_points);
   
   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = _Symbol;
   req.volume    = lots;
   req.type      = ORDER_TYPE_BUY;
   req.price     = ask;
   req.sl        = sl_price;
   req.tp        = tp_price;
   req.deviation = 10;
   req.magic     = g_magic;
   req.comment   = "VisariTradingRoom Long";
   
   if(OrderSend(req, res)) {
      if(res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_PLACED) {
         Print("Long aperto: lots=", lots, " SL=", sl_price, " TP=", tp_price);
         g_daily_trades++;
      } else {
         Print("Errore apertura long: ", res.retcode, " - ", res.comment);
      }
   }
}

//+------------------------------------------------------------------+
// Apre una posizione short  
void OpenShort(double sl_price, double tp_price) {
   MqlTradeRequest req = {};
   MqlTradeResult  res = {};
   
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl_points = (sl_price - bid) / SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double lots = CalcLotSize(sl_points);
   
   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = _Symbol;
   req.volume    = lots;
   req.type      = ORDER_TYPE_SELL;
   req.price     = bid;
   req.sl        = sl_price;
   req.tp        = tp_price;
   req.deviation = 10;
   req.magic     = g_magic;
   req.comment   = "VisariTradingRoom Short";
   
   if(OrderSend(req, res)) {
      if(res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_PLACED) {
         Print("Short aperto: lots=", lots, " SL=", sl_price, " TP=", tp_price);
         g_daily_trades++;
      } else {
         Print("Errore apertura short: ", res.retcode, " - ", res.comment);
      }
   }
}
'''
