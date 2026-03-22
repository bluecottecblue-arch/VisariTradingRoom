'use client'

import { useState } from 'react'
import { strategyApi, formatError } from '@/lib/api'
import type { ParseResult, Ambiguity, FormalSpec } from '@/types'

interface Props {
  sessionId: string
  parseResult: ParseResult
  onComplete: (spec: FormalSpec) => void
  onBack: () => void
}

const SEVERITY_COLORS: Record<string, string> = {
  HIGH:   'border-red-700 bg-red-950/20',
  MEDIUM: 'border-amber-700 bg-amber-950/20',
  LOW:    'border-stone-700 bg-stone-900/30',
}
const SEVERITY_LABELS: Record<string, string> = {
  HIGH:   '⛔ Non codificabile direttamente',
  MEDIUM: '⚠️  Parzialmente codificabile',
  LOW:    '✅ Codificabile con approssimazione',
}

export default function StepAmbiguities({ sessionId, parseResult, onComplete, onBack }: Props) {
  const [resolutions, setResolutions] = useState<Record<string, string>>({})
  const [loading, setLoading]         = useState(false)
  const [error, setError]             = useState<string | null>(null)

  const {
    ambiguities = [],
    required_inputs = [],
    codeable_rules = [],
    bias_warnings = [],
    completeness_score = 0,
    message,
    usage,
    validation,
  } = parseResult

  const resolveWith = (ambId: string, altId: string) =>
    setResolutions((p) => ({ ...p, [ambId]: altId }))

  const unresolvedHigh = ambiguities
    .filter((a) => a.severity === 'HIGH' && !resolutions[a.id]).length
  const missingRequiredInputs = required_inputs.filter((item) => item.blocking !== false).length

  const handleContinue = async () => {
    if (missingRequiredInputs > 0) {
      setError('Mancano informazioni obbligatorie. Torna allo step precedente e completa la strategia prima di formalizzare.')
      return
    }
    if (unresolvedHigh > 0) {
      setError(`Risolvi prima le ${unresolvedHigh} ambiguità CRITICHE.`)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await strategyApi.resolveAmbiguities(sessionId, resolutions) as FormalSpec
      onComplete(data)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-amber-400 mb-2">Revisione AI della tua strategia</h1>
        <p className="text-stone-400 text-sm">
          Qui sotto vedi cosa è codificabile, cosa richiede una tua scelta e cosa blocca
          la generazione finché non inserisci dettagli binari o numerici.
        </p>
      </div>

      <div className={`px-5 py-4 rounded-lg border ${
        parseResult.status === 'VALID'
          ? 'bg-green-950/20 border-green-800/40'
          : 'bg-red-950/20 border-red-800/40'
      }`}>
        <div className="text-stone-200 text-sm font-bold">Stato: {parseResult.status}</div>
        <div className="text-stone-400 text-xs mt-1">{message}</div>
        <div className="text-stone-500 text-xs mt-2">
          {validation?.llm_skipped ? 'Pre-validazione locale: token risparmiati' : 'Revisione LLM completata'}
          {' · '}Issue bloccanti: {validation?.blocking_issues ?? missingRequiredInputs + unresolvedHigh}
          {' · '}Token input stimati: {usage?.estimated_input_tokens ?? 0}
        </div>
      </div>

      {/* Completeness score */}
      <div className="px-5 py-4 bg-stone-900 border border-stone-700 rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <span className="text-stone-300 text-sm font-bold">Codificabilità della strategia</span>
          <span className={`text-lg font-bold ${
            completeness_score >= 0.7 ? 'text-green-400'
            : completeness_score >= 0.4 ? 'text-amber-400'
            : 'text-red-400'
          }`}>
            {Math.round(completeness_score * 100)}%
          </span>
        </div>
        <div className="w-full bg-stone-800 rounded-full h-2">
          <div
            className={`h-2 rounded-full ${
              completeness_score >= 0.7 ? 'bg-green-500'
              : completeness_score >= 0.4 ? 'bg-amber-500'
              : 'bg-red-500'
            }`}
            style={{ width: `${completeness_score * 100}%` }}
          />
        </div>
        <p className="text-stone-500 text-xs mt-2">
          {completeness_score >= 0.7
            ? 'Ottimo! La maggior parte è algoritmizzabile.'
            : completeness_score >= 0.4
            ? 'Buona parte è codificabile ma ci sono elementi soggettivi importanti.'
            : "Molte parti sono discrezionali. Il bot sarà un'approssimazione — questo va saputo."}
        </p>
      </div>

      {/* Bias warnings */}
      {bias_warnings.length > 0 && (
        <div className="px-5 py-4 bg-purple-950/20 border border-purple-800 rounded-lg space-y-2">
          <h3 className="text-purple-300 font-bold text-sm">🧠 Bias cognitivi rilevati</h3>
          {bias_warnings.map((w, i) => (
            <div key={i} className="text-purple-200 text-xs flex gap-2">
              <span>→</span><span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Codeable rules */}
      {codeable_rules.length > 0 && (
        <div>
          <h2 className="text-stone-300 font-bold text-sm uppercase tracking-wider border-b border-stone-800 pb-2 mb-3">
            ✅ Regole già codificabili ({codeable_rules.length})
          </h2>
          <div className="space-y-2">
            {codeable_rules.map((rule) => (
              <div key={rule.id} className="px-4 py-3 bg-green-950/20 border border-green-800/40 rounded flex items-start gap-3">
                <span className="text-green-400 text-xs mt-0.5">✓</span>
                <div>
                  <div className="text-stone-200 text-sm">{rule.description}</div>
                  <div className="text-stone-500 text-xs mt-1 font-mono">{rule.condition}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {required_inputs.length > 0 && (
        <div>
          <h2 className="text-stone-300 font-bold text-sm uppercase tracking-wider border-b border-stone-800 pb-2 mb-4">
            ⛔ Informazioni obbligatorie mancanti ({required_inputs.length})
          </h2>
          <div className="space-y-3">
            {required_inputs.map((item) => (
              <div key={item.id} className="px-4 py-4 bg-red-950/20 border border-red-800/40 rounded space-y-2">
                <div className="text-red-300 text-sm font-bold">{item.label}</div>
                <div className="text-stone-400 text-xs">{item.why}</div>
                <div className="text-stone-500 text-xs font-mono">Esempio valido: {item.example}</div>
                {item.source_text && (
                  <div className="text-stone-600 text-xs">Testo rilevato: &quot;{item.source_text}&quot;</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ambiguities */}
      {ambiguities.length > 0 && (
        <div>
          <h2 className="text-stone-300 font-bold text-sm uppercase tracking-wider border-b border-stone-800 pb-2 mb-4">
            ⚡ Parti che richiedono la tua scelta ({ambiguities.length})
          </h2>
          <div className="space-y-6">
            {ambiguities.map((amb) => (
              <AmbiguityCard
                key={amb.id}
                ambiguity={amb}
                selected={resolutions[amb.id]}
                onSelect={(id) => resolveWith(amb.id, id)}
              />
            ))}
          </div>
        </div>
      )}

      {ambiguities.length === 0 && (
        <div className="px-4 py-3 bg-green-950/20 border border-green-800/40 rounded text-green-300 text-sm">
          ✅ Nessuna ambiguità critica — la strategia è ben definita.
        </div>
      )}

      {error && (
        <div className="px-4 py-3 bg-red-950/40 border border-red-800 rounded text-red-300 text-sm">
          ❌ {error}
        </div>
      )}

      <div className="flex gap-4">
        <button
          onClick={onBack}
          className="px-6 py-3 border border-stone-700 text-stone-400 rounded hover:text-stone-200 transition-colors"
        >
          ← Indietro
        </button>
        <button
          onClick={handleContinue}
          disabled={loading || unresolvedHigh > 0 || missingRequiredInputs > 0}
          className="flex-1 py-3 bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold rounded disabled:opacity-40 transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-stone-700 border-t-stone-950 rounded-full animate-spin" />
              Formalizzazione in corso...
            </span>
          ) : (
            `Conferma e formalizza → ${
              missingRequiredInputs > 0
                ? `(${missingRequiredInputs} input mancanti)`
                : unresolvedHigh > 0
                ? `(${unresolvedHigh} HIGH da risolvere)`
                : ''
            }`
          )}
        </button>
      </div>
    </div>
  )
}

function AmbiguityCard({
  ambiguity,
  selected,
  onSelect,
}: {
  ambiguity: Ambiguity
  selected: string | undefined
  onSelect: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(ambiguity.severity === 'HIGH')
  return (
    <div className={`border rounded-lg overflow-hidden ${SEVERITY_COLORS[ambiguity.severity]}`}>
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full px-5 py-4 text-left flex items-start gap-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500">
              {SEVERITY_LABELS[ambiguity.severity]}
            </span>
            {selected && (
              <span className="text-[10px] text-green-400 font-bold">● RISOLTA</span>
            )}
          </div>
          <div className="text-stone-200 text-sm font-bold">
            &quot;{ambiguity.original_text}&quot;
          </div>
          <div className="text-stone-400 text-xs mt-1">{ambiguity.why_ambiguous}</div>
        </div>
        <span className="text-stone-600 flex-shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-3">
          <p className="text-stone-500 text-xs">
            Scegli l&apos;alternativa codificabile più vicina alla tua logica:
          </p>
          {ambiguity.alternatives.map((alt) => (
            <button
              key={alt.id}
              onClick={() => onSelect(alt.id)}
              className={`w-full text-left px-4 py-3 rounded-lg border transition-all ${
                selected === alt.id
                  ? 'border-amber-500 bg-amber-950/30'
                  : 'border-stone-700 bg-stone-900/50 hover:border-stone-500'
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`w-5 h-5 rounded-full border-2 flex-shrink-0 mt-0.5 flex items-center justify-center ${
                    selected === alt.id
                      ? 'border-amber-400 bg-amber-400'
                      : 'border-stone-600'
                  }`}
                >
                  {selected === alt.id && (
                    <span className="text-stone-950 text-xs font-bold">✓</span>
                  )}
                </span>
                <div>
                  <div className="text-stone-200 text-sm font-bold">{alt.description}</div>
                  <div className="text-stone-400 text-xs mt-1 font-mono">{alt.implementation}</div>
                  <div className="text-amber-600/80 text-xs mt-2">
                    ⚠ Compromesso: {alt.tradeoffs}
                  </div>
                </div>
              </div>
            </button>
          ))}
          {ambiguity.severity !== 'HIGH' && (
            <button
              onClick={() => onSelect('skip_' + ambiguity.id)}
              className="w-full text-left px-4 py-2 rounded border border-stone-800 text-stone-600 text-xs hover:border-stone-600 transition-colors"
            >
              → Salta: non includere questa regola nel bot
            </button>
          )}
        </div>
      )}
    </div>
  )
}
