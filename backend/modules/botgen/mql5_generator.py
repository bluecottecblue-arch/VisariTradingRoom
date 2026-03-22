"""
MQL5Generator — Genera Expert Advisor per MetaTrader 5

Usa Claude API per tradurre la specifica algoritmica formale
in codice MQL5 funzionante, documentato e leggibile.

LIMITAZIONE IMPORTANTE: il codice generato è un punto di partenza.
Non va mai deployato in live senza revisione manuale da un developer MQL5.
"""
import json
import re

from modules.common.anthropic_client import get_anthropic_model, invoke_text, parse_json_response
from modules.common.strategy_validation import (
    STATUS_GENERATION_FAILED,
    STATUS_INVALID,
    STATUS_VALID,
    build_bot_result,
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
No markdown fences."""


class MQL5Generator:
    def __init__(self):
        self.model = get_anthropic_model("botgen")
        self._sessions: dict = {}

    def store_formal_spec(self, session_id: str, spec: dict):
        self._sessions[session_id] = spec

    async def generate(self, session_id: str) -> dict:
        spec = self._sessions.get(session_id, {})
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

        llm_result = await invoke_text(
            module="botgen",
            system_prompt=MQL5_SYSTEM_PROMPT,
            payload=self._build_payload(spec),
            model=self.model,
        )
        data = self._parse_mixed_response(llm_result["text"])
        code = (data.get("mql5_code") or "").strip()
        code_validation = validate_mql5_code(code)
        if not code_validation["is_valid"]:
            return build_bot_result(
                status=STATUS_GENERATION_FAILED,
                message="Il modello ha restituito codice non valido o incompleto.",
                mql5_code=code,
                documentation=(data.get("documentation") or "").strip(),
                implementation_assumptions=data.get("implementation_assumptions") or [],
                limitations_vs_discretionary=data.get("limitations_vs_discretionary") or [],
                code_validation=code_validation,
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
        return {
            "mql5_code": parsed.get("mql5_code", "") if isinstance(parsed.get("mql5_code"), str) else "",
            "documentation": parsed.get("documentation", "") if isinstance(parsed.get("documentation"), str) else "",
            "implementation_assumptions": parsed.get("implementation_assumptions") if isinstance(parsed.get("implementation_assumptions"), list) else [],
            "limitations_vs_discretionary": parsed.get("limitations_vs_discretionary") if isinstance(parsed.get("limitations_vs_discretionary"), list) else [],
        }

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
        return {
            "task": "generate_mql5_ea",
            "app_name": "VisariTradingRoom",
            "formal_spec": spec.get("formal_spec", {}),
            "state_machine": spec.get("state_machine", {}),
            "parameters": spec.get("parameters", []),
            "non_optimizable": spec.get("non_optimizable", []),
            "assumptions": spec.get("assumptions", []),
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
