'use client'

import { useState } from 'react'
import { useBacktest } from '@/hooks/useBacktest'
import {
  Section, Field, inputCls, Alert, MetricCard, NavButtons, Spinner, ProgressBar, TabBar
} from '@/components/ui'
import type { BacktestResult } from '@/types'

const TF_DEFAULT_YEARS: Record<string, number> = {
  M1: 1,
  M5: 2,
  M15: 3,
  M30: 4,
  H1: 6,
  H4: 8,
  D1: 10,
}

interface Props {
  sessionId: string
  onComplete: (result: BacktestResult) => void
  onBack: () => void
}

const DEFAULT_CONFIG = {
  provider: 'demo',
  symbol: 'EURUSD',
  timeframe: 'H1',
  initial_capital: 10000,
  date_from: '2018-01-01',
  date_in_sample_end: '2022-12-31',
  date_oos_start: '2023-01-01',
  date_to: '2024-12-31',
  spread_pips: 1.0,
  slippage_pips: 0.5,
  commission_per_lot: 7.0,
  risk_per_trade_pct: 1.0,
  run_walk_forward: true,
  run_monte_carlo: true,
  mc_simulations: 1000,
}

export default function StepBacktest({ sessionId, onComplete, onBack }: Props) {
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const { phase, phaseLabel, isRunning, results, error, run, reset } = useBacktest()

  const set = <K extends keyof typeof config>(k: K, v: (typeof config)[K]) =>
    setConfig((c) => ({ ...c, [k]: v }))
  const adjustDatesForTimeframe = (tf: string) => {
    const years = TF_DEFAULT_YEARS[tf] ?? 5
    const end = new Date()
    const start = new Date(end)
    start.setFullYear(end.getFullYear() - years)
    const oosStart = new Date(end)
    oosStart.setFullYear(end.getFullYear() - 1)
    setConfig((c) => ({
      ...c,
      timeframe: tf,
      date_from: start.toISOString().slice(0, 10),
      date_in_sample_end: oosStart.toISOString().slice(0, 10),
      date_oos_start: oosStart.toISOString().slice(0, 10),
      date_to: end.toISOString().slice(0, 10),
    }))
  }

  const handleRun = () => run(sessionId, config)

  if (results) {
    return (
      <BacktestResults
        results={results}
        onContinue={() => onComplete(results)}
        onBack={reset}
      />
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-amber-400 mb-2">Backtest su dati storici</h1>
        <p className="text-stone-400 text-sm leading-relaxed">
          Il backtest viene eseguito con split temporale rigoroso. I dati di sviluppo
          (in-sample) non si sovrappongono mai ai dati di test (out-of-sample).
          I numeri che contano sono quelli <strong className="text-stone-300">out-of-sample</strong>.
        </p>
      </div>

      {/* Provider selection */}
      <Section title="Fonte dati storici">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            {
              id: 'demo',
              name: 'Demo (sintetici)',
              desc: 'Per testare il flusso UI',
              warn: 'ZERO valore analitico',
            },
            {
              id: 'polygon',
              name: 'Polygon.io',
              desc: 'Dati OHLC reali',
              warn: 'Richiede API key in .env',
            },
            {
              id: 'dukascopy',
              name: 'Dukascopy CSV',
              desc: 'Tick data FX reali',
              warn: 'Richiede download manuale',
            },
          ].map((p) => (
            <button
              key={p.id}
              onClick={() => set('provider', p.id)}
              className={`text-left p-3 rounded border transition-colors ${
                config.provider === p.id
                  ? 'border-amber-500 bg-amber-950/20'
                  : 'border-stone-700 hover:border-stone-500 bg-stone-900'
              }`}
            >
              <div className="text-stone-200 text-sm font-bold">{p.name}</div>
              <div className="text-stone-500 text-xs">{p.desc}</div>
              <div className="text-amber-700 text-xs mt-1">⚠ {p.warn}</div>
            </button>
          ))}
        </div>
      </Section>

      {/* Strumento */}
      <Section title="Strumento e capitale">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="Simbolo">
            <input
              value={config.symbol}
              onChange={(e) => set('symbol', e.target.value)}
              className={inputCls}
              placeholder="EURUSD"
            />
          </Field>
          <Field label="Timeframe">
            <select
              value={config.timeframe}
              onChange={(e) => adjustDatesForTimeframe(e.target.value)}
              className={inputCls}
            >
              {['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'].map((tf) => (
                <option key={tf}>{tf}</option>
              ))}
            </select>
          </Field>
          <Field label="Capitale ($)">
            <input
              type="number"
              value={config.initial_capital}
              onChange={(e) => set('initial_capital', Number(e.target.value))}
              className={inputCls}
            />
          </Field>
          <Field label="Rischio/trade (%)">
            <input
              type="number"
              step={0.1}
              value={config.risk_per_trade_pct}
              onChange={(e) => set('risk_per_trade_pct', Number(e.target.value))}
              className={inputCls}
            />
          </Field>
        </div>
      </Section>

      {/* Split temporale */}
      <Section title="Split temporale">
        <Alert type="warning">
          <strong>Regola fondamentale:</strong> hai già visto i dati OOS durante lo sviluppo
          della strategia? Se sì, il test è compromesso — usa date future che non hai mai analizzato.
        </Alert>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
          <Field label="Dati totali — inizio">
            <input type="date" value={config.date_from}
              onChange={(e) => set('date_from', e.target.value)} className={inputCls} />
          </Field>
          <Field label="In-sample fine (sviluppo)">
            <input type="date" value={config.date_in_sample_end}
              onChange={(e) => set('date_in_sample_end', e.target.value)} className={inputCls} />
          </Field>
          <Field label="Out-of-sample inizio (test)">
            <input type="date" value={config.date_oos_start}
              onChange={(e) => set('date_oos_start', e.target.value)} className={inputCls} />
          </Field>
          <Field label="Dati totali — fine">
            <input type="date" value={config.date_to}
              onChange={(e) => set('date_to', e.target.value)} className={inputCls} />
          </Field>
        </div>
        <div className="flex gap-2 text-xs mt-2">
          <span className="px-2 py-1 bg-blue-950/40 border border-blue-800/40 rounded text-blue-400">
            In-sample: {config.date_from} → {config.date_in_sample_end}
          </span>
          <span className="px-2 py-1 bg-green-950/40 border border-green-800/40 rounded text-green-400">
            Out-of-sample: {config.date_oos_start} → {config.date_to}
          </span>
        </div>
      </Section>

      {/* Costi */}
      <Section title="Costi di esecuzione (non mettere zero — è irrealistico)">
        <div className="grid grid-cols-3 gap-4">
          <Field label="Spread (pips)" tooltip="Spread medio del broker. Per EURUSD: 1–2 pips.">
            <input type="number" step={0.1} value={config.spread_pips}
              onChange={(e) => set('spread_pips', Number(e.target.value))} className={inputCls} />
          </Field>
          <Field label="Slippage (pips)" tooltip="Scostamento tipico tra prezzo richiesto e ottenuto.">
            <input type="number" step={0.1} value={config.slippage_pips}
              onChange={(e) => set('slippage_pips', Number(e.target.value))} className={inputCls} />
          </Field>
          <Field label="Commissione ($/lotto)" tooltip="Round-trip. 0 se conto spread-only.">
            <input type="number" step={0.5} value={config.commission_per_lot}
              onChange={(e) => set('commission_per_lot', Number(e.target.value))} className={inputCls} />
          </Field>
        </div>
      </Section>

      {/* Analisi avanzate */}
      <Section title="Analisi avanzate">
        <div className="space-y-3">
          {[
            {
              key: 'run_walk_forward' as const,
              label: 'Walk-forward analysis',
              desc: 'Raccomandato. Testa la robustezza su periodi sequenziali out-of-sample.',
            },
            {
              key: 'run_monte_carlo' as const,
              label: `Monte Carlo (${config.mc_simulations} simulazioni)`,
              desc: 'Distribuzione degli esiti permutando l\'ordine dei trade. Quantifica il rischio di rovina.',
            },
          ].map((opt) => (
            <label key={opt.key} className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={config[opt.key] as boolean}
                onChange={(e) => set(opt.key, e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-amber-500 flex-shrink-0"
              />
              <div>
                <div className="text-stone-300 text-sm font-bold group-hover:text-stone-200">
                  {opt.label}
                </div>
                <div className="text-stone-500 text-xs">{opt.desc}</div>
              </div>
            </label>
          ))}
        </div>
      </Section>

      {error && <Alert type="error">{error}</Alert>}

      {isRunning && (
        <div className="p-6 bg-stone-900 border border-stone-700 rounded text-center space-y-4">
          <Spinner label={phaseLabel} />
          <p className="text-stone-600 text-xs">
            Il backtest su dati reali richiede 1–5 minuti a seconda del periodo.
          </p>
        </div>
      )}

      <NavButtons
        onBack={onBack}
        onNext={handleRun}
        nextLabel="Esegui backtest →"
        loading={isRunning}
        disabled={isRunning}
      />
    </div>
  )
}

// ─── Results view ─────────────────────────────────────────────────────────────

function BacktestResults({
  results,
  onContinue,
  onBack,
}: {
  results: BacktestResult
  onContinue: () => void
  onBack: () => void
}) {
  const [tab, setTab] = useState<'oos' | 'is' | 'wf' | 'mc' | 'bias'>('oos')
  const oos = results.out_of_sample
  const is_ = results.in_sample
  const wf = results.walk_forward
  const mc = results.monte_carlo
  const bias = results.bias_check

  const metricColor = (v: number, good: number, bad: number) =>
    v >= good ? 'text-green-400' : v <= bad ? 'text-red-400' : 'text-amber-400'

  const tabs = [
    { id: 'oos' as const, label: '★ Out-of-Sample' },
    { id: 'is' as const, label: 'In-Sample' },
    ...(wf ? [{ id: 'wf' as const, label: 'Walk-Forward' }] : []),
    ...(mc ? [{ id: 'mc' as const, label: 'Monte Carlo' }] : []),
    { id: 'bias' as const, label: `Bias (${bias.critical_count + bias.high_count} ⚠)` },
  ]

  const canProceed = bias.critical_count === 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-amber-400 mb-2">Risultati backtest</h1>
        <p className="text-stone-400 text-sm">
          Leggi prima la tab <strong className="text-amber-400">★ Out-of-Sample</strong> —
          sono i numeri che contano. La tab Bias indica la affidabilità metodologica.
        </p>
      </div>

      {/* Bias headline */}
      <div
        className={`px-4 py-3 border rounded flex items-center justify-between ${
          bias.critical_count > 0
            ? 'border-red-700 bg-red-950/20'
            : bias.high_count > 0
              ? 'border-amber-700 bg-amber-950/20'
              : 'border-green-800 bg-green-950/10'
        }`}
      >
        <span className="text-sm font-bold text-stone-200">
          Affidabilità metodologica:
        </span>
        <span
          className={`text-sm font-bold ${
            bias.critical_count > 0
              ? 'text-red-400'
              : bias.high_count > 0
                ? 'text-amber-400'
                : 'text-green-400'
          }`}
        >
          {bias.overall_reliability}
        </span>
      </div>

      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {/* OOS Tab */}
      {tab === 'oos' && (
        <div className="space-y-4">
          <p className="text-stone-500 text-xs">
            ★ Questi sono i dati non visti durante lo sviluppo della strategia.
            Sono il metro di misura più onesto della performance.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Sharpe Ratio" value={oos.sharpe_ratio?.toFixed(2)}
              colorClass={metricColor(oos.sharpe_ratio, 1.0, 0.3)} />
            <MetricCard label="Sortino Ratio" value={oos.sortino_ratio?.toFixed(2)}
              colorClass={metricColor(oos.sortino_ratio, 1.5, 0.5)} />
            <MetricCard label="Calmar Ratio" value={oos.calmar_ratio?.toFixed(2)}
              colorClass={metricColor(oos.calmar_ratio, 1.0, 0.3)} />
            <MetricCard label="Profit Factor" value={oos.profit_factor?.toFixed(2)}
              colorClass={metricColor(oos.profit_factor, 1.5, 1.0)} />
            <MetricCard label="Hit Rate" value={`${(oos.hit_rate * 100)?.toFixed(1)}%`} />
            <MetricCard label="Expectancy (R)" value={oos.expectancy_r?.toFixed(3)}
              colorClass={metricColor(oos.expectancy_r, 0.2, 0)} />
            <MetricCard label="Max Drawdown" value={`${oos.max_drawdown_pct?.toFixed(1)}%`}
              colorClass={metricColor(-oos.max_drawdown_pct, -5, -25)} />
            <MetricCard label="Rendimento %" value={`${oos.total_return_pct?.toFixed(1)}%`}
              colorClass={metricColor(oos.total_return_pct, 10, 0)} />
            <MetricCard label="Trade totali" value={oos.total_trades} />
            <MetricCard label="Trade vincenti" value={oos.winning_trades} />
            <MetricCard label="Max perd. consec." value={oos.max_consecutive_losses}
              colorClass={metricColor(-(oos.max_consecutive_losses ?? 0), -5, -12)} />
            <MetricCard label="Capitale finale" value={`$${oos.final_capital?.toFixed(0)}`} />
          </div>
          <EquityCurve data={oos.equity_curve} />
          {oos.data_quality_warnings?.map((w, i) => (
            <p key={i} className="text-stone-600 text-xs">• {w}</p>
          ))}
        </div>
      )}

      {/* IS Tab */}
      {tab === 'is' && (
        <div className="space-y-4">
          <Alert type="warning">
            I risultati in-sample sono ATTESI essere buoni — la strategia è stata sviluppata
            su questi dati. Non usarli per valutare la strategia. Confrontali con OOS
            per stimare il grado di overfitting.
          </Alert>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Sharpe (IS)" value={is_.sharpe_ratio?.toFixed(2)} />
            <MetricCard label="Rendimento (IS)" value={`${is_.total_return_pct?.toFixed(1)}%`} />
            <MetricCard label="Max DD (IS)" value={`${is_.max_drawdown_pct?.toFixed(1)}%`} />
            <MetricCard label="Trade (IS)" value={is_.total_trades} />
          </div>
          {oos && is_ && (
            <div className="p-4 bg-stone-900 border border-stone-800 rounded space-y-3">
              <div className="text-stone-400 text-xs font-bold">Rapporto IS/OOS (overfitting indicator)</div>
              <ProgressBar
                value={oos.sharpe_ratio ?? 0}
                max={is_.sharpe_ratio ?? 1}
                label={`Sharpe OOS / IS: ${((oos.sharpe_ratio ?? 0) / (is_.sharpe_ratio || 1) * 100).toFixed(0)}%`}
              />
              <p className="text-stone-600 text-xs">
                Se il rapporto OOS/IS è sotto 50%, c&apos;è probabile overfitting.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Walk-forward Tab */}
      {tab === 'wf' && wf && (
        <div className="space-y-4">
          <p className="text-stone-400 text-sm">{wf.interpretation}</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Sharpe medio OOS"
              value={wf.aggregated.avg_sharpe_oos.toFixed(2)}
              colorClass={metricColor(wf.aggregated.avg_sharpe_oos, 0.8, 0.3)} />
            <MetricCard label="Return medio OOS"
              value={`${wf.aggregated.avg_return_oos.toFixed(1)}%`}
              colorClass={metricColor(wf.aggregated.avg_return_oos, 8, 0)} />
            <MetricCard label="Periodi profittevoli"
              value={`${(wf.aggregated.pct_profitable_periods * 100).toFixed(0)}%`}
              colorClass={metricColor(wf.aggregated.pct_profitable_periods, 0.65, 0.4)} />
            <MetricCard label="WF Efficiency"
              value={wf.wf_efficiency.toFixed(2)}
              colorClass={metricColor(wf.wf_efficiency, 0.5, 0.2)} />
          </div>
        </div>
      )}

      {/* Monte Carlo Tab */}
      {tab === 'mc' && mc && (
        <div className="space-y-4">
          <p className="text-stone-400 text-sm">{mc.interpretation}</p>
          <div className="grid grid-cols-3 gap-3">
            <MetricCard label="Capitale P5 (pessimista)"
              value={`$${mc.final_capital.p5.toFixed(0)}`} colorClass="text-red-400" />
            <MetricCard label="Capitale mediano"
              value={`$${mc.final_capital.median.toFixed(0)}`} />
            <MetricCard label="Capitale P95 (ottimista)"
              value={`$${mc.final_capital.p95.toFixed(0)}`} colorClass="text-green-400" />
            <MetricCard label="Prob. profitto"
              value={`${(mc.prob_profit * 100).toFixed(0)}%`}
              colorClass={metricColor(mc.prob_profit, 0.65, 0.45)} />
            <MetricCard label="Max DD mediano"
              value={`${(mc.max_drawdown.p50 * 100).toFixed(1)}%`} />
            <MetricCard label="Prob. rovina (−50%)"
              value={`${(mc.prob_ruin * 100).toFixed(1)}%`}
              colorClass={metricColor(-mc.prob_ruin, -0.01, -0.1)} />
          </div>
        </div>
      )}

      {/* Bias Tab */}
      {tab === 'bias' && (
        <div className="space-y-3">
          <p className="text-stone-400 text-sm">{bias.recommendation}</p>
          {bias.warnings.map((w, i) => (
            <div
              key={i}
              className={`p-3 rounded border space-y-1 ${
                w.severity === 'CRITICAL'
                  ? 'border-red-700/60 bg-red-950/15'
                  : w.severity === 'HIGH'
                    ? 'border-amber-700/50 bg-amber-950/15'
                    : w.severity === 'MEDIUM'
                      ? 'border-stone-600/50 bg-stone-900'
                      : 'border-stone-800 bg-stone-900/50'
              }`}
            >
              <div
                className={`text-xs font-bold ${
                  w.severity === 'CRITICAL'
                    ? 'text-red-400'
                    : w.severity === 'HIGH'
                      ? 'text-amber-400'
                      : 'text-stone-400'
                }`}
              >
                [{w.severity}] {(w.type || (w as any).bias_type || '').replace(/_/g, ' ')}
              </div>
              <div className="text-stone-300 text-sm">{w.description}</div>
              <div className="text-stone-500 text-xs">{w.what_it_means}</div>
              <div className="text-stone-400 text-xs">
                💡 <em>{w.how_to_mitigate}</em>
              </div>
            </div>
          ))}
          {bias.warnings.length === 0 && (
            <Alert type="success">Nessun bias critico rilevato automaticamente.</Alert>
          )}
        </div>
      )}

      <NavButtons
        onBack={onBack}
        onNext={canProceed ? onContinue : undefined}
        nextLabel="Genera il bot MQL5 →"
        disabled={!canProceed}
      />
      {!canProceed && (
        <p className="text-red-400 text-xs text-center">
          Risolvi i problemi CRITICAL prima di procedere. Torna indietro e modifica
          la configurazione del backtest.
        </p>
      )}
    </div>
  )
}

function EquityCurve({ data }: { data: number[] }) {
  if (!data || data.length < 2) return null
  const w = 560
  const h = 100
  const mn = Math.min(...data)
  const mx = Math.max(...data)
  const rng = mx - mn || 1
  const pts = data
    .map((v, i) =>
      `${Math.round((i / (data.length - 1)) * w)},${Math.round(h - ((v - mn) / rng) * h)}`
    )
    .join(' ')
  const color = data[data.length - 1] >= data[0] ? '#34d399' : '#f87171'
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} className="my-3 p-3 bg-stone-900 border border-stone-800 rounded">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}
