'use client'

import { useRouter } from 'next/navigation'
import Link from 'next/link'
import ProjectMemoryPanel from '@/components/workspace/ProjectMemoryPanel'
import type { ProjectDetail, ProjectSummary } from '@/types'

type WorkspaceMode = 'strategy' | 'botlab'

const PIPELINE = [
  { id: 'strategy', label: 'Strategy', detail: 'Market, timeframe, entry logic' },
  { id: 'parse', label: 'Parse', detail: 'Objective codifiability review' },
  { id: 'formalize', label: 'Formalize', detail: 'Structured trading specification' },
  { id: 'backtest', label: 'Backtest', detail: 'Historical execution and OOS review' },
  { id: 'validation', label: 'Validation', detail: 'Risk, robustness, macro filters' },
  { id: 'export', label: 'Bot Export', detail: 'MT5 package and deployment notes' },
]

type PipelineStepId = (typeof PIPELINE)[number]['id']

function pipelineTone(status: 'complete' | 'running' | 'current' | 'locked') {
  if (status === 'complete') return 'border-emerald-900/70 bg-emerald-950/12 text-emerald-300'
  if (status === 'running') return 'border-cyan-900/70 bg-cyan-950/14 text-cyan-300'
  if (status === 'current') return 'border-slate-700 bg-slate-900/80 text-slate-200'
  return 'border-slate-900 bg-slate-950/60 text-slate-600'
}

function statusTone(status?: string | null) {
  const normalized = String(status || '').toLowerCase()
  if (normalized.includes('reject') || normalized.includes('invalid') || normalized.includes('failed')) {
    return 'border-rose-900/70 bg-rose-950/10 text-rose-300'
  }
  if (normalized.includes('valid') || normalized.includes('candidate') || normalized.includes('complete')) {
    return 'border-cyan-900/70 bg-cyan-950/10 text-cyan-300'
  }
  if (normalized.includes('research') || normalized.includes('paper') || normalized.includes('running')) {
    return 'border-amber-900/70 bg-amber-950/10 text-amber-300'
  }
  return 'border-slate-800 bg-slate-950/60 text-slate-400'
}

export default function WorkspaceOverview({
  workspaceMode,
  setWorkspaceMode,
  projects,
  currentProjectId,
  setCurrentProjectId,
  createProject,
  currentProject,
}: {
  workspaceMode: WorkspaceMode
  setWorkspaceMode: (mode: WorkspaceMode) => void
  projects: ProjectSummary[]
  currentProjectId: string | null
  setCurrentProjectId: (projectId: string) => void
  createProject: (mode: WorkspaceMode) => Promise<void>
  currentProject: ProjectDetail | null
}) {
  const router = useRouter()
  const filteredProjects = projects.filter((project) => project.mode === workspaceMode)
  const completedKinds = new Set((currentProject?.versions || []).map((item) => item.version_kind))
  const hasVerdict = Boolean(currentProject?.latest_verdict)
  const projectArtifacts = currentProject?.artifacts || []
  const projectJobs = currentProject?.jobs || []
  const hasVersion = (kind: string) => completedKinds.has(kind)
  const hasArtifact = (type: string) => projectArtifacts.some((artifact) => artifact.artifact_type === type)
  const hasRunningJob = (jobTypes: string[]) =>
    projectJobs.some((job) => jobTypes.includes(job.job_type) && ['queued', 'running', 'submitted'].includes(job.status))

  const pipelineState = PIPELINE.map((step) => {
    const statusByStep: Record<PipelineStepId, 'complete' | 'running' | 'current' | 'locked'> = {
      strategy: hasVersion('intake') ? 'complete' : 'current',
      parse: hasVersion('parse_result')
        ? 'complete'
        : hasRunningJob(['strategy_parse'])
          ? 'running'
          : hasVersion('intake')
            ? 'current'
            : 'locked',
      formalize: hasVersion('formal_spec')
        ? 'complete'
        : hasRunningJob(['strategy_formalize'])
          ? 'running'
          : hasVersion('parse_result')
            ? 'current'
            : 'locked',
      backtest: hasVersion('backtest')
        ? 'complete'
        : hasRunningJob(['backtest'])
          ? 'running'
          : hasVersion('formal_spec')
            ? 'current'
            : 'locked',
      validation: hasVerdict
        ? 'complete'
        : hasVersion('backtest')
          ? 'current'
          : 'locked',
      export:
        hasVersion('export_package') || hasVersion('bot_code') || hasArtifact('mql5_source')
          ? 'complete'
          : hasRunningJob(['bot_generation'])
            ? 'running'
            : hasVerdict
              ? 'current'
              : 'locked',
    }

    return { ...step, status: statusByStep[step.id] }
  })
  const currentPipelineIndex = pipelineState.findIndex((step) => step.status === 'running' || step.status === 'current')
  const stepActiveIndex = currentPipelineIndex === -1 ? PIPELINE.length - 1 : currentPipelineIndex

  const handleStrategyClick = () => {
    // Navigate to the builder page
    const url = currentProjectId ? `/builder?project_id=${currentProjectId}` : '/builder'
    router.push(url)
  }

  const handleBotLabClick = () => {
    setWorkspaceMode('botlab')
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden border border-slate-800/90 bg-[linear-gradient(135deg,rgba(8,47,73,0.28),rgba(15,23,42,0.86)_35%,rgba(2,6,23,0.96))] px-6 py-7 lg:px-8 lg:py-8">
        <div className="absolute inset-y-0 right-0 hidden w-1/3 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_55%)] lg:block" />
        <div className="relative grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-5">
            <div className="space-y-2">
              <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Visari Trading Room</div>
              <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight text-slate-50 lg:text-[2.85rem]">
                Choose a workflow
              </h1>
              <p className="max-w-xl text-sm leading-relaxed text-slate-400 lg:text-base">
                Start a new strategy or work on an existing MT5 bot.
              </p>
            </div>

            <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
              <button
                onClick={handleStrategyClick}
                className="border border-cyan-900/70 bg-cyan-950/12 px-5 py-4 text-left transition-colors hover:border-cyan-700/70 hover:bg-cyan-950/18"
              >
                <div className="text-[10px] uppercase tracking-[0.18em] text-cyan-300">Create Strategy</div>
                <div className="mt-2 text-lg font-semibold text-slate-50">Start from trading logic</div>
              </button>
              <button
                onClick={handleBotLabClick}
                className="border border-slate-800 bg-slate-950/65 px-5 py-4 text-left transition-colors hover:border-slate-600"
              >
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Analyze Existing Bot</div>
                <div className="mt-2 text-lg font-semibold text-slate-50">Open Bot Lab</div>
              </button>
              <a
                href="#workflow-visual"
                className="flex items-center justify-center border border-slate-800 bg-slate-950/40 px-5 py-3 text-sm font-semibold text-slate-300 hover:border-slate-600 hover:text-slate-100"
              >
                View Pipeline
              </a>
            </div>

            <div className="flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.16em] text-slate-500">
              <span className="border border-slate-800 px-2.5 py-1">Structured validation</span>
              <span className="border border-slate-800 px-2.5 py-1">OOS review</span>
              <span className="border border-slate-800 px-2.5 py-1">MT5 export</span>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="border border-slate-800/90 bg-slate-950/65 px-5 py-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Current project</div>
                <span className={`inline-flex items-center gap-2 border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] ${statusTone(currentProject?.latest_verdict || currentProject?.status)}`}>
                  {(currentProject?.latest_verdict || currentProject?.status || 'new').replaceAll('_', ' ')}
                </span>
              </div>
              <div className="mt-4 text-2xl font-semibold text-slate-50">{currentProject?.title || 'No active project selected'}</div>
              <div className="mt-1 text-sm text-slate-500">
                {workspaceMode === 'strategy' ? pipelineState[stepActiveIndex]?.label || 'Start from intake' : 'Bot Lab'}
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
                <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Projects</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">{filteredProjects.length}</div>
                </div>
                <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Stage</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">
                    {workspaceMode === 'strategy' ? pipelineState[stepActiveIndex]?.label || '—' : 'Bot Lab'}
                  </div>
                </div>
                <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Deliverables</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">{projectArtifacts.length}</div>
                </div>
              </div>
              <div className="mt-4 flex gap-3">
                <button
                  onClick={() => createProject(workspaceMode)}
                  className="border border-slate-800 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-300 hover:border-slate-600 hover:text-slate-100"
                >
                  New Project
                </button>
                <Link href="/dashboard" className="border border-slate-800 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-300 hover:border-slate-600 hover:text-slate-100">
                  Algo Desk
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="border border-slate-800/90 bg-slate-950/75 px-5 py-5">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Active Projects</div>
            <button
              onClick={() => createProject(workspaceMode)}
              className="border border-slate-800 px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-400 hover:border-slate-600 hover:text-slate-100"
            >
              New
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {filteredProjects.slice(0, 4).map((project) => (
              <button
                key={project.project_id}
                onClick={() => setCurrentProjectId(project.project_id)}
                className={`w-full border px-4 py-4 text-left transition-colors ${
                  currentProjectId === project.project_id
                    ? 'border-cyan-900/70 bg-cyan-950/10'
                    : 'border-slate-900 bg-slate-950/40 hover:border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-slate-100">{project.title}</div>
                    <div className="mt-1 text-xs text-slate-500">{project.mode} · {project.project_id.slice(0, 8)}</div>
                  </div>
                  <span className={`inline-flex items-center gap-2 border px-2 py-1 text-[10px] uppercase tracking-[0.14em] ${statusTone(project.latest_verdict || project.status)}`}>
                    {(project.latest_verdict || project.status || 'new').replaceAll('_', ' ')}
                  </span>
                </div>
              </button>
            ))}
            {filteredProjects.length === 0 && (
              <div className="border border-dashed border-slate-800 px-4 py-8 text-sm text-slate-500">
                No projects yet in this workspace.
              </div>
            )}
          </div>
        </div>
        <section id="workflow-visual" className="border border-slate-800/90 bg-slate-950/75 px-5 py-5 lg:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Pipeline</div>
              <div className="mt-2 text-xl font-semibold text-slate-50">Current workflow</div>
            </div>
            <Link href="/dashboard" className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-400 hover:border-slate-600 hover:text-slate-100">
              Command Center
            </Link>
          </div>

          <div className="mt-5 grid gap-3 xl:grid-cols-6">
            {pipelineState.map((step, index) => {
              const active = index === stepActiveIndex && (step.status === 'running' || step.status === 'current')
              const done = step.status === 'complete'
              const locked = step.status === 'locked'
              const running = step.status === 'running'
              return (
                <div key={step.label} className={`relative border px-4 py-4 ${pipelineTone(step.status)}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className={`h-8 w-8 border flex items-center justify-center text-xs font-semibold ${
                      running
                        ? 'border-cyan-800 bg-cyan-950/30 text-cyan-300'
                        : active
                          ? 'border-slate-600 bg-slate-900/80 text-slate-200'
                          : done
                            ? 'border-emerald-900/70 bg-emerald-950/15 text-emerald-300'
                            : locked
                              ? 'border-slate-900 text-slate-700'
                              : 'border-slate-800 text-slate-500'
                    }`}>
                      {done ? '✓' : `0${index + 1}`}
                    </div>
                    <span className={`text-[10px] uppercase tracking-[0.16em] ${
                      running
                        ? 'text-cyan-300'
                        : active
                          ? 'text-slate-200'
                          : done
                            ? 'text-emerald-300'
                            : locked
                              ? 'text-slate-700'
                              : 'text-slate-600'
                    }`}>
                      {running ? 'running' : active ? 'current' : done ? 'done' : locked ? 'locked' : 'ready'}
                    </span>
                  </div>
                  <div className="mt-4 text-sm font-semibold text-slate-100">{step.label}</div>
                  {(active || done || running) ? (
                    <div className="mt-1 text-xs leading-relaxed text-slate-500">{step.detail}</div>
                  ) : null}
                </div>
              )
            })}
          </div>
        </section>
      </section>

      <ProjectMemoryPanel project={currentProject} />
    </div>
  )
}
