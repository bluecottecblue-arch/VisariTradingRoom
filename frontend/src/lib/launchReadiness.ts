import type { BacktestResult, BotResult } from '@/types'

export interface LaunchReadinessPack {
  mode: 'RESEARCH_ONLY' | 'DEMO_ONLY' | 'PAPER_TRADE' | 'LIMITED_LIVE' | 'CONTROLLED_LIVE'
  label: string
  toneClass: string
  summary: string
  firstWeekProtocol: string[]
  operatorBrief: string[]
  deliverables: string[]
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

  return {
    mode,
    label,
    toneClass,
    summary,
    firstWeekProtocol,
    operatorBrief,
    deliverables,
  }
}
