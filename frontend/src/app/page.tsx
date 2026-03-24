"use client";

import { useState } from "react";
import StepIntake from "@/components/wizard/StepIntake";
import StepAmbiguities from "@/components/wizard/StepAmbiguities";
import StepFormalSpec from "@/components/wizard/StepFormalSpec";
import StepBacktest from "@/components/wizard/StepBacktest";
import StepBot from "@/components/wizard/StepBot";
import StepGuide from "@/components/wizard/StepGuide";
import MonetizationSlot from "@/components/MonetizationSlot";
import AuthToolbar from "@/components/AuthToolbar";
import BotLabWorkspace from "@/components/botlab/BotLabWorkspace";

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
  const [currentStep, setCurrentStep] = useState(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<any>(null);
  const [formalSpec, setFormalSpec] = useState<any>(null);
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [botResult, setBotResult] = useState<any>(null);

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
            Public-facing flow. Authenticated users can choose integrated Claude usage or bring their own Claude key; live macro execution remains tied to the user’s economic-calendar provider key.
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
            onComplete={(id, result) => {
              setSessionId(id);
              setParseResult(result);
              setFormalSpec(null);
              setBacktestResult(null);
              setBotResult(null);
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
            onComplete={(result) => {
              setBacktestResult(result);
              setBotResult(null);
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
