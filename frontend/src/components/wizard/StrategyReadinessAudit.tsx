'use client'

import { ProgressBar } from '@/components/ui'
import type { PreflightResult } from '@/types'

function toneForPreflight(preflight: PreflightResult | null) {
  if (!preflight) {
    return {
      badge: 'border-slate-800 bg-slate-950/60 text-slate-400',
      title: 'In attesa degli input strategici critici',
      subtitle: 'Aggiungi mercato, ingressi, invalidazione e uscite per sbloccare l’audit gratuito di prontezza.',
    }
  }

  if (preflight.status === 'VALID' && preflight.blocking_items === 0) {
    return {
      badge: 'border-cyan-900/70 bg-cyan-950/12 text-cyan-300',
      title: 'Pronta per la revisione strutturata',
      subtitle: 'La strategia è abbastanza specifica da giustificare revisione AI e validazione a valle.',
    }
  }

  if ((preflight.completeness_score || 0) >= 0.7) {
    return {
      badge: 'border-amber-900/70 bg-amber-950/12 text-amber-300',
      title: 'Richiede chiarimenti prima di spendere token',
      subtitle: 'La logica è promettente ma lascia ancora troppo spazio all’interpretazione.',
    }
  }

  return {
    badge: 'border-rose-900/70 bg-rose-950/12 text-rose-300',
    title: 'Troppo vaga per un’automazione affidabile',
    subtitle: 'Chiarisci il setup prima di pagare parse, formalizzazione e generazione bot.',
  }
}

function stageLabel(stage: string) {
  if (stage === 'parse') return 'Revisione strutturata'
  if (stage === 'formalize') return 'Specifica formale'
  if (stage === 'botgen') return 'Candidato export bot'
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
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Audit di prontezza strategia</div>
          <h2 className="text-xl font-semibold text-slate-50">{tone.title}</h2>
          <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
            {loading ? 'Aggiorno l’audit locale di prontezza. Nessun token speso.' : tone.subtitle}
          </p>
        </div>
        <div className={`border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${tone.badge}`}>
          {preflight ? preflight.status.replaceAll('_', ' ') : 'in attesa'}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Punteggio di prontezza</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight ? `${readinessScore}/100` : '—'}</div>
          <div className="mt-2">
            <ProgressBar value={readinessScore} max={100} />
          </div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Blocchi aperti</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight?.blocking_items ?? 0}</div>
          <div className="mt-1 text-xs text-slate-500">Elementi che bloccano ancora l’analisi a pagamento.</div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Input richiesti</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight?.required_inputs?.length ?? 0}</div>
          <div className="mt-1 text-xs text-slate-500">Dettagli mancanti con impatto diretto sull’implementazione.</div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Ambiguità</div>
          <div className="mt-2 text-2xl font-semibold text-slate-50">{preflight?.ambiguities?.length ?? 0}</div>
          <div className="mt-1 text-xs text-slate-500">Aree ancora aperte a più interpretazioni.</div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-3 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Cosa stringere adesso</div>
          {topIssues.length > 0 ? (
            topIssues.map((item, index) => (
              <div key={`${item}-${index}`} className="text-sm leading-relaxed text-slate-300">
                • {item}
              </div>
            ))
          ) : (
            <div className="text-sm leading-relaxed text-slate-400">
              Nessun blocco critico rilevato. Passa alla revisione strutturata quando sei pronto.
            </div>
          )}
        </div>

        <div className="space-y-3 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Cosa sblocca</div>
          {preflight ? (
            Object.entries(preflight.expected_stages).map(([stage, estimate]) => (
              <div key={stage} className="flex items-start justify-between gap-3 text-sm">
                <div>
                  <div className="font-medium text-slate-200">{stageLabel(stage)}</div>
                  <div className="mt-1 text-xs leading-relaxed text-slate-500">{estimate.reason}</div>
                </div>
                <span className={`text-[11px] font-semibold ${estimate.enabled ? 'text-cyan-300' : 'text-slate-600'}`}>
                  {estimate.enabled ? `~$${estimate.estimated_cost_usd.toFixed(4)}` : 'bloccato'}
                </span>
              </div>
            ))
          ) : (
            <div className="text-sm leading-relaxed text-slate-500">
              L’audit mapperà automaticamente i prossimi step appena i campi critici saranno presenti.
            </div>
          )}
        </div>
      </div>

      {preflight && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-3 text-xs">
          <div className="max-w-2xl text-slate-400">{preflight.next_recommended_action}</div>
          <div className="font-semibold text-slate-200">
            Costo massimo atteso della pipeline ~ ${preflight.estimated_total_cost_usd.toFixed(4)}
          </div>
        </div>
      )}
    </section>
  )
}
