'use client'

import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

type UserItem = {
  username: string
  status: 'active' | 'suspended' | 'expired'
  plan: string
  expires_at: string | null
  notes: string
  ai_provider: string
  claude_key_configured: boolean
  openai_key_configured: boolean
  google_key_configured: boolean
  created_at: string | null
  updated_at: string | null
  last_login_at: string | null
}

export default function AdminPanel() {
  const router = useRouter()
  const [users, setUsers] = useState<UserItem[]>([])
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<'active' | 'suspended'>('active')
  const [plan, setPlan] = useState('standard')
  const [expiresAt, setExpiresAt] = useState('')
  const [aiProvider, setAiProvider] = useState('anthropic')
  const [claudeApiKey, setClaudeApiKey] = useState('')
  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [googleApiKey, setGoogleApiKey] = useState('')
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
        body: JSON.stringify({
          username,
          password,
          status,
          plan,
          expires_at: expiresAt || null,
          ai_provider: aiProvider,
          claude_api_key: claudeApiKey || null,
          openai_api_key: openaiApiKey || null,
          google_api_key: googleApiKey || null,
        }),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Creazione account fallita')
      setUsername('')
      setPassword('')
      setStatus('active')
      setPlan('standard')
      setExpiresAt('')
      setAiProvider('anthropic')
      setClaudeApiKey('')
      setOpenaiApiKey('')
      setGoogleApiKey('')
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

  async function updateAccount(target: string, payload: Record<string, unknown>, successMessage: string) {
    setError('')
    setNotice('')
    try {
      const response = await fetch(`/api/backend/api/auth/admin/users/${encodeURIComponent(target)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.detail || 'Aggiornamento account fallito')
      setNotice(successMessage)
      await loadUsers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
    }
  }

  async function setUserKey(target: string, provider: 'anthropic' | 'openai' | 'google', isConfigured: boolean) {
    const keyMap = { anthropic: 'Claude', openai: 'OpenAI', google: 'Google Gemini' }
    const fieldMap = { anthropic: 'claude_api_key', openai: 'openai_api_key', google: 'google_api_key' }
    const name = keyMap[provider]
    const keyField = fieldMap[provider]
    
    const nextKey = window.prompt(
      isConfigured
        ? `Aggiorna la ${name} API key assegnata a ${target}`
        : `Inserisci una ${name} API key da assegnare a ${target}`,
    )
    if (nextKey === null) return
    await updateAccount(
      target,
      { [keyField]: nextKey.trim() },
      nextKey.trim()
        ? `${name} key aggiornata per ${target}`
        : `${name} key rimossa per ${target}`,
    )
  }

  async function removeUserKey(target: string, provider: 'anthropic' | 'openai' | 'google') {
    const keyMap = { anthropic: 'Claude', openai: 'OpenAI', google: 'Google Gemini' }
    const fieldMap = { anthropic: 'claude_api_key', openai: 'openai_api_key', google: 'google_api_key' }
    const name = keyMap[provider]
    if (!window.confirm(`Rimuovere la ${name} API key assegnata a ${target}?`)) return
    await updateAccount(target, { [fieldMap[provider]]: '' }, `${name} key rimossa per ${target}`)
  }

  async function changeUserProvider(target: string, current: string) {
    const nextProvider = window.prompt(`Nuovo provider AI per ${target} (anthropic, openai, google) (Attuale: ${current})`, current)
    if (!nextProvider || !['anthropic', 'openai', 'google'].includes(nextProvider.trim().toLowerCase())) return
    await updateAccount(target, { ai_provider: nextProvider.trim().toLowerCase() }, `Provider AI aggiornato a ${nextProvider.trim().toLowerCase()}`)
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
          <div className="md:pl-8">
            <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Visari Trading Room</p>
            <h1 className="mt-3 text-3xl font-semibold">Amministrazione accessi clienti</h1>
            <p className="mt-2 text-sm text-slate-500">
              Gestione essenziale degli account cliente, senza flussi esterni o provider terzi.
            </p>
          </div>
          <div className="flex gap-3 text-sm">
            <Link href="/workspace" className="border border-slate-800 px-4 py-2 hover:border-slate-600">
              Vai all&apos;app
            </Link>
            <Link href="/login" className="border border-slate-800 px-4 py-2 hover:border-slate-600">
              Login utente
            </Link>
            <button
              onClick={logout}
              className="border border-slate-800 px-4 py-2 hover:border-slate-600"
            >
              Esci
            </button>
          </div>
        </header>

        <section className="grid gap-8 md:grid-cols-[360px,1fr]">
          <form onSubmit={createAccount} className="space-y-4 border border-slate-800 bg-slate-950/70 p-6">
            <h2 className="text-lg font-semibold">Nuovo account</h2>
            <label className="block">
                <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Nome utente</span>
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
            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Stato</span>
                <select
                  value={status}
                  onChange={(event) => setStatus(event.target.value as 'active' | 'suspended')}
                  className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                >
                  <option value="active">attivo</option>
                  <option value="suspended">sospeso</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Piano</span>
                <input
                  value={plan}
                  onChange={(event) => setPlan(event.target.value)}
                  className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                  placeholder="standard"
                />
              </label>
            </div>
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Scade il (facoltativo)</span>
              <input
                type="datetime-local"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
              />
            </label>
            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Provider AI</span>
                <select
                  value={aiProvider}
                  onChange={(event) => setAiProvider(event.target.value)}
                  className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                >
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                  <option value="google">Google Gemini</option>
                </select>
              </label>
            </div>
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Chiave API Claude (facoltativa)</span>
              <input
                type="password"
                value={claudeApiKey}
                onChange={(event) => setClaudeApiKey(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                placeholder="sk-ant-..."
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Chiave API OpenAI (facoltativa)</span>
              <input
                type="password"
                value={openaiApiKey}
                onChange={(event) => setOpenaiApiKey(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                placeholder="sk-proj-..."
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.14em] text-slate-500">Chiave API Google (facoltativa)</span>
              <input
                type="password"
                value={googleApiKey}
                onChange={(event) => setGoogleApiKey(event.target.value)}
                className="w-full border border-slate-800 bg-slate-950 px-4 py-3 outline-none focus:border-slate-500"
                placeholder="AIza..."
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
              Ogni account può essere attivo, sospeso o scaduto, con piano, scadenza opzionale e chiavi AI dedicate per utente.
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
                        Stato: {user.status} · Piano: {user.plan} · Ultimo accesso: {user.last_login_at || 'mai'}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        Creato: {user.created_at || 'n/d'} · Scade: {user.expires_at || 'mai'} · Provider: <span className="text-cyan-400">{user.ai_provider}</span>
                      </div>
                      <div className="mt-1 flex gap-2 text-xs text-slate-500">
                        <span>Claude: {user.claude_key_configured ? <span className="text-emerald-400">Si</span> : 'No'}</span>
                        <span>OpenAI: {user.openai_key_configured ? <span className="text-emerald-400">Si</span> : 'No'}</span>
                        <span>Google: {user.google_key_configured ? <span className="text-emerald-400">Si</span> : 'No'}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 md:justify-end">
                      <button
                        onClick={() => changeUserProvider(user.username, user.ai_provider)}
                        className="border border-slate-800 bg-slate-900 px-3 py-2 text-xs hover:border-slate-600"
                      >
                        Cambia provider
                      </button>
                      <button
                        onClick={() =>
                          updateAccount(
                            user.username,
                            { status: user.status === 'suspended' ? 'active' : 'suspended' },
                            user.status === 'suspended'
                              ? `Account riattivato: ${user.username}`
                              : `Account sospeso: ${user.username}`,
                          )
                        }
                        className="border border-slate-800 px-3 py-2 text-xs hover:border-slate-600"
                      >
                        {user.status === 'suspended' ? 'Riattiva' : 'Sospendi'}
                      </button>
                      
                      <div className="flex gap-1">
                        <button
                          onClick={() => setUserKey(user.username, 'anthropic', user.claude_key_configured)}
                          className={`border px-2 py-2 text-[10px] uppercase ${user.claude_key_configured ? 'border-emerald-900/50 text-emerald-500' : 'border-slate-800 text-slate-500'}`}
                        >
                          Claude
                        </button>
                        {user.claude_key_configured && (
                          <button onClick={() => removeUserKey(user.username, 'anthropic')} className="border border-slate-800 px-2 py-2 text-[10px] text-rose-500">✕</button>
                        )}
                        <button
                          onClick={() => setUserKey(user.username, 'openai', user.openai_key_configured)}
                          className={`border px-2 py-2 text-[10px] uppercase ${user.openai_key_configured ? 'border-emerald-900/50 text-emerald-500' : 'border-slate-800 text-slate-500'}`}
                        >
                          OpenAI
                        </button>
                        {user.openai_key_configured && (
                          <button onClick={() => removeUserKey(user.username, 'openai')} className="border border-slate-800 px-2 py-2 text-[10px] text-rose-500">✕</button>
                        )}
                        <button
                          onClick={() => setUserKey(user.username, 'google', user.google_key_configured)}
                          className={`border px-2 py-2 text-[10px] uppercase ${user.google_key_configured ? 'border-emerald-900/50 text-emerald-500' : 'border-slate-800 text-slate-500'}`}
                        >
                          Google
                        </button>
                        {user.google_key_configured && (
                          <button onClick={() => removeUserKey(user.username, 'google')} className="border border-slate-800 px-2 py-2 text-[10px] text-rose-500">✕</button>
                        )}
                      </div>

                      <button
                        onClick={() => resetUserPassword(user.username)}
                        className="border border-slate-800 px-3 py-2 text-xs hover:border-slate-600"
                      >
                        Reimposta password
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
