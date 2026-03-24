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
    <main className="min-h-screen bg-slate-950 px-6 py-8 text-slate-100">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="flex flex-col gap-4 border-b border-slate-800 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Visari Trading Room</p>
            <h1 className="mt-3 text-3xl font-semibold">Client Access Administration</h1>
            <p className="mt-2 text-sm text-slate-500">
              Gestione essenziale degli account cliente, senza flussi esterni o provider terzi.
            </p>
          </div>
          <div className="flex gap-3 text-sm">
            <Link href="/" className="border border-slate-800 px-4 py-2 hover:border-slate-600">
              Vai all&apos;app
            </Link>
            <Link href="/login" className="border border-slate-800 px-4 py-2 hover:border-slate-600">
              Login utente
            </Link>
            <button
              onClick={logout}
              className="border border-slate-800 px-4 py-2 hover:border-slate-600"
            >
              Logout
            </button>
          </div>
        </header>

        <section className="grid gap-8 md:grid-cols-[360px,1fr]">
          <form onSubmit={createAccount} className="space-y-4 border border-slate-800 bg-slate-950/70 p-6">
            <h2 className="text-lg font-semibold">Nuovo account</h2>
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Username</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                placeholder="cliente-01"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Password</span>
              <input
                type="text"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                placeholder="minimo 6 caratteri"
              />
            </label>
            <button
              type="submit"
              disabled={saving || !username.trim() || password.length < 6}
              className="w-full border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Creazione...' : 'Crea account'}
            </button>
            <p className="text-xs text-slate-500">
              Gli account sono salvati nel backend come JSON semplice.
            </p>
          </form>

          <section className="border border-slate-800 bg-slate-950/70 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Utenti esistenti</h2>
              <button
                onClick={loadUsers}
                className="border border-slate-800 px-3 py-2 text-sm hover:border-slate-600"
              >
                Aggiorna
              </button>
            </div>

            {error && (
              <div className="mb-4 border border-rose-950/80 bg-rose-950/10 px-4 py-3 text-sm text-rose-200">
                {error}
              </div>
            )}

            {notice && (
              <div className="mb-4 border border-emerald-950/80 bg-emerald-950/10 px-4 py-3 text-sm text-emerald-200">
                {notice}
              </div>
            )}

            {loading ? (
              <p className="text-slate-400">Caricamento utenti...</p>
            ) : users.length === 0 ? (
              <p className="text-slate-500">Nessun account creato.</p>
            ) : (
              <div className="space-y-3">
                {users.map((user) => (
                  <div
                    key={user.username}
                    className="flex flex-col gap-4 border border-slate-800 bg-slate-950/60 p-4 md:flex-row md:items-center md:justify-between"
                  >
                    <div>
                      <div className="font-semibold text-slate-100">{user.username}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        Creato: {user.created_at || 'n/d'} · Ultimo login: {user.last_login_at || 'mai'}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => resetUserPassword(user.username)}
                        className="border border-slate-800 px-3 py-2 text-xs hover:border-slate-600"
                      >
                        Reset password
                      </button>
                      <button
                        onClick={() => deleteAccount(user.username)}
                        className="border border-rose-950 px-3 py-2 text-xs text-rose-200 hover:bg-rose-950/20"
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
