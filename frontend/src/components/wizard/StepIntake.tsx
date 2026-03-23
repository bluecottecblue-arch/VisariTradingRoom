'use client'

import { useEffect, useState } from 'react'
import { strategyApi, formatError } from '@/lib/api'
import FundamentalFiltersCard from '@/components/FundamentalFiltersCard'
import { DEFAULT_FUNDAMENTAL_FILTERS, summarizeFundamentalFilters } from '@/lib/fundamentals'
import { Section, Field, inputCls, textareaCls, Alert, NavButtons } from '@/components/ui'
import type { ParseResult, PreflightResult, StrategyIntake } from '@/types'

const TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1']
const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
const DAY_LABELS: Record<string, string> = {
  MON: 'Lun', TUE: 'Mar', WED: 'Mer', THU: 'Gio',
  FRI: 'Ven', SAT: 'Sab', SUN: 'Dom',
}

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
  fundamental_filters: DEFAULT_FUNDAMENTAL_FILTERS,
}

interface Props {
  onComplete: (sessionId: string, result: ParseResult) => void
}

export default function StepIntake({ onComplete }: Props) {
  const [form, setForm] = useState<StrategyIntake>(DEFAULT_FORM)
  const [loading, setLoading] = useState(false)
  const [preflight, setPreflight] = useState<PreflightResult | null>(null)
  const [preflightLoading, setPreflightLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const saved = sessionStorage.getItem('sf_intake_form')
    if (!saved) return
    try {
      setForm(JSON.parse(saved))
    } catch {}
  }, [])

  useEffect(() => {
    sessionStorage.setItem('sf_intake_form', JSON.stringify(form))
  }, [form])

  useEffect(() => {
    const requiredReady =
      !!form.name.trim() &&
      !!form.market.trim() &&
      !!form.long_entry.trim() &&
      !!form.invalidation.trim() &&
      !!form.stop_loss.trim() &&
      !!form.take_profit.trim()

    if (!requiredReady) {
      setPreflight(null)
      return
    }

    const timer = window.setTimeout(async () => {
      setPreflightLoading(true)
      try {
        const result = await strategyApi.preflight(buildPayload(form)) as PreflightResult
        setPreflight(result)
      } catch {
        setPreflight(null)
      } finally {
        setPreflightLoading(false)
      }
    }, 450)

    return () => window.clearTimeout(timer)
  }, [form])

  const set = <K extends keyof StrategyIntake>(k: K, v: StrategyIntake[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const toggleDay = (day: string) =>
    set(
      'trading_days',
      form.trading_days.includes(day)
        ? form.trading_days.filter((d) => d !== day)
        : [...form.trading_days, day],
    )

  const validate = () => {
    if (!form.name.trim()) return 'Inserisci il nome della strategia'
    if (!form.market.trim()) return 'Inserisci il mercato (es. EURUSD)'
    if (!form.long_entry.trim()) return 'Descrivi il setup di ingresso long'
    if (!form.stop_loss.trim()) return 'Descrivi il tuo stop loss'
    if (!form.invalidation.trim()) return 'Descrivi le condizioni di invalidazione'
    if (!form.take_profit.trim()) return 'Descrivi il take profit'
    return null
  }

  const buildPayload = (value: StrategyIntake) => ({
    ...value,
    news_management: summarizeFundamentalFilters(value.fundamental_filters, value.news_management),
  })

  const handleSubmit = async () => {
    const err = validate()
    if (err) { setError(err); return }

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
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-amber-400 mb-2">
          Descrivi la tua strategia
        </h1>
        <p className="text-stone-400 text-sm leading-relaxed">
          Scrivi come operi davvero. Il sistema verifica prima se la strategia è
          codificabile e blocca subito le parti troppo vaghe, così non sprechi token
          su formalizzazione e codice quando mancano dettagli decisivi.
        </p>
      </div>

      {/* Sezione 1 */}
      <Section title="1. Identità della strategia">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field
            label="Nome della strategia"
            required
            tooltip="Un nome che ti aiuti a riconoscerla. Es. 'London Breakout EMA' o 'Pullback su supporto'"
          >
            <input
              value={form.name}
              onChange={(e) => set('name', e.target.value)}
              className={inputCls}
              placeholder="Es. London Breakout Pullback"
            />
          </Field>
          <Field
            label="Mercato / Strumento"
            required
            tooltip="Quale strumento tradi? Es. EURUSD, XAUUSD, NQ100, BTCUSD"
          >
            <input
              value={form.market}
              onChange={(e) => set('market', e.target.value)}
              className={inputCls}
              placeholder="Es. EURUSD"
            />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Timeframe di analisi"
            tooltip="Dove vedi il contesto e identifichi il setup"
          >
            <select
              value={form.analysis_timeframe}
              onChange={(e) => set('analysis_timeframe', e.target.value)}
              className={inputCls}
            >
              {TIMEFRAMES.map((tf) => (
                <option key={tf}>{tf}</option>
              ))}
            </select>
          </Field>
          <Field
            label="Timeframe di esecuzione"
            tooltip="Dove entri effettivamente nel trade"
          >
            <select
              value={form.execution_timeframe}
              onChange={(e) => set('execution_timeframe', e.target.value)}
              className={inputCls}
            >
              {TIMEFRAMES.map((tf) => (
                <option key={tf}>{tf}</option>
              ))}
            </select>
          </Field>
        </div>
      </Section>

      {/* Sezione 2 */}
      <Section title="2. Setup di ingresso">
        <Field
          label="Setup LONG — quando entri long?"
          required
          tooltip="Descrivi le condizioni precise. Menziona indicatori, price action, struttura di mercato, timeframe. Più sei specifico, meglio Claude potrà codificarlo."
        >
          <textarea
            value={form.long_entry}
            onChange={(e) => set('long_entry', e.target.value)}
            className={`${textareaCls} h-32`}
            placeholder="Es. Su H4 il prezzo deve essere sopra la EMA200. Aspetto che il prezzo torni sulla EMA20 e formi una rejection candle (wick lungo verso il basso, corpo nella metà superiore). Entro su M15 alla chiusura della prima candela bullish dopo la rejection, solo se l'RSI14 è sotto 50 e sta risalendo..."
          />
          <QualityHint value={form.long_entry} />
        </Field>
        <Field
          label="Setup SHORT — quando entri short? (opzionale)"
          tooltip="Lascia vuoto se operi solo in direzione long"
        >
          <textarea
            value={form.short_entry}
            onChange={(e) => set('short_entry', e.target.value)}
            className={`${textareaCls} h-24`}
            placeholder="Lascia vuoto se operi solo long"
          />
        </Field>
        <Field
          label="Invalidazione — quando il setup NON è più valido?"
          required
          tooltip="Cosa deve succedere per 'uccidere' il setup prima ancora di entrare?"
        >
          <textarea
            value={form.invalidation}
            onChange={(e) => set('invalidation', e.target.value)}
            className={`${textareaCls} h-20`}
            placeholder="Es. Se il prezzo chiude sopra il massimo della rejection candle, oppure se passa più di 1 ora senza entry, il setup è invalidato..."
          />
          <QualityHint value={form.invalidation} />
        </Field>
      </Section>

      {/* Sezione 3 */}
      <Section title="3. Gestione del rischio">
        <Field
          label="Stop Loss — dove lo metti e perché?"
          required
          tooltip="Descrivi la logica del posizionamento, non solo un numero fisso. Es. 'sotto il minimo della candela di setup' è meglio di '20 pips'"
        >
          <textarea
            value={form.stop_loss}
            onChange={(e) => set('stop_loss', e.target.value)}
            className={`${textareaCls} h-20`}
            placeholder="Es. Sotto il minimo della rejection candle + 5 pips di buffer, oppure sotto il livello di supporto più vicino su H4..."
          />
          <QualityHint value={form.stop_loss} />
        </Field>
        <Field
          label="Take Profit — dove esci con profitto?"
          tooltip="Target fisso, rapporto R:R, struttura di mercato, trailing, uscita manuale..."
        >
          <textarea
            value={form.take_profit}
            onChange={(e) => set('take_profit', e.target.value)}
            className={`${textareaCls} h-20`}
            placeholder="Es. 2R dal rischio iniziale, oppure alla prossima resistenza su H4, oppure gestisco manualmente lo scalare della posizione..."
          />
        </Field>
        <Field
          label="Trailing stop (opzionale)"
          tooltip="Come gestisci lo stop mentre sei in profitto?"
        >
          <input
            value={form.trailing_stop}
            onChange={(e) => set('trailing_stop', e.target.value)}
            className={inputCls}
            placeholder="Es. Breakeven a 1R, poi trailing di 15 pips ogni 0.5R guadagnato"
          />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Rischio per trade (%)"
            tooltip="Percentuale del capitale totale che rischi su ogni singolo trade"
          >
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
          <Field
            label="Max trade al giorno"
            tooltip="Quanti trade al massimo apri in una singola giornata?"
          >
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

      {/* Sezione 4 */}
      <Section title="4. Sessioni e orari">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Inizio sessione (UTC)">
            <input
              type="time"
              value={form.trading_hours_start}
              onChange={(e) => set('trading_hours_start', e.target.value)}
              className={inputCls}
            />
          </Field>
          <Field label="Fine sessione (UTC)">
            <input
              type="time"
              value={form.trading_hours_end}
              onChange={(e) => set('trading_hours_end', e.target.value)}
              className={inputCls}
            />
          </Field>
        </div>
        <Field label="Giorni di trading">
          <div className="flex gap-2 flex-wrap">
            {DAYS.map((day) => (
              <button
                key={day}
                type="button"
                onClick={() => toggleDay(day)}
                className={`px-3 py-1.5 rounded text-xs font-bold border transition-colors ${
                  form.trading_days.includes(day)
                    ? 'bg-amber-500 border-amber-500 text-stone-950'
                    : 'bg-stone-900 border-stone-700 text-stone-400 hover:border-stone-500'
                }`}
              >
                {DAY_LABELS[day]}
              </button>
            ))}
          </div>
        </Field>
      </Section>

      {/* Sezione 5 */}
      <Section title="5. Filtri e condizioni (opzionale ma utile)">
        <p className="text-stone-500 text-xs">
          Descrivi in linguaggio naturale. Claude identificherà cosa è codificabile
          e proporrà alternative oggettive per le parti soggettive.
        </p>
        <Field
          label="Filtro di trend"
          tooltip="Come stabilisci se il mercato è in trend prima di cercare setup?"
        >
          <input
            value={form.trend_filter}
            onChange={(e) => set('trend_filter', e.target.value)}
            className={inputCls}
            placeholder="Es. Opero solo se su D1 il prezzo è sopra la MA200 e la MA50 è inclinata verso l'alto"
          />
        </Field>
        <Field label="Filtro di volatilità">
          <input
            value={form.volatility_filter}
            onChange={(e) => set('volatility_filter', e.target.value)}
            className={inputCls}
            placeholder="Es. Evito quando l'ATR giornaliero è sotto 50 pips o sopra 200 pips"
          />
        </Field>
        <Field label="Gestione notizie macro">
          <input
            value={form.news_management}
            onChange={(e) => set('news_management', e.target.value)}
            className={inputCls}
            placeholder="Es. Non apro trade 30 minuti prima e dopo notizie ad alto impatto (NFP, BCE, Fed)"
          />
        </Field>
      </Section>

      <FundamentalFiltersCard
        value={form.fundamental_filters}
        onChange={(next) => set('fundamental_filters', next)}
      />

      {/* Sezione 6 */}
      <Section title="6. Esempi concreti (molto importanti)">
        <p className="text-stone-500 text-xs">
          Gli esempi sono la cosa più utile che puoi fornire. Aiutano Claude a capire
          esattamente cosa intendi con parole come &quot;setup pulito&quot; o
          &quot;mercato in trend&quot;.
        </p>
        <Field
          label="Esempi di trade VALIDI"
          tooltip="2-3 trade che hai fatto (o avresti fatto) che rispettavano perfettamente la tua strategia. Con date se ricordi."
        >
          <textarea
            value={form.valid_trade_examples}
            onChange={(e) => set('valid_trade_examples', e.target.value)}
            className={`${textareaCls} h-28`}
            placeholder="Es. EURUSD 12 marzo 2024: su H4 il prezzo era in trend rialzista con EMA20 sopra EMA50. Alle 10:15 UTC ha toccato la EMA20 su H4 con una candela di rimbalzo forte. Su M15 ho aspettato la chiusura della prima candela bullish e sono entrato long a 1.0892, SL a 1.0865, TP a 1.0946..."
          />
        </Field>
        <Field
          label="Esempi di trade INVALIDI"
          tooltip="Situazioni che sembravano setup ma non lo erano. Fondamentale per definire bene i filtri."
        >
          <textarea
            value={form.invalid_trade_examples}
            onChange={(e) => set('invalid_trade_examples', e.target.value)}
            className={`${textareaCls} h-20`}
            placeholder="Es. Evito setup durante le prime 30 minuti di sessione americana perché troppo volatile. Evito quando il mercato è appena uscito da una notizia macro anche se il setup sembra buono..."
          />
        </Field>
        <Field label="Note aggiuntive">
          <textarea
            value={form.additional_notes}
            onChange={(e) => set('additional_notes', e.target.value)}
            className={`${textareaCls} h-16`}
            placeholder="Qualsiasi altra cosa che ritieni importante e che non hai inserito sopra..."
          />
        </Field>
      </Section>

      {preflight && (
        <section className="rounded-lg border border-stone-800 bg-stone-900/70 p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-stone-500">Preflight gratuito</p>
              <h2 className="text-lg font-bold text-stone-100">
                {preflight.status === 'VALID' ? 'Pipeline pronta' : 'Pipeline bloccata prima dei token'}
              </h2>
            </div>
            <div className={`rounded px-3 py-1 text-xs font-bold ${
              preflight.status === 'VALID'
                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-700/60'
                : 'bg-amber-500/10 text-amber-300 border border-amber-700/50'
            }`}>
              completezza {Math.round(preflight.completeness_score * 100)}%
            </div>
          </div>
          <p className="text-sm text-stone-400">{preflight.message}</p>
          <div className="grid gap-3 md:grid-cols-3">
            {Object.entries(preflight.expected_stages).map(([stage, estimate]) => (
              <div key={stage} className="rounded border border-stone-800 bg-stone-950/70 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold uppercase tracking-[0.18em] text-stone-400">{stage}</span>
                  <span className={`text-[11px] font-bold ${estimate.enabled ? 'text-emerald-300' : 'text-amber-300'}`}>
                    {estimate.enabled ? `~$${estimate.estimated_cost_usd.toFixed(4)}` : 'stopped'}
                  </span>
                </div>
                <p className="mt-2 text-xs text-stone-500">{estimate.reason}</p>
                {estimate.enabled && (
                  <div className="mt-2 space-y-1 text-[11px] text-stone-400">
                    <div>input ~ {estimate.estimated_input_tokens} tok</div>
                    <div>output ~ {estimate.estimated_output_tokens} tok</div>
                    <div>cap {estimate.max_tokens}</div>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <p className="text-stone-400">
              {preflight.next_recommended_action}
              {preflight.blocking_items > 0 ? ` Blocchi aperti: ${preflight.blocking_items}.` : ''}
            </p>
            <p className="font-bold text-stone-200">
              costo massimo atteso pipeline ~ ${preflight.estimated_total_cost_usd.toFixed(4)}
            </p>
          </div>
        </section>
      )}

      {preflightLoading && !loading && (
        <p className="text-stone-500 text-xs text-center">
          Pre-check locale in corso: nessun token speso.
        </p>
      )}

      {error && <Alert type="error">{error}</Alert>}

      <NavButtons
        onNext={handleSubmit}
        nextLabel={loading ? 'Claude sta analizzando...' : 'Analizza la mia strategia →'}
        loading={loading}
        disabled={loading}
      />

      {loading && (
        <p className="text-stone-500 text-xs text-center">
          Claude analizzerà la tua strategia e identificherà le parti codificabili.
          Richiede 20–60 secondi.
        </p>
      )}
    </div>
  )
}

function QualityHint({ value }: { value: string }) {
  return (
    <div className="flex justify-between text-xs mt-1">
      <span className={value.length < 50 ? 'text-amber-600' : 'text-stone-600'}>
        {value.length < 50 ? '⚠ Aggiungi più dettagli per una traduzione migliore' : '✓ Buona descrizione'}
      </span>
      <span className="text-stone-700">{value.length} caratteri</span>
    </div>
  )
}
