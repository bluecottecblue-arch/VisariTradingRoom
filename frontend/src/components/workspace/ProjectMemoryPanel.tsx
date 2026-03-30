'use client'

import type { ProjectArtifactRecord, ProjectDetail, ProjectJobRecord, ProjectVersionRecord } from '@/types'

function formatTimestamp(value?: string | null) {
  if (!value) return 'No timestamp'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
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
    return `${summary.completeness_score ? `${Math.round(Number(summary.completeness_score) * 100)}% complete` : 'Parse reviewed'} · ${summary.required_inputs || 0} required inputs · ${summary.ambiguities || 0} ambiguities`
  }
  if (item.version_kind === 'formal_spec') {
    return `${summary.parameter_count || 0} parameters · ${summary.can_generate_code ? 'code generation unlocked' : 'generation still blocked'}`
  }
  if (item.version_kind === 'backtest') {
    const ret = summary.oos_return_pct
    const dd = summary.oos_max_drawdown_pct
    return `${summary.verdict || 'No verdict'} · ${ret !== undefined ? `${Number(ret).toFixed(1)}% OOS return` : 'return pending'} · ${dd !== undefined ? `${Number(dd).toFixed(1)}% max DD` : 'drawdown pending'}`
  }
  if (item.version_kind === 'bot_code') {
    return `${summary.download_ready ? 'download ready' : 'download blocked'} · ${summary.code_valid ? 'code validation passed' : 'validation failed'}`
  }
  if (item.version_kind === 'export_package') {
    return `${summary.deployment_status || 'status pending'} · ${summary.artifact_count || 0} package artifacts`
  }
  if (item.version_kind === 'bot_modified') {
    return `${summary.change_count || 0} tracked changes${summary.fundamental_filter_added ? ' · macro/fundamental filter added' : ''}`
  }
  if (item.version_kind === 'bot_upload_analysis') {
    return `${summary.health_score || '—'} health score · ${summary.backtest_ready ? 'ready for backtest' : 'analysis only'}`
  }

  const fragments = Object.entries(summary)
    .slice(0, 2)
    .map(([key, value]) => `${prettifyToken(key)}: ${String(value)}`)
  return fragments.join(' · ') || 'No summary available yet'
}

function artifactSummary(item: ProjectArtifactRecord) {
  const metadata = item.metadata || {}
  if (metadata.download_ready) return 'Downloadable artifact'
  if (metadata.size_bytes) return `${Number(metadata.size_bytes).toLocaleString()} bytes`
  if (metadata.lines) return `${metadata.lines} lines`
  if (metadata.artifact_count) return `${metadata.artifact_count} items referenced`
  return 'Stored inside the project record'
}

function jobSummary(item: ProjectJobRecord) {
  const summary = item.result_summary || {}
  if (summary.verdict) return `${summary.verdict} · ${summary.total_trades || 0} trades`
  if (summary.download_ready !== undefined) return summary.download_ready ? 'Bot package ready' : 'Bot generation incomplete'
  if (summary.parameter_count !== undefined) return `${summary.parameter_count} parameters formalized`
  if (summary.required_inputs !== undefined) return `${summary.required_inputs} required inputs still open`
  if (item.error) return item.error
  return 'In progress or awaiting a richer result summary'
}

export default function ProjectMemoryPanel({ project }: { project: ProjectDetail | null }) {
  if (!project) {
    return (
      <section className="border border-dashed border-slate-800/90 bg-slate-950/55 px-5 py-6 text-center">
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Project memory</div>
        <div className="mt-3 text-base font-semibold text-slate-200">Select an active project</div>
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
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Project memory</div>
          <div className="mt-2 text-xl font-semibold text-slate-50">Recent trail</div>
        </div>
        <div className="border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs text-slate-400">
          Active session {project.active_session_id ? project.active_session_id.slice(0, 8) : 'not set'}
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr_1fr]">
        <div className="space-y-2 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Latest decisions</div>
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
            <div className="text-sm text-slate-500">No recorded versions yet.</div>
          )}
        </div>

        <div className="space-y-2 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Deliverables ready</div>
          {recentArtifacts.length > 0 ? (
            recentArtifacts.map((item) => (
              <div key={item.artifact_id} className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                <div className="text-sm font-medium text-slate-100">{item.label}</div>
                <div className="mt-1 text-xs text-slate-500">{prettifyToken(item.artifact_type)}</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-400">{artifactSummary(item)}</div>
              </div>
            ))
          ) : (
            <div className="text-sm text-slate-500">No project artifacts saved yet.</div>
          )}
        </div>

        <div className="space-y-2 border border-slate-800 bg-slate-950/60 px-4 py-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Execution trail</div>
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
            <div className="text-sm text-slate-500">No tracked jobs yet.</div>
          )}
        </div>
      </div>
    </section>
  )
}
