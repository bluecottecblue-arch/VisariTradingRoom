'use client'

import { useEffect, useState } from 'react'
import AuthToolbar from '@/components/AuthToolbar'
import AppSidebar from '@/components/layout/AppSidebar'

interface ReferralData {
  referral_code: string | null
  referral_link: string | null
  referral_count: number
  free_months_credit: number
  note?: string
}

const card = 'border border-slate-800 bg-slate-900/50 p-6'
const sectionTitle = 'text-[10px] uppercase tracking-[0.18em] text-slate-500 pb-2 mb-4 border-b border-slate-800'

export default function ReferralClient() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [data, setData] = useState<ReferralData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<'code' | 'link' | null>(null)
  const [subStatus, setSubStatus] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      fetch('/api/backend/api/billing/referral', { credentials: 'include' }).then((r) => r.json()),
      fetch('/api/backend/api/billing/me', { credentials: 'include' }).then((r) => r.json()).catch(() => null),
    ])
      .then(([ref, me]) => {
        if (!ref.ok) throw new Error(ref.detail || 'Errore caricamento referral')
        setData(ref)
        if (me?.ok) setSubStatus(me.subscription_status)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function copy(text: string, which: 'code' | 'link') {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(which)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  async function openPortal() {
    try {
      const r = await fetch('/api/backend/api/billing/portal', { method: 'POST', credentials: 'include' })
      const d = await r.json()
      if (d.url) window.location.href = d.url
      else setError(d.detail || 'Portale non disponibile')
    } catch {
      setError('Errore apertura portale')
    }
  }

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-200 transition-[padding] duration-200 ${sidebarOpen ? 'xl:pl-80' : 'xl:pl-0'}`}>
      <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800 bg-slate-950/90 px-6 py-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label={sidebarOpen ? 'Chiudi navigazione' : 'Apri navigazione'}
            onClick={() => setSidebarOpen((v) => !v)}
            className="flex h-11 w-11 items-center justify-center border border-slate-800 text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-100"
          >
            <span className="flex flex-col gap-1.5">
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
            </span>
          </button>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-amber-400">Programma Referral</div>
            <div className="text-xl font-semibold text-slate-50">Invita e guadagna mesi gratis</div>
          </div>
        </div>
        <AuthToolbar />
      </header>

      <main className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        {loading && <p className="text-slate-500 animate-pulse">Caricamento...</p>}
        {error && (
          <div className="border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-300">{error}</div>
        )}

        {data && !data.referral_code && (
          <div className="border border-slate-800 bg-slate-900/50 p-6 text-sm text-slate-400">
            {data.note || "Il programma referral è disponibile solo per gli account cliente abbonati."}
          </div>
        )}

        {data && data.referral_code && (
          <>
            {/* Come funziona */}
            <div className="border border-amber-800/40 bg-amber-950/15 p-5 text-sm text-slate-300 leading-relaxed">
              <div className="text-[10px] uppercase tracking-[0.18em] text-amber-400 mb-2">Come funziona</div>
              Condividi il tuo codice. Chi si registra con il tuo codice ottiene il <strong>60% di sconto sul primo mese</strong>.
              Per ogni amico che si abbona, <strong>tu ricevi 1 mese gratis</strong> (scalato automaticamente dalla tua prossima fattura).
            </div>

            {/* Statistiche */}
            <div className="grid grid-cols-2 gap-4">
              <div className={card}>
                <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">Amici abbonati</div>
                <div className="text-4xl font-bold text-slate-50">{data.referral_count}</div>
              </div>
              <div className={card}>
                <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">Mesi gratis accumulati</div>
                <div className="text-4xl font-bold text-amber-400">{data.free_months_credit}</div>
              </div>
            </div>

            {/* Codice */}
            <div className={card}>
              <div className={sectionTitle}>Il tuo codice referral</div>
              <div className="flex items-center gap-3 mb-4">
                <code className="flex-1 border border-slate-700 bg-slate-950 px-4 py-3 font-mono text-lg text-amber-300">
                  {data.referral_code}
                </code>
                <button
                  onClick={() => copy(data.referral_code, 'code')}
                  className="border border-slate-700 px-4 py-3 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
                >
                  {copied === 'code' ? 'Copiato!' : 'Copia'}
                </button>
              </div>

              {data.referral_link && (
                <>
                  <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-2">Link diretto da condividere</div>
                  <div className="flex items-center gap-3">
                    <code className="flex-1 border border-slate-700 bg-slate-950 px-4 py-3 font-mono text-xs text-slate-400 truncate">
                      {data.referral_link}
                    </code>
                    <button
                      onClick={() => copy(data.referral_link!, 'link')}
                      className="border border-slate-700 px-4 py-3 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
                    >
                      {copied === 'link' ? 'Copiato!' : 'Copia'}
                    </button>
                  </div>
                </>
              )}
            </div>

            {/* Gestione abbonamento */}
            <div className={card}>
              <div className={sectionTitle}>Il tuo abbonamento</div>
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-1">Stato</div>
                  <div className={`text-sm font-medium ${
                    subStatus === 'active' ? 'text-green-400' :
                    subStatus === 'past_due' ? 'text-amber-400' :
                    subStatus === 'canceled' ? 'text-red-400' : 'text-slate-400'
                  }`}>
                    {subStatus === 'active' ? 'Attivo' :
                     subStatus === 'past_due' ? 'Pagamento in sospeso' :
                     subStatus === 'canceled' ? 'Cancellato' :
                     subStatus || 'Non disponibile'}
                  </div>
                </div>
                <button
                  onClick={openPortal}
                  className="border border-slate-700 px-4 py-2.5 text-sm text-slate-300 hover:border-slate-500 hover:text-slate-100"
                >
                  Gestisci / Cancella abbonamento
                </button>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
