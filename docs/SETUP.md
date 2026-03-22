# GUIDA DI SETUP LOCALE — StrategyForge

Questa guida ti porta da zero a StrategyForge funzionante in locale.
Non dà nulla per scontato.

---

## Prerequisiti

Installa questi strumenti se non li hai già:

| Tool | Versione minima | Download |
|------|----------------|---------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org |
| Docker Desktop | Ultima | https://www.docker.com/products/docker-desktop |
| Git | Qualsiasi | https://git-scm.com |

**Verifica installazioni:**
```bash
python --version    # deve mostrare 3.11+
node --version      # deve mostrare 18+
docker --version    # qualsiasi
```

---

## Step 1 — Clona il progetto

```bash
git clone https://github.com/tuouser/strategyforge.git
cd strategyforge
```

Se non hai ancora un repo, crea la struttura manualmente dalla cartella scaricata.

---

## Step 2 — Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Apri `.env` con qualsiasi editor di testo e compila:

```
ANTHROPIC_API_KEY=sk-ant-...     ← Obbligatoria. Vai su console.anthropic.com
POLYGON_API_KEY=...              ← Per dati reali. Puoi usare "demo" senza di questa.
```

**Dove trovare le API key:**

1. **Anthropic** → https://console.anthropic.com → API Keys → Create Key
   Costo indicativo: ~$0.003 per parsing strategia, ~$0.015 per generazione bot

2. **Polygon.io** → https://polygon.io → Sign Up (piano free sufficiente per iniziare)
   Piano free: 2 anni di dati OHLC. Piano Starter ($29/mese): 15+ anni.

---

## Step 3 — Avvia database e Redis con Docker

```bash
docker-compose up -d postgres redis
```

Verifica che siano partiti:
```bash
docker-compose ps
# Deve mostrare postgres e redis con status "Up"
```

Attendi 10-15 secondi che PostgreSQL finisca di inizializzare.

---

## Step 4 — Setup backend Python

```bash
cd backend

# Crea ambiente virtuale (fortemente consigliato)
python -m venv venv

# Attiva l'ambiente virtuale
# Su Windows:
venv\Scripts\activate
# Su Mac/Linux:
source venv/bin/activate

# Installa le dipendenze
pip install -r requirements.txt
```

**Possibili errori:**
- `psycopg2 install failed` → Installa `brew install postgresql` (Mac) o `apt install libpq-dev` (Linux)
- `numpy install failed` → Aggiorna pip: `pip install --upgrade pip`

---

## Step 5 — Setup frontend Node.js

```bash
# Dalla root del progetto (non da backend/)
cd frontend
npm install
```

Ignora gli eventuali warning npm — non sono errori bloccanti.

---

## Step 6 — Avvia tutti i servizi

Apri **tre terminali separati**:

**Terminale 1 — Backend API:**
```bash
cd backend
source venv/bin/activate  # o venv\Scripts\activate su Windows
uvicorn api.main:app --reload --port 8000
```
Dovresti vedere: `Application startup complete.`
Testa aprendo http://localhost:8000/health nel browser.

**Terminale 2 — Celery Worker (backtest asincrono):**
```bash
cd backend
source venv/bin/activate
celery -A tasks.worker worker --loglevel=info --concurrency=2
```
Dovresti vedere: `celery@... ready.`

**Terminale 3 — Frontend:**
```bash
cd frontend
npm run dev
```
Dovresti vedere: `✓ Ready on http://localhost:3000`

---

## Step 7 — Verifica finale

Apri http://localhost:3000 nel browser.

Dovresti vedere l'interfaccia StrategyForge con il wizard in 6 step.

Clicca http://localhost:8000/docs per vedere la documentazione interattiva dell'API.

---

## Struttura finale delle cartelle

```
strategyforge/
├── .env                          ← Le tue API key (NON committare su Git)
├── .env.example                  ← Template variabili d'ambiente
├── docker-compose.yml            ← PostgreSQL + Redis
├── README.md
│
├── backend/
│   ├── api/
│   │   ├── main.py              ← FastAPI app entry point
│   │   └── routers/
│   │       ├── strategy.py      ← Parsing + formalizzazione + bot generation
│   │       ├── backtest.py      ← Configurazione ed esecuzione backtest
│   │       ├── export.py        ← Download .mq5 e report PDF/HTML
│   │       └── guide.py         ← Guida MT5 strutturata
│   │
│   ├── modules/
│   │   ├── parser/
│   │   │   └── strategy_parser.py    ← LLM parsing con Claude API
│   │   ├── formalizer/
│   │   │   └── formalizer.py         ← Specifica algoritmica formale
│   │   ├── botgen/
│   │   │   └── mql5_generator.py     ← Generazione codice MQL5
│   │   ├── backtest/
│   │   │   ├── engine.py             ← Motore backtest event-driven
│   │   │   └── data_provider.py      ← Polygon.io + Dukascopy + demo
│   │   └── bias/
│   │       └── bias_checker.py       ← Controllo look-ahead, overfitting, ecc.
│   │
│   ├── db/
│   │   ├── init.sql             ← Schema PostgreSQL
│   │   └── database.py          ← Connection pool SQLAlchemy
│   ├── tasks/
│   │   └── worker.py            ← Celery task per backtest asincrono
│   └── requirements.txt
│
└── frontend/
    └── src/
        ├── app/
        │   └── page.tsx         ← Wizard principale (6 step)
        └── components/wizard/
            ├── StepIntake.tsx       ← Step 1: input strategia
            ├── StepAmbiguities.tsx  ← Step 2: risoluzione ambiguità
            ├── StepFormalSpec.tsx   ← Step 3: revisione specifica formale
            ├── StepBacktest.tsx     ← Step 4: configurazione e avvio backtest
            ├── StepBot.tsx          ← Step 5: visualizzazione e download bot
            └── StepGuide.tsx        ← Step 6: guida installazione MT5
```

---

## Troubleshooting

**"ANTHROPIC_API_KEY non configurata"**
→ Verifica che `.env` sia nella root del progetto e che la key sia corretta

**"Connection refused" sulla porta 5432**
→ `docker-compose up -d postgres` e aspetta 15 secondi

**"Module not found" in Python**
→ Sei nell'ambiente virtuale? (`source venv/bin/activate`)

**Frontend non si connette al backend**
→ Verifica che backend giri su porta 8000 (`uvicorn ... --port 8000`)
→ Verifica `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env`

**Celery non parte**
→ Redis deve essere avviato: `docker-compose up -d redis`
