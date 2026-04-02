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
  const onExternalAbort = () => controller.abort()
  if (options.signal) {
    options.signal.addEventListener('abort', onExternalAbort)
  }
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const url = `${BASE_URL}${path}`
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      credentials: 'include',
      ...options,
      signal: controller.signal,
    })

    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        detail = body?.detail || body?.error || JSON.stringify(body)
      } catch {
        detail = await res.text().catch(() => detail)
      }
      throw new ApiError(res.status, detail)
    }

    const text = await res.text()
    if (!text) return {} as T
    try {
      return JSON.parse(text) as T
    } catch {
      return text as unknown as T
    }
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
    if (options.signal) {
      options.signal.removeEventListener('abort', onExternalAbort)
    }
  }
}

// ─── Strategy endpoints ───────────────────────────────────────────────────────

export const authApi = {
  me: () =>
    request<{
      authenticated: boolean
      username: string | null
      role: string | null
      ai_provider?: string
      claude_key_configured?: boolean
      openai_key_configured?: boolean
      google_key_configured?: boolean
    }>('/api/auth/me', {}, 10_000),
  logout: () =>
    request('/api/auth/logout', { method: 'POST' }),
}

export const strategyApi = {
  preflight: (intake: object, options?: RequestInit) =>
    request('/api/strategy/preflight', { method: 'POST', body: JSON.stringify(intake), ...options }, 30_000),

  parse: (intake: object) =>
    request('/api/strategy/parse', { method: 'POST', body: JSON.stringify(intake) }),

  resolveAmbiguities: (sessionId: string, resolutions: Record<string, string>, missingInputs?: Record<string, string>) =>
    request('/api/strategy/resolve-ambiguities', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, resolutions, missing_inputs: missingInputs || {} }),
    }),

  generateBot: (sessionId: string) =>
    request(`/api/strategy/generate-bot?session_id=${sessionId}`, { method: 'POST' }),

  getSession: (sessionId: string) =>
    request(`/api/strategy/session/${sessionId}`),
}

// ─── Backtest endpoints ───────────────────────────────────────────────────────

export const backtestApi = {
  run: (sessionId: string, config: object, projectId?: string | null) =>
    request('/api/backtest/run', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, project_id: projectId || undefined, config }),
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

export const projectApi = {
  list: () =>
    request('/api/projects'),

  create: (title: string, mode: 'strategy' | 'botlab' = 'strategy') =>
    request('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ title, mode }),
    }),

  detail: (projectId: string) =>
    request(`/api/projects/${projectId}`),

  update: (projectId: string, payload: object) =>
    request(`/api/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  remove: (projectId: string) =>
    request(`/api/projects/${projectId}`, {
      method: 'DELETE',
    }),
}

export const dashboardApi = {
  commandCenter: (params?: {
    projectId?: string | null
    timeframe?: string
    source?: 'auto' | 'live' | 'real' | 'demo'
    dateFrom?: string
    dateTo?: string
  }) => {
    const search = new URLSearchParams()
    if (params?.projectId) search.set('project_id', params.projectId)
    if (params?.timeframe) search.set('timeframe', params.timeframe)
    if (params?.source) search.set('source', params.source)
    if (params?.dateFrom) search.set('date_from', params.dateFrom)
    if (params?.dateTo) search.set('date_to', params.dateTo)
    const suffix = search.toString() ? `?${search.toString()}` : ''
    return request(`/api/dashboard/command-center${suffix}`)
  },
}

export const academyApi = {
  bootstrap: () =>
    request('/api/academy/bootstrap'),

  updateProfile: (payload: { level_input?: string; freeform_background?: string }) =>
    request('/api/academy/profile', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  markViewed: (moduleId: string, lessonId: string) =>
    request('/api/academy/lessons/view', {
      method: 'POST',
      body: JSON.stringify({ module_id: moduleId, lesson_id: lessonId }),
    }),

  setLessonProgress: (moduleId: string, lessonId: string, completed: boolean) =>
    request('/api/academy/lessons/progress', {
      method: 'POST',
      body: JSON.stringify({ module_id: moduleId, lesson_id: lessonId, completed }),
    }),

  search: (query: string) =>
    request(`/api/academy/search?q=${encodeURIComponent(query)}`),
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
