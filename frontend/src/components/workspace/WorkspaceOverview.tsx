'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import ProjectMemoryPanel from '@/components/workspace/ProjectMemoryPanel'
import { formatError } from '@/lib/api'
import type { ProjectDetail, ProjectSummary } from '@/types'

type WorkspaceMode = 'strategy' | 'botlab'

const PIPELINE = [
  { id: 'strategy', label: 'Strategia' },
  { id: 'parse', label: 'Analisi' },
  { id: 'formalize', label: 'Specifica' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'validation', label: 'Valutazione' },
  { id: 'export', label: 'Export bot' },
] as const

type PipelineStepId = (typeof PIPELINE)[number]['id']

function pipelineTone(status: 'complete' | 'running' | 'current' | 'locked') {
  if (status === 'complete') return 'border-emerald-900/70 bg-emerald-950/12 text-emerald-300'
  if (status === 'running') return 'border-cyan-900/70 bg-cyan-950/14 text-cyan-300'
  if (status === 'current') return 'border-cyan-700/70 bg-cyan-950/16 text-slate-100'
  return 'border-slate-900 bg-slate-950/60 text-slate-500'
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

function normalizeMode(mode?: string | null): WorkspaceMode {
  return mode === 'botlab' ? 'botlab' : 'strategy'
}

function modeLabel(mode?: string | null) {
  return normalizeMode(mode) === 'strategy' ? 'Strategia' : 'Bot Lab'
}

function stepStatusLabel(status: 'complete' | 'running' | 'current' | 'locked') {
  if (status === 'current') return 'Pronto adesso'
  return ''
}

export default function WorkspaceOverview({
  workspaceMode,
  setWorkspaceMode,
  projects,
  currentProjectId,
  setCurrentProjectId,
  createProject,
  renameProject,
  deleteProject,
  currentProject,
}: {
  workspaceMode: WorkspaceMode
  setWorkspaceMode: (mode: WorkspaceMode) => void
  projects: ProjectSummary[]
  currentProjectId: string | null
  setCurrentProjectId: (projectId: string) => void
  createProject: (mode: WorkspaceMode) => Promise<ProjectSummary | null>
  renameProject: (projectId: string, title: string) => Promise<void>
  deleteProject: (projectId: string) => Promise<void>
  currentProject: ProjectDetail | null
}) {
  const router = useRouter()
  const [pendingKey, setPendingKey] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

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

  const currentPipelineStep =
    pipelineState.find((step) => step.status === 'running' || step.status === 'current') ||
    pipelineState[pipelineState.length - 1]

  const scrollToBotLab = () => {
    requestAnimationFrame(() => {
      document.getElementById('bot-lab-workspace')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  const openProject = (project: ProjectSummary) => {
    setActionError(null)
    setWorkspaceMode(normalizeMode(project.mode))
    setCurrentProjectId(project.project_id)
    if (normalizeMode(project.mode) === 'strategy') {
      router.push(`/builder?project_id=${project.project_id}`)
      return
    }
    scrollToBotLab()
  }

  const openDesk = (projectId?: string | null) => {
    router.push(projectId ? `/dashboard?project_id=${projectId}` : '/dashboard')
  }

  const handleCreateStrategy = async () => {
    setPendingKey('create-strategy')
    setActionError(null)
    try {
      const project = await createProject('strategy')
      if (project) {
        router.push(`/builder?project_id=${project.project_id}`)
      }
    } catch (error) {
      setActionError(formatError(error))
    } finally {
      setPendingKey(null)
    }
  }

  const handleOpenBotLab = () => {
    setActionError(null)
    setWorkspaceMode('botlab')
    scrollToBotLab()
  }

  const handleCreateBotLabProject = async () => {
    setPendingKey('create-botlab')
    setActionError(null)
    try {
      const project = await createProject('botlab')
      if (project) {
        setWorkspaceMode('botlab')
        setCurrentProjectId(project.project_id)
        scrollToBotLab()
      }
    } catch (error) {
      setActionError(formatError(error))
    } finally {
      setPendingKey(null)
    }
  }

  const handleRenameProject = async (project: ProjectSummary | ProjectDetail | null) => {
    if (!project) return
    const nextTitle = window.prompt('Nuovo nome del progetto', project.title)
    if (!nextTitle || nextTitle.trim() === project.title.trim()) return
    setPendingKey(`rename-${project.project_id}`)
    setActionError(null)
    try {
      await renameProject(project.project_id, nextTitle.trim())
    } catch (error) {
      setActionError(formatError(error))
    } finally {
      setPendingKey(null)
    }
  }

  const handleDeleteProject = async (project: ProjectSummary | ProjectDetail | null) => {
    if (!project) return
    const confirmed = window.confirm(`Eliminare definitivamente il progetto "${project.title}"?`)
    if (!confirmed) return
    setPendingKey(`delete-${project.project_id}`)
    setActionError(null)
    try {
      await deleteProject(project.project_id)
    } catch (error) {
      setActionError(formatError(error))
    } finally {
      setPendingKey(null)
    }
  }

  return (
    <div className="space-y-6">
      {actionError && (
        <div className="border border-rose-900/70 bg-rose-950/10 px-4 py-3 text-sm text-rose-200">
          {actionError}
        </div>
      )}

      <section className="grid items-stretch gap-5 xl:grid-cols-2">
        <div className="min-w-0 border border-slate-800/90 bg-[linear-gradient(135deg,rgba(8,47,73,0.28),rgba(15,23,42,0.88)_38%,rgba(2,6,23,0.96))] px-5 py-5 lg:px-6">
          <div className="text-[10px] uppercase tracking-[0.22em] text-cyan-300">Operazioni rapide</div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-slate-50 lg:text-[2rem]">
            Iniziamo!
          </h1>
          <p className="mt-2 max-w-xl text-sm text-slate-400">
            Scegli il punto di partenza.
          </p>

          <div className="mt-5 flex max-w-[340px] flex-col gap-3">
            <button
              onClick={handleCreateStrategy}
              disabled={pendingKey !== null}
              className="w-full border border-cyan-700/70 bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
            >
              Crea nuova strategia
            </button>

            <button
              onClick={handleOpenBotLab}
              className="w-full border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-slate-600"
            >
              Apri Bot Lab
            </button>
            <button
              onClick={handleCreateBotLabProject}
              disabled={pendingKey !== null}
              className="w-full border border-slate-800 bg-slate-950/40 px-4 py-3 text-sm font-semibold text-slate-100 transition hover:border-slate-600 disabled:cursor-not-allowed disabled:opacity-70"
            >
              Nuovo progetto Bot Lab
            </button>
          </div>
        </div>

        <div className="min-w-0 border border-slate-800/90 bg-slate-950/75 px-5 py-5 lg:px-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Progetto selezionato</div>
              <div className="mt-2 text-2xl font-semibold text-slate-50">
                {currentProject?.title || 'Nessun progetto selezionato'}
              </div>
              <div className="mt-1 text-sm text-slate-400">
                {currentProject
                  ? `${modeLabel(currentProject.mode)} · fase attuale: ${normalizeMode(currentProject.mode) === 'strategy' ? currentPipelineStep.label : 'Bot Lab'}`
                  : 'Seleziona un progetto oppure crea una nuova strategia.'}
              </div>
            </div>
            <span className={`inline-flex items-center gap-2 border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] ${statusTone(currentProject?.latest_verdict || currentProject?.status)}`}>
              {String(currentProject?.latest_verdict || currentProject?.status || 'nuovo').replaceAll('_', ' ')}
            </span>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Fase</div>
              <div className="mt-2 text-lg font-semibold text-slate-50">
                {currentProject ? (normalizeMode(currentProject.mode) === 'strategy' ? currentPipelineStep.label : 'Bot Lab') : '—'}
              </div>
            </div>
            <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Deliverable</div>
              <div className="mt-2 text-lg font-semibold text-slate-50">{projectArtifacts.length}</div>
            </div>
            <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Progetti</div>
              <div className="mt-2 text-lg font-semibold text-slate-50">{filteredProjects.length}</div>
            </div>
          </div>

        </div>
      </section>

      <section className="grid items-start gap-5 xl:grid-cols-2">
        <div className="min-w-0 border border-slate-800/90 bg-slate-950/75 px-5 py-5 lg:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Progetti</div>
              <div className="mt-1 text-xl font-semibold text-slate-50">Apri, rinomina o elimina</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setWorkspaceMode('strategy')}
                className={`border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${
                  workspaceMode === 'strategy'
                    ? 'border-cyan-800/70 bg-cyan-950/15 text-cyan-200'
                    : 'border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-100'
                }`}
              >
                Strategie
              </button>
              <button
                onClick={() => setWorkspaceMode('botlab')}
                className={`border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${
                  workspaceMode === 'botlab'
                    ? 'border-cyan-800/70 bg-cyan-950/15 text-cyan-200'
                    : 'border-slate-800 text-slate-400 hover:border-slate-600 hover:text-slate-100'
                }`}
              >
                Bot Lab
              </button>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {filteredProjects.map((project) => {
              const isActive = currentProjectId === project.project_id
              return (
                <div
                  key={project.project_id}
                  className={`border px-4 py-4 ${isActive ? 'border-cyan-900/70 bg-cyan-950/10' : 'border-slate-900 bg-slate-950/40'}`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <button
                        onClick={() => {
                          setWorkspaceMode(normalizeMode(project.mode))
                          setCurrentProjectId(project.project_id)
                        }}
                        className="text-left text-base font-semibold text-slate-50 hover:text-cyan-200"
                      >
                        {project.title}
                      </button>
                      <div className="mt-1 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.16em]">
                        <span className="border border-slate-800 px-2 py-1 text-slate-500">{modeLabel(project.mode)}</span>
                        <span className={`border px-2 py-1 ${statusTone(project.latest_verdict || project.status)}`}>
                          {String(project.latest_verdict || project.status || 'nuovo').replaceAll('_', ' ')}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => openProject(project)}
                        className="border border-cyan-800/70 bg-cyan-950/15 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200 hover:border-cyan-600"
                      >
                        Apri
                      </button>
                      <button
                        onClick={() => openDesk(project.project_id)}
                        className="border border-slate-800 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-300 hover:border-slate-600 hover:text-slate-100"
                      >
                        Desk
                      </button>
                      <button
                        onClick={() => handleRenameProject(project)}
                        disabled={pendingKey !== null}
                        className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-300 hover:border-slate-600 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Rinomina
                      </button>
                      <button
                        onClick={() => handleDeleteProject(project)}
                        disabled={pendingKey !== null}
                        className="border border-rose-900/70 px-3 py-2 text-xs uppercase tracking-[0.16em] text-rose-200 hover:border-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Elimina
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}

            {filteredProjects.length === 0 && (
              <div className="border border-dashed border-slate-800 px-4 py-8 text-sm text-slate-500">
                Nessun progetto presente in questa sezione.
              </div>
            )}
          </div>
        </div>

        <section className="min-w-0 border border-slate-800/90 bg-slate-950/75 px-5 py-5 lg:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Flusso</div>
              <div className="mt-1 text-xl font-semibold text-slate-50">Pipeline di lavoro</div>
            </div>
            <Link href={currentProjectId ? `/dashboard?project_id=${currentProjectId}` : '/dashboard'} className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-300 hover:border-slate-600 hover:text-slate-100">
              Apri desk
            </Link>
          </div>

          <div className="mt-4 grid auto-rows-fr gap-3 sm:grid-cols-2">
            {pipelineState.map((step, index) => {
              return (
                <div key={step.label} className={`min-w-0 min-h-[108px] border px-4 py-3 ${pipelineTone(step.status)}`}>
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 items-center justify-center border border-current/30 text-sm font-semibold">
                      {step.status === 'complete' ? '✓' : `0${index + 1}`}
                    </div>
                    {stepStatusLabel(step.status) ? (
                      <span className="pt-1 text-[9px] uppercase leading-[1.35] tracking-[0.16em]">
                        {stepStatusLabel(step.status)}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-4 max-w-[10ch] text-[1.2rem] font-semibold leading-[1.05] tracking-tight text-slate-100 sm:text-[1.35rem]">
                    {step.label}
                  </div>
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
