"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import StepIntake from "@/components/wizard/StepIntake";
import StepAmbiguities from "@/components/wizard/StepAmbiguities";
import StepFormalSpec from "@/components/wizard/StepFormalSpec";
import StepBacktest from "@/components/wizard/StepBacktest";
import StepBot from "@/components/wizard/StepBot";
import StepGuide from "@/components/wizard/StepGuide";
import AuthToolbar from "@/components/AuthToolbar";
import { projectApi } from "@/lib/api";
import type { ProjectDetail } from "@/types";

const STEPS = [
  { id: 1, label: "Progettazione strategia", description: "Mercato, timeframe, ingressi e modello di rischio" },
  { id: 2, label: "Revisione strutturata", description: "Risolvi i blocchi prima della formalizzazione" },
  { id: 3, label: "Specifica formale", description: "Regole codificate pronte per l'esecuzione" },
  { id: 4, label: "Validazione", description: "Backtest, regime, stabilita e controllo rischio" },
  { id: 5, label: "Export bot", description: "Pacchetto finale per MT5" },
  { id: 6, label: "Guida deploy", description: "Installa e supervisiona il sistema" },
];

export default function BuilderPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<any>(null);
  const [formalSpec, setFormalSpec] = useState<any>(null);
  const [backtestResult, setBacktestResult] = useState<any>(null);
  const [botResult, setBotResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Initialize from URL if needed or create a default session
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pid = params.get("project_id");
    if (pid) setProjectId(pid);
  }, []);

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

  const stepUnlocked = (stepId: number) => {
    if (stepId === 1) return true
    if (stepId === 2) return !!parseResult
    if (stepId === 3) return !!formalSpec
    if (stepId === 4) return !!sessionId && !!formalSpec
    if (stepId === 5) return !!backtestResult
    if (stepId === 6) return !!botResult
    return false
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Clean Header */}
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between bg-slate-950/50 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-6">
          <button 
            onClick={() => router.push("/workspace")}
            className="text-slate-400 hover:text-slate-100 transition-colors flex items-center gap-2 text-sm"
          >
            ← Dashboard
          </button>
          <div className="h-4 w-[1px] bg-slate-800" />
          <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-[0.2em] text-cyan-500 font-bold">Strategy Builder</span>
            <span className="text-sm font-semibold text-slate-200">
              {STEPS[currentStep - 1].label}
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={restart}
            className="text-xs text-slate-500 hover:text-rose-400 transition-colors"
          >
            Azzera sessione
          </button>
          <AuthToolbar />
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Step Navigation Sidebar */}
        <aside className="w-72 border-r border-slate-800 bg-slate-950/30 p-6 hidden lg:block overflow-y-auto">
          <div className="space-y-4">
            {STEPS.map((step) => {
              const active = step.id === currentStep;
              const completed = step.id < currentStep;
              const unlocked = stepUnlocked(step.id)
              const locked = !completed && !active && !unlocked
              
              return (
                <div 
                  key={step.id}
                  className={`relative pl-8 py-3 group ${active ? 'opacity-100' : completed ? 'opacity-80' : 'opacity-55'}`}
                >
                  {/* Line */}
                  {step.id < STEPS.length && (
                    <div className="absolute left-[11px] top-8 w-[2px] h-full bg-slate-800" />
                  )}
                  
                  {/* Dot */}
                  <div className={`absolute left-0 top-4 w-6 h-6 rounded-full border-2 flex items-center justify-center text-[10px] font-bold transition-all
                    ${active ? 'border-cyan-500 bg-cyan-950 text-cyan-300 scale-110' : 
                      completed ? 'border-emerald-500 bg-emerald-950 text-emerald-400' : locked ? 'border-slate-900 bg-slate-950 text-slate-700' : 'border-slate-800 bg-slate-900 text-slate-500'}`}
                  >
                    {completed ? '✓' : locked ? '•' : step.id}
                  </div>

                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-bold uppercase transition-colors ${active ? 'text-slate-100' : completed ? 'text-slate-300' : 'text-slate-500'}`}>
                        {step.label}
                      </span>
                      {active && (
                        <span className="border border-cyan-900/70 bg-cyan-950/15 px-2 py-0.5 text-[9px] uppercase tracking-[0.16em] text-cyan-300">
                          Attuale
                        </span>
                      )}
                      {locked && (
                        <span className="border border-slate-800 px-2 py-0.5 text-[9px] uppercase tracking-[0.16em] text-slate-600">
                          Bloccato
                        </span>
                      )}
                    </div>
                    {(active || completed) && (
                      <span className="text-[10px] text-slate-600 leading-tight mt-1">
                        {step.description}
                      </span>
                    )}
                    {locked && (
                      <span className="text-[10px] text-slate-700 leading-tight mt-1">
                        Completa lo step attuale per sbloccare questo passaggio.
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-12 p-4 bg-slate-900/40 border border-slate-800 rounded-lg">
            <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Pipeline validata</h4>
            <p className="text-[10px] text-slate-600 leading-relaxed">
              Gli step futuri restano bloccati finche non completi quello attuale. In questo modo il flusso resta controllato e supervisionabile.
            </p>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_right,rgba(8,47,73,0.1),transparent_70%)]">
          <div className="max-w-4xl mx-auto px-6 py-12">
            <div className="mb-8 border border-slate-800/90 bg-slate-950/55 px-5 py-5">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Ingegneria strategica strutturata</div>
              <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <div className="text-2xl font-semibold text-slate-50">{STEPS[currentStep - 1].label}</div>
                  <div className="mt-1 text-sm text-slate-400">{STEPS[currentStep - 1].description}</div>
                </div>
                <div className="text-xs text-slate-500">
                  Step {currentStep} di {STEPS.length} · livello di validazione istituzionale
                </div>
              </div>
            </div>

            {!stepReady && (
              <div className="border border-slate-800 bg-slate-950/60 p-12 text-center rounded-xl backdrop-blur-sm">
                <div className="text-4xl mb-6">🔄</div>
                <h3 className="text-xl font-bold text-slate-200 mb-2">Sessione non sincronizzata</h3>
                <p className="text-slate-500 mb-8 max-w-md mx-auto">
                  La sessione del workflow e scaduta oppure la pagina e stata aggiornata a meta processo. Riparti dall'intake per ripristinare un flusso ordinato.
                </p>
                <button 
                  onClick={restart} 
                  className="bg-cyan-600 hover:bg-cyan-500 text-slate-50 px-8 py-3 rounded font-bold transition-all"
                >
                  Riavvia workflow →
                </button>
              </div>
            )}

            {stepReady && currentStep === 1 && (
              <StepIntake
                projectId={projectId}
                onComplete={(id, result) => {
                  setSessionId(id);
                  setProjectId(result.project_id || projectId);
                  setParseResult(result);
                  setFormalSpec(null);
                  setBacktestResult(null);
                  setBotResult(null);
                  goNext();
                }}
              />
            )}

            {stepReady && currentStep === 2 && parseResult && (
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

            {stepReady && currentStep === 3 && formalSpec && (
              <StepFormalSpec
                formalSpec={formalSpec}
                onComplete={goNext}
                onBack={goPrev}
              />
            )}

            {stepReady && currentStep === 4 && (
              <StepBacktest
                sessionId={sessionId!}
                projectId={projectId}
                onComplete={(result) => {
                  setBacktestResult(result);
                  setBotResult(null);
                  goNext();
                }}
                onBack={goPrev}
              />
            )}

            {stepReady && currentStep === 5 && (
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

            {stepReady && currentStep === 6 && (
              <StepGuide botResult={botResult} onBack={goPrev} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
