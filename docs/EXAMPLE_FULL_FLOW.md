# ESEMPIO COMPLETO — Da strategia discrezionale a bot MT5

Questo documento mostra un esempio reale dell'intero flusso StrategyForge,
dall'input dell'utente all'output finale.

---

## STRATEGIA IN INGRESSO (input utente)

**Nome:** London Breakout EMA con Filtro ADX

**Descritto dall'utente in linguaggio naturale:**

> "Opero su EURUSD, entro su H4 per il contesto e M15 per l'esecuzione.
> Entro long quando su H4 il prezzo è sopra la EMA50 e il mercato sembra in trend,
> poi su M15 aspetto che si formi un pullback alla EMA20 e che la candela rimbalzi.
> Entro alla chiusura della candela di rimbalzo.
> Stop loss sotto il minimo dell'ultima swing low su M15.
> Target 2:1 rispetto al rischio.
> Non opero nelle 30 minuti prima e dopo le news importanti.
> Opero solo dalle 8 alle 17 UTC, dal lunedì al giovedì.
> Rischio 1% per trade, massimo 2 trade al giorno."

---

## STEP 1 — OUTPUT DEL PARSER LLM (Claude)

### Regole già codificabili:
```json
[
  {
    "id": "rule_001",
    "description": "Prezzo sopra EMA50 su H4",
    "condition": "close_H4 > ema(close_H4, 50)",
    "parameters": {"ema_period": 50, "timeframe": "H4"}
  },
  {
    "id": "rule_002",
    "description": "Pullback alla EMA20 su M15 (prezzo tocca la EMA)",
    "condition": "low_M15 <= ema(close_M15, 20) AND close_M15 > ema(close_M15, 20)",
    "parameters": {"ema_period": 20, "timeframe": "M15"}
  },
  {
    "id": "rule_003",
    "description": "Sessione attiva",
    "condition": "hour_utc >= 8 AND hour_utc < 17 AND day_of_week IN [1,2,3,4]",
    "parameters": {"start_hour": 8, "end_hour": 17}
  },
  {
    "id": "rule_004",
    "description": "Rischio per trade",
    "condition": "lot_size = f(account_balance, 0.01, sl_distance_pips)",
    "parameters": {"risk_pct": 1.0}
  }
]
```

### Ambiguità rilevate:

**🔴 ALTA SEVERITÀ — "il mercato sembra in trend"**

*Perché non è codificabile:* "Sembrare in trend" è un giudizio soggettivo che dipende da pattern visivi,
contesto, esperienza del trader. Non c'è una soglia universale.

*Alternative proposte:*
- A: `ADX(14, H4) > 25` — ADX sopra 25 indica trend definito. Semplice e diffuso.
- B: `EMA20_H4 > EMA50_H4` — EMA corta sopra EMA lunga = contesto rialzista
- C: `close_H4 > max(high_H4, 20_bars_ago)` — prezzo sopra i massimi delle ultime 20 barre
- D: `(close_H4 - close_H4[20]) / close_H4[20] > 0.005` — rendimento positivo su 20 barre (>0.5%)

→ **Utente sceglie: B (EMA20 > EMA50 su H4)**

---

**🔴 ALTA SEVERITÀ — "la candela rimbalza"**

*Perché non è codificabile:* Un "rimbalzo" visivo può significare molte cose:
candela con wick lungo, candela di chiusura positiva, pattern specifico.

*Alternative proposte:*
- A: `close_M15 > open_M15` — candela M15 di chiusura rialzista (body verde)
- B: `close_M15 > open_M15 AND (close_M15 - low_M15) > (high_M15 - close_M15) * 1.5` — candela con chiusura nel terzo superiore
- C: `close_M15 > ema(close_M15, 20) AND close_M15[1] < ema(close_M15, 20)[1]` — crossover EMA20 verso l'alto
- D: RSI(14, M15) crosses above 50 — RSI conferma il rimbalzo

→ **Utente sceglie: C (crossover EMA20 su M15)**

---

**🟡 MEDIA SEVERITÀ — "news importanti"**

*Perché è parzialmente ambigua:* Quali news sono "importanti"? NFP, BCE, CPI, PMI?
Solo le tre stelle? Come gestire i timing?

*Alternative proposte:*
- A: Blackout manuale: l'utente disattiva il bot 30 min prima di news High Impact (calendario manuale)
- B: Blackout automatico tramite API economica (es. Forex Factory, Investing.com) — richiede integrazione
- C: Nessun filtro news automatico — l'utente gestisce manualmente come fa ora

→ **Utente sceglie: A (blackout manuale — per ora il bot non filtra le news autonomamente)**

*Nota nell'output:* "Il bot NON filtra automaticamente le news. L'utente deve disattivare AutoTrading manualmente nei periodi di alta volatilità macro."

---

**⚪ BASSA SEVERITÀ — Stop loss "sotto il minimo dell'ultima swing low"**

*Perché è lieve ambiguità:* "Swing low" può essere definito algoritmicamente, ma con parametri.

*Alternative proposte:*
- A: `min(low_M15, 3_bars_before_signal)` — minimo delle ultime 3 barre
- B: `fractal_low_M15` — fractal di Williams (minimo locale con 2 barre ai lati più alte)
- C: `atr(14, M15) * 1.5 below entry` — SL basato su ATR

→ **Utente sceglie: B (fractal low M15)**

---

### Bias warnings rilevati:
```
1. "Il trader ha fornito solo esempi di trade vincenti — rischio cherry-picking"
2. "La strategia descrive condizioni 'buone' ma non specifica cosa accade
   quando il mercato è laterale su H4 — possibile mancanza di filtro contesto"
3. "Il take profit fisso 2:1 ignora la struttura di mercato — potrebbe
   essere subottimale in mercati con livelli tecnici forti tra entry e TP"
```

---

## STEP 2 — SPECIFICA ALGORITMICA FORMALE

```json
{
  "metadata": {
    "strategy_name": "London Breakout EMA",
    "version": "1.0",
    "target_platform": "MetaTrader 5",
    "instruments": ["EURUSD"],
    "timeframes": {"analysis": "H4", "execution": "M15"}
  },
  "indicators": [
    {"id": "ema20_h4", "type": "EMA", "params": {"period": 20}, "timeframe": "H4",
     "mql5_function": "iMA(_Symbol, PERIOD_H4, 20, 0, MODE_EMA, PRICE_CLOSE)"},
    {"id": "ema50_h4", "type": "EMA", "params": {"period": 50}, "timeframe": "H4",
     "mql5_function": "iMA(_Symbol, PERIOD_H4, 50, 0, MODE_EMA, PRICE_CLOSE)"},
    {"id": "ema20_m15", "type": "EMA", "params": {"period": 20}, "timeframe": "M15",
     "mql5_function": "iMA(_Symbol, PERIOD_M15, 20, 0, MODE_EMA, PRICE_CLOSE)"}
  ],
  "entry_conditions": {
    "long": {
      "conditions": [
        {"id": "c1", "description": "EMA20 > EMA50 su H4 (contesto rialzista)",
         "mql5_expression": "ema20_h4_val > ema50_h4_val"},
        {"id": "c2", "description": "Prezzo sopra EMA50 H4",
         "mql5_expression": "close_h4 > ema50_h4_val"},
        {"id": "c3", "description": "Crossover EMA20 M15 verso l'alto (rimbalzo)",
         "mql5_expression": "close_m15[0] > ema20_m15[0] AND close_m15[1] <= ema20_m15[1]"},
        {"id": "c4", "description": "Sessione attiva",
         "mql5_expression": "IsSessionActive()"}
      ],
      "logic": "c1 AND c2 AND c3 AND c4"
    }
  },
  "stop_loss": {
    "type": "structure",
    "description": "Fractal low M15 — minimo locale con 2 barre adiacenti più alte",
    "mql5_note": "Usa iFractals() o calcolo manuale del minimo locale"
  },
  "take_profit": {
    "type": "rr_ratio",
    "rr_ratio": 2.0,
    "description": "TP = entry + (entry - SL) * 2"
  },
  "risk_management": {
    "position_sizing": "fixed_risk_pct",
    "risk_per_trade_pct": 1.0,
    "max_daily_trades": 2,
    "max_open_positions": 1
  },
  "filters": {
    "session": {"active_hours_utc": ["08:00-17:00"], "active_days": ["MON","TUE","WED","THU"]},
    "spread_max_points": 20
  },
  "non_optimizable": [
    "Il rapporto R:R di 2:1 NON va ottimizzato — è una scelta filosofica del trader",
    "Il rischio 1% per trade NON va ottimizzato — è la gestione del denaro",
    "Gli orari di sessione NON vanno ottimizzati — dipendono dalla liquidità reale del mercato"
  ]
}
```

---

## STEP 3 — BOT MQL5 GENERATO (estratto)

```mql5
//+------------------------------------------------------------------+
//| London Breakout EMA — Expert Advisor                              |
//| Generato da StrategyForge                                          |
//| ⚠️ Revisionare prima del deploy in live trading                    |
//+------------------------------------------------------------------+
#property copyright "StrategyForge"
#property version   "1.00"
#property strict

// === INPUT PARAMETERS ===
input double RiskPercent      = 1.0;    // Rischio per trade (%)
input int    EMA_Short_H4     = 20;     // EMA corta su H4
input int    EMA_Long_H4      = 50;     // EMA lunga su H4
input int    EMA_M15          = 20;     // EMA su M15 per entry
input int    MaxDailyTrades   = 2;      // Max trade al giorno
input int    SessionStartHour = 8;      // Inizio sessione UTC
input int    SessionEndHour   = 17;     // Fine sessione UTC
input int    MaxSpreadPoints  = 20;     // Spread massimo
input int    MagicNumber      = 20240101;

// === HANDLES INDICATORI ===
int h_ema_short_h4, h_ema_long_h4, h_ema_m15;
int g_daily_trades = 0;
datetime g_last_trade_day = 0;

int OnInit() {
   h_ema_short_h4 = iMA(_Symbol, PERIOD_H4, EMA_Short_H4, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_long_h4  = iMA(_Symbol, PERIOD_H4, EMA_Long_H4,  0, MODE_EMA, PRICE_CLOSE);
   h_ema_m15      = iMA(_Symbol, PERIOD_M15, EMA_M15,     0, MODE_EMA, PRICE_CLOSE);

   if(h_ema_short_h4 == INVALID_HANDLE || h_ema_long_h4 == INVALID_HANDLE || h_ema_m15 == INVALID_HANDLE) {
      Print("Errore inizializzazione indicatori");
      return(INIT_FAILED);
   }

   Print("London Breakout EMA inizializzato correttamente");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   IndicatorRelease(h_ema_short_h4);
   IndicatorRelease(h_ema_long_h4);
   IndicatorRelease(h_ema_m15);
}

void OnTick() {
   ResetDailyCounterIfNewDay();
   if(!IsSessionActive()) return;
   if(!IsSpreadOk()) return;
   if(PositionSelect(_Symbol)) return;   // già in posizione
   if(g_daily_trades >= MaxDailyTrades) return;

   // Leggi valori indicatori
   double ema_short_h4[2], ema_long_h4[2], ema_m15[2];
   if(CopyBuffer(h_ema_short_h4, 0, 0, 2, ema_short_h4) < 2) return;
   if(CopyBuffer(h_ema_long_h4,  0, 0, 2, ema_long_h4)  < 2) return;
   if(CopyBuffer(h_ema_m15,      0, 0, 2, ema_m15)      < 2) return;

   double close_h4  = iClose(_Symbol, PERIOD_H4,  0);
   double close_m15_cur  = iClose(_Symbol, PERIOD_M15, 0);
   double close_m15_prev = iClose(_Symbol, PERIOD_M15, 1);

   // === FILTRO CONTESTO H4 ===
   bool context_bullish = (ema_short_h4[0] > ema_long_h4[0]) && (close_h4 > ema_long_h4[0]);

   // === SEGNALE ENTRY M15 (crossover EMA20) ===
   bool ema_crossover_up = (close_m15_cur > ema_m15[0]) && (close_m15_prev <= ema_m15[1]);

   // === CONDIZIONE ENTRY LONG ===
   if(context_bullish && ema_crossover_up) {
      // Calcola SL basato su fractal low M15
      double sl_price = GetFractalLow(3);  // minimo delle ultime 3 barre M15
      if(sl_price <= 0) {
         Print("Fractal low non trovato, skip trade");
         return;
      }

      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(sl_price >= ask) {
         Print("SL >= entry price, skip trade anomalo");
         return;
      }

      double sl_distance = ask - sl_price;
      double tp_price = ask + sl_distance * 2.0;  // RR 2:1
      double sl_pips = sl_distance / SymbolInfoDouble(_Symbol, SYMBOL_POINT) / 10;
      double lots = CalcLotSize(sl_pips);

      Print("Segnale LONG: entry=", ask, " SL=", sl_price, " TP=", tp_price, " lots=", lots);
      OpenLong(sl_price, tp_price, lots);
   }
}

// Calcola il minimo locale (fractal semplificato) delle ultime N barre M15
double GetFractalLow(int lookback) {
   double min_low = DBL_MAX;
   for(int i = 1; i <= lookback; i++) {
      double low = iLow(_Symbol, PERIOD_M15, i);
      if(low < min_low) min_low = low;
   }
   return min_low < DBL_MAX ? min_low : 0;
}
```

---

## STEP 4 — RISULTATI BACKTEST (esempio)

### In-Sample (2020-01-01 → 2022-06-30)
| Metrica | Valore | Note |
|---------|--------|------|
| Trade totali | 187 | |
| Hit rate | 48% | Normale per strategia trend-following |
| Expectancy | +0.42 R | Ok |
| Profit Factor | 1.68 | > 1.5 è buono |
| Sharpe Ratio | 0.89 | Accettabile |
| Max Drawdown | -14.2% | |
| Rendimento totale | +34.1% | |

### Out-of-Sample (2022-07-01 → 2023-06-30) — I numeri che contano davvero
| Metrica | Valore | vs In-Sample |
|---------|--------|--------------|
| Trade totali | 73 | |
| Hit rate | 41% | ↓ -7pp — degrado |
| Expectancy | +0.21 R | ↓ dimezzato |
| Sharpe Ratio | 0.52 | ↓ calo |
| Max Drawdown | -18.6% | ↑ peggiorato |
| Rendimento totale | +11.3% | ↓ |

### Bias Check
- ✅ No look-ahead bias rilevato
- ⚠️ MEDIUM: Walk-forward efficiency 0.61 — accettabile ma non ottimo
- ⚠️ HIGH: Solo 73 trade OOS — campione limitato
- ⚠️ MEDIUM: Performance significativamente peggiore OOS vs IS — possibile parziale overfitting

### Raccomandazione finale
> "Risultati marginali. La strategia mostra un edge ma modesto e con degrado significativo
> out-of-sample. Prima di andare live: testa in demo per 2-4 mesi. Considera di semplificare
> ulteriormente la logica (meno parametri = meno overfitting). Non ottimizzare ulteriormente
> sui dati OOS — userete i test set finale per la verifica definitiva."

---

## LIMITAZIONI DICHIARATE DI QUESTA TRADUZIONE

1. **Perso nella traduzione**: Il trader discrezionale valuta anche il "momentum" visivo della candela
   di rimbalzo, la qualità del pullback, il contesto macro del giorno. Il bot non può farlo.

2. **Fractal semplificato**: Il bot usa il minimo delle ultime 3 barre invece del fractal di Williams
   completo — differenza sottile ma presente in alcuni casi.

3. **News non filtrate**: Il bot non ha accesso automatico al calendario economico. L'utente
   deve disattivare manualmente il trading prima di notizie ad alto impatto.

4. **Slippage non simulato perfettamente**: Il backtest assume fill sempre al prezzo esatto.
   In live con slippage reale i risultati saranno leggermente peggiori.

5. **OHLC M15**: Il backtest non sa in che ordine si sono mossi High e Low nella stessa candela M15.
   In casi limite (SL e TP nella stessa candela) assume sempre SL — assunzione conservativa corretta.
