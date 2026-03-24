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
        throw new Error(body.detail || 'Credenziali non valide')
      }

      router.replace(nextPath)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-100">
      <div className="w-full max-w-md border border-slate-800 bg-slate-950/90 p-9 shadow-[0_0_0_1px_rgba(15,23,42,0.4)]">
        <div className="mb-6">
          <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Visari Trading Room</p>
          <h1 className="mt-3 text-3xl font-semibold text-slate-50">{title}</h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-500">{description}</p>
          <div className="mt-3 text-xs uppercase tracking-[0.18em] text-amber-300">Quantitative Strategy Platform</div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Username</span>
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full border border-slate-800 bg-slate-950 px-4 py-3 text-slate-100 outline-none transition-colors focus:border-slate-500"
              placeholder="username"
              autoFocus
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full border border-slate-800 bg-slate-950 px-4 py-3 text-slate-100 outline-none transition-colors focus:border-slate-500"
              placeholder="password"
            />
          </label>

          {error && (
            <div className="border border-rose-950/80 bg-rose-950/10 px-4 py-3 text-sm text-rose-200">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password}
            className="w-full border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Accesso in corso...' : submitLabel}
          </button>
        </form>

        {secondaryHref && secondaryLabel && (
          <div className="mt-5 text-center text-sm text-slate-500">
            <Link href={secondaryHref} className="text-slate-300 hover:text-slate-100">
              {secondaryLabel}
            </Link>
          </div>
        )}
      </div>
    </main>
  )
}
