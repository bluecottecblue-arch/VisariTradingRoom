# LIMITI TECNICI E METODOLOGICI — StrategyForge

Documento di onestà intellettuale. Leggerlo prima di usare il prodotto.

---

## Limiti del Parser LLM (Claude)

### Cosa funziona bene
- Riconoscimento di indicatori standard (EMA, RSI, MACD, ATR, Bollinger)
- Identificazione di condizioni temporali (sessioni, orari)
- Rilevamento di condizioni ovviamente non codificabili ("buon senso", "sensazione")
- Generazione di alternative concrete per ambiguità comuni

### Cosa funziona male
- Strategie molto originali o non-standard: Claude potrebbe non avere frame di riferimento
- Strategie descritte in modo molto vago (meno di 100 parole): output troppo generico
- Pattern di price action complessi (es. "terza onda di Elliott"): codificazione approssimativa
- Riferimenti a indicatori proprietari o custom: non codificabili

### Cosa non funziona
- Giudizi estetici di mercato ("grafico pulito", "setup di qualità")
- Context awareness profonda (es. "dopo una settimana di range")
- Strategie basate su order flow o footprint: non algoritmizzabili su OHLC
- Intuizioni statistiche del trader esperto non verbalizzabili

---

## Limiti del Backtester

### Inevitabili (noti, dichiarati)

**Bar ambiguity bias**: Su dati OHLC non sappiamo se nella stessa candela High si muove prima o Low.
Convenzione usata: se entrambi SL e TP vengono colpiti nella stessa candela, assume SL (conservativo).
Questo può sottostimare leggermente il profit factor.

**Slippage semplificato**: Il backtest usa uno slippage fisso costante.
Nella realtà: lo slippage varia con volatilità, liquidità, dimensione ordine, broker, orario.

**Fill garantito**: Il backtest assume che ogni ordine venga eseguito al prezzo richiesto.
Nella realtà: ordini limit possono non essere eseguiti, ordini market subiscono slippage variabile.

**Spread costante**: Usiamo spread medio. Nelle ore di bassa liquidità (apertura Tokyo, fine sessione NY)
lo spread è significativamente più alto.

**No overnight gap**: Il backtester non simula perfettamente i gap di apertura (weekend, news, halts).

### Limitabili con dati migliori

**Qualità OHLC aggregato**: I dati Polygon.io sono ottimi ma non tick reali.
Con dati Dukascopy tick-by-tick si riduce l'ambiguità intra-candela.

**Periodo limitato (piano free)**: Con Polygon free solo 2 anni. Con Starter 15+ anni.
Backtest su pochi anni possono essere regime-specific.

### Non risolvibili con questo approccio

**Struttura del mercato cambia**: Un backtest su 2020-2023 include un ciclo raro (COVID crash,
reflazione, rate hike aggressivi). Non è garantito che i parametri reggano nel prossimo ciclo.

**Impatto del tuo bot**: Se il bot viene eseguito con dimensioni significative, impatta il mercato.
Il backtest assume impact zero.

---

## Limiti del Generatore MQL5

**Il codice generato da LLM NON è production-ready senza revisione manuale.**

Problemi tipici del codice LLM-generated:
- Edge case non gestiti (es. cosa succede se il simbolo non ha storia sufficiente per l'indicatore)
- Memory management degli handle indicatori (importantissimo in MQL5)
- Gestione del requote e dell'errore 4756 (TRADE_RETCODE_REJECT)
- Algoritmi di position sizing con lotti non normalizzati al SYMBOL_VOLUME_STEP
- Mancata gestione dei tick off-quote nei periodi di bassa liquidità

**Prima del deploy in live:**
1. Far revisionare il codice a un developer MQL5 esperto
2. Compilare senza warning (0 warning, non solo 0 errori)
3. Testare su Strategy Tester con "Ogni tick basato su tick reali"
4. Testare in demo per almeno 4-8 settimane
5. Verificare ogni singolo ordine aperto in demo

---

## Limiti dei Dati Storici

| Fonte | Qualità | Limite principale |
|-------|---------|-------------------|
| Polygon.io Free | Buona | Max 2 anni storia, no bid/ask |
| Polygon.io Starter | Ottima | $29/mese, 15+ anni |
| Dukascopy | Ottima | Download manuale, solo Forex/indici |
| Demo sintetici | Nulla | Solo test UI — non usare per decisioni |

**Nessuna fonte risolve:**
- Dati pre-2010 di qualità per molti asset
- Tick data per crypto sui periodi storici
- Dati proprietari di broker specifici (spread, commissioni, rollover reali)

---

## Limiti Metodologici Fondamentali

### Il backtest non è la realtà

Un backtest è la simulazione di cosa sarebbe successo SE:
- Avessi seguito le regole ESATTAMENTE (nessun trader lo fa)
- Lo slippage fosse quello simulato (raramente vero)
- Le tue regole fossero state le stesse in tutto il periodo (raramente vero)
- Il mercato futuro si comporti come quello passato (non garantito)

### La formalizzazione non cattura l'edge discrezionale

Se la tua edge come trader discrezionale è nel "leggere il mercato" in modo sfumato,
quella edge non può essere trasmessa all'algoritmo. Il bot sarà una versione meccanica
impoverita della tua strategia. Questo è inevitabile.

### L'ottimizzazione crea illusioni

Ogni parametro ottimizzato sui dati storici riduce la credibilità del backtest.
Più parametri ottimizzi, più il backtest "vede" il futuro attraverso la scelta dei parametri.

---

## Roadmap v2 e v3

### v2 — Miglioramenti critici
- [ ] Integrazione calendario economico in tempo reale (Forex Factory API / Investing.com)
- [ ] Filtro news automatico nel bot MQL5 generato
- [ ] Supporto per strategie multi-timeframe più complesse
- [ ] Ottimizzazione bayesiana dei parametri (meno data snooping)
- [ ] Analisi di stabilità per regime (trend/range/alta-bassa volatilità)
- [ ] Report PDF professionale con grafici
- [ ] Supporto MT4 (MQL4 generator)

### v3 — Funzionalità avanzate
- [ ] Connessione diretta a broker per paper trading automatico
- [ ] Monitoraggio live delle performance del bot
- [ ] Portfolio di bot con correlazione e risk management a livello portfolio
- [ ] Integrazione con VPS per esecuzione 24/7
- [ ] Supporto per strategie su indici, crypto (Binance, Bybit)
- [ ] Comunità: condivisione (anonimizzata) di strategie e benchmark
- [ ] Fine-tuning del modello LLM su dataset di strategie reali annotate

### Cosa NON farà mai StrategyForge
- Garantire profitti o performance future
- Sostituire la revisione umana del codice MQL5
- Essere un segnale di trading autonomo
- Operare senza la supervisione del trader
