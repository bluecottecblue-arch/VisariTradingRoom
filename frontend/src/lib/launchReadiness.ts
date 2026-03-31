import type { BacktestResult, BotResult } from '@/types'

export interface LaunchReadinessPack {
  mode: 'RESEARCH_ONLY' | 'DEMO_ONLY' | 'PAPER_TRADE' | 'LIMITED_LIVE' | 'CONTROLLED_LIVE'
  label: string
  toneClass: string
  summary: string
  firstWeekProtocol: string[]
  operatorBrief: string[]
  deliverables: string[]
  governanceSummary: string
  controls: string[]
  pauseTriggers: string[]
  reviewCadence: string
}

export interface LiveDriftMonitor {
  status: 'TRACKING' | 'WATCH' | 'DRIFTING'
  toneClass: string
  summary: string
  metrics: Array<{ label: string; value: string }>
  watchItems: string[]
}

export function deriveLaunchReadinessPack(
  botResult: BotResult | null | undefined,
  backtestResult: BacktestResult | null | undefined,
): LaunchReadinessPack | null {
  const readiness = botResult?.deployment_readiness
  if (!readiness) return null

  const verdict = backtestResult?.final_decision?.verdict
  const warnings = readiness.warnings || []
  const blockers = readiness.live_blockers || []
  const requiredRuntime = (readiness.runtime_requirements || [])
    .filter((item) => item.required)
    .map((item) => `${item.label}: ${item.value}`)

  let mode: LaunchReadinessPack['mode'] = 'DEMO_ONLY'
  let label = 'Demo-only launch'
  let toneClass = 'border-amber-900/70 bg-amber-950/12 text-amber-300'
  let summary = 'The bot package is usable for controlled installation work, but should still be supervised on demo before any capital is exposed.'

  if (readiness.status === 'BLOCKED' || verdict === 'REJECT' || verdict === 'NEEDS_RESEARCH') {
    mode = 'RESEARCH_ONLY'
    label = 'Research only'
    toneClass = 'border-rose-900/70 bg-rose-950/12 text-rose-300'
    summary = 'Do not deploy this build. Keep it inside research, close the blockers, and improve the strategy before any execution environment is considered.'
  } else if (verdict === 'PAPER_TRADE_ONLY') {
    mode = 'PAPER_TRADE'
    label = 'Paper trade candidate'
    toneClass = 'border-amber-900/70 bg-amber-950/12 text-amber-300'
    summary = 'The strategy is mature enough for paper trading, but not yet strong enough to justify live capital allocation.'
  } else if (verdict === 'LIMITED_LIVE_TEST' && readiness.status === 'READY_FOR_EXPORT') {
    mode = 'LIMITED_LIVE'
    label = 'Limited live candidate'
    toneClass = 'border-cyan-900/70 bg-cyan-950/12 text-cyan-300'
    summary = 'The package is suitable for a tightly supervised live pilot with reduced size, one broker environment, and strict operator oversight.'
  } else if (verdict === 'PRODUCTION_CANDIDATE' && readiness.status === 'READY_FOR_EXPORT') {
    mode = 'CONTROLLED_LIVE'
    label = 'Controlled live candidate'
    toneClass = 'border-cyan-900/70 bg-cyan-950/12 text-cyan-300'
    summary = 'The validation and packaging layers support a controlled live rollout, but the bot still requires supervision, broker-specific checks, and staged capital.'
  }

  const firstWeekProtocol = [
    mode === 'CONTROLLED_LIVE' || mode === 'LIMITED_LIVE'
      ? 'Start with reduced size and one symbol or strategy slot only.'
      : 'Keep the bot on demo or paper until behavior matches the validated workflow.',
    'Review MT5 Journal and trade-by-trade behavior at the end of every session.',
    'Confirm risk sizing, session windows, spread controls, and macro filters before market open.',
    'Pause the bot immediately if you see unexpected entries, missing exits, or runtime errors.',
  ]

  if ((botResult?.code_validation?.checks || {}).has_api_key_input) {
    firstWeekProtocol.push('Verify macro/news runtime inputs and WebRequest permissions before the first live session.')
  }

  const operatorBrief = [
    readiness.recommended_next_action,
    ...blockers.slice(0, 2),
    ...warnings.slice(0, 2),
    ...requiredRuntime.slice(0, 2),
  ].filter(Boolean)

  const deliverables = [
    'Strategy specification',
    'Validation report',
    'Risk assessment',
    'MQL5 bot source',
    'Deployment guide',
  ]

  const governanceSummary =
    mode === 'RESEARCH_ONLY'
      ? 'Nessun deploy: resta in ricerca fino alla chiusura dei blocker.'
      : mode === 'PAPER_TRADE' || mode === 'DEMO_ONLY'
        ? 'Deploy consentito solo in ambiente controllato con revisione giornaliera.'
        : 'Deploy ammesso solo con size ridotta, un ambiente broker e presidio operativo.'

  const controls = [
    mode === 'LIMITED_LIVE' || mode === 'CONTROLLED_LIVE'
      ? 'Avvio con size ridotta e un solo simbolo.'
      : 'Mantieni il bot in demo o paper fino a conferma operativa.',
    'Controllo Journal MT5 e trade log a fine sessione.',
    'Verifica giornaliera di spread, sessione e parametri runtime.',
    'Nessuna escalation di capitale finché il comportamento non replica la validazione.',
  ]

  if ((botResult?.code_validation?.checks || {}).has_api_key_input) {
    controls.push('Conferma ogni giorno API key, WebRequest e filtro macro prima dell’apertura.')
  }

  const pauseTriggers = [
    'Entry inattese o uscite mancanti.',
    'Errori runtime o Journal anomalo.',
    'Drawdown giornaliero oltre soglia operativa.',
    'Deviazione evidente dal profilo validato.',
  ]

  const reviewCadence =
    mode === 'CONTROLLED_LIVE' || mode === 'LIMITED_LIVE'
      ? 'Review giornaliera + confronto settimanale con il profilo validato.'
      : 'Review a fine sessione fino a stabilità confermata.'

  return {
    mode,
    label,
    toneClass,
    summary,
    firstWeekProtocol,
    operatorBrief,
    deliverables,
    governanceSummary,
    controls: controls.slice(0, 5),
    pauseTriggers,
    reviewCadence,
  }
}

export function deriveLiveDriftMonitor(
  backtestResult: BacktestResult | null | undefined,
): LiveDriftMonitor | null {
  if (!backtestResult) return null

  const oos = backtestResult.out_of_sample
  const stabilityPeriods = backtestResult.statistical_validation.subperiod_stability.periods || []
  const lastPeriod = stabilityPeriods[stabilityPeriods.length - 1]
  const baselineExpectancy = Number(oos.expectancy_r || 0)
  const currentExpectancy = Number(lastPeriod?.expectancy_r || baselineExpectancy)
  const dd = Number(oos.max_drawdown_pct || 0)
  const fragility = Number(backtestResult.robustness_suite.parameter_fragility_score || 0)
  const regimeDependence = Number(backtestResult.regime_analysis.dependence_score || 0)
  const variance = Number(backtestResult.risk_review.metrics.variance_pressure_score || 0)
  const degradationPct =
    baselineExpectancy === 0
      ? 0
      : ((baselineExpectancy - currentExpectancy) / Math.max(0.01, Math.abs(baselineExpectancy))) * 100

  let status: LiveDriftMonitor['status'] = 'TRACKING'
  let toneClass = 'border-cyan-900/70 bg-cyan-950/12 text-cyan-300'
  let summary =
    'Il monitor live deve confermare che execution quality, drawdown e regime restino dentro il profilo validato.'

  if (degradationPct >= 35 || dd >= 12 || fragility >= 0.5) {
    status = 'DRIFTING'
    toneClass = 'border-rose-900/70 bg-rose-950/12 text-rose-300'
    summary =
      'Rischio concreto di degenerazione: serve confronto stretto tra comportamento live e profilo validato prima di aumentare esposizione.'
  } else if (degradationPct >= 15 || regimeDependence >= 0.45 || variance >= 0.55) {
    status = 'WATCH'
    toneClass = 'border-amber-900/70 bg-amber-950/12 text-amber-300'
    summary =
      'Il sistema richiede sorveglianza: piccoli cambi di regime o execution cost possono spostare il profilo di rischio.'
  }

  return {
    status,
    toneClass,
    summary,
    metrics: [
      { label: 'Expectancy base', value: `${baselineExpectancy.toFixed(2)}R` },
      { label: 'Ultimo blocco', value: `${currentExpectancy.toFixed(2)}R` },
      { label: 'Drift stimato', value: `${Math.max(0, degradationPct).toFixed(0)}%` },
      { label: 'Max DD', value: `${dd.toFixed(1)}%` },
    ],
    watchItems: [
      regimeDependence >= 0.45
        ? 'Controlla i cambi di regime prima di ogni nuova finestra operativa.'
        : 'Confronta il regime corrente con quello che ha generato il risultato migliore.',
      fragility >= 0.45
        ? 'Execution cost e parametri possono degradare il sistema più del previsto.'
        : 'Mantieni invariati parametri e broker conditions durante la fase iniziale.',
      dd >= 10
        ? 'Sorveglia il drawdown giornaliero e interrompi al primo scostamento anomalo.'
        : 'Verifica che drawdown e trade frequency restino coerenti con il profilo validato.',
    ],
  }
}
