'use client'

import { useState } from 'react'
import { useBacktest } from '@/hooks/useBacktest'
import {
  Section, Field, inputCls, Alert, MetricCard, NavButtons, Spinner, ProgressBar, TabBar
} from '@/components/ui'
import FundamentalFiltersCard from '@/components/FundamentalFiltersCard'
import { DEFAULT_FUNDAMENTAL_FILTERS } from '@/lib/fundamentals'
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
  fundamental_filters: DEFAULT_FUNDAMENTAL_FILTERS,
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

      <FundamentalFiltersCard
        value={config.fundamental_filters}
        onChange={(next) => setConfig((c) => ({ ...c, fundamental_filters: next }))}
        title="Confluenza tecnica + fondamentale per il backtest"
        compact
      />

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
  const [tab, setTab] = useState<'oos' | 'is' | 'wf' | 'mc' | 'research' | 'robust' | 'regime' | 'risk' | 'bias'>('oos')
  const oos = results.out_of_sample
  const is_ = results.in_sample
  const wf = results.walk_forward
  const mc = results.monte_carlo
  const bias = results.bias_check
  const stats = results.statistical_validation
  const robustness = results.robustness_suite
  const regime = results.regime_analysis
  const risk = results.risk_review
  const decision = results.final_decision
  const calendarContext = results.data_info?.calendar_context

  const metricColor = (v: number, good: number, bad: number) =>
    v >= good ? 'text-green-400' : v <= bad ? 'text-red-400' : 'text-amber-400'

  const tabs = [
    { id: 'oos' as const, label: '★ Out-of-Sample' },
    { id: 'is' as const, label: 'In-Sample' },
    ...(wf ? [{ id: 'wf' as const, label: 'Walk-Forward' }] : []),
    ...(mc ? [{ id: 'mc' as const, label: 'Monte Carlo' }] : []),
    { id: 'research' as const, label: 'Statistica' },
    { id: 'robust' as const, label: 'Robustezza' },
    { id: 'regime' as const, label: 'Regimi' },
    { id: 'risk' as const, label: 'Rischio' },
    { id: 'bias' as const, label: `Bias (${bias.critical_count + bias.high_count} ⚠)` },
  ]

  const canProceed = decision.generate_bot_allowed

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-amber-400 mb-2">Risultati backtest</h1>
        <p className="text-stone-400 text-sm">
          La pipeline ora valuta non solo performance OOS ma anche statistica, robustezza,
          dipendenza da regime, rischio operativo e completezza dell&apos;implementazione.
        </p>
      </div>

      <div
        className={`px-4 py-3 border rounded flex items-center justify-between ${
          decision.verdict === 'REJECT'
            ? 'border-red-700 bg-red-950/20'
            : decision.verdict === 'NEEDS_RESEARCH'
              ? 'border-amber-700 bg-amber-950/20'
              : decision.verdict === 'PAPER_TRADE_ONLY'
                ? 'border-blue-700 bg-blue-950/20'
                : 'border-green-800 bg-green-950/10'
        }`}
      >
        <div className="space-y-1">
          <div className="text-xs uppercase tracking-[0.2em] text-stone-500">Final Decision Engine</div>
          <div className="flex items-center gap-3">
            <VerdictPill verdict={decision.verdict} />
            <span className="text-stone-300 text-sm">
              score {decision.overall_score.toFixed(2)} · {decision.confidence_label}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-stone-500 text-xs">Pipeline</div>
          <div className="text-stone-300 text-sm">
            codifiability → backtest → research → verdict
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Codifiability" value={`${(decision.score_breakdown.codifiability * 100).toFixed(0)}%`} />
        <MetricCard label="Robustness" value={`${(decision.score_breakdown.robustness * 100).toFixed(0)}%`} />
        <MetricCard label="Regime independence" value={`${(decision.score_breakdown.regime_independence * 100).toFixed(0)}%`} />
        <MetricCard label="Risk quality" value={`${(decision.score_breakdown.risk_quality * 100).toFixed(0)}%`} />
      </div>

      {(calendarContext?.provider && calendarContext.provider !== 'none') || (calendarContext?.warnings?.length ?? 0) > 0 ? (
        <Alert type={calendarContext?.provider && calendarContext.provider !== 'none' ? 'info' : 'warning'} title="News / Fundamentals context">
          <div className="space-y-1">
            {calendarContext?.provider && (
              <div>
                Provider: <span className="font-bold">{calendarContext.provider}</span>
                {typeof calendarContext.events_used === 'number' ? ` · eventi usati ${calendarContext.events_used}` : ''}
              </div>
            )}
            {(calendarContext?.warnings || []).map((warning, index) => (
              <div key={index}>• {warning}</div>
            ))}
          </div>
        </Alert>
      ) : null}

      {(decision.blockers.length > 0 || decision.reasons.length > 0) && (
        <Alert type={canProceed ? 'info' : 'error'} title={canProceed ? 'Why this is promoted with caution' : 'Why this is rejected / blocked'}>
          <div className="space-y-1">
            {[...decision.blockers, ...decision.reasons].map((item, index) => (
              <div key={index}>• {item}</div>
            ))}
          </div>
        </Alert>
      )}

      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {tab === 'oos' && (
        <div className="space-y-4">
          <p className="text-stone-500 text-xs">
            ★ Questi sono i dati non visti durante lo sviluppo. Restano il metro di misura
            più onesto, ma adesso vengono letti insieme al research verdict finale.
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

      {tab === 'research' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Trade OOS" value={stats.sample_rules.trade_count} />
            <MetricCard label="Sample status" value={stats.sample_rules.status} />
            <MetricCard label="Bootstrap edge +" value={`${(stats.bootstrap.positive_expectancy_probability * 100).toFixed(0)}%`} />
            <MetricCard label="Stability score" value={`${(stats.subperiod_stability.stability_score * 100).toFixed(0)}%`} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Mean R 95% CI" value={`${stats.confidence_intervals.mean_return_per_trade_r.ci_95_low.toFixed(2)} → ${stats.confidence_intervals.mean_return_per_trade_r.ci_95_high.toFixed(2)}`} />
            <MetricCard label="Hit rate 95% CI" value={`${(stats.confidence_intervals.hit_rate.ci_95_low * 100).toFixed(0)}% → ${(stats.confidence_intervals.hit_rate.ci_95_high * 100).toFixed(0)}%`} />
            <MetricCard label="Skew" value={stats.distribution_diagnostics.skew.toFixed(2)} />
            <MetricCard label="Tail concentration" value={`${(stats.distribution_diagnostics.tail_concentration * 100).toFixed(0)}%`} />
          </div>
          <div className="p-4 bg-stone-900 border border-stone-800 rounded space-y-2">
            <div className="text-stone-300 text-sm font-bold">Sottoperiodi</div>
            {stats.subperiod_stability.periods.map((period) => (
              <div key={period.label} className="grid grid-cols-4 gap-3 text-xs text-stone-400">
                <div>{period.label}</div>
                <div>{period.trade_count} trade</div>
                <div>Expectancy {period.expectancy_r.toFixed(2)}R</div>
                <div>Win rate {(period.hit_rate * 100).toFixed(0)}%</div>
              </div>
            ))}
          </div>
          {stats.warnings.length > 0 && (
            <Alert type="warning" title="Statistical humility">
              <div className="space-y-1">
                {stats.warnings.map((warning, index) => (
                  <div key={index}>• {warning}</div>
                ))}
              </div>
            </Alert>
          )}
        </div>
      )}

      {tab === 'robust' && (
        <div className="space-y-4">
          <Alert type="info" title="Robustness suite">
            {robustness.summary}
          </Alert>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Robustness score" value={`${(robustness.robustness_score * 100).toFixed(0)}%`} />
            <MetricCard label="Cost robustness" value={`${(robustness.cost_robustness_score * 100).toFixed(0)}%`} />
            <MetricCard label="Fragility" value={`${(robustness.parameter_fragility_score * 100).toFixed(0)}%`} colorClass={metricColor(-robustness.parameter_fragility_score, -0.2, -0.7)} />
            <MetricCard label="Overfit suspicion" value={`${(robustness.overfit_suspicion_score * 100).toFixed(0)}%`} colorClass={metricColor(-robustness.overfit_suspicion_score, -0.2, -0.7)} />
          </div>
          <HeatmapTable heatmap={robustness.heatmap} />
          <div className="space-y-2">
            {robustness.stress_scenarios.map((scenario) => (
              <div key={scenario.label} className="grid grid-cols-5 gap-3 text-xs p-3 bg-stone-900 border border-stone-800 rounded text-stone-400">
                <div className="font-bold text-stone-300">{scenario.label}</div>
                <div>Return {scenario.total_return_pct.toFixed(1)}%</div>
                <div>Expectancy {scenario.expectancy_r.toFixed(2)}R</div>
                <div>DD {scenario.max_drawdown_pct.toFixed(1)}%</div>
                <div>Sharpe {scenario.sharpe_ratio.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'regime' && (
        <div className="space-y-4">
          {regime.warning && <Alert type="warning">{regime.warning}</Alert>}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Dependence score" value={`${(regime.dependence_score * 100).toFixed(0)}%`} colorClass={metricColor(-regime.dependence_score, -0.25, -0.7)} />
            <MetricCard label="Regimi attivi" value={regime.by_regime.length} />
          </div>
          {regime.by_regime.map((item) => (
            <div key={item.regime} className="p-4 bg-stone-900 border border-stone-800 rounded">
              <div className="text-stone-200 font-bold text-sm">{item.regime}</div>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-2 text-xs text-stone-400">
                <div>{item.trade_count} trade</div>
                <div>Expectancy {item.expectancy_r.toFixed(2)}R</div>
                <div>Win rate {(item.win_rate * 100).toFixed(0)}%</div>
                <div>Drawdown {item.drawdown_r.toFixed(2)}R</div>
                <div>Contrib. {item.contribution_to_total_r_pct.toFixed(0)}%</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'risk' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Daily DD guard" value={`${risk.guards.daily_drawdown_guard_pct.toFixed(1)}%`} />
            <MetricCard label="Kill switch" value={`${risk.guards.equity_kill_switch_pct.toFixed(1)}%`} />
            <MetricCard label="Consecutive loss guard" value={risk.guards.consecutive_losses_guard} />
            <MetricCard label="Risk score" value={`${(risk.risk_score * 100).toFixed(0)}%`} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Worst day" value={`${risk.metrics.worst_daily_return_pct.toFixed(2)}%`} />
            <MetricCard label="Risk concentration" value={`${risk.metrics.risk_concentration_pct.toFixed(2)}%`} />
            <MetricCard label="Risk of ruin proxy" value={`${(risk.metrics.risk_of_ruin_proxy * 100).toFixed(1)}%`} />
            <MetricCard label="Variance pressure" value={`${(risk.metrics.variance_pressure_score * 100).toFixed(0)}%`} />
          </div>
          {risk.warnings.length > 0 && (
            <Alert type="warning" title="Risk review">
              <div className="space-y-1">
                {risk.warnings.map((warning, index) => (
                  <div key={index}>• {warning}</div>
                ))}
              </div>
            </Alert>
          )}
        </div>
      )}

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
          Il bot resta bloccato finché il verdict finale non arriva almeno a `PAPER_TRADE_ONLY`.
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

function VerdictPill({ verdict }: { verdict: string }) {
  const styles: Record<string, string> = {
    REJECT: 'bg-red-950/30 border-red-700 text-red-300',
    NEEDS_RESEARCH: 'bg-amber-950/30 border-amber-700 text-amber-300',
    PAPER_TRADE_ONLY: 'bg-blue-950/30 border-blue-700 text-blue-300',
    LIMITED_LIVE_TEST: 'bg-green-950/20 border-green-700 text-green-300',
    PRODUCTION_CANDIDATE: 'bg-emerald-950/20 border-emerald-700 text-emerald-300',
  }
  return (
    <span className={`px-3 py-1 rounded border text-xs font-bold ${styles[verdict] || 'bg-stone-900 border-stone-700 text-stone-300'}`}>
      {verdict}
    </span>
  )
}

function HeatmapTable({
  heatmap,
}: {
  heatmap: Array<{
    spread_multiplier: number
    cells: Array<{
      slippage_multiplier: number
      total_return_pct: number
      expectancy_r: number
    }>
  }>
}) {
  if (!heatmap?.length) return null
  return (
    <div className="p-4 bg-stone-900 border border-stone-800 rounded space-y-2">
      <div className="text-stone-300 text-sm font-bold">Heatmap cost sensitivity</div>
      {heatmap.map((row) => (
        <div key={row.spread_multiplier} className="grid grid-cols-4 gap-3 text-xs">
          <div className="text-stone-500">Spread ×{row.spread_multiplier.toFixed(1)}</div>
          {row.cells.map((cell) => (
            <div key={cell.slippage_multiplier} className="text-stone-400">
              Slip ×{cell.slippage_multiplier.toFixed(1)} → {cell.total_return_pct.toFixed(1)}%
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
