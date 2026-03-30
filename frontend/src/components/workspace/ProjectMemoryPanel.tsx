'use client'

import type { ProjectArtifactRecord, ProjectDetail, ProjectJobRecord, ProjectVersionRecord } from '@/types'

function formatTimestamp(value?: string | null) {
  if (!value) return 'Nessuna data'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('it-IT')
}

function prettifyToken(value?: string | null) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replaceAll('-', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function versionSummary(item: ProjectVersionRecord) {
  const summary = item.summary || {}

  if (item.version_kind === 'parse_result') {
    return `${summary.completeness_score ? `${Math.round(Number(summary.completeness_score) * 100)}% completo` : 'Analisi eseguita'} · ${summary.required_inputs || 0} input richiesti · ${summary.ambiguities || 0} ambiguita`
  }
  if (item.version_kind === 'formal_spec') {
    return `${summary.parameter_count || 0} parametri · ${summary.can_generate_code ? 'generazione sbloccata' : 'generazione ancora bloccata'}`
  }
  if (item.version_kind === 'backtest') {
    const ret = summary.oos_return_pct
    const dd = summary.oos_max_drawdown_pct
    return `${summary.verdict || 'Nessun verdetto'} · ${ret !== undefined ? `${Number(ret).toFixed(1)}% rendimento OOS` : 'rendimento in attesa'} · ${dd !== undefined ? `${Number(dd).toFixed(1)}% max DD` : 'drawdown in attesa'}`
  }
  if (item.version_kind === 'bot_code') {
    return `${summary.download_ready ? 'download pronto' : 'download bloccato'} · ${summary.code_valid ? 'validazione codice ok' : 'validazione fallita'}`
  }
  if (item.version_kind === 'export_package') {
    return `${summary.deployment_status || 'stato in attesa'} · ${summary.artifact_count || 0} artefatti`
  }
  if (item.version_kind === 'bot_modified') {
    return `${summary.change_count || 0} modifiche tracciate${summary.fundamental_filter_added ? ' · filtro macro/fondamentale aggiunto' : ''}`
  }
  if (item.version_kind === 'bot_upload_analysis') {
    return `${summary.health_score || '—'} health score · ${summary.backtest_ready ? 'pronto per backtest' : 'solo analisi'}`
  }

  const fragments = Object.entries(summary)
    .slice(0, 2)
    .map(([key, value]) => `${prettifyToken(key)}: ${String(value)}`)
  return fragments.join(' · ') || 'Nessun riepilogo disponibile'
}

function artifactSummary(item: ProjectArtifactRecord) {
  const metadata = item.metadata || {}
  if (metadata.download_ready) return 'Artefatto scaricabile'
  if (metadata.size_bytes) return `${Number(metadata.size_bytes).toLocaleString('it-IT')} byte`
  if (metadata.lines) return `${metadata.lines} righe`
  if (metadata.artifact_count) return `${metadata.artifact_count} elementi inclusi`
  return 'Salvato nel progetto'
}

function jobSummary(item: ProjectJobRecord) {
  const summary = item.result_summary || {}
  if (summary.verdict) return `${summary.verdict} · ${summary.total_trades || 0} trade`
  if (summary.download_ready !== undefined) return summary.download_ready ? 'Pacchetto bot pronto' : 'Generazione bot incompleta'
  if (summary.parameter_count !== undefined) return `${summary.parameter_count} parametri formalizzati`
  if (summary.required_inputs !== undefined) return `${summary.required_inputs} input ancora aperti`
  if (item.error) return item.error
  return 'In corso o in attesa di un risultato piu ricco'
}

export default function ProjectMemoryPanel({ project }: { project: ProjectDetail | null }) {
  if (!project) {
    return (
        <section className="border border-dashed border-slate-800/90 bg-slate-950/55 px-5 py-6 text-center">
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Memoria progetto</div>
        <div className="mt-3 text-base font-semibold text-slate-200">Seleziona un progetto attivo</div>
      </section>
    )
  }

  const recentVersions = (project.versions || []).slice(0, 3)
  const recentArtifacts = (project.artifacts || []).slice(0, 3)
  const recentJobs = (project.jobs || []).slice(0, 3)

  return (
    <section className="space-y-4 border border-slate-800/90 bg-slate-950/75 px-5 py-5 lg:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Memoria progetto</div>
          <div className="mt-2 text-xl font-semibold text-slate-50">Ultime attivita</div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-400">
          Sessione attiva {project.active_session_id ? project.active_session_id.slice(0, 8) : 'non impostata'}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr_1fr]">
        <div className="space-y-2 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Decisioni recenti</div>
          {recentVersions.length > 0 ? (
            recentVersions.map((item) => (
              <div key={item.version_id} className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-100">{prettifyToken(item.version_kind)}</div>
                    <div className="mt-1 text-xs text-slate-500">{formatTimestamp(item.created_at)}</div>
                  </div>
                  <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500">{prettifyToken(item.status)}</span>
                </div>
                <div className="mt-2 text-sm leading-relaxed text-slate-400">{versionSummary(item)}</div>
              </div>
            ))
          ) : (
            <div className="text-sm text-slate-500">Nessuna versione registrata.</div>
          )}
        </div>

        <div className="space-y-2 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Deliverable pronti</div>
          {recentArtifacts.length > 0 ? (
            recentArtifacts.map((item) => (
              <div key={item.artifact_id} className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                <div className="text-sm font-medium text-slate-100">{item.label}</div>
                <div className="mt-1 text-xs text-slate-500">{prettifyToken(item.artifact_type)}</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-400">{artifactSummary(item)}</div>
              </div>
            ))
          ) : (
            <div className="text-sm text-slate-500">Nessun artefatto ancora salvato.</div>
          )}
        </div>

        <div className="space-y-2 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Storico esecuzioni</div>
          {recentJobs.length > 0 ? (
            recentJobs.map((item) => (
              <div key={item.job_id} className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-medium text-slate-100">{prettifyToken(item.job_type)}</div>
                  <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500">{prettifyToken(item.status)}</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">{formatTimestamp(item.updated_at || item.created_at)}</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-400">{jobSummary(item)}</div>
              </div>
            ))
          ) : (
            <div className="text-sm text-slate-500">Nessun job tracciato.</div>
          )}
        </div>
      </div>
    </section>
  )
}
