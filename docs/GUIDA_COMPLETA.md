# StrategyForge — Guida Completa

## PARTE 1 — Setup locale (per chi installa il progetto)

### Prerequisiti

Prima di iniziare, assicurati di avere installato:

| Strumento | Versione minima | Come verificare |
|-----------|----------------|-----------------|
| Node.js   | 18+            | `node --version` |
| Python    | 3.11+          | `python --version` |
| Docker    | 24+            | `docker --version` |
| Git       | qualsiasi      | `git --version` |

### Step 1 — Clona il progetto

```bash
git clone https://github.com/tuousername/strategyforge.git
cd strategyforge
```

### Step 2 — Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Apri `.env` con un editor di testo e compila:

```
ANTHROPIC_API_KEY=sk-ant-...     ← OBBLIGATORIO
POLYGON_API_KEY=...               ← Opzionale (per dati reali)
```

**Come ottenere la Anthropic API key:**
1. Vai su https://console.anthropic.com
2. Registrati (o accedi)
3. Vai su "API Keys" → "Create Key"
4. Copia la chiave e incollala nel file .env

**Come ottenere la Polygon.io API key:**
1. Vai su https://polygon.io
2. Registrati gratuitamente
3. Il piano gratuito include dati limitati — per backtest seri usa il piano Starter ($29/mese)
4. Copia la API Key e incollala nel file .env

### Step 3 — Avvia il database e Redis

```bash
docker-compose up -d postgres redis
```

Verifica che siano avviati:
```bash
docker ps
# Dovresti vedere: strategyforge_postgres_1 e strategyforge_redis_1
```

### Step 4 — Installa e avvia il backend Python

```bash
cd backend
python -m venv venv

# Su Mac/Linux:
source venv/bin/activate
# Su Windows:
venv\Scripts\activate

pip install -r requirements.txt

# Avvia il server FastAPI
uvicorn api.main:app --reload --port 8000
```

Verifica: apri http://localhost:8000/health — deve rispondere `{"status": "ok"}`

### Step 5 — Avvia il worker Celery (per task asincroni)

Apri un NUOVO terminale (lascia il precedente con il server):

```bash
cd backend
source venv/bin/activate  # o venv\Scripts\activate su Windows
celery -A tasks.worker worker --loglevel=info --concurrency=2
```

### Step 6 — Installa e avvia il frontend

Apri un TERZO terminale:

```bash
cd frontend
npm install
npm run dev
```

Apri http://localhost:3000 — dovresti vedere l'interfaccia di StrategyForge.

### Risoluzione problemi comuni

**"Connection refused" al database:**
```bash
docker-compose up -d postgres redis
# Aspetta 10 secondi poi riprova
```

**"ANTHROPIC_API_KEY not set":**
Verifica che il file .env esista e contenga la chiave corretta.
Riavvia il server dopo aver modificato .env.

**Errori npm install:**
```bash
rm -rf node_modules package-lock.json
npm install
```

**Port già in uso:**
```bash
# Trova e termina il processo sulla porta 8000
lsof -i :8000 | grep LISTEN
kill -9 <PID>
```

---

## PARTE 2 — Guida utente completa

### Come usare StrategyForge — passo per passo

#### Prima di iniziare: cosa ti serve

- La tua strategia di trading descritta per iscritto (anche in modo approssimativo)
- Se possibile: 2-3 esempi di trade reali che hai fatto (anche senza dati precisi)
- Circa 1 ora di tempo per il primo utilizzo completo

#### Step 1: Descrivi la tua strategia

Quando apri StrategyForge, ti trovi davanti a un modulo guidato.

**Campo "Setup di ingresso LONG"** — è il più importante. Scrivi esattamente quello che fai:

*Esempio pessimo (vago):*
> "Entro quando il mercato è bullish"

*Esempio buono (specifico):*
> "Entro long quando su H4 vedo un livello di supporto chiaro con almeno 2 test precedenti,
> il prezzo rimbalza con una candela engulfing bullish, e su M15 il prezzo chiude sopra
> la EMA20 nelle prime 2 ore della sessione di Londra"

Non preoccuparti se non sai se è "algoritmizzabile". Claude capirà cosa è codificabile
e cosa no, e te lo spiegherà.

**Esempi di trade** — fondamentali. Se ricordi anche solo approssimativamente:
- Data o periodo
- Direzione (long/short)
- Perché hai aperto il trade
- Cosa è successo
- Perché hai chiuso

Questo aiuta Claude a capire la tua logica reale, non quella che pensi di avere.

#### Step 2: Rivedi l'analisi di Claude

Claude ti mostra:
- **Regole già codificabili**: le parti della tua strategia che diventano automaticamente condizioni booleane
- **Ambiguità**: le parti soggettive, con 2-5 alternative oggettive tra cui scegliere
- **Bias cognitivi rilevati**: osservazioni oneste sulla tua descrizione

**Per ogni ambiguità**, devi scegliere un'alternativa. Esempio reale:

*Ambiguità:* "Entro solo quando il mercato ha 'momentum'"

*Alternative proposte:*
1. RSI(14) > 60 sulla chiusura della candela
2. Rate of Change (ROC) a 10 periodi > 0.5%
3. Prezzo > EMA50 E EMA50 in salita (slope positivo)
4. Volume relativo > 1.5x la media degli ultimi 20 periodi

Nessuna di queste replica perfettamente la tua sensazione di "momentum" — ma è il compromesso inevitabile della traduzione algoritmica.

**Se nessuna alternativa ti soddisfa:** puoi saltare la regola. Questo significa che quella parte della tua edge non sarà nel bot — è un dato di fatto, non un fallimento del tool.

#### Step 3: Verifica la specifica formale

Prima di generare il codice, ti viene mostrata la specifica algoritmica completa:
- Tutti gli indicatori con i parametri esatti
- La logica di entry/exit in formato booleano
- La macchina a stati del bot
- I parametri ottimizzabili (e quelli che NON devi ottimizzare)

**Leggila attentamente.** Se c'è qualcosa che non corrisponde alla tua logica reale, torna indietro.

#### Step 4: Configura e avvia il backtest

**Scelta della fonte dati:**
- Per un primo test usa i "Dati demo" — capisci il flusso senza spendere soldi
- Per un backtest reale usa Polygon.io o Dukascopy
- Non fare mai decisioni reali su dati demo

**Split temporale — la cosa più importante:**
- In-sample (es. 2018-2022): dati su cui il bot viene sviluppato
- Out-of-sample (es. 2023-2024): dati mai visti prima, usati SOLO per la valutazione finale

Il out-of-sample è l'unico numero che conta veramente.

**Costi di esecuzione:** metti sempre spread e slippage reali del tuo broker.
Spread a zero = risultati falsati.

#### Step 5: Interpreta i risultati

**Leggi PRIMA il bias check, poi le metriche.**

Se il bias check segnala problemi CRITICI, le metriche sotto non hanno valore —
anche se sembrano fantastiche.

**Metriche minime accettabili:**
| Metrica | Minimo | Buono | Ottimo |
|---------|--------|-------|--------|
| Sharpe Ratio | 0.5 | 1.0 | 1.5+ |
| Profit Factor | 1.2 | 1.5 | 2.0+ |
| Max Drawdown | < 30% | < 20% | < 10% |
| Hit Rate | > 30% | > 45% | > 55% |
| Trade totali | > 100 | > 200 | > 500 |

**Walk-forward:** se il bot è profittevole nel 70%+ dei periodi out-of-sample,
è un buon segnale di robustezza.

**Monte Carlo:** guarda il P5 (scenario peggiore 5%). Se lì vedi ancora un capital
superiore al tuo investimento, la strategia è abbastanza robusta.

#### Step 6: Scarica e installa il bot

Dopo il backtest, puoi scaricare:
- Il file `.mq5` — il codice Expert Advisor per MetaTrader 5
- Il report completo del backtest in JSON

Per l'installazione su MT5: vedi la Parte 3 qui sotto.

---

## PARTE 3 — Guida MetaTrader 5 passo per passo

### Cos'è MetaTrader 5

MetaTrader 5 (MT5) è il software di trading più usato al mondo per Forex e CFD.
È gratuito e fornito dai broker. Funziona su Windows, Mac (con limitazioni), iOS e Android.

**MT5 ≠ il tuo broker.** MT5 è il cruscotto; il broker gestisce i tuoi soldi.

### Download e installazione

1. Vai su https://www.metatrader5.com/en/download
2. Clicca "Download MetaTrader 5 for Windows"
3. Apri il file `mt5setup.exe` scaricato
4. Segui la procedura guidata (Avanti → Avanti → Fine)
5. MT5 si avvierà automaticamente alla fine

**Primo avvio — apri un conto demo:**
1. MT5 ti chiede di accedere o aprire un conto
2. Scegli il tuo broker dall'elenco (o cerca per nome)
3. Seleziona "Open a demo account"
4. Compila il modulo (nome, email, importo virtuale)
5. Riceverai login e password via email

### Installare il tuo Expert Advisor

**Passo 1 — Trova la cartella degli EA:**
- In MT5: menu `File` → `Open Data Folder`
- Si apre Windows Explorer
- Naviga in: `MQL5` → `Experts`

**Passo 2 — Copia il file .mq5:**
- Prendi il file scaricato da StrategyForge
- Copialo nella cartella `Experts`

**Passo 3 — Compila con MetaEditor:**
- In MT5: menu `Tools` → `MetaQuotes Language Editor` (o premi F4)
- Nel Navigator a sinistra: `Expert Advisors` → trova il tuo file
- Doppio clic per aprirlo
- Premi F7 o clicca l'icona "Compile"
- Controlla il pannello "Errors" in basso: deve dire `0 errors, 0 warnings`

**Passo 4 — Attiva AutoTrading:**
- In MT5, toolbar in alto: pulsante "AutoTrading"
- Deve essere verde (attivo)
- Se è grigio/rosso: il bot non potrà fare trade

**Passo 5 — Allega l'EA al grafico:**
- Apri il grafico del tuo strumento (es. EURUSD)
- Imposta il timeframe corretto (es. H1)
- Nel pannello Navigator: `Expert Advisors` → trascina l'EA sul grafico
- Si apre la finestra di configurazione
- Tab "Common": spunta "Allow Automated Trading"
- Tab "Inputs": configura i parametri (usa i valori suggeriti da StrategyForge)
- Clicca OK

**Verifica finale:**
- In alto a destra del grafico: vedi il nome dell'EA
- Deve esserci una **faccina sorridente** 😊
- Faccina triste = problema → controlla AutoTrading e le impostazioni

### Backtest nel Strategy Tester di MT5

1. Menu `View` → `Strategy Tester` (o Ctrl+R)
2. Seleziona il tuo EA nel menu
3. Imposta: Symbol, Period (timeframe), Model (usa "Every tick"), Date range
4. Imposta Deposit e Currency
5. Clicca "Start"
6. Quando finisce, guarda i tab: Results, Graph, Report

**Cosa guardare nel Report:**
- Profit Factor > 1.3
- Sharpe Ratio > 1.0
- Max Drawdown < 30%
- Total Net Profit positivo

### Regole d'oro per il test in demo

1. **Minimo 3 mesi di demo** prima di considerare il live
2. **Controlla ogni giorno**: faccina sorridente? AutoTrading attivo? Errori nel Journal?
3. **Confronta con le aspettative**: il bot fa quello che il backtest prevedeva?
4. **Non modificare i parametri** durante il periodo di test demo — invalidi i risultati
5. **Se il bot fa cose strane**: fermalo (rimuovi dal grafico) e analizza prima di riavviarlo
6. **Non passare al live** finché non hai almeno 50-100 trade reali in demo con risultati coerenti

---

## PARTE 4 — Limiti tecnici e metodologici

Questi limiti sono reali e non negoziabili. Conoscerli è parte fondamentale
dell'uso responsabile dello strumento.

### Limiti del parsing LLM

- Claude non può codificare intuizioni puramente sensoriali o esperienziali
- La qualità dell'output dipende dalla qualità e specificità dell'input
- Claude può interpretare erroneamente alcune descrizioni ambigue
- **Revisione umana obbligatoria** della specifica formale generata

### Limiti del backtest

- I dati OHLC non rivelano l'ordine intra-candela di High e Low
- Slippage simulato con costante — in realtà è variabile e dipende dalla liquidità
- Fill sempre eseguito al prezzo richiesto (ottimistico)
- Spread fisso — in realtà varia durante la giornata e nei periodi di volatilità
- Nessuna simulazione di partial fill o reject di ordini
- I dati storici Forex non includono il book reale con cui avresti tradato

### Limiti del codice MQL5 generato

- Il codice generato da LLM ha bisogno di revisione manuale da un developer MQL5
- Potrebbero esserci edge case non gestiti (gap di mercato, simboli diversi, ecc.)
- Il codice non è ottimizzato per performance (ma è leggibile)
- Non gestisce automaticamente: rollover, dividendi (se applicabili), cambio di margine

### Limiti metodologici fondamentali

- **Un backtest positivo NON implica edge reale** — è una condizione necessaria ma non sufficiente
- **Walk-forward riduce ma non elimina** il rischio di overfitting
- **La strategia algoritmizzata ≠ la strategia discrezionale** — parte dell'edge va sempre perduta
- **Il mercato cambia**: una strategia robusta su 2019-2023 potrebbe non funzionare nel 2025
- **La lunghezza del track record conta**: 100 trade sono pochissimi per conclusioni statistiche

### Idee per versioni future

**v2:**
- Integrazione diretta con MT5 via API (senza export manuale)
- Support per più piattaforme: cTrader, Interactive Brokers
- Report PDF professionale con grafici
- Confronto automatico tra strategia discrezionale e algoritmica su stesso periodo
- Ottimizzatore genetico integrato con protezione anti-overfitting

**v3:**
- Dati tick reali integrati (non solo OHLC)
- Live trading dashboard con monitoring real-time
- Alert se il bot diverge dalle aspettative del backtest
- Community di strategie anonimizzate con metriche pubbliche
- Support per machine learning (solo per utenti avanzati, con disclaimer forti)
