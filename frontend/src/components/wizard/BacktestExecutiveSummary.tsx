'use client'

import { Alert } from '@/components/ui'
import type { BacktestResult, DashboardTone, FinalVerdict } from '@/types'

type Tone = DashboardTone

function clampScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function verdictLabel(verdict: FinalVerdict) {
  if (verdict === 'PRODUCTION_CANDIDATE') return 'STRONG'
  if (verdict === 'LIMITED_LIVE_TEST' || verdict === 'PAPER_TRADE_ONLY') return 'VIABLE'
  if (verdict === 'NEEDS_RESEARCH') return 'NEEDS WORK'
  return 'REJECT'
}

function verdictTone(verdict: FinalVerdict): Tone {
  if (verdict === 'PRODUCTION_CANDIDATE') return 'positive'
  if (verdict === 'LIMITED_LIVE_TEST' || verdict === 'PAPER_TRADE_ONLY') return 'warning'
  if (verdict === 'NEEDS_RESEARCH') return 'warning'
  return 'negative'
}

function toneClasses(tone: Tone) {
  if (tone === 'positive') return 'border-cyan-900/70 bg-cyan-950/10 text-cyan-300'
  if (tone === 'warning') return 'border-amber-900/70 bg-amber-950/10 text-amber-300'
  if (tone === 'negative') return 'border-rose-900/70 bg-rose-950/10 text-rose-300'
  return 'border-slate-800 bg-slate-950/60 text-slate-300'
}

function buildWhyEngine(results: BacktestResult) {
  const oos = results.out_of_sample
  const regime = results.regime_analysis
  const robustness = results.robustness_suite
  const distribution = results.statistical_validation.distribution_diagnostics
  const risk = results.risk_review
  const macroWarnings = results.data_info?.calendar_context?.warnings || []

  const opening =
    oos.expectancy_r > 0 && oos.profit_factor > 1.2
      ? 'This system shows a repeatable edge in out-of-sample testing and captures directional moves with positive expectancy.'
      : 'This system does not yet demonstrate a sufficiently repeatable out-of-sample edge to justify automatic deployment.'

  const regimeSentence =
    regime.dependence_score >= 0.45
      ? 'Performance is regime-dependent, with clear sensitivity to trend or volatility shifts.'
      : 'Performance is comparatively consistent across the observed market regimes.'

  const fragilitySentence =
    robustness.parameter_fragility_score >= 0.45
      ? 'Small parameter or cost changes produce material degradation, which makes the system fragile.'
      : 'Parameter and cost perturbations stay within a controlled range, which improves confidence in implementation stability.'

  const distributionSentence =
    distribution.tail_concentration >= 0.35
      ? 'A meaningful share of performance still depends on a relatively small number of outsized trades.'
      : 'Trade outcomes are not excessively concentrated in a handful of extreme winners.'

  const riskSentence =
    risk.risk_score < 0.55 || oos.max_drawdown_pct > 15
      ? 'Risk quality remains the main constraint, with drawdown pressure still too high for comfortable live deployment.'
      : 'Risk quality remains within a controlled range relative to the observed return profile.'

  const macroSentence =
    macroWarnings.length > 0
      ? 'Macro and news context is materially relevant and should stay part of the operating rule set.'
      : ''

  return [opening, regimeSentence, fragilitySentence, distributionSentence, riskSentence, macroSentence]
    .filter(Boolean)
    .slice(0, 3)
    .join(' ')
}

function buildSuggestedImprovements(results: BacktestResult) {
  const suggestions: Array<{ title: string; detail: string }> = []
  const oos = results.out_of_sample
  const regime = results.regime_analysis
  const robustness = results.robustness_suite
  const stats = results.statistical_validation
  const risk = results.risk_review
  const macroProvider = results.data_info?.calendar_context?.provider

  if (oos.total_trades > 220 && oos.expectancy_r < 0.18) {
    suggestions.push({
      title: 'Reduce trade frequency',
      detail: 'The strategy generates a high number of trades relative to its edge per trade. Tightening entry quality should improve signal density.',
    })
  }
  if (regime.dependence_score > 0.45) {
    suggestions.push({
      title: 'Add a stronger regime filter',
      detail: 'Performance changes materially across trend/range or volatility conditions. Add a regime gate before allowing new entries.',
    })
  }
  if (robustness.parameter_fragility_score > 0.45 || robustness.cost_robustness_score < 0.55) {
    suggestions.push({
      title: 'Improve parameter stability',
      detail: 'The system is too sensitive to small changes in execution costs or parameter perturbations. Simplify the rule set or widen tolerances.',
    })
  }
  if (oos.max_drawdown_pct > 12 || risk.metrics.risk_of_ruin_proxy > 0.08) {
    suggestions.push({
      title: 'Tighten stop-loss and risk budget logic',
      detail: 'Drawdown pressure is too visible relative to the observed return profile. Reduce risk per trade or improve protective exits.',
    })
  }
  if (stats.distribution_diagnostics.tail_concentration > 0.35) {
    suggestions.push({
      title: 'Reduce dependency on a few outsized trades',
      detail: 'The payoff distribution is too concentrated. Add confirmation filters or scale back weak entries that dilute median trade quality.',
    })
  }
  if ((!macroProvider || macroProvider === 'none') && oos.max_consecutive_losses >= 6) {
    suggestions.push({
      title: 'Avoid high-impact macro events',
      detail: 'The loss clustering suggests that news or volatility shocks may be distorting entries. Add macro exclusion or post-event waiting rules.',
    })
  }

  if (!suggestions.length) {
    suggestions.push({
      title: 'Preserve the current structure and test in narrower live conditions',
      detail: 'The strategy already clears the main local hurdles. Focus on smaller live validation instead of adding unnecessary complexity.',
    })
  }

  return suggestions.slice(0, 5)
}

function buildStatusBadges(results: BacktestResult) {
  const badges: Array<{ label: string; tone: Tone }> = []
  const verdict = results.final_decision.verdict
  const regime = results.regime_analysis
  const robustness = results.robustness_suite
  const risk = results.risk_review
  const macro = results.data_info?.calendar_context

  if (verdict === 'PRODUCTION_CANDIDATE' || verdict === 'LIMITED_LIVE_TEST') {
    badges.push({ label: 'STABLE', tone: 'positive' })
  }
  if (robustness.parameter_fragility_score > 0.45 || robustness.overfit_suspicion_score > 0.55) {
    badges.push({ label: 'FRAGILE', tone: 'warning' })
  }
  if (risk.metrics.risk_of_ruin_proxy > 0.08 || results.out_of_sample.max_drawdown_pct > 12) {
    badges.push({ label: 'HIGH RISK', tone: 'negative' })
  }
  if ((macro?.events_used || 0) > 0 || (macro?.warnings?.length || 0) > 0) {
    badges.push({ label: 'MACRO SENSITIVE', tone: 'warning' })
  }
  if (verdict === 'NEEDS_RESEARCH' || regime.dependence_score > 0.45) {
    badges.push({ label: 'RESEARCH CANDIDATE', tone: 'neutral' })
  }
  return badges.slice(0, 4)
}

function summaryMetricTone(value: number, thresholdHigh: number, thresholdLow: number): Tone {
  if (value >= thresholdHigh) return 'positive'
  if (value <= thresholdLow) return 'negative'
  return 'warning'
}

function SectionCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  return (
    <section className="border border-slate-800/90 bg-slate-950/72 px-5 py-5">
      <div className="flex items-end justify-between gap-4 border-b border-slate-900/80 pb-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{title}</div>
          {subtitle && <div className="mt-1 text-sm text-slate-400">{subtitle}</div>}
        </div>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function CompactMetric({
  label,
  value,
  tone = 'neutral',
  detail,
}: {
  label: string
  value: string
  tone?: Tone
  detail?: string
}) {
  return (
    <div className={`border px-4 py-4 ${toneClasses(tone)}`}>
      <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-100">{value}</div>
      {detail && <div className="mt-2 text-xs leading-relaxed text-slate-500">{detail}</div>}
    </div>
  )
}

function formatPct(value: number) {
  return `${value.toFixed(1)}%`
}

interface Props {
  results: BacktestResult
}

export default function BacktestExecutiveSummary({ results }: Props) {
  const oos = results.out_of_sample
  const stats = results.statistical_validation
  const robustness = results.robustness_suite
  const regime = results.regime_analysis
  const risk = results.risk_review
  const decision = results.final_decision
  const healthScore = clampScore((decision.overall_score || 0) * 100)
  const whyEngine = buildWhyEngine(results)
  const suggestions = buildSuggestedImprovements(results)
  const badges = buildStatusBadges(results)
  const distribution = stats.distribution_diagnostics
  const stabilityScore = clampScore(
    ((1 - robustness.parameter_fragility_score) * 0.45 +
      (stats.subperiod_stability.stability_score || 0) * 0.35 +
      robustness.cost_robustness_score * 0.2) * 100,
  )

  return (
    <div className="space-y-6">
      <section className={`border px-5 py-5 ${toneClasses(verdictTone(decision.verdict))}`}>
        <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl space-y-4">
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Strategy Verdict</div>
            <div className="flex flex-wrap items-center gap-3">
              <span className={`inline-flex items-center gap-2 border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] ${toneClasses(verdictTone(decision.verdict))}`}>
                {verdictLabel(decision.verdict)}
              </span>
              <div className="text-sm text-slate-400">Research-backed evaluation · {decision.confidence_label.replaceAll('_', ' ')}</div>
            </div>
            <div className="space-y-2">
              <div className="text-4xl font-semibold tracking-tight text-slate-50">{healthScore} / 100</div>
              <div className="text-sm font-medium uppercase tracking-[0.14em] text-slate-500">Strategy Health Score</div>
            </div>
            <p className="max-w-3xl text-sm leading-relaxed text-slate-300">{whyEngine}</p>
            <div className="flex flex-wrap gap-2">
              {badges.map((badge) => (
                <span key={badge.label} className={`inline-flex items-center gap-2 border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] ${toneClasses(badge.tone)}`}>
                  <span className="h-1.5 w-1.5 bg-current" />
                  {badge.label}
                </span>
              ))}
            </div>
          </div>

          <div className="grid min-w-[260px] gap-3">
            <CompactMetric
              label="Validated Pipeline"
              value={decision.generate_bot_allowed ? 'Ready for export gate' : 'Research gate active'}
              tone={decision.generate_bot_allowed ? 'positive' : 'warning'}
              detail="Structured strategy engineering with staged validation before bot export."
            />
            <CompactMetric
              label="Institutional-grade validation layer"
              value={`${oos.total_trades} OOS trades`}
              tone={summaryMetricTone(oos.total_trades, 120, 40)}
              detail="Out-of-sample performance remains the primary decision anchor."
            />
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <CompactMetric label="Sharpe" value={oos.sharpe_ratio.toFixed(2)} tone={summaryMetricTone(oos.sharpe_ratio, 1, 0.35)} />
        <CompactMetric label="Max Drawdown" value={formatPct(oos.max_drawdown_pct)} tone={summaryMetricTone(-oos.max_drawdown_pct, -6, -18)} />
        <CompactMetric label="Win Rate" value={formatPct(oos.hit_rate * 100)} tone={summaryMetricTone(oos.hit_rate, 0.5, 0.35)} />
        <CompactMetric label="Expectancy" value={`${oos.expectancy_r.toFixed(2)}R`} tone={summaryMetricTone(oos.expectancy_r, 0.18, 0)} />
        <CompactMetric label="Profit Factor" value={oos.profit_factor.toFixed(2)} tone={summaryMetricTone(oos.profit_factor, 1.4, 1.0)} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <SectionCard title="Risk Overview" subtitle="What can hurt the system fastest">
          <div className="grid gap-3 md:grid-cols-2">
            <CompactMetric label="Risk Quality" value={`${clampScore(risk.risk_score * 100)} / 100`} tone={summaryMetricTone(risk.risk_score, 0.7, 0.45)} />
            <CompactMetric label="Risk of Ruin Proxy" value={formatPct(risk.metrics.risk_of_ruin_proxy * 100)} tone={summaryMetricTone(-risk.metrics.risk_of_ruin_proxy, -3, -12)} />
            <CompactMetric label="Daily Loss Guard Used" value={formatPct(risk.metrics.worst_daily_return_pct)} tone="warning" detail="Worst single-day return observed in the tested sample." />
            <CompactMetric label="Variance Pressure" value={`${clampScore(risk.metrics.variance_pressure_score * 100)} / 100`} tone={summaryMetricTone(-risk.metrics.variance_pressure_score, -20, -65)} />
          </div>
        </SectionCard>

        <SectionCard title="Stability & Robustness" subtitle="How much the edge survives perturbation">
          <div className="grid gap-3 md:grid-cols-2">
            <CompactMetric label="Stability Score" value={`${stabilityScore} / 100`} tone={summaryMetricTone(stabilityScore, 70, 45)} />
            <CompactMetric label="Robustness Score" value={`${clampScore(robustness.robustness_score * 100)} / 100`} tone={summaryMetricTone(robustness.robustness_score, 0.7, 0.45)} />
            <CompactMetric label="Parameter Fragility" value={formatPct(robustness.parameter_fragility_score * 100)} tone={summaryMetricTone(-robustness.parameter_fragility_score, -20, -55)} />
            <CompactMetric label="Overfit Suspicion" value={formatPct(robustness.overfit_suspicion_score * 100)} tone={summaryMetricTone(-robustness.overfit_suspicion_score, -15, -50)} />
          </div>
        </SectionCard>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard title="Performance by Market Regime" subtitle="Trend vs range and volatility segmentation">
          <div className="space-y-3">
            {regime.by_regime.slice(0, 4).map((item) => (
              <div key={item.regime} className="grid gap-3 border border-slate-900/80 bg-slate-950/55 px-4 py-4 md:grid-cols-[1.1fr_1fr_1fr_1fr]">
                <div>
                  <div className="text-sm font-semibold text-slate-100">{item.regime}</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                    {item.trend_regime} · {item.volatility_regime}
                  </div>
                </div>
                <div className="text-sm text-slate-300">{item.trade_count} trades</div>
                <div className="text-sm text-slate-300">Expectancy {item.expectancy_r.toFixed(2)}R</div>
                <div className="text-sm text-slate-300">Win rate {formatPct(item.win_rate * 100)}</div>
              </div>
            ))}
            {regime.warning && <Alert type="warning">{regime.warning}</Alert>}
          </div>
        </SectionCard>

        <SectionCard title="Trade Distribution" subtitle="PnL shape and concentration">
          <div className="grid gap-3">
            <CompactMetric label="Skewness" value={distribution.skew.toFixed(2)} tone={summaryMetricTone(distribution.skew, 0.2, -0.5)} />
            <CompactMetric label="Fat Tails" value={distribution.kurtosis_excess.toFixed(2)} tone={distribution.kurtosis_excess > 2 ? 'warning' : 'neutral'} detail="Higher values indicate more extreme outlier dependence." />
            <CompactMetric label="Tail Concentration" value={formatPct(distribution.tail_concentration * 100)} tone={summaryMetricTone(-distribution.tail_concentration, -15, -35)} />
            <CompactMetric label="Positive Expectancy Probability" value={formatPct(stats.bootstrap.positive_expectancy_probability * 100)} tone={summaryMetricTone(stats.bootstrap.positive_expectancy_probability, 0.65, 0.5)} />
          </div>
        </SectionCard>
      </section>

      <SectionCard title="Suggested Improvements" subtitle="Professional diagnosis translated into action">
        <div className="grid gap-3">
          {suggestions.map((item) => (
            <div key={item.title} className="flex gap-4 border border-slate-900/80 bg-slate-950/55 px-4 py-4">
              <div className="mt-0.5 h-5 w-5 border border-cyan-900/70 bg-cyan-950/15 text-center text-[11px] font-semibold leading-5 text-cyan-300">
                +
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-100">{item.title}</div>
                <div className="mt-1 text-sm leading-relaxed text-slate-400">{item.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Deliverables" subtitle="What the platform packages for execution and handoff">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {[
            { label: 'Strategy Specification', detail: 'Structured rule set already formalized.', tone: 'positive' as Tone },
            { label: 'Validation Report', detail: 'Research-backed evaluation is ready.', tone: 'positive' as Tone },
            { label: 'Risk Assessment', detail: 'Risk review and robustness diagnostics included.', tone: 'positive' as Tone },
            { label: 'MQL5 Bot', detail: decision.generate_bot_allowed ? 'Unlocked by the validation gate.' : 'Unlocked once the verdict reaches the export threshold.', tone: decision.generate_bot_allowed ? 'positive' as Tone : 'warning' as Tone },
            { label: 'Deployment Guide', detail: 'Provided after export as part of the delivery package.', tone: decision.generate_bot_allowed ? 'neutral' as Tone : 'warning' as Tone },
          ].map((item) => (
            <div key={item.label} className={`border px-4 py-4 ${toneClasses(item.tone)}`}>
              <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{item.label}</div>
              <div className="mt-3 text-sm leading-relaxed text-slate-300">{item.detail}</div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}
