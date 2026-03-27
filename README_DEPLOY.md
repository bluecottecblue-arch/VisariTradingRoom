# VisariTradingRoom — Deploy rapido

Deploy gratuito e personale:

- Frontend: Vercel Hobby
- Backend: Render Free Web Service
- Persistenza: stateless/in-memory se non configuri un DB

## 1. Backend su Render

- Crea un nuovo `Web Service` dal repository.
- Render leggerà `render.yaml`.
- Variabili da impostare:
  - `ANTHROPIC_API_KEY` opzionale
    - utile per manutenzione interna, test admin o fallback operativo
    - la UI pubblica usa solo Claude key personale inserita dall'utente
  - `POLYGON_API_KEY` opzionale
  - `SESSION_SECRET`
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - `DATABASE_URL` consigliata
    - senza DB il backend degrada in memoria e perde persistenza professionale su progetti/versioni/job
  - `USERS_STORAGE_PATH`
    - valore consigliato: `./storage/users.json`
  - `PERSISTENT_STORAGE_PATH` opzionale ma consigliata
    - se la imposti, backend e fallback utenti salvano tutto lì
    - in alternativa, se usi un disco Render montato su `/var/data`, il backend lo rileva automaticamente
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
- Se il database non è disponibile, il backend ora usa davvero il fallback su `users.json` invece di mostrare una lista utenti vuota.
- La soluzione resta semplice: adatta a pochi clienti, non enterprise.

## 4. Claude key personale

- La piattaforma pubblica non propone più una Claude key condivisa/integrata.
- Ogni utente deve inserire la propria Claude API key nel workflow di creazione strategia o Bot Lab.
- La Claude key del backend, se configurata, resta solo un'opzione operativa per manutenzione interna e non viene esposta in UI.

## 5. Persistenza professionale

- Per uso demo il sistema continua a funzionare anche senza database.
- Per uso professionale vero è fortemente consigliato configurare `DATABASE_URL`.
- Se non configuri `DATABASE_URL`, il backend usa SQLite nella storage root attiva.
- Se lo storage è locale/effimero, utenti e dati possono ancora sparire dopo restart o redeploy.
- Per evitare questo senza Postgres, usa almeno un path persistente:
  - `PERSISTENT_STORAGE_PATH`
  - oppure un disk Render montato su `/var/data`
- Con DB attivo vengono persistiti:
  - utenti e stato account
  - progetti
  - versioni
  - artifact export
  - job status

## 6. Fallback locale

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
