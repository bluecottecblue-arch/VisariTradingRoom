'use client'

import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

type LoginFormProps = {
  endpoint: string
  title: string
  description: string
  submitLabel: string
  nextPath: string
  secondaryHref?: string
  secondaryLabel?: string
}

export default function LoginForm({
  endpoint,
  title,
  description,
  submitLabel,
  nextPath,
  secondaryHref,
  secondaryLabel,
}: LoginFormProps) {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [warmingUp, setWarmingUp] = useState(false)

  useEffect(() => {
    let cancelled = false
    setWarmingUp(true)

    fetch('/api/auth/warmup', { cache: 'no-store' })
      .catch(() => null)
      .finally(() => {
        if (!cancelled) setWarmingUp(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  async function submitOnce() {
    return fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      let lastError = 'Credenziali non valide'

      for (let attempt = 0; attempt < 3; attempt += 1) {
        const response = await submitOnce()

        let body: any = {}
        try {
          body = await response.json()
        } catch {}

        if (response.ok) {
          router.replace(nextPath)
          router.refresh()
          return
        }

        lastError = body.detail || 'Credenziali non valide'

        const shouldRetry =
          response.status === 503 &&
          attempt < 2 &&
          /non raggiungibile|riattivazione/i.test(String(lastError))

        if (!shouldRetry) {
          throw new Error(lastError)
        }

        setError('Riattivo il servizio, attendi qualche secondo...')
        await new Promise((resolve) => setTimeout(resolve, 2500 * (attempt + 1)))
      }
      throw new Error(lastError)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.14),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(245,158,11,0.08),transparent_22%),linear-gradient(180deg,#06111f_0%,#030712_100%)] px-6 text-slate-100">
      <div className="grid w-full max-w-6xl overflow-hidden border border-slate-800/90 bg-slate-950/82 shadow-[0_0_0_1px_rgba(15,23,42,0.4),0_24px_80px_rgba(2,6,23,0.65)] lg:grid-cols-[1.1fr_0.9fr]">
        <div className="hidden border-r border-slate-800/90 bg-[linear-gradient(140deg,rgba(8,47,73,0.4),rgba(15,23,42,0.84)_38%,rgba(2,6,23,0.96))] p-10 lg:block">
          <div className="space-y-6 md:pl-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Visari Trading Room</div>
              <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-tight text-slate-50">
                Piattaforma di ingegneria strategica
              </h1>
              <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-400">
                Trasforma logiche di trading in algoritmi MT5 validati con ricerca strutturata, revisioni controllate ed export pronti al deploy.
              </p>
            </div>

            <div className="grid gap-4">
              {[
                {
                  title: 'Workflow validato',
                  detail: 'Raccolta strutturata, specifica formale, backtest out-of-sample e controllo dell’export.',
                },
                {
                  title: 'Revisione istituzionale',
                  detail: 'Rischio, robustezza, filtri macro e controlli finali in un unico workspace professionale.',
                },
                {
                  title: 'Pronto per MT5',
                  detail: 'Dall’idea strategica o da un bot esistente fino a un pacchetto finale pronto all’handoff.',
                },
              ].map((item) => (
                <div key={item.title} className="border border-slate-800/90 bg-slate-950/45 px-4 py-4">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{item.title}</div>
                  <div className="mt-2 text-sm leading-relaxed text-slate-300">{item.detail}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="p-8 sm:p-10">
          <div className="mb-8">
            <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Accesso protetto</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-50">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">{description}</p>
            {warmingUp && (
              <p className="mt-2 text-xs text-slate-600">Connessione ai servizi in preparazione…</p>
            )}
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.16em] text-slate-500">Nome utente</span>
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950/90 px-4 py-3.5 text-slate-100 outline-none transition-colors focus:border-cyan-700/70"
                placeholder="il tuo nome utente"
                autoFocus
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.16em] text-slate-500">Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950/90 px-4 py-3.5 text-slate-100 outline-none transition-colors focus:border-cyan-700/70"
                placeholder="la tua password"
              />
            </label>

            {error && (
              <div className="border border-rose-900/80 bg-rose-950/10 px-4 py-3 text-sm text-rose-200">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full border border-cyan-800/70 bg-cyan-400/90 px-4 py-3.5 font-semibold text-slate-950 transition-colors hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Accesso in corso...' : submitLabel}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-between gap-4 text-xs text-slate-500">
            <span>Workspace cliente protetto</span>
            <span>Accesso basato su sessione</span>
          </div>

          {secondaryHref && secondaryLabel && (
            <div className="mt-6 text-sm text-slate-500">
              <Link href={secondaryHref} className="text-slate-300 hover:text-slate-100">
                {secondaryLabel}
              </Link>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
