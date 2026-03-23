# VisariTradingRoom — Deploy rapido

Deploy gratuito e personale:

- Frontend: Vercel Hobby
- Backend: Render Free Web Service
- Persistenza: stateless/in-memory se non configuri un DB

## 1. Backend su Render

- Crea un nuovo `Web Service` dal repository.
- Render leggerà `render.yaml`.
- Variabili da impostare:
  - `ANTHROPIC_API_KEY`
  - `POLYGON_API_KEY` opzionale
  - `SESSION_SECRET`
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - `USERS_STORAGE_PATH`
    - valore consigliato: `./storage/users.json`
  - `CORS_ALLOW_ORIGINS`
    - valore consigliato iniziale: `https://TUO-FRONTEND.vercel.app`
  - `CORS_ALLOW_ORIGIN_REGEX`
    - valore consigliato: `https://.*\\.vercel\\.app`

Comportamento atteso:
- start command: `./start.sh`
- health check: `/health`
- auto deploy: attivo su push a `main` se il servizio Render è collegato al repository
- backend stateless se il DB non è disponibile

## 2. Frontend su Vercel

- Crea un nuovo progetto dal repository.
- Imposta `Root Directory` su `frontend`.
- Framework: Next.js.
- Variabili da impostare:
  - `NEXT_PUBLIC_API_BASE_URL`
    - URL pubblico Render, ad esempio `https://visari-trading-room-api.onrender.com`
  - `NEXT_PUBLIC_API_PROXY_BASE`
    - lascia `'/api/backend'` oppure non impostarla

## 3. Login utenti

- L'app reindirizza a `/login` se non esiste una sessione utente valida.
- Il pannello admin è su `/admin` con login separato su `/admin/login`.
- Gli account cliente sono salvati dal backend in `users.json`.
- La soluzione è intenzionalmente semplice: adatta a pochi clienti, non enterprise.

## 4. Fallback locale

Backend:

```bash
cd backend
source .venv/bin/activate
./start.sh
```

Frontend:

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```
