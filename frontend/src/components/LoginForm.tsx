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
    <main className="min-h-screen bg-stone-950 text-stone-100 font-mono flex items-center justify-center px-6">
      <div className="w-full max-w-md border border-stone-800 bg-stone-900/80 rounded-2xl p-8 shadow-2xl">
        <div className="mb-6">
          <p className="text-xs tracking-[0.3em] text-amber-400 uppercase">VisariTradingRoom</p>
          <h1 className="mt-3 text-2xl font-bold text-stone-100">{title}</h1>
          <p className="mt-2 text-sm text-stone-400">{description}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-2 block text-sm text-stone-300">Username</span>
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="w-full rounded-lg border border-stone-700 bg-stone-950 px-4 py-3 text-stone-100 outline-none focus:border-amber-500"
              placeholder="username"
              autoFocus
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm text-stone-300">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-stone-700 bg-stone-950 px-4 py-3 text-stone-100 outline-none focus:border-amber-500"
              placeholder="password"
            />
          </label>

          {error && (
            <div className="rounded-lg border border-red-900/60 bg-red-950/30 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !username.trim() || !password}
            className="w-full rounded-lg bg-amber-400 px-4 py-3 font-bold text-stone-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Accesso in corso...' : submitLabel}
          </button>
        </form>

        {secondaryHref && secondaryLabel && (
          <div className="mt-5 text-center text-sm text-stone-500">
            <Link href={secondaryHref} className="text-amber-400 hover:text-amber-300">
              {secondaryLabel}
            </Link>
          </div>
        )}
      </div>
    </main>
  )
}
