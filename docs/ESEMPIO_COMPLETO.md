# Esempio Completo: London Breakout su EURUSD
## Strategia discrezionale → Specifica formale → Bot → Backtest

---

## 1. INPUT UTENTE (strategia discrezionale)

```
Nome: London Breakout Pullback
Mercato: EURUSD
Timeframe analisi: H1
Timeframe esecuzione: M15

Setup LONG:
Nelle prime 2 ore di apertura di Londra (08:00-10:00 UTC) cerco un breakout
rialzista del range formatosi durante la sessione asiatica (00:00-07:00 UTC).
Entro long solo se il prezzo rompe verso l'alto con una candela H1 forte (corpo
almeno 60% della candela). Aspetto un piccolo pullback alla zona di breakout
su M15 e entro alla chiusura della prima candela bullish di rimbalzo.

Invalidazione:
Se il prezzo non pullbacka entro 3 candele M15 o se chiude sotto il punto
di breakout originale.

Stop Loss:
Sotto il minimo del pullback su M15 + 5 pips di buffer

Take Profit:
2.5R dal rischio, oppure alla prossima resistenza H4 se è vicina

Rischio per trade: 1%
Max trade al giorno: 2
Orari: 08:00-11:00 UTC solo
Giorni: Lunedì-Venerdì, evito Venerdì dopo le 14:00

Filtri:
- Non opero nei 30 minuti prima/dopo NFP, BCE, e altri high-impact events
- Evito se lo spread è > 2 pips
- Evito se l'ATR(14) su H1 è < 30 pips (mercato troppo piatto)

Esempi trade validi:
- 12 feb 2024: Range asiatico 1.0780-1.0810. Breakout rialzista alle 08:30 UTC
  con candela H1 che chiude a 1.0832 (corpo 22 pips su range 28 pips = 78%).
  Pullback a 1.0815 su M15 alle 09:15, rimbalzo. Entry 1.0817, SL 1.0800,
  TP 1.0857 (2.5R). Trade chiuso a TP.

Esempi trade invalidi:
- Evito quando il breakout avviene su volume basso e la candela ha wick lungo
- Evito i breakout "falsi" dove il prezzo rompe e poi torna subito nel range
```

---

## 2. OUTPUT PARSER — Analisi Claude

```json
{
  "structured_strategy": {
    "instruments": ["EURUSD"],
    "timeframes": { "analysis": "H1", "execution": "M15" },
    "sessions": [
      { "name": "London Open", "start_utc": "08:00", "end_utc": "11:00" }
    ]
  },
  "ambiguities": [
    {
      "id": "amb_001",
      "original_text": "breakout rialzista del range formatosi durante la sessione asiatica",
      "why_ambiguous": "Il 'range asiatico' non ha una definizione algoritmica standard. Serve specificare: quante ore? Quale tipo di High/Low? Include spike?",
      "severity": "HIGH",
      "alternatives": [
        {
          "id": "alt_a",
          "description": "High/Low delle candele H1 tra 00:00 e 07:00 UTC",
          "implementation": "asian_high = max(High[t] per t in 00:00-07:00 UTC); asian_low = min(Low[t]...)",
          "tradeoffs": "Semplice e oggettivo. Include spike su news notturne."
        },
        {
          "id": "alt_b",
          "description": "High/Low escludendo candele con ATR spike (> 2x ATR medio)",
          "implementation": "Stesso ma filtra candele con range > 2 * ATR(20)",
          "tradeoffs": "Più robusto agli spike. Più complesso."
        },
        {
          "id": "alt_c",
          "description": "Banda di Bollinger (20,1) delle ultime 7 candele H1 notturne",
          "implementation": "BB(20,1) calcolata su Close delle 7 candele 00:00-07:00",
          "tradeoffs": "Cattura la volatilità storica del range. Meno intuitivo."
        }
      ]
    },
    {
      "id": "amb_002",
      "original_text": "piccolo pullback alla zona di breakout",
      "why_ambiguous": "Quanto è 'piccolo'? Quale zona esattamente? Il prezzo deve toccare il livello o avvicinarsi?",
      "severity": "MEDIUM",
      "alternatives": [
        {
          "id": "alt_a",
          "description": "Low della candela M15 entro 5 pips dall'Asian High",
          "implementation": "Low[0] >= asian_high - 5*point AND Low[0] <= asian_high + 10*point",
          "tradeoffs": "Preciso ma potrebbe perdere pullback che si fermano prima."
        },
        {
          "id": "alt_b",
          "description": "Retracement Fibonacci del 38.2% o 50% del movimento di breakout",
          "implementation": "Low[0] in range [breakout_move * 0.382, breakout_move * 0.618] da entry",
          "tradeoffs": "Più dinamico. I livelli Fib non sono algoritmicamente migliori del 38.2%."
        }
      ]
    },
    {
      "id": "amb_003",
      "original_text": "prima candela bullish di rimbalzo",
      "why_ambiguous": "Cosa definisce 'bullish'? Solo close > open? O serve un minimo di corpo?",
      "severity": "LOW",
      "alternatives": [
        {
          "id": "alt_a",
          "description": "Close > Open (definizione base)",
          "implementation": "Close[0] > Open[0]",
          "tradeoffs": "Semplicissimo. Potrebbe includere doji e candele insignificanti."
        },
        {
          "id": "alt_b",
          "description": "Corpo candela > 50% del range della candela",
          "implementation": "(Close[0] - Open[0]) / (High[0] - Low[0]) > 0.5",
          "tradeoffs": "Richiede candela con forza direzionale. Perderà alcune entry valide."
        }
      ]
    }
  ],
  "codeable_rules": [
    {
      "id": "rule_001",
      "description": "Solo nella finestra oraria di trading",
      "condition": "Hour(TimeCurrent()) >= 8 AND Hour(TimeCurrent()) <= 10"
    },
    {
      "id": "rule_002",
      "description": "Corpo candela H1 breakout > 60% del range",
      "condition": "MathAbs(Close[0] - Open[0]) / (High[0] - Low[0]) > 0.60"
    },
    {
      "id": "rule_003",
      "description": "Spread inferiore a 2 pips",
      "condition": "SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= 20"
    },
    {
      "id": "rule_004",
      "description": "ATR(14) su H1 > 30 pips",
      "condition": "iATR(_Symbol, PERIOD_H1, 14, 0) > 0.0030"
    },
    {
      "id": "rule_005",
      "description": "Max 2 trade al giorno",
      "condition": "daily_trade_count < 2"
    }
  ],
  "bias_warnings": [
    "Gli esempi forniti mostrano solo trade vincenti. Questo può portare a sovrastimare la qualità del setup.",
    "La descrizione 'pullback alla zona di breakout' è soggetta a confirmation bias: è più facile riconoscerla dopo che il trade ha funzionato.",
    "Il criterio 'evito i breakout falsi' non è definito oggettivamente — ogni algoritmizzazione di questo filtro è un'approssimazione."
  ],
  "completeness_score": 0.68
}
```

---

## 3. SCELTE UTENTE per le ambiguità

```json
{
  "amb_001": "alt_a",   // Asian range = High/Low H1 candele 00:00-07:00
  "amb_002": "alt_a",   // Pullback = Low M15 entro 5 pips da Asian High
  "amb_003": "alt_b"    // Bullish = corpo > 50% range
}
```

---

## 4. SPECIFICA FORMALE (estratto)

```json
{
  "formal_spec": {
    "metadata": {
      "strategy_name": "London Breakout Pullback",
      "version": "1.0",
      "target_platform": "MetaTrader 5",
      "instruments": ["EURUSD"],
      "timeframes": { "analysis": "H1", "execution": "M15" }
    },
    "indicators": [
      { "id": "atr_h1", "name": "ATR", "type": "ATR", "params": {"period": 14}, "timeframe": "H1",
        "mql5_function": "iATR(_Symbol, PERIOD_H1, 14, 0)" },
      { "id": "asian_high", "name": "Asian Session High", "type": "CUSTOM", 
        "params": {"session_start": "00:00", "session_end": "07:00"},
        "mql5_function": "CalcAsianHigh()" },
      { "id": "asian_low", "name": "Asian Session Low", "type": "CUSTOM",
        "mql5_function": "CalcAsianLow()" }
    ],
    "entry_conditions": {
      "long": {
        "conditions": [
          { "id": "c001", "description": "H1 chiude sopra Asian High con corpo forte",
            "mql5_expression": "iClose(_Symbol,PERIOD_H1,0) > g_asian_high AND (MathAbs(iClose(_Symbol,PERIOD_H1,0)-iOpen(_Symbol,PERIOD_H1,0))/(iHigh(_Symbol,PERIOD_H1,0)-iLow(_Symbol,PERIOD_H1,0))) > 0.60" },
          { "id": "c002", "description": "M15 Low in zona pullback (entro 5 pips da Asian High)",
            "mql5_expression": "iLow(_Symbol,PERIOD_M15,0) >= g_asian_high - 5*_Point AND iLow(_Symbol,PERIOD_M15,0) <= g_asian_high + 10*_Point" },
          { "id": "c003", "description": "Candela M15 bullish (corpo > 50% range)",
            "mql5_expression": "(iClose(_Symbol,PERIOD_M15,0)-iOpen(_Symbol,PERIOD_M15,0))/(iHigh(_Symbol,PERIOD_M15,0)-iLow(_Symbol,PERIOD_M15,0)) > 0.50" },
          { "id": "c004", "description": "Nella finestra oraria London Open",
            "mql5_expression": "TimeHour(TimeCurrent()) >= 8 && TimeHour(TimeCurrent()) <= 10" },
          { "id": "c005", "description": "ATR H1 > 30 pips",
            "mql5_expression": "iATR(_Symbol,PERIOD_H1,14,0) > 0.0030" },
          { "id": "c006", "description": "Spread <= 2 pips",
            "mql5_expression": "SymbolInfoInteger(_Symbol,SYMBOL_SPREAD) <= 20" }
        ],
        "logic": "AND"
      }
    },
    "stop_loss": { "type": "structure", "description": "Low del pullback M15 - 5 pips" },
    "take_profit": { "type": "rr_ratio", "rr_ratio": 2.5 },
    "risk_management": {
      "position_sizing": "fixed_risk_pct",
      "risk_per_trade_pct": 1.0,
      "max_daily_trades": 2,
      "max_daily_loss_pct": 2.0
    }
  },
  "non_optimizable": [
    "Il timeframe di analisi H1 — fa parte della logica strutturale della strategia",
    "Il 2.5R di take profit — non va ottimizzato perché cambierebbe il profilo rischio/rendimento atteso",
    "L'orario 08:00-11:00 UTC — è legato alla sessione di Londra, non a una scelta arbitraria"
  ]
}
```

---

## 5. BOT MQL5 GENERATO (estratto)

```mql5
//+------------------------------------------------------------------+
//| StrategyForge EA - London Breakout Pullback                        |
//| Generato da StrategyForge — REVISIONARE PRIMA DEL DEPLOY          |
//+------------------------------------------------------------------+
#property copyright "StrategyForge"
#property version   "1.00"
#property strict

// === INPUT PARAMETERS ===
input double RiskPercent        = 1.0;   // Rischio per trade (%)
input double RR_Ratio           = 2.5;   // Risk/Reward ratio
input int    MaxDailyTrades     = 2;     // Max trade al giorno
input int    SessionStartHour   = 8;     // Ora inizio sessione UTC
input int    SessionEndHour     = 10;    // Ora fine sessione UTC
input int    AsianSessionStart  = 0;     // Inizio sessione asiatica (00:00)
input int    AsianSessionEnd    = 7;     // Fine sessione asiatica (07:00)
input int    ATR_Period         = 14;    // Periodo ATR
input double ATR_Min_Pips       = 30.0;  // ATR minimo in pips
input double BreakoutBodyPct    = 0.60;  // Corpo candela breakout minimo (%)
input double PullbackBullBodyPct= 0.50;  // Corpo candela pullback bullish (%)
input int    PullbackZonePips   = 5;     // Zona pullback (pips da Asian High)
input int    MaxSpreadPoints    = 20;    // Spread massimo (points)
input int    MagicNumber        = 99001; // Magic number EA

// === GLOBAL VARIABLES ===
double g_asian_high = 0;
double g_asian_low  = 0;
double g_breakout_high = 0;   // High della candela H1 breakout
bool   g_breakout_confirmed = false;
int    g_daily_trades = 0;
datetime g_last_trade_day = 0;
datetime g_asian_calc_day = 0;

//+------------------------------------------------------------------+
int OnInit() {
   Print("London Breakout EA inizializzato. Magic: ", MagicNumber);
   if(!SymbolInfoDouble(_Symbol, SYMBOL_POINT)) return INIT_FAILED;
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   Print("London Breakout EA rimosso. Reason: ", reason);
}

//+------------------------------------------------------------------+
void OnTick() {
   // Reset contatore giornaliero se nuovo giorno
   ResetDailyIfNewDay();
   
   // Calcola range asiatico all'inizio di ogni giornata di trading
   CalcAsianRange();
   
   // Se già in posizione, gestisci (trailing stop se configurato)
   if(PositionSelect(_Symbol)) {
      ManagePosition();
      return;
   }
   
   // Controlla max trade giornalieri
   if(g_daily_trades >= MaxDailyTrades) return;
   
   // Controlla se siamo nella sessione attiva
   if(!IsSessionActive()) return;
   
   // Controlla spread
   if(!IsSpreadOk()) return;
   
   // Controlla ATR minimo
   if(!IsVolatilityOk()) return;
   
   // Verifica breakout H1 (aggiorna stato)
   CheckH1Breakout();
   
   // Se breakout confermato, cerca entry su M15
   if(g_breakout_confirmed && g_asian_high > 0) {
      CheckM15Entry();
   }
}

//+------------------------------------------------------------------+
void CalcAsianRange() {
   datetime today = (datetime)((long)TimeCurrent() / 86400 * 86400);
   if(today == g_asian_calc_day) return; // Già calcolato oggi
   
   g_asian_high = 0;
   g_asian_low  = 999999;
   g_breakout_confirmed = false;
   
   // Scorri le candele H1 della sessione asiatica
   for(int i = 0; i < 24; i++) {
      datetime bar_time = iTime(_Symbol, PERIOD_H1, i);
      MqlDateTime dt;
      TimeToStruct(bar_time, dt);
      
      if(dt.hour >= AsianSessionStart && dt.hour < AsianSessionEnd) {
         double h = iHigh(_Symbol, PERIOD_H1, i);
         double l = iLow(_Symbol, PERIOD_H1, i);
         if(h > g_asian_high) g_asian_high = h;
         if(l < g_asian_low)  g_asian_low  = l;
      }
   }
   
   if(g_asian_high == 0) g_asian_low = 0; // Range non valido
   g_asian_calc_day = today;
   
   if(g_asian_high > 0)
      Print("Asian Range calcolato: H=", g_asian_high, " L=", g_asian_low);
}

//+------------------------------------------------------------------+
void CheckH1Breakout() {
   if(g_asian_high <= 0) return;
   
   double h1_close = iClose(_Symbol, PERIOD_H1, 0);
   double h1_open  = iOpen(_Symbol, PERIOD_H1, 0);
   double h1_high  = iHigh(_Symbol, PERIOD_H1, 0);
   double h1_low   = iLow(_Symbol, PERIOD_H1, 0);
   
   // Verifica breakout rialzista
   if(h1_close > g_asian_high) {
      double body = MathAbs(h1_close - h1_open);
      double range = h1_high - h1_low;
      double body_pct = (range > 0) ? (body / range) : 0;
      
      if(body_pct >= BreakoutBodyPct && !g_breakout_confirmed) {
         g_breakout_confirmed = true;
         g_breakout_high = h1_high;
         Print("✅ Breakout H1 confermato a ", h1_close, " (corpo: ", DoubleToString(body_pct*100,1), "%)");
      }
   }
}

//+------------------------------------------------------------------+
void CheckM15Entry() {
   double m15_close = iClose(_Symbol, PERIOD_M15, 0);
   double m15_open  = iOpen(_Symbol, PERIOD_M15, 0);
   double m15_high  = iHigh(_Symbol, PERIOD_M15, 0);
   double m15_low   = iLow(_Symbol, PERIOD_M15, 0);
   
   // Verifica pullback: Low M15 nella zona del breakout
   double zone_low  = g_asian_high - PullbackZonePips * _Point;
   double zone_high = g_asian_high + (PullbackZonePips * 2) * _Point;
   
   bool in_pullback_zone = (m15_low >= zone_low && m15_low <= zone_high);
   
   // Verifica candela bullish con corpo significativo
   double body = m15_close - m15_open;
   double range = m15_high - m15_low;
   double body_pct = (range > 0) ? (body / range) : 0;
   bool is_bullish = (body_pct >= PullbackBullBodyPct);
   
   if(in_pullback_zone && is_bullish) {
      Print("📍 Condizioni M15 soddisfatte — tentativo entry LONG");
      OpenLong(m15_low - PullbackZonePips * _Point);
   }
}

//+------------------------------------------------------------------+
void OpenLong(double sl_price) {
   MqlTradeRequest req = {};
   MqlTradeResult  res = {};
   
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double sl_pips = (ask - sl_price) / _Point;
   
   if(sl_pips < 5) {  // SL troppo piccolo — skip
      Print("⚠️  SL troppo piccolo (", sl_pips, " pips) — skip");
      return;
   }
   
   double tp_price = ask + sl_pips * RR_Ratio * _Point;
   double lots = CalcLotSize(sl_pips);
   
   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = _Symbol;
   req.volume    = lots;
   req.type      = ORDER_TYPE_BUY;
   req.price     = ask;
   req.sl        = sl_price;
   req.tp        = tp_price;
   req.deviation = 15;
   req.magic     = MagicNumber;
   req.comment   = "LBP_Long";
   
   if(OrderSend(req, res) && (res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_PLACED)) {
      Print("✅ Long aperto: lots=", lots, " ask=", ask, " SL=", sl_price, " TP=", tp_price);
      g_daily_trades++;
      g_breakout_confirmed = false; // Reset per evitare entry multiple
   } else {
      Print("❌ Errore apertura: ", res.retcode, " - ", res.comment);
   }
}

//+------------------------------------------------------------------+
double CalcLotSize(double sl_pips) {
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amt = balance * (RiskPercent / 100.0);
   double tick_val = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_sz  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(sl_pips <= 0 || tick_val <= 0 || tick_sz <= 0) return 0.01;
   
   double lot = risk_amt / (sl_pips * _Point / tick_sz * tick_val);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lot = MathFloor(lot / step) * step;
   
   return MathMin(MathMax(lot, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)),
                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX));
}

//+------------------------------------------------------------------+
bool IsSessionActive() {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6) return false;
   return (dt.hour >= SessionStartHour && dt.hour < SessionEndHour);
}

bool IsSpreadOk() {
   return (SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= MaxSpreadPoints);
}

bool IsVolatilityOk() {
   double atr = iATR(_Symbol, PERIOD_H1, ATR_Period, 0);
   return (atr >= ATR_Min_Pips * _Point);
}

void ManagePosition() {
   // Placeholder — aggiungi trailing stop se necessario
}

void ResetDailyIfNewDay() {
   datetime today = (datetime)((long)TimeCurrent() / 86400 * 86400);
   if(today != g_last_trade_day) {
      g_daily_trades = 0;
      g_last_trade_day = today;
   }
}
```

---

## 6. RISULTATI BACKTEST (esempio realistico)

```
Periodo in-sample: 2019-01-01 → 2022-12-31
Periodo OOS: 2023-01-01 → 2024-12-31
Strumento: EURUSD H1/M15
Capitale iniziale: $10,000
Spread: 1.2 pip | Slippage: 0.5 pip | Commissione: $7/lotto

--- IN-SAMPLE ---
Trade totali: 187
Hit rate: 42.2%
Avg Win (R): +2.41R | Avg Loss (R): -1.00R
Expectancy: +0.39R per trade
Profit Factor: 1.74
Sharpe Ratio: 0.91
Sortino Ratio: 1.28
Calmar Ratio: 0.88
Max Drawdown: -14.3%
Perdite consecutive max: 7
Return totale: +38.4%

--- OUT-OF-SAMPLE (2023-2024) ---
Trade totali: 89
Hit rate: 38.2%
Expectancy: +0.28R
Sharpe Ratio: 0.64
Max Drawdown: -18.1%
Return totale: +16.8%

--- WALK-FORWARD (12 periodi) ---
Profittevoli: 8/12 (66.7%)
Sharpe medio OOS: 0.58
Interpretazione: ⚠️  Risultati misti — profittevole nel 66.7% dei periodi OOS.
                 Edge presente ma non robustissima. Testare con cautela.

--- MONTE CARLO (1000 simulazioni, base OOS) ---
Prob. profitto: 71%
Capitale mediano dopo 2 anni: $13,200
P5 (scenario pessimo 5%): $8,100 (-19%)
Max DD P95: 28.4%

--- BIAS CHECK ---
Affidabilità: AFFIDABILITÀ MODERATA — Con riserve
Warning: [MEDIUM] Spread usato come costante. In realtà varia.
Warning: [LOW] Campione OOS (89 trade) è nella fascia bassa.
Raccomandazione: ⚠️  Procedere con test demo. Non aumentare il capitale 
                 prima di 3+ mesi di forward testing.
```

---

## 7. INTERPRETAZIONE ONESTA PER L'UTENTE

> La strategia London Breakout Pullback mostra un edge **modesto ma presente** sui dati storici.
> 
> In 4 anni di in-sample fa +38% con drawdown max del 14%. Sembra buono. Ma attenzione:
> nel periodo out-of-sample (2023-2024) il Sharpe scende a 0.64 e l'hit rate cala al 38%.
> 
> Il walk-forward dice che funziona nel 67% dei periodi — accettabile, non entusiasmante.
> 
> **Cosa significa per te:**
> - Il bot può avere edge reale, ma non è una macchina del denaro
> - Il mercato del 2023-2024 è stato diverso dal 2019-2022 per EURUSD
> - Con 89 trade OOS, le conclusioni statistiche sono ancora deboli
> 
> **Prossimi passi consigliati:**
> 1. Testa in demo per 3-4 mesi
> 2. Confronta i trade del bot con quelli che avresti fatto manualmente
> 3. Se i risultati demo sono coerenti con il backtest OOS, considera un piccolo live ($500-1000)
> 4. Non scalare il capitale prima di almeno 200 trade reali
