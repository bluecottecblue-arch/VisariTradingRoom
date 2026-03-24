/**
 * API Client — Wrapper centralizzato per tutte le chiamate al backend
 * Gestisce errori, timeout e headers comuni
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_PROXY_BASE || '/api/backend'

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = 120_000,
): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const url = `${BASE_URL}${path}`
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      signal: controller.signal,
      credentials: 'include',
      ...options,
    })

    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body.detail || JSON.stringify(body)
      } catch {
        detail = await res.text().catch(() => detail)
      }
      throw new ApiError(res.status, detail)
    }

    return res.json() as Promise<T>
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError(408, 'Richiesta scaduta — il server ha impiegato troppo. Riprova.')
    }
    if (e instanceof TypeError && e.message.includes('fetch')) {
      throw new ApiError(503, 'Connessione al server persa o backend non raggiungibile. Controlla la rete e riprova.')
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

// ─── Strategy endpoints ───────────────────────────────────────────────────────

export const strategyApi = {
  preflight: (intake: object) =>
    request('/api/strategy/preflight', { method: 'POST', body: JSON.stringify(intake) }, 30_000),

  parse: (intake: object) =>
    request('/api/strategy/parse', { method: 'POST', body: JSON.stringify(intake) }),

  resolveAmbiguities: (sessionId: string, resolutions: Record<string, string>) =>
    request('/api/strategy/resolve-ambiguities', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, resolutions }),
    }),

  generateBot: (sessionId: string) =>
    request(`/api/strategy/generate-bot?session_id=${sessionId}`, { method: 'POST' }),

  getSession: (sessionId: string) =>
    request(`/api/strategy/session/${sessionId}`),
}

// ─── Backtest endpoints ───────────────────────────────────────────────────────

export const backtestApi = {
  run: (sessionId: string, config: object) =>
    request('/api/backtest/run', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, config }),
    }),

  status: (taskId: string) =>
    request(`/api/backtest/status/${taskId}`),

  providers: () =>
    request('/api/backtest/providers'),
}

export const botLabApi = {
  upload: (payload: object) =>
    request('/api/bot-lab/upload', { method: 'POST', body: JSON.stringify(payload) }),

  modify: (payload: object) =>
    request('/api/bot-lab/modify', { method: 'POST', body: JSON.stringify(payload) }),

  session: (sessionId: string) =>
    request(`/api/bot-lab/session/${sessionId}`),

  calendarProviders: () =>
    request('/api/bot-lab/calendar/providers'),

  previewCalendar: (payload: object) =>
    request('/api/bot-lab/calendar/preview', { method: 'POST', body: JSON.stringify(payload) }),
}

// ─── Export endpoints ─────────────────────────────────────────────────────────

export const exportApi = {
  saveMql5: (sessionId: string, code: string) =>
    request(`/api/export/mql5/${sessionId}`, {
      method: 'POST',
      body: JSON.stringify({ mql5_code: code }),
    }),

  bundleInfo: (sessionId: string) =>
    request(`/api/export/bundle/${sessionId}`),

  downloadMql5Url: (sessionId: string) =>
    `${BASE_URL}/api/export/mql5/${sessionId}`,

  reportUrl: (sessionId: string) =>
    `${BASE_URL}/api/export/report/${sessionId}`,

  bundleSetupUrl: (sessionId: string) =>
    `${BASE_URL}/api/export/bundle/${sessionId}/setup.txt`,

  bundleManifestUrl: (sessionId: string) =>
    `${BASE_URL}/api/export/bundle/${sessionId}/manifest.json`,
}

// ─── Health check ─────────────────────────────────────────────────────────────

export const healthApi = {
  check: () => request<{ status: string }>('/health'),
}

export function formatError(e: unknown): string {
  if (e instanceof ApiError) return `Errore ${e.status}: ${e.detail}`
  if (e instanceof Error) return e.message
  return 'Errore sconosciuto'
}

export { ApiError }
