'use client'

import { useEffect, useState } from 'react'

interface Entry {
  rank: number
  username: string
  display_name: string
  country: string
  bot_name: string | null
  performance_pct: number
  period: string
  period_label: string
  verified: boolean
  updated_at: string | null
}

interface MyEntry extends Entry {
  is_public?: boolean
}

const COUNTRIES: Record<string, string> = {
  IT: '🇮🇹 Italia', US: '🇺🇸 USA', GB: '🇬🇧 UK', DE: '🇩🇪 Germania',
  FR: '🇫🇷 Francia', ES: '🇪🇸 Spagna', CH: '🇨🇭 Svizzera', NL: '🇳🇱 Olanda',
  BR: '🇧🇷 Brasile', AE: '🇦🇪 Dubai', SG: '🇸🇬 Singapore', JP: '🇯🇵 Giappone',
}

function medal(rank: number) {
  if (rank === 1) return '🥇'
  if (rank === 2) return '🥈'
  if (rank === 3) return '🥉'
  return `#${rank}`
}

function perfColor(pct: number) {
  if (pct >= 50) return 'text-emerald-300'
  if (pct >= 20) return 'text-emerald-400'
  if (pct >= 0) return 'text-slate-300'
  return 'text-rose-400'
}

function RankTable({ entries, title, subtitle }: { entries: Entry[]; title: string; subtitle?: string }) {
  if (entries.length === 0) return (
    <div className="border border-slate-800 bg-slate-900/30 p-6 text-center text-sm text-slate-500">
      Nessun trader in classifica ancora. Sii il primo!
    </div>
  )
  return (
    <div className="border border-slate-800 bg-slate-900/30">
      <div className="border-b border-slate-800 px-5 py-4">
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{subtitle}</div>
        <div className="mt-0.5 text-base font-semibold text-slate-100">{title}</div>
      </div>
      <div className="divide-y divide-slate-800/60">
        {entries.map((e) => (
          <div key={e.username} className="flex items-center gap-4 px-5 py-3">
            <div className={`w-8 shrink-0 text-center text-sm font-bold ${e.rank <= 3 ? 'text-lg' : 'text-slate-500'}`}>
              {medal(e.rank)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-slate-100 truncate">{e.display_name}</span>
                {e.verified && <span className="text-[9px] border border-amber-700/50 text-amber-400 px-1.5 py-0.5 uppercase tracking-wider">verificato</span>}
                {e.rank <= 5 && <span className="text-[9px] border border-cyan-800/50 text-cyan-400 px-1.5 py-0.5 uppercase tracking-wider">top trader</span>}
              </div>
              <div className="text-xs text-slate-500 truncate">
                {e.bot_name ? `Bot: ${e.bot_name}` : 'Bot algoritmico'} · {e.period_label} · {COUNTRIES[e.country] ?? e.country}
              </div>
            </div>
            <div className={`shrink-0 text-right font-bold text-lg ${perfColor(e.performance_pct)}`}>
              {e.performance_pct > 0 ? '+' : ''}{e.performance_pct.toFixed(1)}%
            </div>
          </div>
        ))}
      </div>
      {entries.length > 0 && entries[0].rank <= 5 && (
        <div className="border-t border-slate-800/60 px-5 py-3 text-[10px] text-slate-600">
          ⭐ I top 5 mondiali vengono monitorati da piattaforme di quant trading come QuantConnect, Numerai e hedge fund algoritmici internazionali.
        </div>
      )}
    </div>
  )
}

export default function LeaderboardPanel() {
  const [global, setGlobal] = useState<Entry[]>([])
  const [national, setNational] = useState<Entry[]>([])
  const [me, setMe] = useState<MyEntry | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [tab, setTab] = useState<'mondiale' | 'nazionale'>('mondiale')

  // Form state
  const [displayName, setDisplayName] = useState('')
  const [country, setCountry] = useState('IT')
  const [botName, setBotName] = useState('')
  const [perfPct, setPerfPct] = useState('')
  const [period, setPeriod] = useState('ytd')
  const [formOpen, setFormOpen] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [gRes, nRes, mRes] = await Promise.all([
        fetch('/api/backend/api/leaderboard/global?limit=20', { credentials: 'include' }).then(r => r.json()),
        fetch('/api/backend/api/leaderboard/national?country=IT&limit=20', { credentials: 'include' }).then(r => r.json()),
        fetch('/api/backend/api/leaderboard/me', { credentials: 'include' }).then(r => r.json()),
      ])
      setGlobal(gRes.entries || [])
      setNational(nRes.entries || [])
      if (mRes.entry) {
        setMe(mRes.entry)
        setDisplayName(mRes.entry.display_name || '')
        setCountry(mRes.entry.country || 'IT')
        setBotName(mRes.entry.bot_name || '')
        setPerfPct(String(mRes.entry.performance_pct || ''))
        setPeriod(mRes.entry.period || 'ytd')
      }
    } catch (e) {
      setError('Errore caricamento classifica')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function submit() {
    const pct = parseFloat(perfPct)
    if (isNaN(pct)) { setError('Inserisci una percentuale valida'); return }
    setSaving(true); setError(null); setNotice(null)
    try {
      const r = await fetch('/api/backend/api/leaderboard/me', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ display_name: displayName || undefined, country, bot_name: botName || undefined, performance_pct: pct, period }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Errore')
      setMe(d.entry)
      setNotice('Classifica aggiornata!')
      setFormOpen(false)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Errore')
    } finally {
      setSaving(false) }
  }

  async function remove() {
    if (!window.confirm('Vuoi rimuoverti dalla classifica?')) return
    setSaving(true)
    try {
      await fetch('/api/backend/api/leaderboard/me', { method: 'DELETE', credentials: 'include' })
      setMe(null); setNotice('Rimosso dalla classifica')
      await load()
    } catch { setError('Errore') }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">

      {/* Header + CTA */}
      <div className="border border-amber-800/30 bg-amber-950/10 p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-amber-400 mb-1">Classifica trader algoritmici</div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Condividi i risultati del tuo bot e scala la classifica. I <strong>top 5 mondiali</strong> vengono monitorati da piattaforme internazionali di quant trading — hedge fund, QuantConnect, Numerai e investitori istituzionali cercano trader algoritmici con track record verificabile.
            </p>
          </div>
          <div className="shrink-0">
            {me ? (
              <div className="flex gap-2">
                <button onClick={() => setFormOpen(!formOpen)}
                  className="border border-amber-700/60 px-4 py-2 text-sm text-amber-300 hover:bg-amber-950/30">
                  Aggiorna
                </button>
                <button onClick={remove} disabled={saving}
                  className="border border-slate-700 px-4 py-2 text-sm text-slate-400 hover:border-slate-500">
                  Rimuovi
                </button>
              </div>
            ) : (
              <button onClick={() => setFormOpen(!formOpen)}
                className="border border-amber-700/60 bg-amber-400/10 px-5 py-2.5 text-sm font-semibold text-amber-300 hover:bg-amber-950/40">
                + Entra in classifica
              </button>
            )}
          </div>
        </div>
      </div>

      {/* My current position */}
      {me && !formOpen && (
        <div className="border border-slate-700 bg-slate-900/50 px-5 py-4">
          <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">La tua posizione</div>
          <div className="flex items-center gap-4">
            <div className={`text-2xl font-bold ${perfColor(me.performance_pct)}`}>
              {me.performance_pct > 0 ? '+' : ''}{me.performance_pct.toFixed(1)}%
            </div>
            <div className="text-sm text-slate-400">
              {me.bot_name || 'Bot algoritmico'} · {me.period_label} · {COUNTRIES[me.country] ?? me.country}
            </div>
          </div>
        </div>
      )}

      {/* Submit form */}
      {formOpen && (
        <div className="border border-slate-700 bg-slate-900/40 p-5 space-y-4">
          <div className="text-sm font-semibold text-slate-300">
            {me ? 'Aggiorna i tuoi risultati' : 'Inserisci i tuoi risultati'}
          </div>

          {error && <div className="border border-rose-900 bg-rose-950/20 px-3 py-2 text-xs text-rose-300">{error}</div>}

          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <label className="col-span-2 md:col-span-1 block">
              <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Nome visualizzato</span>
              <input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder={`es. Trader_${Math.floor(Math.random()*999)}`}
                className="w-full border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-500" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Paese</span>
              <select value={country} onChange={e => setCountry(e.target.value)}
                className="w-full border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none">
                {Object.entries(COUNTRIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Periodo</span>
              <select value={period} onChange={e => setPeriod(e.target.value)}
                className="w-full border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none">
                <option value="ytd">Anno in corso</option>
                <option value="monthly">Ultimo mese</option>
                <option value="alltime">All time</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Nome bot (opzionale)</span>
              <input value={botName} onChange={e => setBotName(e.target.value)} placeholder="es. MomentumEA_v3"
                className="w-full border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-500" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[10px] uppercase tracking-widest text-slate-500">Rendimento % *</span>
              <input value={perfPct} onChange={e => setPerfPct(e.target.value)} placeholder="es. 34.5" type="number" step="0.1"
                className="w-full border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-500" />
            </label>
          </div>

          <p className="text-[10px] text-slate-600">
            Inserendo i dati dichiari che i risultati sono reali e riferiti al periodo selezionato. Puoi rimuoverti dalla classifica in qualsiasi momento.
          </p>

          <div className="flex gap-3">
            <button onClick={submit} disabled={saving || !perfPct}
              className="border border-amber-700/60 bg-amber-400/10 px-5 py-2 text-sm font-semibold text-amber-300 disabled:opacity-40 hover:bg-amber-950/40">
              {saving ? 'Salvataggio...' : me ? 'Aggiorna classifica' : 'Entra in classifica'}
            </button>
            <button onClick={() => setFormOpen(false)} className="border border-slate-700 px-4 py-2 text-sm text-slate-400 hover:border-slate-500">
              Annulla
            </button>
          </div>
        </div>
      )}

      {notice && <div className="border border-emerald-900 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-300">{notice}</div>}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-800">
        {(['mondiale', 'nazionale'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-5 py-2.5 text-sm font-medium transition-colors ${tab === t ? 'border-b-2 border-amber-400 text-amber-300' : 'text-slate-500 hover:text-slate-300'}`}>
            {t === 'mondiale' ? '🌍 Mondiale' : '🇮🇹 Italia'}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-slate-500 animate-pulse">Caricamento classifica...</p>
      ) : tab === 'mondiale' ? (
        <RankTable entries={global} title="Classifica Mondiale" subtitle="Top trader algoritmici globali" />
      ) : (
        <RankTable entries={national} title="Classifica Italia" subtitle="Top trader algoritmici italiani" />
      )}
    </div>
  )
}
