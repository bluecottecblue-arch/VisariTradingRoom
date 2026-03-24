"use client";

import { useEffect, useState } from "react";
import StepIntake from "@/components/wizard/StepIntake";
import StepAmbiguities from "@/components/wizard/StepAmbiguities";
import StepFormalSpec from "@/components/wizard/StepFormalSpec";
import StepBacktest from "@/components/wizard/StepBacktest";
import StepBot from "@/components/wizard/StepBot";
import StepGuide from "@/components/wizard/StepGuide";
import MonetizationSlot from "@/components/MonetizationSlot";
import AuthToolbar from "@/components/AuthToolbar";
import BotLabWorkspace from "@/components/botlab/BotLabWorkspace";
import { projectApi } from "@/lib/api";
import type { ProjectDetail, ProjectSummary } from "@/types";

const STEPS = [
  { id: 1, label: "La tua strategia",   description: "Descrivi come operi" },
  { id: 2, label: "Revisione AI",       description: "Ambiguità e alternative" },
  { id: 3, label: "Specifica formale",  description: "Regole codificate" },
  { id: 4, label: "Backtest",          description: "Dati storici reali" },
  { id: 5, label: "Il tuo bot",         description: "Expert Advisor MQL5" },
  { id: 6, label: "Installa su MT5",    description: "Guida passo passo" },
];

export default function WizardPage() {
  const [workspaceMode, setWorkspaceMode] = useState<"strategy" | "botlab">("strategy");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [currentProject, setCurrentProject] = useState<ProjectDetail | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<any>(null);
  const [formalSpec, setFormalSpec] = useState<any>(null);
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [botResult, setBotResult] = useState<any>(null);

  async function loadProjects(preferredProjectId?: string | null) {
    try {
      const response = await projectApi.list() as { projects?: ProjectSummary[] }
      const nextProjects = response.projects || []
      setProjects(nextProjects)
      const selectedId =
        preferredProjectId ||
        currentProjectId ||
        nextProjects.find((project) => project.mode === workspaceMode)?.project_id ||
        nextProjects[0]?.project_id ||
        null
      setCurrentProjectId(selectedId)
    } catch {
      setProjects([])
    }
  }

  async function loadProjectDetail(projectId: string) {
    try {
      const response = await projectApi.detail(projectId) as { project?: ProjectDetail }
      setCurrentProject(response.project || null)
    } catch {
      setCurrentProject(null)
    }
  }

  async function createProject(mode: "strategy" | "botlab") {
    const label = mode === "strategy" ? "New Strategy Project" : "New Bot Lab Project"
    try {
      const response = await projectApi.create(label, mode) as { project?: ProjectSummary }
      const projectId = response.project?.project_id || null
      if (projectId) {
        setCurrentProjectId(projectId)
        await loadProjects(projectId)
      }
    } catch {
      // ignore: the workspace can still operate session-based as fallback
    }
  }

  useEffect(() => {
    loadProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!currentProjectId) {
      setCurrentProject(null)
      return
    }
    loadProjectDetail(currentProjectId)
  }, [currentProjectId])

  useEffect(() => {
    if (!projects.length) return
    const filtered = projects.filter((project) => project.mode === workspaceMode)
    if (currentProjectId && filtered.some((project) => project.project_id === currentProjectId)) {
      return
    }
    setCurrentProjectId(filtered[0]?.project_id || projects[0]?.project_id || null)
  }, [workspaceMode, projects, currentProjectId]);

  const goNext = () => setCurrentStep((s) => Math.min(s + 1, STEPS.length));
  const goPrev = () => setCurrentStep((s) => Math.max(s - 1, 1));
  const restart = () => {
    setCurrentStep(1);
    setSessionId(null);
    setParseResult(null);
    setFormalSpec(null);
    setBacktestResult(null);
    setBotResult(null);
  };
  const stepRequirements: Record<number, boolean> = {
    2: !!parseResult,
    3: !!formalSpec,
    4: !!sessionId,
    5: !!sessionId && !!formalSpec,
    6: !!botResult,
  };
  const stepReady = stepRequirements[currentStep] ?? true;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="flex min-h-screen">
        <aside className="hidden w-80 shrink-0 border-r border-slate-800 bg-slate-950 xl:flex xl:flex-col">
          <div className="border-b border-slate-800 px-6 py-6">
            <div className="text-[11px] uppercase tracking-[0.28em] text-amber-300">Visari Trading Room</div>
            <div className="mt-3 text-2xl font-semibold text-slate-50">Quantitative Strategy Platform</div>
            <div className="mt-2 text-sm leading-relaxed text-slate-500">
              Strategy design, research validation, macro-aware MQL5 delivery.
            </div>
          </div>

          <div className="space-y-8 px-6 py-6">
            <div className="space-y-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Workspace</div>
              <button
                onClick={() => setWorkspaceMode("strategy")}
                className={`w-full border px-4 py-3 text-left text-sm transition-colors ${
                  workspaceMode === "strategy"
                    ? "border-slate-500 bg-slate-900 text-slate-100"
                    : "border-slate-800 bg-transparent text-slate-500 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                <div className="font-medium">Create Strategy</div>
                <div className="mt-1 text-xs text-slate-500">From idea to formal spec, research and bot export.</div>
              </button>
              <button
                onClick={() => setWorkspaceMode("botlab")}
                className={`w-full border px-4 py-3 text-left text-sm transition-colors ${
                  workspaceMode === "botlab"
                    ? "border-slate-500 bg-slate-900 text-slate-100"
                    : "border-slate-800 bg-transparent text-slate-500 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                <div className="font-medium">Bot Lab</div>
                <div className="mt-1 text-xs text-slate-500">Audit, modify, compare and re-test existing bots.</div>
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Projects</div>
                <button
                  onClick={() => createProject(workspaceMode)}
                  className="border border-slate-800 px-2 py-1 text-[11px] uppercase tracking-[0.12em] text-slate-400 hover:border-slate-600 hover:text-slate-200"
                >
                  New
                </button>
              </div>
              <div className="space-y-2">
                {projects.filter((project) => project.mode === workspaceMode).slice(0, 6).map((project) => (
                  <button
                    key={project.project_id}
                    onClick={() => setCurrentProjectId(project.project_id)}
                    className={`w-full border px-4 py-3 text-left transition-colors ${
                      currentProjectId === project.project_id
                        ? "border-slate-500 bg-slate-900 text-slate-100"
                        : "border-slate-900 bg-transparent text-slate-500 hover:border-slate-700 hover:text-slate-200"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-sm font-medium">{project.title}</span>
                      <span className="text-[11px] text-slate-500">{project.latest_verdict || project.status}</span>
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {(project.metadata?.["market"] as string | undefined) || project.mode} · {project.project_id.slice(0, 8)}
                    </div>
                  </button>
                ))}
                {projects.filter((project) => project.mode === workspaceMode).length === 0 && (
                  <div className="border border-dashed border-slate-800 px-4 py-4 text-xs text-slate-500">
                    Nessun progetto ancora salvato per questo workspace.
                  </div>
                )}
              </div>
            </div>

            {workspaceMode === "strategy" && (
              <div className="space-y-2">
                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Pipeline</div>
                {STEPS.map((step) => {
                  const active = step.id === currentStep
                  const completed = step.id < currentStep
                  return (
                    <button
                      key={step.id}
                      onClick={() => sessionId && setCurrentStep(step.id)}
                      disabled={!sessionId && step.id > 1}
                      className={`w-full border px-4 py-3 text-left transition-colors ${
                        active
                          ? "border-slate-500 bg-slate-900"
                          : completed
                          ? "border-slate-800 bg-slate-950/60 text-slate-300 hover:border-slate-700"
                          : "border-slate-900 bg-transparent text-slate-600"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{step.label}</span>
                        <span className="text-[11px] text-slate-500">{completed ? "done" : `0${step.id}`}</span>
                      </div>
                      <div className="mt-1 text-xs text-slate-500">{step.description}</div>
                    </button>
                  )
                })}
              </div>
            )}

            <div className="space-y-3 border border-slate-800 bg-slate-950/70 px-4 py-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Methodology Note</div>
              <div className="text-sm leading-relaxed text-slate-400">
                Positive backtests do not imply future profits. The platform enforces fail-fast validation, research governance and explicit blockers before code export.
              </div>
            </div>
          </div>
        </aside>

        <div className="flex min-h-screen flex-1 flex-col">
          <header className="border-b border-slate-800 px-6 py-4 lg:px-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Active Workspace</div>
                <div className="mt-1 text-2xl font-semibold text-slate-50">
                  {workspaceMode === "strategy" ? "Strategy Factory" : "Bot Lab"}
                </div>
                <div className="mt-2 text-sm text-slate-500">
                  {workspaceMode === "strategy"
                    ? "Design, validate and export a macro-aware trading bot."
                    : "Upload an existing bot, inspect its logic and produce a controlled revision."}
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
                  <span>Project: {currentProject?.title || "No project selected"}</span>
                  <span>Versions: {currentProject?.versions?.length ?? 0}</span>
                  <span>Artifacts: {currentProject?.artifacts?.length ?? 0}</span>
                  <span>Jobs: {currentProject?.jobs?.length ?? 0}</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right text-xs text-slate-500">
                  {workspaceMode === 'strategy'
                    ? (sessionId ? `Session ${sessionId.slice(0, 8)}` : "New strategy session")
                    : 'Bot Lab active'}
                </div>
                <AuthToolbar />
              </div>
            </div>
          </header>

          <div className="border-b border-slate-800 px-6 py-4 lg:px-8 xl:hidden">
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => setWorkspaceMode("strategy")}
                className={`border px-4 py-2 text-sm transition-colors ${
                  workspaceMode === "strategy"
                    ? "border-slate-500 bg-slate-900 text-slate-100"
                    : "border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                Create Strategy
              </button>
              <button
                onClick={() => setWorkspaceMode("botlab")}
                className={`border px-4 py-2 text-sm transition-colors ${
                  workspaceMode === "botlab"
                    ? "border-slate-500 bg-slate-900 text-slate-100"
                    : "border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                Bot Lab
              </button>
            </div>
          </div>

          <div className="border-b border-slate-800 px-6 py-4 text-xs text-slate-500 lg:px-8">
            Public-facing flow. Authenticated users can operate with a personal Claude API key or with a Claude key assigned to their account by admin; live macro execution remains tied to the user’s economic-calendar provider key.
          </div>

          <main className="flex-1 px-6 py-8 lg:px-8">
            <div className="mx-auto max-w-6xl">
        {workspaceMode === "strategy" && !stepReady && (
          <div className="border border-slate-800 bg-slate-950/60 px-8 py-16 text-center space-y-4">
            <p className="text-slate-400">Sessione persa dopo il refresh.</p>
            <button onClick={restart} className="border border-slate-200 bg-slate-100 px-6 py-3 font-semibold text-slate-950">
              Ricomincia dall&apos;inizio →
            </button>
          </div>
        )}
        {workspaceMode === "botlab" && <BotLabWorkspace />}
        {workspaceMode === "strategy" && currentStep === 1 && (
          <StepIntake
            projectId={currentProjectId}
            onComplete={(id, result) => {
              setSessionId(id);
              setCurrentProjectId(result.project_id || currentProjectId);
              setParseResult(result);
              setFormalSpec(null);
              setBacktestResult(null);
              setBotResult(null);
              loadProjects(result.project_id || currentProjectId);
              goNext();
            }}
          />
        )}
        {workspaceMode === "strategy" && currentStep === 2 && parseResult && stepReady && (
          <StepAmbiguities
            sessionId={sessionId!}
            parseResult={parseResult}
            onComplete={(spec) => {
              setFormalSpec(spec);
              setBacktestResult(null);
              setBotResult(null);
              goNext();
            }}
            onBack={goPrev}
          />
        )}
        {workspaceMode === "strategy" && currentStep === 3 && formalSpec && stepReady && (
          <StepFormalSpec
            formalSpec={formalSpec}
            onComplete={goNext}
            onBack={goPrev}
          />
        )}
        {workspaceMode === "strategy" && currentStep === 4 && stepReady && (
          <StepBacktest
            sessionId={sessionId!}
            projectId={currentProjectId}
            onComplete={(result) => {
              setBacktestResult(result);
              setBotResult(null);
              loadProjects(currentProjectId);
              goNext();
            }}
            onBack={goPrev}
          />
        )}
        {workspaceMode === "strategy" && currentStep === 5 && stepReady && (
          <StepBot
            sessionId={sessionId!}
            formalSpec={formalSpec}
            backtestResult={backtestResult}
            onComplete={(result) => {
              setBotResult(result);
              loadProjects(currentProjectId);
              goNext();
            }}
            onBack={goPrev}
          />
        )}
        {workspaceMode === "strategy" && currentStep === 6 && stepReady && (
          <StepGuide botResult={botResult} onBack={goPrev} />
        )}

              <MonetizationSlot slotId="research_footer" />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
