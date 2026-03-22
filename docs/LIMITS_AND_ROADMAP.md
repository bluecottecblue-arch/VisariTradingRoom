# Limiti tecnici e metodologici — StrategyForge

## ⚠️ Limitazioni critiche da comunicare sempre all'utente

### 1. La traduzione discrezionale → algoritmica è SEMPRE un'approssimazione

Molte edge discrezionali vengono da:
- Esperienza non codificabile ("senso del mercato")
- Pattern visivi complessi ("candlestick con wick lungo e corpo piccolo in zona di interesse")
- Giudizio contestuale ("questo breakout sembra falso")
- Lettura del flusso ordini

Nessuna di queste cose è algoritmizzabile con certezza.
Il bot traduce la strategia con la massima fedeltà possibile,
ma la distanza dalla strategia originale può essere significativa.

### 2. Il codice MQL5 generato da LLM non è production-ready

Claude genera codice MQL5 valido, ma:
- Non è stato testato su tutti i broker/simboli/configurazioni
- Può contenere bug sottili che emergono solo in condizioni specifiche
- La gestione degli errori potrebbe essere insufficiente
- Non è ottimizzato per performance

**Raccomandazione:** Far rivedere il codice da un developer MQL5 certificato prima del deploy live.

### 3. Il backtest su OHLC ha limitazioni intrinseche

**Problema dell'ordine High/Low nella stessa candela:**
Su una candela H4, non sappiamo se il High o il Low si è mosso per primo.
Se SL e TP sono entrambi nella stessa candela, il motore assume sempre SL (assunzione conservativa),
ma il comportamento reale varia. Questo introduce un bias sistematico.

**Soluzione:** Tick data o bid/ask data riducono questo problema ma non lo eliminano.

**Slippage simulato:**
Lo slippage reale è variabile, non costante. Dipende da:
- Liquidità del momento
- Dimensione dell'ordine
- Condizioni di mercato (notizie, apertura sessione)

Un backtest non può replicare queste condizioni perfettamente.

### 4. I dati gratuiti hanno qualità limitata

| Provider | Qualità | Limite piano gratuito |
|----------|---------|----------------------|
| Polygon.io free | Buona (OHLC) | 2 anni storia, rate limit |
| Dukascopy | Ottima (tick/bid-ask) | Download manuale, lento |
| yfinance | Mediocre | Solo per azioni su D1+ |

Per backtest seri su FX raccomandato:
- Polygon Starter ($29/mese) oppure
- Dukascopy scaricato localmente

### 5. Walk-forward non elimina il rischio di overfitting

Walk-forward riduce significativamente il rischio, ma non è una garanzia.
Con abbastanza periodi di walk-forward e abbastanza tentativi,
si può comunque trovare una configurazione che "funziona" per puro caso.

**La vera validazione** è il forward test in condizioni reali di mercato,
su account demo, per almeno 3-6 mesi.

### 6. Il sistema non gestisce eventi di mercato straordinari

- Flash crash (es. CHF 2015)
- Gap di liquidità estremi
- Halt del trading
- Cambiamenti di regime strutturali del mercato

Il backtest non può simulare questi eventi.

---

## 🔮 Idee per V2

### V2.1 — Qualità del codice
- [ ] Unit test automatici per ogni EA generato
- [ ] Validazione del codice MQL5 tramite compilatore headless
- [ ] Generazione di test case per ogni condizione di ingresso/uscita
- [ ] Confronto automatico tra comportamento atteso e codice generato

### V2.2 — Backtest avanzato
- [ ] Integrazione tick data da Dukascopy in modo automatizzato
- [ ] Supporto per bid/ask separati (simulazione spread variabile)
- [ ] Regime detection automatico (trend/range/alta volatilità)
- [ ] Analisi di sensitività automatica su tutti i parametri
- [ ] Benchmark contro strategia buy-and-hold e trend following semplice

### V2.3 — Multi-asset e portafoglio
- [ ] Backtest su multipli strumenti simultaneamente
- [ ] Correlation analysis tra strumenti
- [ ] Portfolio-level risk management
- [ ] Diversification score

### V2.4 — Connessione live
- [ ] Integrazione diretta con MT5 via Python API (MT5 offre libreria Python ufficiale)
- [ ] Forward test automatizzato con dashboard risultati real-time
- [ ] Alert quando il comportamento live diverge dal backtest
- [ ] Auto-stop se drawdown supera soglia definita

### V2.5 — UX e collaborazione
- [ ] Salvataggio e versionamento delle strategie
- [ ] Confronto tra versioni della stessa strategia
- [ ] Export della specifica formale in formato JSON/YAML standardizzato
- [ ] Import da specifiche esterne
- [ ] Community di strategie (anonimizzate)

### V2.6 — Analisi più sofisticata
- [ ] Integrazione dati macro (calendar economico) nel backtest
- [ ] Analisi per sessione (Asia/Londra/New York) automatica
- [ ] Stability by market regime (ADX buckets)
- [ ] Rolling Sharpe ratio nel tempo
- [ ] Correlazione performance / VIX o volatilità implicita

---

## 🚫 Cosa NON farà mai StrategyForge (per principio)

1. **Non garantirà mai che una strategia sia profittevole** — chiunque affermi questo mente
2. **Non permetterà di saltare la fase di test in demo** — è non negoziabile per la sicurezza dell'utente
3. **Non nasconderà i bias del backtest** — trasparenza metodologica sempre
4. **Non ottimizzerà automaticamente i parametri** — troppo alto il rischio di curve fitting senza supervisione
5. **Non si connette mai automaticamente a un account live** — richiede sempre azione esplicita dell'utente
