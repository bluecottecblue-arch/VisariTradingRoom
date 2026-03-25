'use client'

import { useEffect, useState, useRef } from 'react'
import { strategyApi, formatError, authApi } from '@/lib/api'
import FundamentalFiltersCard from '@/components/FundamentalFiltersCard'
import { DEFAULT_FUNDAMENTAL_FILTERS, summarizeFundamentalFilters } from '@/lib/fundamentals'
import { Alert, Field, NavButtons, Section, Accordion, inputCls, textareaCls } from '@/components/ui'
import type { ParseResult, PreflightResult, StrategyIntake } from '@/types'

const TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1']
const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
const DAY_LABELS: Record<string, string> = {
  MON: 'Mon', TUE: 'Tue', WED: 'Wed', THU: 'Thu',
  FRI: 'Fri', SAT: 'Sat', SUN: 'Sun',
}
const FORM_STEPS = [
  { id: 1, label: 'Market & access', detail: 'Instrument, timeframes and Claude access' },
  { id: 2, label: 'Entry logic', detail: 'Long, short and invalidation rules' },
  { id: 3, label: 'Exit & risk', detail: 'Stop, target and sizing constraints' },
  { id: 4, label: 'Filters', detail: 'Sessions, trend, volatility and macro/news' },
  { id: 5, label: 'Examples & review', detail: 'Concrete trades and final preflight' },
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
        {value.length < 50 ? 'Add more detail to improve codifiability.' : 'Good level of detail.'}
      </span>
      <span className="text-slate-600">{value.length} chars</span>
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
    if (!form.name.trim()) return 'Give the strategy a name.'
    if (!form.market.trim()) return 'Select the market or instrument.'
    if (form.claude_access?.credential_source === 'account' && !accountClaudeAvailable) {
      return 'This account has no AI API key assigned yet. Switch to your personal key or ask admin to assign one.'
    }
    if (form.claude_access?.credential_source !== 'account' && !(form.claude_access?.api_key || '').trim()) {
      return 'Insert your personal AI API key to continue.'
    }
    if (!form.long_entry.trim()) return 'Describe the long setup.'
    if (!form.invalidation.trim()) return 'Describe the invalidation logic.'
    if (!form.stop_loss.trim()) return 'Describe the stop loss logic.'
    if (!form.take_profit.trim()) return 'Describe the take profit logic.'
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
          <div className="text-[11px] uppercase tracking-[0.24em] text-cyan-300">Create Strategy</div>
          <h1 className="text-4xl font-semibold tracking-tight text-slate-50">
            Structured strategy intake for serious trading systems
          </h1>
          <p className="max-w-3xl text-sm leading-relaxed text-slate-400">
            Define the market, the setup, the risk framework and the macro filters in a guided builder. Preflight keeps running in the background so you only trigger paid AI steps when the strategy is specific enough.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Strategy</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">{form.name || 'Unnamed strategy'}</div>
            <div className="mt-1 text-sm text-slate-500">{form.market || 'Market not selected'}</div>
          </div>
          <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Execution frame</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">{form.analysis_timeframe} / {form.execution_timeframe}</div>
            <div className="mt-1 text-sm text-slate-500">Context and trigger horizon</div>
          </div>
          <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Readiness</div>
            <div className="mt-2 text-lg font-semibold text-slate-50">{preflight ? `${Math.round(preflight.completeness_score * 100)}%` : 'Waiting'}</div>
            <div className="mt-1 text-sm text-slate-500">{preflight ? preflight.status.replaceAll('_', ' ') : 'Fill the critical fields to unlock preflight.'}</div>
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
                    {completed ? '✓ done' : `Step ${step.id} of 5`}
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
              <Section title="AI Engine access">
                <div className="space-y-4">
                  <div className="text-xs text-stone-500">
                    Strategy analysis, formalization and bot generation require an AI API key. You can use the key assigned to your account by admin or provide your own personal key for this run.
                  </div>
                  <div className="rounded border border-stone-800 bg-stone-900/60 px-4 py-3 text-xs text-stone-500">
                    No global shared key is exposed to users. Every workflow uses either your personal key or the key assigned to your account.
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
                      <div className="text-sm font-medium">Use my assigned AI key</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {accountClaudeAvailable ? 'Available on this account.' : 'No account key configured.'}
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
                      <div className="text-sm font-medium">Use my personal AI key</div>
                      <div className="mt-1 text-xs text-slate-500">Used only for this strategy workflow.</div>
                    </button>
                  </div>
                  {form.claude_access?.credential_source === 'personal' ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      <Field label="AI Provider">
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
                      <Field label={`${form.claude_access.provider === 'openai' ? 'OpenAI' : form.claude_access.provider === 'google' ? 'Google Gemini' : 'Claude'} API key`} required>
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
                        ? 'This run will use the AI provider and key already assigned to your account.'
                        : 'Switch to personal key or ask admin to assign a key to your account.'}
                    </div>
                  )}
                </div>
              </Section>

              <Section title="Market & timeframes">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Strategy name" required>
                    <input value={form.name} onChange={(e) => set('name', e.target.value)} className={inputCls} placeholder="London Breakout Pullback" />
                  </Field>
                  <Field label="Market / instrument" required>
                    <input value={form.market} onChange={(e) => set('market', e.target.value)} className={inputCls} placeholder="EURUSD" />
                  </Field>
                </div>
                <div className="mt-4">
                  <Accordion title="Advanced Context & Timeframes" defaultOpen={false}>
                    <div className="grid gap-4 md:grid-cols-2">
                      <Field label="Analysis timeframe">
                        <select value={form.analysis_timeframe} onChange={(e) => set('analysis_timeframe', e.target.value)} className={inputCls}>
                          {TIMEFRAMES.map((tf) => <option key={tf}>{tf}</option>)}
                        </select>
                      </Field>
                      <Field label="Execution timeframe">
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
            <Section title="Entry rules">
              <Field label="Long setup" required tooltip="Describe the exact conditions that must be true before a long trade is allowed.">
                <textarea
                  value={form.long_entry}
                  onChange={(e) => set('long_entry', e.target.value)}
                  className={`${textareaCls} h-36`}
                  placeholder="Example: On H4 price must be above EMA200. Wait for a pullback into EMA20, then enter on M15 after the first bullish close if RSI(14) is rising and no high-impact news window is active."
                />
                <QualityHint value={form.long_entry} />
              </Field>
              <Field label="Short setup" tooltip="Optional. Leave blank if the strategy is long only.">
                <textarea
                  value={form.short_entry}
                  onChange={(e) => set('short_entry', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Optional short-side logic"
                />
              </Field>
              <Field label="Invalidation logic" required tooltip="What cancels the setup before entry?">
                <textarea
                  value={form.invalidation}
                  onChange={(e) => set('invalidation', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Example: If price closes beyond the rejection candle high or more than one hour passes without the trigger, the setup is invalidated."
                />
                <QualityHint value={form.invalidation} />
              </Field>
            </Section>
          )}

          {formStep === 3 && (
            <Section title="Exit & risk management">
              <Field label="Stop loss logic" required>
                <textarea
                  value={form.stop_loss}
                  onChange={(e) => set('stop_loss', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Example: Below the setup candle low plus a small buffer, or below the nearest H4 support."
                />
                <QualityHint value={form.stop_loss} />
              </Field>
              <Field label="Take profit logic" required>
                <textarea
                  value={form.take_profit}
                  onChange={(e) => set('take_profit', e.target.value)}
                  className={`${textareaCls} h-28`}
                  placeholder="Example: Fixed 2R target, next structural resistance, or partials plus runner."
                />
              </Field>
              <div className="mt-4">
                <Accordion title="Trailing Stop (Optional)" defaultOpen={false}>
                  <Field label="Trailing stop logic">
                    <input
                      value={form.trailing_stop}
                      onChange={(e) => set('trailing_stop', e.target.value)}
                      className={inputCls}
                      placeholder="Breakeven at 1R, then trail by ATR or swing structure"
                    />
                  </Field>
                </Accordion>
              </div>
              <div className="grid gap-4 md:grid-cols-2 mt-8">
                <Field label="Risk per trade (%)">
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
                <Field label="Max trades per day">
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
                <Accordion title="Session & Day Triggers" defaultOpen={false}>
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
                  <Accordion title="Advanced Context & News Handling" defaultOpen={false}>
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
                    placeholder="Describe 2–3 concrete trades that perfectly matched the strategy."
                  />
                </Field>
                <Field label="Examples of invalid trades">
                  <textarea
                    value={form.invalid_trade_examples}
                    onChange={(e) => set('invalid_trade_examples', e.target.value)}
                    className={`${textareaCls} h-24`}
                    placeholder="Describe situations that looked tradable but should be rejected."
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
