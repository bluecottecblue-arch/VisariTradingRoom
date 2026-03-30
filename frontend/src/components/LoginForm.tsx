'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })

      let body: any = {}
      try {
        body = await response.json()
      } catch {}

      if (!response.ok) {
        throw new Error(body.detail || 'Invalid credentials')
      }

      router.replace(nextPath)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.14),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(245,158,11,0.08),transparent_22%),linear-gradient(180deg,#06111f_0%,#030712_100%)] px-6 text-slate-100">
      <div className="grid w-full max-w-6xl overflow-hidden border border-slate-800/90 bg-slate-950/82 shadow-[0_0_0_1px_rgba(15,23,42,0.4),0_24px_80px_rgba(2,6,23,0.65)] lg:grid-cols-[1.1fr_0.9fr]">
        <div className="hidden border-r border-slate-800/90 bg-[linear-gradient(140deg,rgba(8,47,73,0.4),rgba(15,23,42,0.84)_38%,rgba(2,6,23,0.96))] p-10 lg:block">
          <div className="space-y-6 md:pl-10">
            <div>
              <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Visari Trading Room</div>
              <h1 className="mt-4 text-4xl font-semibold leading-tight tracking-tight text-slate-50">
                Quantitative Strategy Platform
              </h1>
              <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-400">
                Transform trading logic into validated MT5 systems with structured research, controlled revisions and delivery-ready exports.
              </p>
            </div>

            <div className="grid gap-4">
              {[
                {
                  title: 'Validated workflow',
                  detail: 'Structured intake, formal specification, out-of-sample backtesting and export control.',
                },
                {
                  title: 'Institutional review',
                  detail: 'Risk, robustness, macro filters and delivery checks in one professional workspace.',
                },
                {
                  title: 'MT5 deployment ready',
                  detail: 'From strategy idea or existing bot to a professional handoff package.',
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
            <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Secure access</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-50">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">{description}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.16em] text-slate-500">Username</span>
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950/90 px-4 py-3.5 text-slate-100 outline-none transition-colors focus:border-cyan-700/70"
                placeholder="your username"
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
                placeholder="your password"
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
              {loading ? 'Signing in...' : submitLabel}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-between gap-4 text-xs text-slate-500">
            <span>Protected client workspace</span>
            <span>Session-based access</span>
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
