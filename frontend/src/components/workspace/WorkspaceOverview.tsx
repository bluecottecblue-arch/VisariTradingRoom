'use client'

import Link from 'next/link'
import type { ProjectDetail, ProjectSummary } from '@/types'

type WorkspaceMode = 'strategy' | 'botlab'

const PIPELINE = [
  { label: 'Strategy', detail: 'Market, timeframe, entry logic' },
  { label: 'Parse', detail: 'Objective codifiability review' },
  { label: 'Formalize', detail: 'Structured trading specification' },
  { label: 'Backtest', detail: 'Historical execution and OOS review' },
  { label: 'Validation', detail: 'Risk, robustness, macro filters' },
  { label: 'Bot Export', detail: 'MT5 package and deployment notes' },
]

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
  currentStep,
  restart,
}: {
  workspaceMode: WorkspaceMode
  setWorkspaceMode: (mode: WorkspaceMode) => void
  projects: ProjectSummary[]
  currentProjectId: string | null
  setCurrentProjectId: (projectId: string) => void
  createProject: (mode: WorkspaceMode) => Promise<void>
  currentProject: ProjectDetail | null
  currentStep: number
  restart: () => void
}) {
  const filteredProjects = projects.filter((project) => project.mode === workspaceMode)
  const stepActiveIndex = Math.max(0, currentStep - 1)

  const handleStrategyClick = () => {
    restart()
    setWorkspaceMode('strategy')
  }

  const handleBotLabClick = () => {
    restart()
    setWorkspaceMode('botlab')
  }

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden border border-slate-800/90 bg-[linear-gradient(135deg,rgba(8,47,73,0.28),rgba(15,23,42,0.86)_35%,rgba(2,6,23,0.96))] px-6 py-8 lg:px-8 lg:py-10">
        <div className="absolute inset-y-0 right-0 hidden w-1/3 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_55%)] lg:block" />
        <div className="relative grid gap-8 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-6">
            <div className="space-y-3">
              <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Visari Trading Room</div>
              <h1 className="max-w-4xl text-4xl font-semibold leading-tight tracking-tight text-slate-50 lg:text-5xl">
                Transform your trading strategy into a validated MT5 algorithm
              </h1>
              <p className="max-w-2xl text-base leading-relaxed text-slate-400 lg:text-lg">
                Analyze, improve, and deploy trading systems with structured validation and real backtesting.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                onClick={handleStrategyClick}
                className="border border-cyan-800/70 bg-cyan-400/90 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-300"
              >
                Create Strategy
              </button>
              <button
                onClick={handleBotLabClick}
                className="border border-slate-700 bg-slate-950/70 px-5 py-3 text-sm font-semibold text-slate-100 hover:border-slate-500"
              >
                Upload Bot
              </button>
              <a
                href="#workflow-visual"
                className="border border-slate-800 bg-slate-950/40 px-5 py-3 text-sm font-semibold text-slate-300 hover:border-slate-600 hover:text-slate-100"
              >
                View Demo Workflow
              </a>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">What it does</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-300">
                  Converts discretionary logic or existing bots into structured MT5-ready systems.
                </div>
              </div>
              <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Why it matters</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-300">
                  Reduces vague specs, exposes weak systems early, and makes delivery more reliable.
                </div>
              </div>
              <div className="border border-slate-800/90 bg-slate-950/55 px-4 py-4">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">What to click</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-300">
                  Start with Create Strategy for new systems, or Upload Bot to audit and improve an existing EA.
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="border border-slate-800/90 bg-slate-950/65 px-5 py-5">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Desk Overview</div>
                <span className={`inline-flex items-center gap-2 border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] ${statusTone(currentProject?.latest_verdict || currentProject?.status)}`}>
                  {(currentProject?.latest_verdict || currentProject?.status || 'new').replaceAll('_', ' ')}
                </span>
              </div>
              <div className="mt-4 text-2xl font-semibold text-slate-50">{currentProject?.title || 'No active project selected'}</div>
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Projects</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">{filteredProjects.length}</div>
                </div>
                <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Artifacts</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">{currentProject?.artifacts?.length || 0}</div>
                </div>
                <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Versions</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">{currentProject?.versions?.length || 0}</div>
                </div>
                <div className="border border-slate-900 bg-slate-950/70 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Current step</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">{workspaceMode === 'strategy' ? `${currentStep}/6` : 'Bot Lab'}</div>
                </div>
              </div>
            </div>

            <div className="border border-slate-800/90 bg-slate-950/65 px-5 py-5">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Validated workflow</div>
              <div className="mt-3 text-sm leading-relaxed text-slate-400">
                Fail-fast intake, formal specification, out-of-sample review, robustness checks and deploy-ready export package.
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                <span className="border border-slate-800 px-2.5 py-1">Out-of-sample tested</span>
                <span className="border border-slate-800 px-2.5 py-1">Validation verdict</span>
                <span className="border border-slate-800 px-2.5 py-1">MT5 export ready</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr_1fr]">
        <div className="border border-slate-800/90 bg-slate-950/75 px-5 py-5">
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Create Strategy</div>
          <div className="mt-3 text-xl font-semibold text-slate-50">Design a new strategy from trading logic</div>
          <div className="mt-2 text-sm leading-relaxed text-slate-400">
            Structured wizard for market, entries, exits, risk management and macro/news filters.
          </div>
          <button
            onClick={handleStrategyClick}
            className="mt-5 border border-cyan-800/70 bg-cyan-400/90 px-4 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-300"
          >
            Open Strategy Builder
          </button>
        </div>

        <div className="border border-slate-800/90 bg-slate-950/75 px-5 py-5">
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Bot Lab</div>
          <div className="mt-3 text-xl font-semibold text-slate-50">Analyze and improve existing bots</div>
          <div className="mt-2 text-sm leading-relaxed text-slate-400">
            Drag, inspect, compare and improve existing `.mq5`, `.txt` or `.py` bots with structured validation.
          </div>
          <button
            onClick={handleBotLabClick}
            className="mt-5 border border-slate-700 bg-slate-950/40 px-4 py-3 text-sm font-semibold text-slate-100 hover:border-slate-500"
          >
            Open Bot Lab
          </button>
        </div>

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
      </section>

      <section id="workflow-visual" className="border border-slate-800/90 bg-slate-950/75 px-5 py-5 lg:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Workflow visualization</div>
            <div className="mt-2 text-xl font-semibold text-slate-50">Validated delivery pipeline</div>
          </div>
          <Link href="/dashboard" className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-400 hover:border-slate-600 hover:text-slate-100">
            Open Command Center
          </Link>
        </div>

        <div className="mt-6 grid gap-3 xl:grid-cols-6">
          {PIPELINE.map((step, index) => {
            const active = workspaceMode === 'strategy' && index <= stepActiveIndex
            return (
              <div key={step.label} className="relative border border-slate-900 bg-slate-950/60 px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div className={`h-8 w-8 border ${active ? 'border-cyan-800 bg-cyan-950/30 text-cyan-300' : 'border-slate-800 text-slate-500'} flex items-center justify-center text-xs font-semibold`}>
                    0{index + 1}
                  </div>
                  <span className={`text-[10px] uppercase tracking-[0.16em] ${active ? 'text-cyan-300' : 'text-slate-600'}`}>
                    {active ? 'active' : 'pending'}
                  </span>
                </div>
                <div className="mt-4 text-sm font-semibold text-slate-100">{step.label}</div>
                <div className="mt-1 text-xs leading-relaxed text-slate-500">{step.detail}</div>
              </div>
            )
          })}
        </div>
      </section>
    </div>
  )
}
