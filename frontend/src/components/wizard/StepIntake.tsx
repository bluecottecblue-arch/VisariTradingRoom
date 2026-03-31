'use client'

import { useEffect, useState, useRef } from 'react'
import { strategyApi, formatError, authApi } from '@/lib/api'
import FundamentalFiltersCard from '@/components/FundamentalFiltersCard'
import StrategyReadinessAudit from '@/components/wizard/StrategyReadinessAudit'
import { DEFAULT_FUNDAMENTAL_FILTERS, summarizeFundamentalFilters } from '@/lib/fundamentals'
import { Alert, Field, NavButtons, Section, Accordion, inputCls, textareaCls } from '@/components/ui'
import type { ParseResult, PreflightResult, StrategyIntake } from '@/types'

const TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1']
const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
const DAY_LABELS: Record<string, string> = {
  MON: 'Lun', TUE: 'Mar', WED: 'Mer', THU: 'Gio',
  FRI: 'Ven', SAT: 'Sab', SUN: 'Dom',
}
const FORM_STEPS = [
  { id: 1, label: 'Mercato e accesso AI', detail: 'Strumento, timeframe e chiave AI' },
  { id: 2, label: 'Logica di ingresso', detail: 'Setup long, short e invalidazione' },
  { id: 3, label: 'Uscite e rischio', detail: 'Stop, target e sizing' },
  { id: 4, label: 'Filtri', detail: 'Sessioni, trend, volatilita e macro/news' },
  { id: 5, label: 'Esempi e revisione', detail: 'Trade concreti e preflight finale' },
]

const DEFAULT_FORM: StrategyIntake = {
  name: '',
  market: '',
  analysis_timeframe: 'H4',
  execution_timeframe: 'M15',
  long_entry: '',
  short_entry: '',
  invalidation: '',
  stop_loss: '',
  take_profit: '',
  trailing_stop: '',
  risk_per_trade_pct: 1.0,
  max_daily_trades: 3,
  trading_hours_start: '08:00',
  trading_hours_end: '17:00',
  trading_days: ['MON', 'TUE', 'WED', 'THU', 'FRI'],
  volatility_filter: '',
  trend_filter: '',
  context_filter: '',
  news_management: '',
  valid_trade_examples: '',
  invalid_trade_examples: '',
  additional_notes: '',
  claude_access: {
    credential_source: 'personal',
    api_key: '',
    provider: 'anthropic',
  },
  inference_policy: {
    allow_non_critical_assumptions: false,
    operator_notes: '',
  },
  macro_news: DEFAULT_FUNDAMENTAL_FILTERS,
}

interface Props {
  projectId?: string | null
  onComplete: (sessionId: string, result: ParseResult) => void
}

function QualityHint({ value }: { value: string }) {
  return (
    <div className="mt-2 flex items-center justify-between text-xs">
      <span className={value.length < 50 ? 'text-amber-400' : 'text-cyan-300'}>
        {value.length < 50 ? 'Aggiungi piu dettaglio per aumentare la codificabilita.' : 'Livello di dettaglio buono.'}
      </span>
      <span className="text-slate-600">{value.length} caratteri</span>
    </div>
  )
}

export default function StepIntake({ projectId, onComplete }: Props) {
  const [form, setForm] = useState<StrategyIntake>(DEFAULT_FORM)
  const [formStep, setFormStep] = useState(1)
  const [accountClaudeAvailable, setAccountClaudeAvailable] = useState(false)
  const [loading, setLoading] = useState(false)
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [preflightLoading, setPreflightLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const preflightReqIdRef = useRef(0)
  const preflightDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const preflightAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const saved = sessionStorage.getItem('sf_intake_form')
    if (!saved) return
    try {
      setForm((current) => ({ ...current, ...JSON.parse(saved) }))
    } catch {}
  }, [])

  useEffect(() => {
    let cancelled = false
    authApi.me()
      .then((body) => {
        if (!cancelled) {
          const hasKey = Boolean(
            body.claude_key_configured || 
            body.openai_key_configured || 
            body.google_key_configured
          )
          setAccountClaudeAvailable(hasKey)
          
          const accountProvider = body.ai_provider || 'anthropic'
          
          if (hasKey) {
            setForm((prev) => {
              const currentAccess = prev.claude_access || { credential_source: 'personal', api_key: '', provider: 'anthropic' }
              // ONLY update if it's currently personal AND has no key
              if (currentAccess.credential_source === 'personal' && !currentAccess.api_key) {
                return {
                  ...prev,
                  claude_access: {
                    ...currentAccess,
                    credential_source: 'account',
                    provider: accountProvider as any
                  }
                }
              }
              return prev
            })
          }
        }
      })
      .catch(() => {
        if (!cancelled) setAccountClaudeAvailable(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      sessionStorage.setItem('sf_intake_form', JSON.stringify(form))
    }, 500)
    return () => clearTimeout(timer)
  }, [form])

  const buildPayload = (value: StrategyIntake) => ({
    ...value,
    project_id: projectId || undefined,
    macro_news: value.macro_news,
    news_management: summarizeFundamentalFilters(value.macro_news, value.news_management),
  })

  useEffect(() => {
    const requiredReady =
      !!form.name.trim() &&
      !!form.market.trim() &&
      !!form.long_entry.trim() &&
      !!form.invalidation.trim() &&
      !!form.stop_loss.trim() &&
      !!form.take_profit.trim()

    if (!requiredReady) {
      preflightReqIdRef.current += 1
      if (preflightDebounceRef.current) clearTimeout(preflightDebounceRef.current)
      if (preflightAbortRef.current) preflightAbortRef.current.abort()
      setPreflight(null)
      setPreflightLoading(false)
      return
    }

    preflightReqIdRef.current += 1
    const currentReqId = preflightReqIdRef.current
    if (preflightDebounceRef.current) clearTimeout(preflightDebounceRef.current)
    if (preflightAbortRef.current) preflightAbortRef.current.abort()

    preflightDebounceRef.current = setTimeout(async () => {
      if (preflightReqIdRef.current !== currentReqId) return
      setPreflightLoading(true)
      preflightAbortRef.current = new AbortController()

      try {
        const result = await strategyApi.preflight(buildPayload(form), { signal: preflightAbortRef.current.signal }) as PreflightResult
        if (preflightReqIdRef.current === currentReqId) {
          setPreflight(result)
        }
      } catch (e: unknown) {
        const isAbort = e instanceof Error && (e.name === 'AbortError' || (e as any).status === 408)
        if (isAbort) return
        
        if (preflightReqIdRef.current === currentReqId) {
          setPreflight(null)
        }
      } finally {
        if (preflightReqIdRef.current === currentReqId) {
          setPreflightLoading(false)
        }
      }
    }, 450)

    return () => {
      if (preflightDebounceRef.current) clearTimeout(preflightDebounceRef.current)
      if (preflightAbortRef.current) preflightAbortRef.current.abort()
    }
  }, [form])

  const set = <K extends keyof StrategyIntake>(key: K, value: StrategyIntake[K]) => {
    // Only update if the value is actually different to prevent unnecessary re-renders
    setForm((current) => {
      if (current[key] === value) return current
      return { ...current, [key]: value }
    })
  }

  const toggleDay = (day: string) => {
    const nextDays = form.trading_days.includes(day)
      ? form.trading_days.filter((item) => item !== day)
      : [...form.trading_days, day]
    set('trading_days', nextDays)
  }

  const validate = () => {
    if (!form.name.trim()) return 'Inserisci un nome per la strategia.'
    if (!form.market.trim()) return 'Seleziona il mercato o lo strumento.'
    if (form.claude_access?.credential_source === 'account' && !accountClaudeAvailable) {
      return "Usa una chiave personale oppure chiedi all'admin di assegnarne una al tuo account."
    }
    if (form.claude_access?.credential_source !== 'account' && !(form.claude_access?.api_key || '').trim()) {
      return 'Inserisci la tua chiave AI personale per continuare.'
    }
    if (!form.long_entry.trim()) return 'Descrivi il setup long.'
    if (!form.invalidation.trim()) return "Descrivi la logica di invalidazione."
    if (!form.stop_loss.trim()) return 'Descrivi la logica dello stop loss.'
    if (!form.take_profit.trim()) return 'Descrivi la logica del take profit.'
    if ((form.long_entry || '').trim().length < 80) return 'Rendi il setup long piu completo. Includi contesto, trigger e condizione di esecuzione.'
    if ((form.valid_trade_examples || '').trim().length < 60) return 'Aggiungi 2-3 esempi di trade validi prima di continuare.'
    if ((form.invalid_trade_examples || '').trim().length < 40) return 'Aggiungi esempi di trade da scartare o descrivi esplicitamente cosa filtrare.'
    return null
  }

  const canAdvanceStep = (step: number) => {
    if (step === 1) {
      if (!form.name.trim() || !form.market.trim()) return false
      if (form.claude_access?.credential_source === 'account') return accountClaudeAvailable
      return Boolean((form.claude_access?.api_key || '').trim())
    }
    if (step === 2) return Boolean(form.long_entry.trim() && form.invalidation.trim())
    if (step === 3) return Boolean(form.stop_loss.trim() && form.take_profit.trim())
    return true
  }

  const nextFormStep = () => {
    if (!canAdvanceStep(formStep)) {
      const err = validate()
      if (err) setError(err)
      return
    }
    setError(null)
    setFormStep((current) => Math.min(FORM_STEPS.length, current + 1))
  }

  const prevFormStep = () => setFormStep((current) => Math.max(1, current - 1))

  const handleSubmit = async () => {
    const err = validate()
    if (err) {
      setError(err)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const result = await strategyApi.parse(buildPayload(form)) as ParseResult
      sessionStorage.removeItem('sf_intake_form')
      onComplete(result.session_id, result)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div className="space-y-5 border border-slate-800/90 bg-[linear-gradient(135deg,rgba(8,47,73,0.18),rgba(15,23,42,0.82)_36%,rgba(2,6,23,0.96))] px-6 py-7">
        <div className="space-y-2">
          <div className="text-[11px] uppercase tracking-[0.24em] text-cyan-300">Crea strategia</div>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-50">
            Compila la strategia in modo strutturato
          </h1>
          <p className="max-w-3xl text-sm leading-relaxed text-slate-400">
            Definisci mercato, setup, rischio e filtri macro in un builder guidato. Il preflight gira in background cosi attivi gli step AI a pagamento solo quando la strategia e abbastanza precisa.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Strategia</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">{form.name || 'Strategia senza nome'}</div>
            <div className="mt-1 text-sm text-slate-500">{form.market || 'Mercato non selezionato'}</div>
          </div>
          <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Timeframe</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">{form.analysis_timeframe} / {form.execution_timeframe}</div>
            <div className="mt-1 text-sm text-slate-500">Contesto e trigger operativo</div>
          </div>
          <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Prontezza</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">{preflight ? `${Math.round(preflight.completeness_score * 100)}%` : 'In attesa'}</div>
            <div className="mt-1 text-sm text-slate-500">{preflight ? preflight.status.replaceAll('_', ' ') : 'Compila i campi critici per sbloccare il preflight.'}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.36fr_0.64fr]">
        <aside className="space-y-3">
          {FORM_STEPS.map((step) => {
            const active = step.id === formStep
            const completed = step.id < formStep
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => setFormStep(step.id)}
                className={`w-full border px-4 py-4 text-left transition-colors ${
                  active
                    ? 'border-cyan-900/70 bg-cyan-950/10'
                    : completed
                    ? 'border-slate-800 bg-slate-950/60 text-slate-300'
                    : 'border-slate-900 bg-slate-950/30 text-slate-500 hover:border-slate-700'
                }`}
              >
                    <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{step.label}</span>
                  <span className={`text-[10px] uppercase tracking-[0.16em] ${completed ? 'text-cyan-400' : 'text-slate-600'}`}>
                    {completed ? '✓ fatto' : `Step ${step.id} di 5`}
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-500">{step.detail}</div>
              </button>
            )
          })}
        </aside>

        <div className="space-y-8">
          {formStep === 1 && (
            <>
              <Section title="Accesso motore AI">
                <div className="space-y-4">
                  <div className="text-xs text-stone-500">
                    Usa la chiave assegnata al tuo account, altrimenti inserisci una chiave personale.
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => accountClaudeAvailable && set('claude_access', { ...(form.claude_access || { api_key: '', provider: 'anthropic' }), credential_source: 'account' })}
                      disabled={!accountClaudeAvailable}
                      className={`border px-4 py-3 text-left transition-colors ${
                        form.claude_access?.credential_source === 'account'
                          ? 'border-slate-500 bg-slate-900 text-slate-100'
                          : 'border-slate-800 bg-transparent text-slate-400 hover:border-slate-700 hover:text-slate-100'
                      } ${!accountClaudeAvailable ? 'cursor-not-allowed opacity-50' : ''}`}
                    >
                      <div className="text-sm font-medium">Usa la chiave assegnata al mio account</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {accountClaudeAvailable ? 'Disponibile su questo account.' : 'Nessuna chiave configurata sull’account.'}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={() => set('claude_access', { ...(form.claude_access || { api_key: '', provider: 'anthropic' }), credential_source: 'personal' })}
                      className={`border px-4 py-3 text-left transition-colors ${
                        form.claude_access?.credential_source === 'personal'
                          ? 'border-slate-500 bg-slate-900 text-slate-100'
                          : 'border-slate-800 bg-transparent text-slate-400 hover:border-slate-700 hover:text-slate-100'
                      }`}
                    >
                      <div className="text-sm font-medium">Usa la mia chiave AI personale</div>
                      <div className="mt-1 text-xs text-slate-500">Viene usata solo per questo workflow.</div>
                    </button>
                  </div>
                  {form.claude_access?.credential_source === 'personal' ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      <Field label="Provider AI">
                        <select
                          value={form.claude_access.provider || 'anthropic'}
                          onChange={(e) => set('claude_access', { ...form.claude_access!, provider: e.target.value })}
                          className={inputCls}
                        >
                          <option value="anthropic">Anthropic (Claude)</option>
                          <option value="openai">OpenAI (o1/GPT-4o)</option>
                          <option value="google">Google (Gemini)</option>
                        </select>
                      </Field>
                      <Field label={`Chiave API ${form.claude_access.provider === 'openai' ? 'OpenAI' : form.claude_access.provider === 'google' ? 'Google Gemini' : 'Claude'}`} required>
                        <input
                          type="password"
                          value={form.claude_access?.api_key || ''}
                          onChange={(e) => set('claude_access', { ...form.claude_access!, api_key: e.target.value })}
                          className={inputCls}
                          placeholder={form.claude_access.provider === 'openai' ? 'sk-proj-...' : form.claude_access.provider === 'google' ? 'AIza...' : 'sk-ant-...'}
                        />
                      </Field>
                    </div>
                  ) : (
                    <div className="rounded border border-slate-800 bg-slate-950/60 px-4 py-3 text-xs text-slate-500">
                      {accountClaudeAvailable
                        ? 'Questo workflow usera la chiave gia assegnata al tuo account.'
                        : 'Usa una chiave personale oppure chiedi all’admin di assegnarne una al tuo account.'}
                    </div>
                  )}
                </div>
              </Section>

              <Section title="Mercato e timeframe">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Nome strategia" required>
                    <input value={form.name} onChange={(e) => set('name', e.target.value)} className={inputCls} placeholder="London Breakout Pullback" />
                  </Field>
                  <Field label="Mercato / strumento" required>
                    <input value={form.market} onChange={(e) => set('market', e.target.value)} className={inputCls} placeholder="EURUSD" />
                  </Field>
                </div>
                <div className="mt-4">
                  <Accordion title="Contesto avanzato e timeframe" defaultOpen={true}>
                    <div className="grid gap-4 md:grid-cols-2">
                      <Field label="Timeframe analisi">
                        <select value={form.analysis_timeframe} onChange={(e) => set('analysis_timeframe', e.target.value)} className={inputCls}>
                          {TIMEFRAMES.map((tf) => <option key={tf}>{tf}</option>)}
                        </select>
                      </Field>
                      <Field label="Timeframe esecuzione">
                        <select value={form.execution_timeframe} onChange={(e) => set('execution_timeframe', e.target.value)} className={inputCls}>
                          {TIMEFRAMES.map((tf) => <option key={tf}>{tf}</option>)}
                        </select>
                      </Field>
                    </div>
                  </Accordion>
                </div>
              </Section>
            </>
          )}

          {formStep === 2 && (
            <Section title="Regole di ingresso">
              <Field label="Setup long" required tooltip="Descrivi le condizioni esatte che devono essere vere prima di consentire un trade long.">
                <textarea
                  value={form.long_entry}
                  onChange={(e) => set('long_entry', e.target.value)}
                  className={`${textareaCls} h-36`}
                  placeholder="Esempio: Su H4 il prezzo deve stare sopra EMA200. Aspetta un pullback su EMA20, poi entra su M15 dopo la prima chiusura rialzista se RSI(14) sale e non c'e una finestra news ad alto impatto."
                />
                <QualityHint value={form.long_entry} />
              </Field>
              <Field label="Setup short" tooltip="Opzionale. Lascia vuoto se la strategia e solo long.">
                <textarea
                  value={form.short_entry}
                  onChange={(e) => set('short_entry', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Logica short opzionale"
                />
              </Field>
              <Field label="Logica di invalidazione" required tooltip="Cosa invalida il setup prima dell'ingresso?">
                <textarea
                  value={form.invalidation}
                  onChange={(e) => set('invalidation', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Esempio: Se il prezzo chiude oltre il massimo della candela di rigetto o passa piu di un'ora senza trigger, il setup e invalidato."
                />
                <QualityHint value={form.invalidation} />
              </Field>
            </Section>
          )}

          {formStep === 3 && (
            <Section title="Uscite e gestione del rischio">
              <Field label="Logica stop loss" required>
                <textarea
                  value={form.stop_loss}
                  onChange={(e) => set('stop_loss', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Esempio: Sotto il minimo della candela di setup piu un piccolo buffer, oppure sotto il supporto H4 piu vicino."
                />
                <QualityHint value={form.stop_loss} />
              </Field>
              <Field label="Logica take profit" required>
                <textarea
                  value={form.take_profit}
                  onChange={(e) => set('take_profit', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Esempio: Target fisso a 2R, prossima resistenza strutturale, oppure parziali piu runner."
                />
              </Field>
              <div className="mt-4">
                <Accordion title="Trailing stop (opzionale)" defaultOpen={true}>
                  <Field label="Logica trailing stop">
                    <input
                      value={form.trailing_stop}
                      onChange={(e) => set('trailing_stop', e.target.value)}
                      className={inputCls}
                      placeholder="Breakeven a 1R, poi trailing su ATR o swing structure"
                    />
                  </Field>
                </Accordion>
              </div>
              <div className="grid gap-4 md:grid-cols-2 mt-8">
                <Field label="Rischio per trade (%)">
                  <input
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    value={form.risk_per_trade_pct}
                    onChange={(e) => set('risk_per_trade_pct', parseFloat(e.target.value))}
                    className={inputCls}
                  />
                </Field>
                <Field label="Trade massimi al giorno">
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={form.max_daily_trades}
                    onChange={(e) => set('max_daily_trades', parseInt(e.target.value))}
                    className={inputCls}
                  />
                </Field>
              </div>
            </Section>
          )}

          {formStep === 4 && (
            <div className="space-y-8">
              <Section title="Sessions and filters">
                <Accordion title="Session & Day Triggers" defaultOpen={true}>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Session start (UTC)">
                      <input type="time" value={form.trading_hours_start} onChange={(e) => set('trading_hours_start', e.target.value)} className={inputCls} />
                    </Field>
                    <Field label="Session end (UTC)">
                      <input type="time" value={form.trading_hours_end} onChange={(e) => set('trading_hours_end', e.target.value)} className={inputCls} />
                    </Field>
                  </div>
                  <div className="mt-4">
                    <Field label="Trading days">
                      <div className="flex flex-wrap gap-2">
                        {DAYS.map((day) => (
                          <button
                            key={day}
                            type="button"
                            onClick={() => toggleDay(day)}
                            className={`border px-3 py-2 text-xs font-semibold ${
                              form.trading_days.includes(day)
                                ? 'border-cyan-900/70 bg-cyan-950/10 text-cyan-300'
                                : 'border-slate-800 bg-slate-950/50 text-slate-500 hover:border-slate-700'
                            }`}
                          >
                            {DAY_LABELS[day]}
                          </button>
                        ))}
                      </div>
                    </Field>
                  </div>
                </Accordion>
                
                <div className="mt-4 space-y-4">
                  <Field label="Trend filter">
                    <input
                      value={form.trend_filter}
                      onChange={(e) => set('trend_filter', e.target.value)}
                      className={inputCls}
                      placeholder="Only trade with higher timeframe trend or structural bias"
                    />
                  </Field>
                  <Field label="Volatility filter">
                    <input
                      value={form.volatility_filter}
                      onChange={(e) => set('volatility_filter', e.target.value)}
                      className={inputCls}
                      placeholder="Avoid compressed or extreme volatility conditions"
                    />
                  </Field>
                </div>

                <div className="mt-4">
                  <Accordion title="Advanced Context & News Handling" defaultOpen={true}>
                    <Field label="Context notes">
                      <input
                        value={form.context_filter}
                        onChange={(e) => set('context_filter', e.target.value)}
                        className={inputCls}
                        placeholder="Session, structure, liquidity, correlated market context"
                      />
                    </Field>
                    <Field label="News handling notes">
                      <input
                        value={form.news_management}
                        onChange={(e) => set('news_management', e.target.value)}
                        className={inputCls}
                        placeholder="Example: block trading 30 minutes before and after high-impact USD events"
                      />
                    </Field>
                  </Accordion>
                </div>
              </Section>

              <div className="mt-8">
                <FundamentalFiltersCard
                  title="Macro / news filters"
                  value={form.macro_news}
                  onChange={(next) => set('macro_news', next)}
                />
              </div>
            </div>
          )}

          {formStep === 5 && (
            <>
              <Section title="Examples and trader notes">
                <Field label="Examples of valid trades">
                  <textarea
                    value={form.valid_trade_examples}
                    onChange={(e) => set('valid_trade_examples', e.target.value)}
                    className={`${textareaCls} h-32`}
                    placeholder="Describe 2–3 concrete trades that perfectly matched the strategy, including context, trigger, stop and target."
                  />
                </Field>
                <Field label="Examples of invalid trades">
                  <textarea
                    value={form.invalid_trade_examples}
                    onChange={(e) => set('invalid_trade_examples', e.target.value)}
                    className={`${textareaCls} h-24`}
                    placeholder="Describe situations that looked tradable but must be rejected, and explain why."
                  />
                </Field>
                <Field label="Additional notes">
                  <textarea
                    value={form.additional_notes}
                    onChange={(e) => set('additional_notes', e.target.value)}
                    className={`${textareaCls} h-20`}
                    placeholder="Anything else that matters for execution or interpretation."
                  />
                </Field>
              </Section>

              <Section title="Assumption policy">
                <div className="space-y-4">
                  <div className="rounded border border-slate-800 bg-slate-950/60 px-4 py-3 text-xs leading-relaxed text-slate-500">
                    The platform should not invent critical logic. You can, however, authorize conservative completion of non-critical gaps so the outputs stay complete without overriding your stated rules.
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => set('inference_policy', { ...(form.inference_policy || { operator_notes: '' }), allow_non_critical_assumptions: false })}
                      className={`border px-4 py-4 text-left transition-colors ${
                        !form.inference_policy?.allow_non_critical_assumptions
                          ? 'border-slate-500 bg-slate-900 text-slate-100'
                          : 'border-slate-800 bg-transparent text-slate-400 hover:border-slate-700 hover:text-slate-100'
                      }`}
                    >
                      <div className="text-sm font-medium">Strict interpretation only</div>
                      <div className="mt-1 text-xs text-slate-500">Block incomplete logic instead of completing it.</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => set('inference_policy', { ...(form.inference_policy || { operator_notes: '' }), allow_non_critical_assumptions: true })}
                      className={`border px-4 py-4 text-left transition-colors ${
                        form.inference_policy?.allow_non_critical_assumptions
                          ? 'border-cyan-900/70 bg-cyan-950/10 text-slate-100'
                          : 'border-slate-800 bg-transparent text-slate-400 hover:border-slate-700 hover:text-slate-100'
                      }`}
                    >
                      <div className="text-sm font-medium">Authorize conservative completion</div>
                      <div className="mt-1 text-xs text-slate-500">Allow non-critical operational assumptions, but force them to be listed explicitly.</div>
                    </button>
                  </div>
                  {form.inference_policy?.allow_non_critical_assumptions && (
                    <Field label="Authorization notes">
                      <textarea
                        value={form.inference_policy?.operator_notes || ''}
                        onChange={(e) =>
                          set('inference_policy', {
                            ...(form.inference_policy || { allow_non_critical_assumptions: true }),
                            operator_notes: e.target.value,
                          })
                        }
                        className={`${textareaCls} h-24`}
                        placeholder="Optional: specify what the platform may assume conservatively and what it must never infer."
                      />
                    </Field>
                  )}
                </div>
              </Section>

              <StrategyReadinessAudit preflight={preflight} loading={preflightLoading} />

              {preflight && (
                <section className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Free preflight</p>
                      <h2 className="text-lg font-semibold text-slate-100">
                        {preflight.status === 'VALID' ? 'Pipeline ready' : 'Pipeline blocked before token spend'}
                      </h2>
                    </div>
                    <div className={`border px-3 py-1 text-xs font-semibold ${
                      preflight.status === 'VALID'
                        ? 'border-cyan-900/70 bg-cyan-950/10 text-cyan-300'
                        : 'border-amber-900/70 bg-amber-950/10 text-amber-300'
                    }`}>
                      completeness {Math.round(preflight.completeness_score * 100)}%
                    </div>
                  </div>
                  <p className="text-sm text-slate-400">{preflight.message}</p>
                  <div className="grid gap-3 md:grid-cols-3">
                    {Object.entries(preflight.expected_stages).map(([stage, estimate]) => (
                      <div key={stage} className="border border-slate-800 bg-slate-950/70 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{stage}</span>
                          <span className={`text-[11px] font-semibold ${estimate.enabled ? 'text-cyan-300' : 'text-amber-300'}`}>
                            {estimate.enabled ? `~$${estimate.estimated_cost_usd.toFixed(4)}` : 'stopped'}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-slate-500">{estimate.reason}</p>
                        {estimate.enabled && (
                          <div className="mt-2 space-y-1 text-[11px] text-slate-400">
                            <div>input ~ {estimate.estimated_input_tokens} tok</div>
                            <div>output ~ {estimate.estimated_output_tokens} tok</div>
                            <div>cap {estimate.max_tokens}</div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
                    <p className="text-slate-400">
                      {preflight.next_recommended_action}
                      {preflight.blocking_items > 0 ? ` Open blockers: ${preflight.blocking_items}.` : ''}
                    </p>
                    <p className="font-semibold text-slate-200">
                      max expected pipeline cost ~ ${preflight.estimated_total_cost_usd.toFixed(4)}
                    </p>
                  </div>
                </section>
              )}
            </>
          )}

          {preflightLoading && !loading && (
            <p className="text-xs text-slate-500">
              Running local pre-check. No tokens spent.
            </p>
          )}

          {error && <Alert type="error">{error}</Alert>}

          {formStep < FORM_STEPS.length ? (
            <NavButtons
              onBack={formStep > 1 ? prevFormStep : undefined}
              onNext={nextFormStep}
              nextLabel="Continue section →"
              backLabel="← Previous section"
              disabled={loading}
            />
          ) : (
            <NavButtons
              onBack={prevFormStep}
              onNext={handleSubmit}
              nextLabel={loading ? 'Analyzing strategy...' : 'Analyze Strategy →'}
              backLabel="← Previous section"
              loading={loading}
              disabled={loading}
            />
          )}

          {loading && (
            <p className="text-xs text-slate-500">
              Claude is translating the strategy into structured trading logic. Typical runtime: 20–60 seconds.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
