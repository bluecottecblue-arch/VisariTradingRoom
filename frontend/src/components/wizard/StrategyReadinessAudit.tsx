'use client'

import { ProgressBar } from '@/components/ui'
import type { PreflightResult } from '@/types'

function toneForPreflight(preflight: PreflightResult | null) {
  if (!preflight) {
    return {
      badge: 'border-slate-800 bg-slate-950/60 text-slate-400',
      title: 'Waiting for critical strategy inputs',
      subtitle: 'Add the core market, entry, invalidation and exit rules to unlock a free readiness audit.',
    }
  }

  if (preflight.status === 'VALID' && preflight.blocking_items === 0) {
    return {
      badge: 'border-cyan-900/70 bg-cyan-950/12 text-cyan-300',
      title: 'Ready for structured review',
      subtitle: 'The strategy is specific enough to justify paid AI review and downstream validation.',
    }
  }

  if ((preflight.completeness_score || 0) >= 0.7) {
    return {
      badge: 'border-amber-900/70 bg-amber-950/12 text-amber-300',
      title: 'Needs clarification before token spend',
      subtitle: 'The logic is promising but still leaves too much room for interpretation.',
    }
  }

  return {
    badge: 'border-rose-900/70 bg-rose-950/12 text-rose-300',
    title: 'Too vague for reliable automation',
    subtitle: 'Clarify the setup before paying for parse, formalization and bot generation.',
  }
}

function stageLabel(stage: string) {
  if (stage === 'parse') return 'Structured review'
  if (stage === 'formalize') return 'Formal specification'
  if (stage === 'botgen') return 'Bot export candidate'
  return stage
}

export default function StrategyReadinessAudit({
  preflight,
  loading = false,
}: {
  preflight: PreflightResult | null
  loading?: boolean
}) {
  const tone = toneForPreflight(preflight)
  const readinessScore = Math.round((preflight?.completeness_score || 0) * 100)
  const topIssues = [
    ...(preflight?.required_inputs || []).map((item) => item.label),
    ...(preflight?.ambiguities || []).map((item) => item.why_ambiguous),
  ].slice(0, 4)

  return (
    <section className="space-y-4 border border-slate-800/90 bg-[linear-gradient(135deg,rgba(15,23,42,0.92),rgba(2,6,23,0.98))] px-5 py-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Strategy readiness audit</div>
          <h2 className="text-xl font-semibold text-slate-50">{tone.title}</h2>
          <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
            {loading ? 'Refreshing the local readiness audit. No tokens spent.' : tone.subtitle}
          </p>
        </div>
        <div className={`border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${tone.badge}`}>
          {preflight ? preflight.status.replaceAll('_', ' ') : 'waiting'}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Readiness score</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight ? `${readinessScore}/100` : '—'}</div>
          <div className="mt-2">
            <ProgressBar value={readinessScore} max={100} />
          </div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Open blockers</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight?.blocking_items ?? 0}</div>
          <div className="mt-1 text-xs text-slate-500">Items that still stop paid analysis.</div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Required inputs</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight?.required_inputs?.length ?? 0}</div>
          <div className="mt-1 text-xs text-slate-500">Missing details with direct implementation impact.</div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Ambiguities</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight?.ambiguities?.length ?? 0}</div>
          <div className="mt-1 text-xs text-slate-500">Areas still open to multiple interpretations.</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-3 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">What to tighten now</div>
          {topIssues.length > 0 ? (
            topIssues.map((item, index) => (
              <div key={`${item}-${index}`} className="text-sm leading-relaxed text-slate-300">
                • {item}
              </div>
            ))
          ) : (
            <div className="text-sm leading-relaxed text-slate-400">
              No critical blockers detected. Move into structured review when you are ready.
            </div>
          )}
        </div>

        <div className="space-y-3 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">What this unlocks</div>
          {preflight ? (
            Object.entries(preflight.expected_stages).map(([stage, estimate]) => (
              <div key={stage} className="flex items-start justify-between gap-3 text-sm">
                <div>
                  <div className="font-medium text-slate-200">{stageLabel(stage)}</div>
                  <div className="mt-1 text-xs leading-relaxed text-slate-500">{estimate.reason}</div>
                </div>
                <span className={`text-[11px] font-semibold ${estimate.enabled ? 'text-cyan-300' : 'text-slate-600'}`}>
                  {estimate.enabled ? `~$${estimate.estimated_cost_usd.toFixed(4)}` : 'locked'}
                </span>
              </div>
            ))
          ) : (
            <div className="text-sm leading-relaxed text-slate-500">
              The audit will map the next stages automatically once the critical fields are present.
            </div>
          )}
        </div>
      </div>

      {preflight && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-3 text-xs">
          <div className="max-w-2xl text-slate-400">{preflight.next_recommended_action}</div>
          <div className="font-semibold text-slate-200">
            Max expected pipeline cost ~ ${preflight.estimated_total_cost_usd.toFixed(4)}
          </div>
        </div>
      )}
    </section>
  )
}
