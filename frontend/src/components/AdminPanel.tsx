'use client'

import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

type UserItem = {
  username: string
  created_at: string | null
  updated_at: string | null
  last_login_at: string | null
}

export default function AdminPanel() {
  const router = useRouter()
  const [users, setUsers] = useState<UserItem[]>([])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  async function loadUsers() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/backend/api/auth/admin/users', { cache: 'no-store' })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Impossibile caricare gli utenti')
      setUsers(body.users || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  async function createAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch('/api/backend/api/auth/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Creazione account fallita')
      setUsername('')
      setPassword('')
      setNotice(`Account creato: ${body.user?.username || username}`)
      await loadUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
    } finally {
      setSaving(false)
    }
  }

  async function deleteAccount(target: string) {
    if (!window.confirm(`Cancellare l'account ${target}?`)) return
    setError('')
    setNotice('')
    try {
      const response = await fetch(`/api/backend/api/auth/admin/users/${encodeURIComponent(target)}`, {
        method: 'DELETE',
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Cancellazione fallita')
      setNotice(`Account cancellato: ${target}`)
      await loadUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
    }
  }

  async function resetUserPassword(target: string) {
    const nextPassword = window.prompt(`Nuova password per ${target}`)
    if (!nextPassword) return
    setError('')
    setNotice('')
    try {
      const response = await fetch(
        `/api/backend/api/auth/admin/users/${encodeURIComponent(target)}/reset-password`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: nextPassword }),
        },
      )
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Reset password fallito')
      setNotice(`Password aggiornata per ${target}`)
      await loadUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
    }
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' })
    router.replace('/admin/login')
    router.refresh()
  }

  return (
    <main className="min-h-screen bg-stone-950 text-stone-100 font-mono px-6 py-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="flex flex-col gap-4 border-b border-stone-800 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs tracking-[0.3em] text-amber-400 uppercase">VisariTradingRoom</p>
            <h1 className="mt-3 text-3xl font-bold">Admin utenti</h1>
            <p className="mt-2 text-sm text-stone-400">
              Crea, resetta o cancella account cliente senza toccare il codice.
            </p>
          </div>
          <div className="flex gap-3 text-sm">
            <Link href="/" className="rounded border border-stone-700 px-4 py-2 hover:border-amber-500">
              Vai all&apos;app
            </Link>
            <Link href="/login" className="rounded border border-stone-700 px-4 py-2 hover:border-amber-500">
              Login utente
            </Link>
            <button
              onClick={logout}
              className="rounded border border-stone-700 px-4 py-2 hover:border-amber-500"
            >
              Logout
            </button>
          </div>
        </header>

        <section className="grid gap-8 md:grid-cols-[360px,1fr]">
          <form onSubmit={createAccount} className="space-y-4 rounded-2xl border border-stone-800 bg-stone-900/70 p-6">
            <h2 className="text-lg font-bold">Nuovo account</h2>
            <label className="block">
              <span className="mb-2 block text-sm text-stone-300">Username</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full rounded-lg border border-stone-700 bg-stone-950 px-4 py-3 outline-none focus:border-amber-500"
                placeholder="cliente-01"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm text-stone-300">Password</span>
              <input
                type="text"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-stone-700 bg-stone-950 px-4 py-3 outline-none focus:border-amber-500"
                placeholder="minimo 6 caratteri"
              />
            </label>
            <button
              type="submit"
              disabled={saving || !username.trim() || password.length < 6}
              className="w-full rounded-lg bg-amber-400 px-4 py-3 font-bold text-stone-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Creazione...' : 'Crea account'}
            </button>
            <p className="text-xs text-stone-500">
              Gli account sono salvati nel backend come JSON semplice.
            </p>
          </form>

          <section className="rounded-2xl border border-stone-800 bg-stone-900/70 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">Utenti esistenti</h2>
              <button
                onClick={loadUsers}
                className="rounded border border-stone-700 px-3 py-2 text-sm hover:border-amber-500"
              >
                Aggiorna
              </button>
            </div>

            {error && (
              <div className="mb-4 rounded-lg border border-red-900/60 bg-red-950/30 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            {notice && (
              <div className="mb-4 rounded-lg border border-green-900/60 bg-green-950/30 px-4 py-3 text-sm text-green-300">
                {notice}
              </div>
            )}

            {loading ? (
              <p className="text-stone-400">Caricamento utenti...</p>
            ) : users.length === 0 ? (
              <p className="text-stone-500">Nessun account creato.</p>
            ) : (
              <div className="space-y-3">
                {users.map((user) => (
                  <div
                    key={user.username}
                    className="flex flex-col gap-4 rounded-xl border border-stone-800 bg-stone-950/60 p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <div className="font-bold text-stone-100">{user.username}</div>
                      <div className="mt-1 text-xs text-stone-500">
                        Creato: {user.created_at || 'n/d'} · Ultimo login: {user.last_login_at || 'mai'}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => resetUserPassword(user.username)}
                        className="rounded border border-stone-700 px-3 py-2 text-xs hover:border-amber-500"
                      >
                        Reset password
                      </button>
                      <button
                        onClick={() => deleteAccount(user.username)}
                        className="rounded border border-red-900 px-3 py-2 text-xs text-red-300 hover:bg-red-950/40"
                      >
                        Cancella
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  )
}
