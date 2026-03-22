# StrategyForge

**Traduttore tra strategia discrezionale e bot algoritmico per MetaTrader 5.**

> ⚠️ AVVERTENZA METODOLOGICA: Questo tool NON garantisce che la tua strategia sia profittevole.
> Un backtest positivo è una condizione necessaria ma NON sufficiente per il trading reale.
> Ogni parte soggettiva della tua strategia che non è codificabile andrà persa nella traduzione.

## Cosa fa StrategyForge

1. **Strategy Intake** — inserisci la strategia in linguaggio naturale via wizard guidato
2. **LLM Parsing** — Claude analizza la strategia, rileva ambiguità, propone alternative codificabili
3. **Formalizzazione** — la strategia diventa una specifica algoritmica rigorosa
4. **Bot Generation** — genera un Expert Advisor MQL5 per MetaTrader 5
5. **Backtest robusto** — in-sample, out-of-sample, walk-forward, Monte Carlo
6. **Bias Control** — controlla look-ahead, overfitting, data snooping, leakage
7. **Report completo** — Sharpe, Sortino, Calmar, drawdown, R-multiples, robustezza
8. **Guida MT5** — istruzioni passo passo per installare e testare il bot

## Stack

| Layer | Tecnologia |
|-------|-----------|
| Frontend | Next.js 14, React, TypeScript, Tailwind CSS |
| Backend | Python 3.11, FastAPI |
| Backtest Engine | Python (pandas, numpy, scipy) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 15 |
| LLM | Claude claude-sonnet-4-20250514 via Anthropic API |
| Dati storici | Polygon.io (OHLC), Dukascopy (tick/bid-ask) |
| Bot output | MQL5 / MetaTrader 5 Expert Advisor |

## Setup veloce

Vedi `docs/SETUP.md` per istruzioni complete.

```bash
# Prerequisiti: Docker, Node.js 18+, Python 3.11+
git clone <repo>
cd strategyforge
cp .env.example .env  # inserisci le tue API key
docker-compose up -d  # avvia DB + Redis
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
# Terminale 1:
cd backend && uvicorn api.main:app --reload
# Terminale 2:
cd backend && celery -A tasks.worker worker --loglevel=info
# Terminale 3:
cd frontend && npm run dev
```

## Limiti dichiarati

- Il codice MQL5 generato da LLM è un punto di partenza, NON va deployato in live senza revisione manuale
- I dati gratuiti (es. Yahoo Finance) hanno qualità inferiore per backtest seri; consigliamo Polygon.io o Dukascopy
- Il backtest non può simulare perfettamente slippage, partial fills, latenza reale
- Parti discrezionali della strategia (es. "senso di mercato", "lettura del flusso") NON sono algoritmizzabili
- Walk-forward riduce ma non elimina il rischio di overfitting
