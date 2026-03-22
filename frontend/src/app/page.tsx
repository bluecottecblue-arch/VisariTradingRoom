"use client";

import { useState } from "react";
import StepIntake from "@/components/wizard/StepIntake";
import StepAmbiguities from "@/components/wizard/StepAmbiguities";
import StepFormalSpec from "@/components/wizard/StepFormalSpec";
import StepBacktest from "@/components/wizard/StepBacktest";
import StepBot from "@/components/wizard/StepBot";
import StepGuide from "@/components/wizard/StepGuide";

const STEPS = [
  { id: 1, label: "La tua strategia",   description: "Descrivi come operi" },
  { id: 2, label: "Revisione AI",       description: "Ambiguità e alternative" },
  { id: 3, label: "Specifica formale",  description: "Regole codificate" },
  { id: 4, label: "Backtest",          description: "Dati storici reali" },
  { id: 5, label: "Il tuo bot",         description: "Expert Advisor MQL5" },
  { id: 6, label: "Installa su MT5",    description: "Guida passo passo" },
];

export default function WizardPage() {
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
    <div className="min-h-screen bg-stone-950 text-stone-100 font-mono">
      {/* Header */}
      <header className="border-b border-stone-800 px-8 py-4 flex items-center justify-between">
        <div>
          <span className="text-amber-400 font-bold text-lg tracking-tight">VISARI</span>
          <span className="text-stone-100 font-bold text-lg tracking-tight ml-1">TRADING ROOM</span>
          <span className="ml-3 text-stone-500 text-xs">discrezionale → algoritmico → MT5</span>
        </div>
        <div className="text-stone-500 text-xs">
          {sessionId ? `Sessione: ${sessionId.slice(0, 8)}...` : "Nuova strategia"}
        </div>
      </header>

      {/* Step progress bar */}
      <div className="px-8 py-6 border-b border-stone-800">
        <div className="flex items-center gap-0 overflow-x-auto">
          {STEPS.map((step, idx) => (
            <div key={step.id} className="flex items-center">
              {/* Step circle */}
              <button
                onClick={() => sessionId && setCurrentStep(step.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded transition-all ${
                  step.id === currentStep
                    ? "text-amber-400"
                    : step.id < currentStep
                    ? "text-stone-400 cursor-pointer hover:text-stone-200"
                    : "text-stone-600 cursor-not-allowed"
                }`}
                disabled={!sessionId && step.id > 1}
              >
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border ${
                  step.id === currentStep
                    ? "border-amber-400 bg-amber-400 text-stone-950"
                    : step.id < currentStep
                    ? "border-stone-500 bg-stone-700 text-stone-300"
                    : "border-stone-700 text-stone-600"
                }`}>
                  {step.id < currentStep ? "✓" : step.id}
                </span>
                <div className="hidden md:block text-left">
                  <div className="text-xs font-bold">{step.label}</div>
                  <div className="text-[10px] opacity-60">{step.description}</div>
                </div>
              </button>
              {idx < STEPS.length - 1 && (
                <div className={`w-8 h-px mx-1 ${step.id < currentStep ? "bg-stone-500" : "bg-stone-800"}`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Warning metodologico — sempre visibile */}
      <div className="mx-8 mt-4 px-4 py-3 bg-amber-950/30 border border-amber-800/50 rounded text-xs text-amber-300">
        ⚠️ <strong>Onestà metodologica:</strong> Un backtest positivo NON garantisce profitti futuri.
        Parti della strategia discrezionale non codificabili verranno segnalate esplicitamente.
        Il bot generato è un punto di partenza — va rivisto prima del trading live.
      </div>

      {/* Step content */}
      <main className="px-8 py-8 max-w-4xl">
        {!stepReady && (
          <div className="px-8 py-16 text-center space-y-4 border border-stone-800 rounded-lg bg-stone-900/60">
            <p className="text-stone-400">Sessione persa dopo il refresh.</p>
            <button onClick={restart} className="px-6 py-3 bg-amber-500 text-stone-950 font-bold rounded">
              Ricomincia dall&apos;inizio →
            </button>
          </div>
        )}
        {currentStep === 1 && (
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
        {currentStep === 2 && parseResult && stepReady && (
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
        {currentStep === 3 && formalSpec && stepReady && (
          <StepFormalSpec
            formalSpec={formalSpec}
            onComplete={goNext}
            onBack={goPrev}
          />
        )}
        {currentStep === 4 && stepReady && (
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
        {currentStep === 5 && stepReady && (
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
        {currentStep === 6 && stepReady && (
          <StepGuide botResult={botResult} onBack={goPrev} />
        )}
      </main>
    </div>
  );
}
