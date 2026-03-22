'use client'

import { useState } from 'react'
import { strategyApi, exportApi, formatError } from '@/lib/api'
import { Alert, Spinner, TabBar, CodeBlock, NavButtons } from '@/components/ui'
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
  const generationBlocked = formalSpec?.status !== 'VALID'

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

  // Stato iniziale: mostra il box "genera"
  if (!result && !loading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-amber-400 mb-2">
            Genera il tuo Expert Advisor MQL5
          </h1>
          <p className="text-stone-400 text-sm leading-relaxed">
            Claude genererà il codice MQL5 partendo dalla specifica formale della tua strategia,
            con documentazione in italiano e commenti su ogni blocco logico.
          </p>
        </div>

        <Alert type="error" title="Leggere prima di scaricare">
          <ul className="space-y-1 mt-1">
            <li>• Il codice MQL5 è un <strong>punto di partenza</strong> generato da AI — non un prodotto finito</li>
            <li>• Va <strong>sempre testato in demo</strong> prima di qualsiasi uso live</li>
            <li>• Un developer MQL5 dovrebbe revisionarlo prima del deploy in produzione</li>
            <li>• Le parti discrezionali non codificabili sono state approssimate — verifica che l&apos;approssimazione sia accettabile per te</li>
          </ul>
        </Alert>

        {generationBlocked && (
          <Alert type="error" title="Generazione bloccata prima di spendere token">
            La specifica formale non è in stato `VALID`. Completa gli input mancanti o risolvi le ambiguità prima di tentare la generazione del bot.
          </Alert>
        )}

        {backtestResult && (
          <div className="p-4 bg-stone-900 border border-stone-700 rounded space-y-2">
            <div className="text-stone-400 text-xs font-bold uppercase tracking-wider">
              Riepilogo backtest — base per il bot
            </div>
            <div className="flex gap-6 text-sm">
              <div>
                <span className="text-stone-500 text-xs">Sharpe OOS </span>
                <span className={`font-bold ${
                  (backtestResult.out_of_sample.sharpe_ratio ?? 0) >= 1
                    ? 'text-green-400'
                    : 'text-amber-400'
                }`}>
                  {backtestResult.out_of_sample.sharpe_ratio?.toFixed(2) ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-stone-500 text-xs">Trade OOS </span>
                <span className="text-stone-200 font-bold">
                  {backtestResult.out_of_sample.total_trades ?? '—'}
                </span>
              </div>
              <div>
                <span className="text-stone-500 text-xs">Return OOS </span>
                <span className={`font-bold ${
                  (backtestResult.out_of_sample.total_return_pct ?? 0) > 0
                    ? 'text-green-400'
                    : 'text-red-400'
                }`}>
                  {backtestResult.out_of_sample.total_return_pct?.toFixed(1) ?? '—'}%
                </span>
              </div>
              <div>
                <span className="text-stone-500 text-xs">Max DD </span>
                <span className="text-stone-200 font-bold">
                  {backtestResult.out_of_sample.max_drawdown_pct?.toFixed(1) ?? '—'}%
                </span>
              </div>
            </div>
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
        <h1 className="text-2xl font-bold text-amber-400 mb-2">
          {generationSucceeded ? 'Expert Advisor generato ✓' : 'Generazione non valida'}
        </h1>
        <p className="text-stone-400 text-sm">
          {generationSucceeded
            ? 'Leggi prima la documentazione, poi scarica il file .mq5 e segui la guida di installazione MT5 nel prossimo step.'
            : result?.message}
        </p>
      </div>

      {!generationSucceeded && (
        <Alert type="error" title="Download disabilitato">
          {(result?.code_validation?.errors || []).join(' · ') || 'Il backend ha bloccato il download perché il codice è vuoto, incompleto o non valido.'}
        </Alert>
      )}

      <TabBar
        tabs={[
          { id: 'doc', label: '📄 Documentazione' },
          { id: 'code', label: '💻 Codice MQL5' },
          { id: 'limits', label: '⚠️ Limiti' },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === 'doc' && (
        <div className="p-5 bg-stone-900 border border-stone-800 rounded">
          <p className="text-stone-300 text-sm whitespace-pre-wrap leading-relaxed">
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
          <div className="p-5 bg-stone-900 border border-stone-800 rounded text-stone-400 text-sm">
            Nessun codice scaricabile: la generazione è stata fermata o ha prodotto un output non valido.
          </div>
        )
      )}

      {tab === 'limits' && (
        <div className="space-y-4">
          {result!.implementation_assumptions?.length > 0 && (
            <div className="p-4 bg-stone-900 border border-stone-800 rounded space-y-2">
              <h3 className="text-stone-300 font-bold text-sm">
                Assunzioni implementative
              </h3>
              <p className="text-stone-500 text-xs">
                Cose che il codice assume e che non erano esplicitamente specificate:
              </p>
              {result!.implementation_assumptions.map((a, i) => (
                <div key={i} className="flex gap-2 text-stone-400 text-xs">
                  <span className="text-stone-600">•</span>
                  <span>{a}</span>
                </div>
              ))}
            </div>
          )}
          {result!.limitations_vs_discretionary?.length > 0 && (
            <div className="p-4 bg-amber-950/15 border border-amber-800/40 rounded space-y-2">
              <h3 className="text-amber-400 font-bold text-sm">
                Cosa il bot NON può replicare della strategia discrezionale
              </h3>
              {result!.limitations_vs_discretionary.map((l, i) => (
                <div key={i} className="flex gap-2 text-amber-300 text-xs">
                  <span className="text-amber-700">•</span>
                  <span>{l}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={downloadBot}
          disabled={!generationSucceeded}
          className="flex-1 py-3 bg-green-700 hover:bg-green-600 text-white font-bold rounded transition-colors disabled:opacity-40"
        >
          ⬇ Scarica .mq5
        </button>
        <button
          onClick={() => onComplete(result!)}
          disabled={!generationSucceeded}
          className="flex-1 py-3 bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold rounded transition-colors disabled:opacity-40"
        >
          Guida installazione MT5 →
        </button>
      </div>
      <button
        onClick={onBack}
        className="w-full py-2 text-stone-500 hover:text-stone-300 text-sm transition-colors"
      >
        ← Torna al backtest
      </button>
    </div>
  )
}
