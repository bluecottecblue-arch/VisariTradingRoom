'use client'

import Link from 'next/link'
import { FormEvent, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'

export default function RegisterForm() {
  const searchParams = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [referral, setReferral] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [config, setConfig] = useState<{ price_eur?: number; referral_discount_pct?: number; billing_enabled?: boolean } | null>(null)

  useEffect(() => {
    const ref = searchParams.get('ref')
    if (ref) setReferral(ref.trim().toUpperCase())
    fetch('/api/billing/config', { cache: 'no-store' })
      .then((r) => r.json())
      .then(setConfig)
      .catch(() => null)
  }, [searchParams])

  const price = config?.price_eur ?? 50
  const discount = config?.referral_discount_pct ?? 60
  const discountedFirst = referral ? price * (1 - discount / 100) : null

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    if (password.length < 6) {
      setError('La password deve avere almeno 6 caratteri.')
      return
    }
    if (password !== confirm) {
      setError('Le password non coincidono.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch('/api/billing/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, referral_code: referral || undefined }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Errore durante la registrazione.')
      }
      if (data.checkout_url) {
        // Redirect al checkout Stripe
        window.location.href = data.checkout_url
        return
      }
      throw new Error('Risposta inattesa dal server.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore sconosciuto')
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
                Crea il tuo accesso
              </h1>
              <p className="mt-4 max-w-xl text-sm leading-relaxed text-slate-400">
                Accesso completo alla piattaforma: strategie, Bot Lab, Mean Reversion Lab, Data Lab e Accademia.
              </p>
            </div>

            <div className="border border-amber-800/50 bg-amber-950/15 px-5 py-5">
              <div className="text-[10px] uppercase tracking-[0.18em] text-amber-400">Abbonamento</div>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-semibold text-slate-50">€{price.toFixed(0)}</span>
                <span className="text-sm text-slate-400">/ mese</span>
              </div>
              {discountedFirst != null && (
                <div className="mt-3 border-t border-amber-900/40 pt-3 text-sm text-amber-300">
                  Con codice referral: <strong>€{discountedFirst.toFixed(2)}</strong> il primo mese
                  <span className="text-amber-500/80"> (-{discount}%)</span>
                </div>
              )}
              <p className="mt-3 text-xs leading-relaxed text-slate-500">
                Cancellabile in qualsiasi momento dal portale di gestione. Rinnovo automatico mensile.
              </p>
            </div>

            <div className="border border-slate-800/90 bg-slate-950/45 px-4 py-4">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Programma referral</div>
              <div className="mt-2 text-sm leading-relaxed text-slate-300">
                Invita un amico: lui ottiene il {discount}% di sconto sul primo mese, tu ricevi 1 mese gratis per ogni amico che si abbona.
              </div>
            </div>
          </div>
        </div>

        <div className="p-8 sm:p-10">
          <div className="mb-8">
            <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Registrazione</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-50">Sottoscrivi un account</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">
              Dopo la registrazione verrai indirizzato al pagamento sicuro Stripe.
            </p>
          </div>

          {config && config.billing_enabled === false && (
            <div className="mb-6 border border-amber-900/80 bg-amber-950/10 px-4 py-3 text-sm text-amber-200">
              I pagamenti non sono ancora attivi. Contatta l'amministratore.
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.16em] text-slate-500">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-slate-800 bg-slate-950/90 px-4 py-3.5 text-slate-100 outline-none transition-colors focus:border-cyan-700/70"
                placeholder="nome@email.com"
                autoFocus
                required
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.16em] text-slate-500">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-slate-800 bg-slate-950/90 px-4 py-3.5 text-slate-100 outline-none transition-colors focus:border-cyan-700/70"
                placeholder="minimo 6 caratteri"
                required
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.16em] text-slate-500">Conferma password</span>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full border border-slate-800 bg-slate-950/90 px-4 py-3.5 text-slate-100 outline-none transition-colors focus:border-cyan-700/70"
                placeholder="ripeti la password"
                required
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-[11px] uppercase tracking-[0.16em] text-slate-500">
                Codice referral <span className="text-slate-600">(opzionale)</span>
              </span>
              <input
                type="text"
                value={referral}
                onChange={(e) => setReferral(e.target.value.toUpperCase())}
                className="w-full border border-slate-800 bg-slate-950/90 px-4 py-3.5 font-mono text-slate-100 outline-none transition-colors focus:border-amber-600/70"
                placeholder="ES. ABC-123"
              />
              {discountedFirst != null && (
                <span className="mt-1 block text-xs text-amber-400">
                  Sconto del {discount}% applicato al primo mese
                </span>
              )}
            </label>

            {error && (
              <div className="border border-rose-900/80 bg-rose-950/10 px-4 py-3 text-sm text-rose-200">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !email.trim() || !password || config?.billing_enabled === false}
              className="w-full border border-amber-700/70 bg-amber-400/90 px-4 py-3.5 font-semibold text-slate-950 transition-colors hover:bg-amber-300 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Reindirizzamento al pagamento...' : 'Procedi al pagamento'}
            </button>
          </form>

          <div className="mt-6 text-sm text-slate-500">
            Hai già un account?{' '}
            <Link href="/login" className="text-slate-300 hover:text-slate-100">
              Accedi
            </Link>
          </div>
        </div>
      </div>
    </main>
  )
}
