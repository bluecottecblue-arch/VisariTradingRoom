'use client'

import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

type UserItem = {
  username: string
  email: string | null
  status: 'active' | 'suspended' | 'expired' | 'pending'
  plan: string
  expires_at: string | null
  notes: string
  ai_provider: string
  claude_key_configured: boolean
  openai_key_configured: boolean
  google_key_configured: boolean
  polygon_key_configured: boolean
  twelvedata_key_configured: boolean
  alphavantage_key_configured: boolean
  subscription_status: string
  referral_code: string | null
  referred_by: string | null
  referral_count: number
  free_months_credit: number
  created_at: string | null
  updated_at: string | null
  last_login_at: string | null
}

const statusColor: Record<string, string> = {
  active: 'text-emerald-400',
  suspended: 'text-rose-400',
  expired: 'text-amber-400',
  pending: 'text-slate-400',
}

const subStatusColor: Record<string, string> = {
  active: 'text-emerald-400',
  past_due: 'text-amber-400',
  canceled: 'text-rose-400',
  none: 'text-slate-500',
  trialing: 'text-cyan-400',
}

function fmt(dt: string | null) {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' }) }
  catch { return dt }
}

export default function AdminPanel() {
  const router = useRouter()
  const [users, setUsers] = useState<UserItem[]>([])
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  // Create form
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newStatus, setNewStatus] = useState<'active' | 'suspended'>('active')
  const [newPlan, setNewPlan] = useState('standard')
  const [newExpiresAt, setNewExpiresAt] = useState('')

  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  async function loadUsers() {
    setLoading(true)
    setError('')
    try {
      const r = await fetch('/api/backend/api/auth/admin/users', { cache: 'no-store' })
      const b = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(b.detail || 'Impossibile caricare gli utenti')
      setUsers(b.users || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore sconosciuto')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadUsers() }, [])

  async function api(method: string, path: string, body?: unknown): Promise<unknown> {
    const r = await fetch(`/api/backend/api/auth/admin/users${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    })
    const b = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error((b as { detail?: string }).detail || 'Errore API')
    return b
  }

  async function act(fn: () => Promise<unknown>, successMsg: string) {
    setError(''); setNotice('')
    try { await fn(); setNotice(successMsg); await loadUsers() }
    catch (e) { setError(e instanceof Error ? e.message : 'Errore sconosciuto') }
  }

  async function createAccount(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSaving(true); setError(''); setNotice('')
    try {
      await api('POST', '', { username: newUsername, password: newPassword, email: newEmail || undefined, status: newStatus, plan: newPlan, expires_at: newExpiresAt || null })
      setNewUsername(''); setNewPassword(''); setNewEmail(''); setNewStatus('active'); setNewPlan('standard'); setNewExpiresAt('')
      setNotice(`Account creato: ${newUsername}`)
      await loadUsers()
    } catch (e) { setError(e instanceof Error ? e.message : 'Errore') }
    finally { setSaving(false) }
  }

  function promptKey(user: UserItem, field: string, label: string, configured: boolean) {
    const val = window.prompt(configured ? `Aggiorna ${label} key per ${user.username}` : `Inserisci ${label} key per ${user.username}`)
    if (val === null) return
    act(() => api('PATCH', `/${encodeURIComponent(user.username)}`, { [field]: val.trim() }),
      val.trim() ? `${label} key aggiornata` : `${label} key rimossa`)
  }

  const filtered = users.filter(u =>
    !search || u.username.includes(search.toLowerCase()) || (u.email || '').toLowerCase().includes(search.toLowerCase())
  )

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' })
    router.replace('/admin/login'); router.refresh()
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-6xl space-y-8">

        {/* Header */}
        <header className="flex flex-col gap-4 border-b border-slate-800 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[0.28em] text-amber-400">Visari Trading Room</p>
            <h1 className="mt-2 text-2xl font-semibold">Pannello amministrazione</h1>
            <p className="mt-1 text-sm text-slate-500">{users.length} utenti totali</p>
          </div>
          <div className="flex gap-3 text-sm">
            <Link href="/workspace" className="border border-slate-800 px-4 py-2 hover:border-slate-600">App</Link>
            <button onClick={logout} className="border border-slate-800 px-4 py-2 hover:border-slate-600">Esci</button>
          </div>
        </header>

        {error && <div className="border border-rose-900 bg-rose-950/20 px-4 py-3 text-sm text-rose-300">{error}</div>}
        {notice && <div className="border border-emerald-900 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-300">{notice}</div>}

        <div className="grid gap-8 lg:grid-cols-[340px,1fr]">

          {/* Create user form */}
          <form onSubmit={createAccount} className="h-fit space-y-4 border border-slate-800 bg-slate-900/40 p-6">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">Nuovo account</h2>
            {[
              { label: 'Nome utente', val: newUsername, set: setNewUsername, ph: 'cliente-01', type: 'text' },
              { label: 'Password', val: newPassword, set: setNewPassword, ph: 'minimo 6 caratteri', type: 'text' },
              { label: 'Email (facoltativa)', val: newEmail, set: setNewEmail, ph: 'nome@email.com', type: 'email' },
            ].map(({ label, val, set, ph, type }) => (
              <label key={label} className="block">
                <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">{label}</span>
                <input type={type} value={val} onChange={e => set(e.target.value)}
                  className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm outline-none focus:border-slate-600" placeholder={ph} />
              </label>
            ))}
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Stato</span>
                <select value={newStatus} onChange={e => setNewStatus(e.target.value as 'active' | 'suspended')}
                  className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm outline-none">
                  <option value="active">attivo</option>
                  <option value="suspended">sospeso</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Piano</span>
                <input value={newPlan} onChange={e => setNewPlan(e.target.value)}
                  className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm outline-none" placeholder="standard" />
              </label>
            </div>
            <label className="block">
              <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Scade il (facoltativo)</span>
              <input type="datetime-local" value={newExpiresAt} onChange={e => setNewExpiresAt(e.target.value)}
                className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm outline-none" />
            </label>
            <button type="submit" disabled={saving || !newUsername.trim() || newPassword.length < 6}
              className="w-full border border-slate-300 bg-slate-100 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-40">
              {saving ? 'Creazione...' : 'Crea account'}
            </button>
          </form>

          {/* User list */}
          <section className="space-y-4">
            <div className="flex items-center gap-3">
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Cerca per username o email..."
                className="flex-1 border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm outline-none focus:border-slate-600" />
              <button onClick={loadUsers} className="border border-slate-800 px-4 py-2.5 text-sm hover:border-slate-600">Aggiorna</button>
            </div>

            {loading ? (
              <p className="text-sm text-slate-500">Caricamento...</p>
            ) : filtered.length === 0 ? (
              <p className="text-sm text-slate-500">Nessun utente trovato.</p>
            ) : (
              <div className="space-y-2">
                {filtered.map((user) => (
                  <div key={user.username} className="border border-slate-800 bg-slate-900/40">
                    {/* Row summary */}
                    <button
                      onClick={() => setExpanded(expanded === user.username ? null : user.username)}
                      className="w-full px-4 py-3 text-left"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex items-center gap-3">
                            <span className="font-medium text-slate-100">{user.username}</span>
                            <span className={`text-[10px] font-semibold uppercase tracking-wider ${statusColor[user.status] || 'text-slate-400'}`}>
                              {user.status}
                            </span>
                            {user.subscription_status !== 'none' && (
                              <span className={`text-[10px] uppercase tracking-wider ${subStatusColor[user.subscription_status] || 'text-slate-400'}`}>
                                stripe:{user.subscription_status}
                              </span>
                            )}
                          </div>
                          <div className="mt-0.5 truncate text-xs text-slate-500">
                            {user.email || '—'} · {user.plan} · ultimo accesso: {fmt(user.last_login_at)}
                          </div>
                        </div>
                        <span className="shrink-0 text-xs text-slate-600">{expanded === user.username ? '▲' : '▼'}</span>
                      </div>
                    </button>

                    {/* Expanded detail */}
                    {expanded === user.username && (
                      <div className="border-t border-slate-800 px-4 py-4 space-y-5">

                        {/* Info grid */}
                        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs md:grid-cols-4">
                          {[
                            ['Creato', fmt(user.created_at)],
                            ['Scade', user.expires_at ? fmt(user.expires_at) : 'mai'],
                            ['Abbonamento', user.subscription_status],
                            ['Piano', user.plan],
                            ['Referral code', user.referral_code || '—'],
                            ['Invitato da', user.referred_by || '—'],
                            ['Amici invitati', String(user.referral_count)],
                            ['Mesi gratis', String(user.free_months_credit)],
                          ].map(([k, v]) => (
                            <div key={k}>
                              <div className="text-[10px] uppercase tracking-widest text-slate-600">{k}</div>
                              <div className="text-slate-300">{v}</div>
                            </div>
                          ))}
                        </div>

                        {/* Actions row */}
                        <div className="flex flex-wrap gap-2">
                          <button
                            onClick={() => act(
                              () => api('PATCH', `/${encodeURIComponent(user.username)}`, { status: user.status === 'suspended' ? 'active' : 'suspended' }),
                              user.status === 'suspended' ? `Riattivato: ${user.username}` : `Sospeso: ${user.username}`
                            )}
                            className={`border px-3 py-1.5 text-xs ${user.status === 'suspended' ? 'border-emerald-800 text-emerald-400 hover:bg-emerald-950/30' : 'border-rose-800 text-rose-400 hover:bg-rose-950/30'}`}
                          >
                            {user.status === 'suspended' ? 'Riattiva account' : 'Sospendi account'}
                          </button>

                          <button
                            onClick={() => {
                              const pw = window.prompt(`Nuova password per ${user.username}`)
                              if (pw) act(() => api('POST', `/${encodeURIComponent(user.username)}/reset-password`, { password: pw }), 'Password reimpostata')
                            }}
                            className="border border-slate-700 px-3 py-1.5 text-xs hover:border-slate-500"
                          >
                            Reimposta password
                          </button>

                          <button
                            onClick={() => {
                              const exp = window.prompt(`Data scadenza per ${user.username} (formato: YYYY-MM-DD o lascia vuoto)`)
                              if (exp !== null) act(() => api('PATCH', `/${encodeURIComponent(user.username)}`, { expires_at: exp || null }), 'Scadenza aggiornata')
                            }}
                            className="border border-slate-700 px-3 py-1.5 text-xs hover:border-slate-500"
                          >
                            Imposta scadenza
                          </button>

                          <button
                            onClick={() => { if (window.confirm(`Cancellare ${user.username}?`)) act(() => api('DELETE', `/${encodeURIComponent(user.username)}`), `Cancellato: ${user.username}`) }}
                            className="border border-rose-900 px-3 py-1.5 text-xs text-rose-400 hover:bg-rose-950/20"
                          >
                            Cancella account
                          </button>
                        </div>

                        {/* API keys */}
                        <div>
                          <div className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Chiavi AI</div>
                          <div className="flex flex-wrap gap-2">
                            {([
                              ['Claude', 'claude_api_key', user.claude_key_configured],
                              ['OpenAI', 'openai_api_key', user.openai_key_configured],
                              ['Google', 'google_api_key', user.google_key_configured],
                            ] as [string, string, boolean][]).map(([label, field, configured]) => (
                              <button key={label}
                                onClick={() => promptKey(user, field, label, configured)}
                                className={`border px-3 py-1.5 text-xs ${configured ? 'border-emerald-800/60 text-emerald-400' : 'border-slate-700 text-slate-500 hover:border-slate-500'}`}
                              >
                                {label} {configured ? '✓' : '+'}
                              </button>
                            ))}
                          </div>
                        </div>

                        <div>
                          <div className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">Chiavi dati mercato</div>
                          <div className="flex flex-wrap gap-2">
                            {([
                              ['Polygon', 'polygon_api_key', user.polygon_key_configured],
                              ['TwelveData', 'twelvedata_api_key', user.twelvedata_key_configured],
                              ['AlphaVantage', 'alphavantage_api_key', user.alphavantage_key_configured],
                            ] as [string, string, boolean][]).map(([label, field, configured]) => (
                              <button key={label}
                                onClick={() => promptKey(user, field, label, configured)}
                                className={`border px-3 py-1.5 text-xs ${configured ? 'border-amber-800/60 text-amber-400' : 'border-slate-700 text-slate-500 hover:border-slate-500'}`}
                              >
                                {label} {configured ? '✓' : '+'}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Notes */}
                        <div>
                          <div className="mb-1 text-[10px] uppercase tracking-widest text-slate-500">Note</div>
                          <div className="flex gap-2">
                            <input
                              defaultValue={user.notes}
                              id={`notes-${user.username}`}
                              className="flex-1 border border-slate-800 bg-slate-950 px-3 py-2 text-xs outline-none focus:border-slate-600"
                              placeholder="Note interne..."
                            />
                            <button
                              onClick={() => {
                                const el = document.getElementById(`notes-${user.username}`) as HTMLInputElement
                                act(() => api('PATCH', `/${encodeURIComponent(user.username)}`, { notes: el.value }), 'Note salvate')
                              }}
                              className="border border-slate-700 px-3 py-2 text-xs hover:border-slate-500"
                            >
                              Salva
                            </button>
                          </div>
                        </div>

                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </main>
  )
}
