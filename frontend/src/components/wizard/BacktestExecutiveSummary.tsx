'use client'

import { Alert } from '@/components/ui'
import { deriveLiveDriftMonitor } from '@/lib/launchReadiness'
import type { BacktestResult, DashboardTone, FinalVerdict } from '@/types'

type Tone = DashboardTone

function clampScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function verdictLabel(verdict: FinalVerdict) {
  if (verdict === 'PRODUCTION_CANDIDATE') return 'FORTE'
  if (verdict === 'LIMITED_LIVE_TEST' || verdict === 'PAPER_TRADE_ONLY') return 'VALIDA'
  if (verdict === 'NEEDS_RESEARCH') return 'DA RIVEDERE'
  return 'RIFIUTA'
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
      ? 'Questo sistema mostra un vantaggio ripetibile nei test out-of-sample e cattura movimenti direzionali con expectancy positiva.'
      : 'Questo sistema non dimostra ancora un edge out-of-sample abbastanza ripetibile da giustificare un deploy automatico.'

  const regimeSentence =
    regime.dependence_score >= 0.45
      ? 'La performance dipende dal regime, con sensibilità evidente ai cambi di trend o volatilità.'
      : 'La performance è relativamente coerente tra i regimi di mercato osservati.'

  const fragilitySentence =
    robustness.parameter_fragility_score >= 0.45
      ? 'Piccoli cambi di parametri o costi producono un degrado sostanziale, rendendo il sistema fragile.'
      : 'Le perturbazioni di parametri e costi restano entro un range controllato, aumentando la fiducia nella stabilità implementativa.'

  const distributionSentence =
    distribution.tail_concentration >= 0.35
      ? 'Una quota rilevante della performance dipende ancora da un numero relativamente ridotto di trade eccezionali.'
      : 'Gli esiti dei trade non sono eccessivamente concentrati in pochi vincitori estremi.'

  const riskSentence =
    risk.risk_score < 0.55 || oos.max_drawdown_pct > 15
      ? 'La qualità del rischio resta il vincolo principale, con una pressione di drawdown ancora troppo alta per un deploy live tranquillo.'
      : 'La qualità del rischio resta entro un range controllato rispetto al profilo di rendimento osservato.'

  const macroSentence =
    macroWarnings.length > 0
      ? 'Il contesto macro e news è materialmente rilevante e deve restare parte delle regole operative.'
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
      title: 'Riduci la frequenza dei trade',
      detail: 'La strategia genera troppi trade rispetto al vantaggio medio per operazione. Migliorare la qualità degli ingressi dovrebbe aumentare la densità del segnale.',
    })
  }
  if (regime.dependence_score > 0.45) {
    suggestions.push({
      title: 'Aggiungi un filtro di regime più forte',
      detail: 'La performance cambia in modo netto tra trend/range o condizioni di volatilità. Aggiungi un filtro di regime prima di permettere nuovi ingressi.',
    })
  }
  if (robustness.parameter_fragility_score > 0.45 || robustness.cost_robustness_score < 0.55) {
    suggestions.push({
      title: 'Migliora la stabilità dei parametri',
      detail: 'Il sistema è troppo sensibile a piccoli cambi di costi esecutivi o parametri. Semplifica il set di regole o amplia le tolleranze.',
    })
  }
  if (oos.max_drawdown_pct > 12 || risk.metrics.risk_of_ruin_proxy > 0.08) {
    suggestions.push({
      title: 'Stringi la logica di stop e budget rischio',
      detail: 'La pressione del drawdown è troppo alta rispetto al profilo di rendimento osservato. Riduci il rischio per trade o migliora le uscite protettive.',
    })
  }
  if (stats.distribution_diagnostics.tail_concentration > 0.35) {
    suggestions.push({
      title: 'Riduci la dipendenza da pochi trade fuori scala',
      detail: 'La distribuzione dei payoff è troppo concentrata. Aggiungi filtri di conferma o riduci gli ingressi deboli che abbassano la qualità mediana dei trade.',
    })
  }
  if ((!macroProvider || macroProvider === 'none') && oos.max_consecutive_losses >= 6) {
    suggestions.push({
      title: 'Evita eventi macro ad alto impatto',
      detail: 'L’addensamento delle perdite suggerisce che news o shock di volatilità stiano distorcendo gli ingressi. Aggiungi esclusioni macro o regole di attesa post-evento.',
    })
  }

  if (!suggestions.length) {
    suggestions.push({
      title: 'Mantieni la struttura attuale e testa in live controllato',
      detail: 'La strategia supera già i principali ostacoli locali. Concentrati su una validazione live più stretta invece di aggiungere complessità inutile.',
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
    badges.push({ label: 'STABILE', tone: 'positive' })
  }
  if (robustness.parameter_fragility_score > 0.45 || robustness.overfit_suspicion_score > 0.55) {
    badges.push({ label: 'FRAGILE', tone: 'warning' })
  }
  if (risk.metrics.risk_of_ruin_proxy > 0.08 || results.out_of_sample.max_drawdown_pct > 12) {
    badges.push({ label: 'ALTO RISCHIO', tone: 'negative' })
  }
  if ((macro?.events_used || 0) > 0 || (macro?.warnings?.length || 0) > 0) {
    badges.push({ label: 'SENSIBILE AL MACRO', tone: 'warning' })
  }
  if (verdict === 'NEEDS_RESEARCH' || regime.dependence_score > 0.45) {
    badges.push({ label: 'DA RICERCARE', tone: 'neutral' })
  }
  return badges.slice(0, 4)
}

function summaryMetricTone(value: number, thresholdHigh: number, thresholdLow: number): Tone {
  if (value >= thresholdHigh) return 'positive'
  if (value <= thresholdLow) return 'negative'
  return 'warning'
}

function confidenceLabel(label: string) {
  const normalized = label.toUpperCase()
  if (normalized === 'HIGH_CONFIDENCE') return 'alta confidenza'
  if (normalized === 'MEDIUM_CONFIDENCE') return 'confidenza media'
  if (normalized === 'LOW_CONFIDENCE') return 'bassa confidenza'
  return label.replaceAll('_', ' ').toLowerCase()
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
  const driftMonitor = deriveLiveDriftMonitor(results)
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
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Verdetto strategia</div>
            <div className="flex flex-wrap items-center gap-3">
              <span className={`inline-flex items-center gap-2 border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] ${toneClasses(verdictTone(decision.verdict))}`}>
                {verdictLabel(decision.verdict)}
              </span>
              <div className="text-sm text-slate-400">Valutazione supportata dalla ricerca · {confidenceLabel(decision.confidence_label)}</div>
            </div>
            <div className="space-y-2">
              <div className="text-4xl font-semibold tracking-tight text-slate-50">{healthScore} / 100</div>
              <div className="text-sm font-medium uppercase tracking-[0.14em] text-slate-500">Punteggio salute strategia</div>
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
              label="Pipeline validata"
              value={decision.generate_bot_allowed ? 'Pronta per la soglia export' : 'Soglia ricerca attiva'}
              tone={decision.generate_bot_allowed ? 'positive' : 'warning'}
              detail="Ingegneria strategica strutturata con validazione a step prima dell’export del bot."
            />
            <CompactMetric
              label="Layer di validazione istituzionale"
              value={`${oos.total_trades} trade OOS`}
              tone={summaryMetricTone(oos.total_trades, 120, 40)}
              detail="La performance out-of-sample resta l’ancora principale della decisione."
            />
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-5">
        <CompactMetric label="Sharpe" value={oos.sharpe_ratio.toFixed(2)} tone={summaryMetricTone(oos.sharpe_ratio, 1, 0.35)} />
        <CompactMetric label="Max drawdown" value={formatPct(oos.max_drawdown_pct)} tone={summaryMetricTone(-oos.max_drawdown_pct, -6, -18)} />
        <CompactMetric label="Win rate" value={formatPct(oos.hit_rate * 100)} tone={summaryMetricTone(oos.hit_rate, 0.5, 0.35)} />
        <CompactMetric label="Expectancy" value={`${oos.expectancy_r.toFixed(2)}R`} tone={summaryMetricTone(oos.expectancy_r, 0.18, 0)} />
        <CompactMetric label="Profit factor" value={oos.profit_factor.toFixed(2)} tone={summaryMetricTone(oos.profit_factor, 1.4, 1.0)} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <SectionCard title="Panoramica rischio" subtitle="Cosa può danneggiare il sistema più rapidamente">
          <div className="grid gap-3 md:grid-cols-2">
            <CompactMetric label="Qualità rischio" value={`${clampScore(risk.risk_score * 100)} / 100`} tone={summaryMetricTone(risk.risk_score, 0.7, 0.45)} />
            <CompactMetric label="Proxy rischio rovina" value={formatPct(risk.metrics.risk_of_ruin_proxy * 100)} tone={summaryMetricTone(-risk.metrics.risk_of_ruin_proxy, -3, -12)} />
            <CompactMetric label="Perdita giornaliera usata" value={formatPct(risk.metrics.worst_daily_return_pct)} tone="warning" detail="Peggior rendimento osservato in una singola giornata del campione testato." />
            <CompactMetric label="Pressione varianza" value={`${clampScore(risk.metrics.variance_pressure_score * 100)} / 100`} tone={summaryMetricTone(-risk.metrics.variance_pressure_score, -20, -65)} />
          </div>
        </SectionCard>

        <SectionCard title="Stabilità e robustezza" subtitle="Quanto l’edge sopravvive alle perturbazioni">
          <div className="grid gap-3 md:grid-cols-2">
            <CompactMetric label="Punteggio stabilità" value={`${stabilityScore} / 100`} tone={summaryMetricTone(stabilityScore, 70, 45)} />
            <CompactMetric label="Punteggio robustezza" value={`${clampScore(robustness.robustness_score * 100)} / 100`} tone={summaryMetricTone(robustness.robustness_score, 0.7, 0.45)} />
            <CompactMetric label="Fragilità parametri" value={formatPct(robustness.parameter_fragility_score * 100)} tone={summaryMetricTone(-robustness.parameter_fragility_score, -20, -55)} />
            <CompactMetric label="Sospetto overfit" value={formatPct(robustness.overfit_suspicion_score * 100)} tone={summaryMetricTone(-robustness.overfit_suspicion_score, -15, -50)} />
          </div>
        </SectionCard>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard title="Performance per regime di mercato" subtitle="Segmentazione trend/range e volatilità">
          <div className="space-y-3">
            {regime.by_regime.slice(0, 4).map((item) => (
              <div key={item.regime} className="grid gap-3 border border-slate-900/80 bg-slate-950/55 px-4 py-4 md:grid-cols-[1.1fr_1fr_1fr_1fr]">
                <div>
                  <div className="text-sm font-semibold text-slate-100">{item.regime}</div>
                  <div className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                    {item.trend_regime} · {item.volatility_regime}
                  </div>
                </div>
                <div className="text-sm text-slate-300">{item.trade_count} trade</div>
                <div className="text-sm text-slate-300">Expectancy {item.expectancy_r.toFixed(2)}R</div>
                <div className="text-sm text-slate-300">Win rate {formatPct(item.win_rate * 100)}</div>
              </div>
            ))}
            {regime.warning && <Alert type="warning">{regime.warning}</Alert>}
          </div>
        </SectionCard>

        <SectionCard title="Distribuzione trade" subtitle="Forma del PnL e concentrazione">
          <div className="grid gap-3">
            <CompactMetric label="Asimmetria" value={distribution.skew.toFixed(2)} tone={summaryMetricTone(distribution.skew, 0.2, -0.5)} />
            <CompactMetric label="Code grasse" value={distribution.kurtosis_excess.toFixed(2)} tone={distribution.kurtosis_excess > 2 ? 'warning' : 'neutral'} detail="Valori più alti indicano maggiore dipendenza da outlier estremi." />
            <CompactMetric label="Concentrazione code" value={formatPct(distribution.tail_concentration * 100)} tone={summaryMetricTone(-distribution.tail_concentration, -15, -35)} />
            <CompactMetric label="Probabilità expectancy positiva" value={formatPct(stats.bootstrap.positive_expectancy_probability * 100)} tone={summaryMetricTone(stats.bootstrap.positive_expectancy_probability, 0.65, 0.5)} />
          </div>
        </SectionCard>
      </section>

      <SectionCard title="Migliorie suggerite" subtitle="Diagnosi professionale tradotta in azione">
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

      {driftMonitor && (
        <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <SectionCard title="Monitor drift live" subtitle="Cosa osservare dopo il deploy">
            <div className={`border px-4 py-4 ${driftMonitor.toneClass}`}>
              <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{driftMonitor.status}</div>
              <div className="mt-2 text-sm leading-relaxed text-slate-300">{driftMonitor.summary}</div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {driftMonitor.metrics.map((item) => (
                  <div key={item.label} className="border border-slate-900/80 bg-slate-950/50 px-3 py-3">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{item.label}</div>
                    <div className="mt-2 text-sm font-semibold text-slate-100">{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Trigger di drift" subtitle="Metti in pausa prima che l’edge degradi">
            <div className="space-y-3">
              {driftMonitor.watchItems.map((item, index) => (
                <div key={index} className="border border-slate-900/80 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                  {item}
                </div>
              ))}
            </div>
          </SectionCard>
        </section>
      )}

      <SectionCard title="Deliverable" subtitle="Cosa la piattaforma prepara per esecuzione e handoff">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          {[
            { label: 'Specifica strategia', detail: 'Set di regole strutturato già formalizzato.', tone: 'positive' as Tone },
            { label: 'Report validazione', detail: 'La valutazione supportata dalla ricerca è pronta.', tone: 'positive' as Tone },
            { label: 'Valutazione rischio', detail: 'Inclusi revisione rischio e diagnostica di robustezza.', tone: 'positive' as Tone },
            { label: 'Algoritmo MQL5', detail: decision.generate_bot_allowed ? 'Sbloccato dalla soglia di validazione.' : 'Sbloccato quando il verdetto raggiunge la soglia export.', tone: decision.generate_bot_allowed ? 'positive' as Tone : 'warning' as Tone },
            { label: 'Guida deploy', detail: 'Fornita dopo l’export come parte del pacchetto finale.', tone: decision.generate_bot_allowed ? 'neutral' as Tone : 'warning' as Tone },
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
