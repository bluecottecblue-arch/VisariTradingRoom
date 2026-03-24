'use client'

import { useState } from 'react'
import { strategyApi, exportApi, formatError } from '@/lib/api'
import { Alert, Spinner, TabBar, CodeBlock, NavButtons, MetricCard } from '@/components/ui'
import type { BacktestResult, BotResult, FormalSpec } from '@/types'

interface Props {
  sessionId: string
  formalSpec: FormalSpec | null
  backtestResult: BacktestResult | null
  onComplete: (result: BotResult) => void
  onBack: () => void
}

export default function StepBot({ sessionId, formalSpec, backtestResult, onComplete, onBack }: Props) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BotResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'doc' | 'code' | 'limits'>('doc')
  const verdict = backtestResult?.final_decision
  const generationBlocked = formalSpec?.status !== 'VALID' || verdict?.generate_bot_allowed === false

  const generate = async () => {
    if (generationBlocked) {
      setError('La specifica non è valida per la generazione codice. Torna indietro e completa i dettagli mancanti.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await strategyApi.generateBot(sessionId) as BotResult

      if (data.download_ready && data.code_validation?.is_valid && data.mql5_code) {
        await exportApi.saveMql5(sessionId, data.mql5_code)
      }

      setResult(data)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setLoading(false)
    }
  }

  const downloadBot = () => {
    if (!result?.download_ready) return
    const a = document.createElement('a')
    a.href = exportApi.downloadMql5Url(sessionId)
    a.download = `VisariTradingRoom_${sessionId.slice(0, 8)}.mq5`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const downloadSetupGuide = () => {
    const a = document.createElement('a')
    a.href = exportApi.bundleSetupUrl(sessionId)
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // Stato iniziale: mostra il box "genera"
  if (!result && !loading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="mb-2 text-3xl font-semibold text-slate-50">
            Operational Bot Package
          </h1>
          <p className="text-sm leading-relaxed text-slate-400">
            La piattaforma produrrà un EA MQL5 esportabile, con documentazione, readiness operativa e setup guide per MT5.
          </p>
        </div>

        <Alert type="info" title="Output atteso">
          <ul className="space-y-1 mt-1">
            <li>• Codice `.mq5` validato dal backend</li>
            <li>• Documentazione operativa in italiano</li>
            <li>• Setup guide MT5 e manifest di deployment</li>
            <li>• Checklist esplicita su macro live, WebRequest e runtime inputs</li>
          </ul>
        </Alert>

        {generationBlocked && (
        <Alert type="error" title="Generazione bloccata prima di spendere token">
          {formalSpec?.status !== 'VALID'
            ? 'La specifica formale non è in stato VALID. Completa gli input mancanti o risolvi le ambiguità prima di tentare la generazione del bot.'
            : `Il research layer ha bloccato la generazione: verdict ${verdict?.verdict}.`}
        </Alert>
      )}

        {backtestResult && (
        <div className="space-y-2 border border-slate-800 bg-slate-950/70 p-4">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Research basis for export
            </div>
            <div className="flex flex-wrap gap-6 text-sm">
              <div>
                <span className="text-slate-500 text-xs">Sharpe OOS </span>
                <span className={`font-bold ${
                  (backtestResult.out_of_sample.sharpe_ratio ?? 0) >= 1
                    ? 'text-emerald-300'
                    : 'text-slate-300'
                }`}>
                  {backtestResult.out_of_sample.sharpe_ratio?.toFixed(2) ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Trade OOS </span>
                <span className="text-slate-200 font-bold">
                  {backtestResult.out_of_sample.total_trades ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Return OOS </span>
                <span className={`font-bold ${
                  (backtestResult.out_of_sample.total_return_pct ?? 0) > 0
                    ? 'text-emerald-300'
                    : 'text-rose-300'
                }`}>
                  {backtestResult.out_of_sample.total_return_pct?.toFixed(1) ?? '—'}%
                </span>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Verdict </span>
                <span className={`font-bold ${
                  verdict?.verdict === 'REJECT' || verdict?.verdict === 'NEEDS_RESEARCH'
                    ? 'text-rose-300'
                    : verdict?.verdict === 'PAPER_TRADE_ONLY'
                      ? 'text-amber-300'
                      : 'text-emerald-300'
                }`}>
                  {verdict?.verdict ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-slate-500 text-xs">Max DD </span>
                <span className="text-slate-200 font-bold">
                  {backtestResult.out_of_sample.max_drawdown_pct?.toFixed(1) ?? '—'}%
                </span>
              </div>
            </div>
            {verdict && (
              <div className="space-y-1 pt-2 text-xs text-slate-400">
                {[...(verdict.blockers || []), ...(verdict.reasons || [])].slice(0, 3).map((item, index) => (
                  <div key={index}>• {item}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {error && <Alert type="error">{error}</Alert>}

        <NavButtons
          onBack={onBack}
          onNext={generationBlocked ? undefined : generate}
          nextLabel={generationBlocked ? 'Generazione bloccata' : 'Genera Expert Advisor MQL5 →'}
          loading={loading}
          disabled={generationBlocked}
        />
      </div>
    )
  }

  // Loading state
  if (loading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-amber-400 mb-2">Generazione in corso...</h1>
        </div>
        <div className="p-8 bg-stone-900 border border-stone-700 rounded">
          <Spinner label="Claude sta scrivendo il codice MQL5..." />
          <p className="text-stone-600 text-xs text-center mt-2">
            30–90 secondi, a seconda della complessità della strategia
          </p>
        </div>
      </div>
    )
  }

  // Result state
  const generationSucceeded = result?.status === 'VALID' && result.download_ready && result.code_validation?.is_valid

  return (
    <div className="space-y-6">
        <div>
          <h1 className="mb-2 text-3xl font-semibold text-slate-50">
            {generationSucceeded ? 'Export Package Ready' : 'Generation Failed Validation'}
          </h1>
          <p className="text-sm text-slate-400">
            {generationSucceeded
              ? 'Il bot ha superato la validazione minima. Ora puoi scaricare codice, setup guide e manifest operativo.'
              : result?.message}
          </p>
        </div>

      {!generationSucceeded && (
        <Alert type="error" title="Download disabilitato">
          {(result?.code_validation?.errors || []).join(' · ') ||
            error ||
          'Il backend ha bloccato il download perché il codice è vuoto, incompleto o non valido.'}
        </Alert>
      )}

      {result?.deployment_readiness && (
        <div className="space-y-4 border border-slate-800 bg-slate-950/70 p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Deployment readiness</div>
              <div className="mt-1 text-sm text-slate-400">{result.deployment_readiness.summary}</div>
            </div>
            <div className="text-right">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Status</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">
                {result.deployment_readiness.status} · {result.deployment_readiness.score}/100
              </div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <MetricCard label="Export status" value={result.deployment_readiness.status} />
            <MetricCard label="Readiness score" value={`${result.deployment_readiness.score}/100`} />
            <MetricCard label="Macro runtime" value={result.code_validation.checks?.has_api_key_input ? 'enabled' : 'not required'} />
          </div>

          {result.deployment_readiness.live_blockers?.length > 0 && (
            <Alert type="error" title="Live blockers">
              {result.deployment_readiness.live_blockers.join(' · ')}
            </Alert>
          )}

          {result.deployment_readiness.warnings?.length > 0 && (
            <Alert type="warning" title="Operator warnings">
              {result.deployment_readiness.warnings.join(' · ')}
            </Alert>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-2 border border-slate-800 bg-slate-950 p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Setup steps</div>
              {(result.deployment_readiness.setup_steps || []).map((item, index) => (
                <div key={index} className="text-sm text-slate-300">• {item}</div>
              ))}
            </div>
            <div className="space-y-2 border border-slate-800 bg-slate-950 p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Runtime requirements</div>
              {(result.deployment_readiness.runtime_requirements || []).map((item, index) => (
                <div key={index} className="text-sm text-slate-300">
                  <span className="font-medium">{item.label}:</span> {item.value}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <TabBar
        tabs={[
          { id: 'doc', label: 'Documentation' },
          { id: 'code', label: 'MQL5 Code' },
          { id: 'limits', label: 'Assumptions & Limits' },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === 'doc' && (
        <div className="border border-slate-800 bg-slate-950/70 p-5">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
            {generationSucceeded
              ? result!.documentation || 'Documentazione non disponibile.'
              : 'Documentazione non disponibile perché la generazione è stata bloccata o ha restituito un output non valido.'}
          </p>
        </div>
      )}

      {tab === 'code' && (
        generationSucceeded ? (
          <CodeBlock
            code={result!.mql5_code}
            language="MQL5"
            maxHeight="32rem"
          />
        ) : (
          <div className="border border-slate-800 bg-slate-950/70 p-5 text-sm text-slate-400">
            Nessun codice scaricabile: la generazione è stata fermata o ha prodotto un output non valido.
          </div>
        )
      )}

      {tab === 'limits' && (
        <div className="space-y-4">
          {result!.implementation_assumptions?.length > 0 && (
            <div className="space-y-2 border border-slate-800 bg-slate-950/70 p-4">
              <h3 className="text-sm font-semibold text-slate-200">
                Assunzioni implementative
              </h3>
              <p className="text-xs text-slate-500">
                Cose che il codice assume e che non erano esplicitamente specificate:
              </p>
              {result!.implementation_assumptions.map((a, i) => (
                <div key={i} className="flex gap-2 text-xs text-slate-400">
                  <span className="text-slate-600">•</span>
                  <span>{a}</span>
                </div>
              ))}
            </div>
          )}
          {result!.limitations_vs_discretionary?.length > 0 && (
            <div className="space-y-2 border border-amber-900/50 bg-amber-950/10 p-4">
              <h3 className="text-sm font-semibold text-amber-200">
                Cosa il bot NON può replicare della strategia discrezionale
              </h3>
              {result!.limitations_vs_discretionary.map((l, i) => (
                <div key={i} className="flex gap-2 text-xs text-amber-200">
                  <span className="text-amber-700">•</span>
                  <span>{l}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-4">
        <button
          onClick={downloadBot}
          disabled={!generationSucceeded}
          className="border border-slate-200 bg-slate-100 py-3 font-semibold text-slate-950 transition-colors hover:bg-white disabled:opacity-40"
        >
          Scarica .mq5
        </button>
        <button
          onClick={downloadSetupGuide}
          disabled={!generationSucceeded}
          className="border border-slate-800 py-3 text-slate-200 transition-colors hover:border-slate-600 disabled:opacity-40"
        >
          Setup guide
        </button>
        <a
          href={exportApi.reportUrl(sessionId)}
          target="_blank"
          rel="noreferrer"
          className={`border py-3 text-center transition-colors ${generationSucceeded ? 'border-slate-800 text-slate-200 hover:border-slate-600' : 'pointer-events-none border-slate-900 text-slate-700'}`}
        >
          Research report
        </a>
        <button
          onClick={() => onComplete(result!)}
          disabled={!generationSucceeded}
          className="border border-slate-800 py-3 text-slate-200 transition-colors hover:border-slate-600 disabled:opacity-40"
        >
          MT5 install guide
        </button>
      </div>
      <button
        onClick={onBack}
        className="w-full py-2 text-sm text-slate-500 transition-colors hover:text-slate-300"
      >
        ← Torna al backtest
      </button>
    </div>
  )
}
