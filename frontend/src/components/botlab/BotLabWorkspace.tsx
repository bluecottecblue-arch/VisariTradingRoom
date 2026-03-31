'use client'

import { useEffect, useMemo, useState, useRef } from 'react'
import { botLabApi, exportApi, formatError, authApi } from '@/lib/api'
import FundamentalFiltersCard from '@/components/FundamentalFiltersCard'
import { DEFAULT_FUNDAMENTAL_FILTERS } from '@/lib/fundamentals'
import { useBacktest } from '@/hooks/useBacktest'
import {
  Alert,
  CodeBlock,
  EmptyState,
  Field,
  MetricCard,
  ProgressBar,
  Section,
  Spinner,
  TabBar,
  Accordion,
  inputCls,
  textareaCls,
} from '@/components/ui'
import type {
  BacktestResult,
  BotLabAnalysisResult,
  BotLabModifyResult,
  FundamentalFilterConfig,
} from '@/types'

const ACTIONS = [
  'Analizza il bot',
  'Spiega la logica',
  'Migliora il sistema',
  'Applica le mie istruzioni',
  'Preparalo per il backtest',
  'Controlla la robustezza',
]

const PROMPT_PRESETS = [
  'aggiungi un trailing stop',
  'usa conferma RSI',
  'non tradare durante news USD ad alto impatto',
  'aggiungi filtro sessione Londra e New York',
  'trasforma lo stop loss in rischio basato su ATR',
  'rendi il bot piu conservativo',
]

const DEFAULT_BACKTEST_CONFIG = {
  provider: 'demo',
  symbol: 'EURUSD',
  timeframe: 'H1',
  initial_capital: 10000,
  date_from: '2018-01-01',
  date_in_sample_end: '2022-12-31',
  date_oos_start: '2023-01-01',
  date_to: '2024-12-31',
  spread_pips: 1.0,
  slippage_pips: 0.5,
  commission_per_lot: 7.0,
  risk_per_trade_pct: 1.0,
  run_walk_forward: true,
  run_monte_carlo: true,
  mc_simulations: 500,
  fundamental_filters: DEFAULT_FUNDAMENTAL_FILTERS as FundamentalFilterConfig,
}

export default function BotLabWorkspace() {
  const [filename, setFilename] = useState('uploaded_bot.mq5')
  const [code, setCode] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [claudeSource, setClaudeSource] = useState<'account' | 'personal'>('personal')
  const [aiProvider, setAiProvider] = useState('anthropic')
  const [claudeApiKey, setClaudeApiKey] = useState('')
  const [accountClaudeAvailable, setAccountClaudeAvailable] = useState(false)
  const [sourceOrigin, setSourceOrigin] = useState<'user' | 'visari'>('user')
  const [actionFocus, setActionFocus] = useState(ACTIONS[0])
  const [analysis, setAnalysis] = useState<BotLabAnalysisResult | null>(null)
  const [modifyResult, setModifyResult] = useState<BotLabModifyResult | null>(null)
  const [modifyPrompt, setModifyPrompt] = useState('')
  const [loadingAnalyze, setLoadingAnalyze] = useState(false)
  const [loadingModify, setLoadingModify] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [uploadToast, setUploadToast] = useState<string | null>(null)
  const [exportSaveFailed, setExportSaveFailed] = useState(false)
  const [tab, setTab] = useState<'overview' | 'code' | 'modify' | 'compare'>('overview')
  const [config, setConfig] = useState(DEFAULT_BACKTEST_CONFIG)

  const analyzeTokenRef = useRef(0)
  const modifyTokenRef = useRef(0)

  const originalBacktest = useBacktest()
  const modifiedBacktest = useBacktest()
  const modifiedVerdict = modifyResult?.session_id ? modifiedBacktest.results?.final_decision : null
  const modifiedExportBlocked = Boolean(modifiedVerdict && !modifiedVerdict.export_allowed)

  const effectiveFundamentals = config.fundamental_filters.enabled
    ? config.fundamental_filters
    : DEFAULT_FUNDAMENTAL_FILTERS

  const uiLocked = loadingAnalyze || loadingModify

  const cancelInFlightOperations = () => {
    analyzeTokenRef.current += 1
    modifyTokenRef.current += 1
    setLoadingAnalyze(false)
    setLoadingModify(false)
  }

  const resetWorkspaceState = () => {
    setAnalysis(null)
    setModifyResult(null)
    setModifyPrompt('')
    setError(null)
    setExportSaveFailed(false)
    originalBacktest.reset()
    modifiedBacktest.reset()
  }

  const compareMetrics = useMemo(() => {
    if (!originalBacktest.results || !modifiedBacktest.results) return null
    return {
      trades:
        (modifiedBacktest.results.out_of_sample.total_trades || 0) -
        (originalBacktest.results.out_of_sample.total_trades || 0),
      expectancy:
        (modifiedBacktest.results.out_of_sample.expectancy_r || 0) -
        (originalBacktest.results.out_of_sample.expectancy_r || 0),
      drawdown:
        (modifiedBacktest.results.out_of_sample.max_drawdown_pct || 0) -
        (originalBacktest.results.out_of_sample.max_drawdown_pct || 0),
      returnPct:
        (modifiedBacktest.results.out_of_sample.total_return_pct || 0) -
        (originalBacktest.results.out_of_sample.total_return_pct || 0),
    }
  }, [modifiedBacktest.results, originalBacktest.results])

  useEffect(() => {
    let cancelled = false
    authApi.me()
      .then((body) => {
        if (!cancelled) {
          const hasKey = Boolean(
             (body.ai_provider === 'openai' && body.openai_key_configured) ||
             (body.ai_provider === 'google' && body.google_key_configured) ||
             ((!body.ai_provider || body.ai_provider === 'anthropic') && body.claude_key_configured)
          )
          setAccountClaudeAvailable(hasKey)
        }
      })
      .catch(() => {
        if (!cancelled) setAccountClaudeAvailable(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!uploadToast) return
    const timeout = window.setTimeout(() => setUploadToast(null), 3000)
    return () => window.clearTimeout(timeout)
  }, [uploadToast])

  const showUploadToast = (message: string) => {
    setUploadToast(message)
  }

  const handleFileSelected = async (file?: File | null) => {
    if (!file) return
    
    const maxBytes = 2 * 1024 * 1024 // 2MB
    if (file.size === 0) {
      setError(null)
      showUploadToast('Caricamento fallito. Il file è vuoto. Usa .mq5, .txt o .py.')
      return
    }
    if (file.size > maxBytes) {
      setError(null)
      showUploadToast('Caricamento fallito. Dimensione massima 2 MB. Usa .mq5, .txt o .py.')
      return
    }
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !['mq5', 'txt', 'py'].includes(ext)) {
      setError(null)
      showUploadToast('Caricamento fallito. Formati supportati: .mq5, .txt, .py.')
      return
    }

    try {
      const text = await file.text()
      cancelInFlightOperations()
      setFilename(file.name)
      setCode(text)
      resetWorkspaceState()
    } catch {
      setError(null)
      showUploadToast('Caricamento fallito. Riprova con un file .mq5, .txt o .py.')
    }
  }

  const onDropFile = async (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragActive(false)
    if (uiLocked) return
    await handleFileSelected(event.dataTransfer.files?.[0] || null)
  }

  const buildBacktestPayload = () => ({
    ...config,
    fundamental_filters: effectiveFundamentals,
  })

  const analyze = async () => {
    if (!code.trim()) {
      setError('Carica un file o incolla il codice del bot prima di avviare l’analisi.')
      return
    }
    analyzeTokenRef.current += 1
    const currentToken = analyzeTokenRef.current
    setLoadingAnalyze(true)
    setError(null)
    setExportSaveFailed(false)
    try {
      const result = await botLabApi.upload({
        filename,
        content: code,
        source_origin: sourceOrigin,
        action_focus: actionFocus,
        fundamental_filters: effectiveFundamentals,
      }) as BotLabAnalysisResult
      if (analyzeTokenRef.current !== currentToken) return
      setAnalysis(result)
      setModifyResult(null)
      originalBacktest.reset()
      modifiedBacktest.reset()
      setTab('overview')
    } catch (e) {
      if (analyzeTokenRef.current !== currentToken) return
      setError(formatError(e))
    } finally {
      if (analyzeTokenRef.current === currentToken) {
        setLoadingAnalyze(false)
      }
    }
  }

  const modify = async () => {
    if (!analysis) {
      setError('Analizza prima il bot originale.')
      return
    }
    if (!modifyPrompt.trim()) {
      setError('Scrivi una richiesta di revisione chiara prima di generare una nuova versione.')
      return
    }
    if (claudeSource === 'account' && !accountClaudeAvailable) {
      setError('Per questo account non risulta configurata una API key. Usa la tua key personale oppure chiedi all’admin di assegnartene una.')
      return
    }
    if (claudeSource === 'personal' && !claudeApiKey.trim()) {
      setError('Inserisci la tua API key personale per usare la modifica assistita del bot.')
      return
    }
    modifyTokenRef.current += 1
    const currentToken = modifyTokenRef.current
    setLoadingModify(true)
    setError(null)
    setExportSaveFailed(false)
    try {
      const result = await botLabApi.modify({
        session_id: analysis.session_id,
        prompt: modifyPrompt,
        claude_access: {
          credential_source: claudeSource,
          api_key: claudeSource === 'personal' ? claudeApiKey : '',
          provider: claudeSource === 'personal' ? aiProvider : 'anthropic',
        },
        fundamental_filters: effectiveFundamentals,
      }) as BotLabModifyResult
      if (modifyTokenRef.current !== currentToken) return
      setModifyResult(result)
      setTab(result.status === 'VALID' ? 'compare' : 'modify')
      if (result.status === 'VALID' && result.session_id && result.modified_code && result.code_validation?.is_valid) {
        await exportApi.saveMql5(result.session_id, result.modified_code).catch(() => {
          if (modifyTokenRef.current === currentToken) {
            setExportSaveFailed(true)
          }
        })
      }
    } catch (e) {
      if (modifyTokenRef.current !== currentToken) return
      setError(formatError(e))
    } finally {
      if (modifyTokenRef.current === currentToken) {
        setLoadingModify(false)
      }
    }
  }

  const runOriginalBacktest = () => {
    if (!analysis?.backtest_ready) {
      setError('Il parser locale non considera questo bot abbastanza interpretabile per un backtest proxy credibile.')
      return
    }
    originalBacktest.run(analysis.session_id, buildBacktestPayload())
  }

  const runModifiedBacktest = () => {
    if (!modifyResult?.session_id || modifyResult.status !== 'VALID') {
      setError('Genera prima una versione rivista valida.')
      return
    }
    modifiedBacktest.run(modifyResult.session_id, buildBacktestPayload())
  }

  const codeLineCount = code.split('\n').filter((line) => line.trim()).length
  const previewSnippet = code
    .split('\n')
    .slice(0, 12)
    .join('\n')

  return (
    <div className="space-y-8">
      {uploadToast && (
        <div className="fixed right-6 top-20 z-50 border border-rose-900/70 bg-slate-950/95 px-4 py-3 text-sm text-slate-100 shadow-2xl">
          {uploadToast}
        </div>
      )}

      <section className="relative overflow-hidden border border-slate-800/90 bg-[linear-gradient(135deg,rgba(8,47,73,0.22),rgba(15,23,42,0.84)_32%,rgba(2,6,23,0.97))] px-6 py-8 lg:px-8 lg:py-9">
        <div className="absolute inset-y-0 right-0 hidden w-1/3 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.16),transparent_55%)] lg:block" />
        <div className="relative space-y-5">
          <div>
            <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Bot Lab</div>
            <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-50 lg:text-5xl">
              Analizza, migliora e governa algoritmi MT5 esistenti
            </h1>
          </div>

          <div className="flex flex-wrap gap-3 text-[11px] uppercase tracking-[0.16em] text-slate-500">
            <span className="border border-slate-800 px-3 py-1.5">Analisi locale del codice</span>
            <span className="border border-slate-800 px-3 py-1.5">Revisioni strutturate</span>
            <span className="border border-slate-800 px-3 py-1.5">Pronto per review e backtest</span>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="space-y-6">
          <Section title="Carica bot">
            <div
              onDragOver={(event) => {
                event.preventDefault()
                if (uiLocked) return
                setDragActive(true)
              }}
              onDragLeave={() => {
                if (uiLocked) return
                setDragActive(false)
              }}
              onDrop={onDropFile}
              className={`border border-dashed px-5 py-8 transition-colors ${
                dragActive ? 'border-cyan-700/80 bg-cyan-950/10' : 'border-slate-800 bg-slate-950/45'
              }`}
            >
              <div className="text-lg font-semibold text-slate-50">Carica o trascina un file bot</div>
              <div className="mt-5">
                <input
                  type="file"
                  accept=".mq5,.txt,.py"
                  aria-label="Carica file bot"
                  onChange={(e) => handleFileSelected(e.target.files?.[0] || null)}
                  disabled={uiLocked}
                  className="block w-full text-sm text-slate-400 file:mr-4 file:border file:border-slate-700 file:bg-slate-900 file:px-4 file:py-2 file:text-slate-200 disabled:opacity-50"
                />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Nome file">
                <input
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  disabled={uiLocked}
                  className={inputCls}
                  placeholder="expert_advisor.mq5"
                />
              </Field>
              <Field label="Origine bot">
                <div className="flex gap-2">
                  {[
                    { id: 'user' as const, label: 'Bot del trader' },
                    { id: 'visari' as const, label: 'Creato da Visari' },
                  ].map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => setSourceOrigin(option.id)}
                      disabled={uiLocked}
                      className={`flex-1 border px-3 py-3 text-sm font-semibold transition-colors disabled:opacity-50 ${
                        sourceOrigin === option.id
                          ? 'border-cyan-900/70 bg-cyan-950/10 text-cyan-300'
                          : 'border-slate-800 bg-slate-950/50 text-slate-400 hover:border-slate-600'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </Field>
            </div>
            <Field label="Oppure incolla il codice">
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                disabled={uiLocked}
                className={`${textareaCls} h-64`}
                placeholder="Incolla qui il codice del bot..."
              />
            </Field>
            <Field label="Obiettivo">
              <select value={actionFocus} onChange={(e) => setActionFocus(e.target.value)} disabled={uiLocked} className={inputCls}>
                {ACTIONS.map((action) => (
                  <option key={action} value={action}>{action}</option>
                ))}
              </select>
            </Field>
            <div className="flex gap-3">
              <button
                onClick={analyze}
                disabled={loadingAnalyze || loadingModify}
                className="flex-1 border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 transition-all duration-200 hover:-translate-y-0.5 hover:bg-white hover:shadow-[0_10px_28px_rgba(255,255,255,0.08)] disabled:opacity-50"
              >
                {loadingAnalyze ? 'Analisi in corso...' : 'Analizza'}
              </button>
              <button
                onClick={() => {
                  cancelInFlightOperations()
                  setFilename('uploaded_bot.mq5')
                  setCode('')
                  resetWorkspaceState()
                }}
                className="border border-slate-800 px-4 py-3 text-slate-300"
              >
                Pulisci
              </button>
            </div>
          </Section>

          <div className="mt-8 border-t border-slate-800/80 pt-6">
            <Accordion title="Configurazione avanzata" defaultOpen={false}>
              <div className="space-y-8 py-2">
                <FundamentalFiltersCard
                  value={config.fundamental_filters}
                  onChange={(next) => setConfig((current) => ({ ...current, fundamental_filters: next }))}
                />

                <div className="space-y-4 border border-slate-800/40 bg-slate-950/20 p-5">
                  <div className="text-sm font-semibold text-slate-200 uppercase tracking-widest text-[11px]">Ambiente backtest</div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Field label="Provider dati">
                      <select
                        value={config.provider}
                        onChange={(e) => setConfig((c) => ({ ...c, provider: e.target.value }))}
                        className={inputCls}
                      >
                        <option value="demo">demo</option>
                        <option value="polygon">polygon</option>
                        <option value="dukascopy">dukascopy</option>
                      </select>
                    </Field>
                    <Field label="Simbolo">
                      <input value={config.symbol} onChange={(e) => setConfig((c) => ({ ...c, symbol: e.target.value }))} className={inputCls} />
                    </Field>
                    <Field label="Timeframe">
                      <select value={config.timeframe} onChange={(e) => setConfig((c) => ({ ...c, timeframe: e.target.value }))} className={inputCls}>
                        {['M15', 'M30', 'H1', 'H4', 'D1'].map((tf) => (
                          <option key={tf}>{tf}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Capitale">
                      <input type="number" value={config.initial_capital} onChange={(e) => setConfig((c) => ({ ...c, initial_capital: Number(e.target.value) }))} className={inputCls} />
                    </Field>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Field label="Data inizio">
                      <input type="date" value={config.date_from} onChange={(e) => setConfig((c) => ({ ...c, date_from: e.target.value }))} className={inputCls} />
                    </Field>
                    <Field label="Fine IS">
                      <input type="date" value={config.date_in_sample_end} onChange={(e) => setConfig((c) => ({ ...c, date_in_sample_end: e.target.value }))} className={inputCls} />
                    </Field>
                    <Field label="Inizio OOS">
                      <input type="date" value={config.date_oos_start} onChange={(e) => setConfig((c) => ({ ...c, date_oos_start: e.target.value }))} className={inputCls} />
                    </Field>
                    <Field label="Data fine">
                      <input type="date" value={config.date_to} onChange={(e) => setConfig((c) => ({ ...c, date_to: e.target.value }))} className={inputCls} />
                    </Field>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <Field label="Spread">
                      <input type="number" step={0.1} value={config.spread_pips} onChange={(e) => setConfig((c) => ({ ...c, spread_pips: Number(e.target.value) }))} className={inputCls} />
                    </Field>
                    <Field label="Slippage">
                      <input type="number" step={0.1} value={config.slippage_pips} onChange={(e) => setConfig((c) => ({ ...c, slippage_pips: Number(e.target.value) }))} className={inputCls} />
                    </Field>
                    <Field label="Rischio %">
                      <input type="number" step={0.1} value={config.risk_per_trade_pct} onChange={(e) => setConfig((c) => ({ ...c, risk_per_trade_pct: Number(e.target.value) }))} className={inputCls} />
                    </Field>
                  </div>
                </div>
              </div>
            </Accordion>
          </div>
        </div>

        <div className="space-y-6">
          <section className="space-y-4 border border-slate-800/90 bg-slate-950/70 px-5 py-5">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Chiave AI</div>
              <span className="border border-slate-800 px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                {claudeSource === 'account'
                  ? accountClaudeAvailable
                    ? 'assegnata'
                    : 'non assegnata'
                  : 'personale'}
              </span>
            </div>
            <div className="text-xs text-slate-500">
              Usa la chiave assegnata al tuo account, altrimenti inserisci una chiave personale.
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <button
                type="button"
                onClick={() => accountClaudeAvailable && setClaudeSource('account')}
                disabled={!accountClaudeAvailable}
                className={`border px-4 py-4 text-left transition-colors ${
                  claudeSource === 'account'
                    ? 'border-cyan-900/70 bg-cyan-950/10 text-slate-100'
                    : 'border-slate-800 bg-transparent text-slate-400 hover:border-slate-700 hover:text-slate-100'
                } ${!accountClaudeAvailable ? 'cursor-not-allowed opacity-50' : ''}`}
              >
                <div className="text-sm font-medium">Chiave account</div>
              </button>
              <button
                type="button"
                onClick={() => setClaudeSource('personal')}
                className={`border px-4 py-4 text-left transition-colors ${
                  claudeSource === 'personal'
                    ? 'border-cyan-900/70 bg-cyan-950/10 text-slate-100'
                    : 'border-slate-800 bg-transparent text-slate-400 hover:border-slate-700 hover:text-slate-100'
                }`}
              >
                <div className="text-sm font-medium">Chiave personale</div>
              </button>
            </div>
            {claudeSource === 'personal' && (
              <div className="grid gap-4 md:grid-cols-2">
                <select
                  value={aiProvider}
                  onChange={(e) => setAiProvider(e.target.value)}
                  className={inputCls}
                >
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="openai">OpenAI (GPT-4o)</option>
                  <option value="google">Google (Gemini)</option>
                </select>
                <input
                  type="password"
                  value={claudeApiKey}
                  onChange={(e) => setClaudeApiKey(e.target.value)}
                  className={inputCls}
                  placeholder={aiProvider === 'openai' ? 'sk-proj-...' : aiProvider === 'google' ? 'AIza...' : 'sk-ant-...'}
                />
              </div>
            )}
          </section>

          <Section title="Anteprima desk">
            <div className="space-y-4 border border-slate-800/90 bg-slate-950/70 px-5 py-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">File corrente</div>
                  <div className="mt-2 text-lg font-semibold text-slate-50">{filename || 'Nessun file selezionato'}</div>
                </div>
                <span className="border border-slate-800 px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                  {analysis ? analysis.file_info.language : 'in attesa'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="border border-slate-900 bg-slate-950/60 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-slate-600">Righe</div>
                  <div className="mt-2 text-xl font-semibold text-slate-50">{codeLineCount || 0}</div>
                </div>
                <div className="border border-slate-900 bg-slate-950/60 px-4 py-3">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-slate-600">Obiettivo</div>
                  <div className="mt-2 text-sm font-semibold text-slate-50">{actionFocus}</div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Anteprima</div>
                <div className="border border-slate-900 bg-slate-950 px-4 py-4 text-xs leading-relaxed text-slate-400">
                  <pre className="overflow-x-auto whitespace-pre-wrap break-words">{previewSnippet || 'Nessun codice caricato.'}</pre>
                </div>
              </div>

              <ul className="list-disc space-y-2 pl-5 text-sm text-slate-400 marker:text-slate-600">
                <li>Controllo salute bot</li>
                <li>Spiegazione chiara</li>
                <li>Flusso di revisione controllato</li>
                <li>Confronto tra logica originale e rivista</li>
                <li>Backtest prima dell’export</li>
              </ul>
            </div>
          </Section>

          {loadingAnalyze && (
            <div className="border border-slate-800 bg-slate-950/70 p-6">
                  <Spinner label="Analisi locale in corso..." />
                </div>
              )}

          {error && <Alert type="error">{error}</Alert>}
        </div>
      </div>

      {analysis && (
            <div className="space-y-6">
          <TabBar
            tabs={[
              { id: 'overview', label: 'Panoramica' },
              { id: 'code', label: 'Codice' },
              { id: 'modify', label: 'Migliora' },
              { id: 'compare', label: 'Confronta' },
            ]}
            active={tab}
            onChange={setTab}
          />

          {tab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard label="Linguaggio" value={analysis.file_info.language} />
                <MetricCard label="Piattaforma" value={analysis.file_info.platform} />
                <MetricCard label="LOC" value={analysis.file_info.line_count} />
                <MetricCard label="Punteggio salute" value={`${analysis.health_check.score}/100`} />
              </div>

              <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-slate-200 font-semibold text-sm">Spiegami il bot</div>
                  <div className="text-xs text-cyan-300">analisi locale, nessuna spesa Claude</div>
                </div>
                <div className="text-sm text-slate-400">{analysis.explanation.plain_language}</div>
                <ProgressBar value={analysis.health_check.score} max={100} label="Controllo salute bot" />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                  <div className="text-slate-200 font-semibold text-sm">Logica di trading rilevata</div>
                  {analysis.bot_profile.entry_logic.map((item, index) => (
                    <div key={index} className="text-xs text-slate-400">• {item}</div>
                  ))}
                  {analysis.bot_profile.exit_logic.map((item, index) => (
                    <div key={`exit-${index}`} className="text-xs text-slate-400">• {item}</div>
                  ))}
                </div>
                <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                  <div className="text-slate-200 font-semibold text-sm">Debolezze probabili</div>
                  {(analysis.health_check.likely_issues.length ? analysis.health_check.likely_issues : analysis.health_check.warnings).map((item, index) => (
                    <div key={index} className="text-xs text-amber-300">• {item}</div>
                  ))}
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={runOriginalBacktest}
                  disabled={originalBacktest.isRunning}
                  className="border border-cyan-800/70 bg-cyan-400/90 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
                >
                  Esegui backtest
                </button>
                <button
                  onClick={() => setTab('modify')}
                  className="border border-slate-800 px-4 py-3 text-slate-300"
                >
                  Migliora bot
                </button>
              </div>

              {originalBacktest.isRunning && (
                <div className="border border-slate-800 bg-slate-950/70 p-6">
                  <Spinner label={originalBacktest.phaseLabel} />
                </div>
              )}

              {originalBacktest.results && <BacktestMiniSummary title="Backtest bot originale" results={originalBacktest.results} />}
            </div>
          )}

          {tab === 'code' && (
            <CodeBlock code={code} language={analysis.file_info.language.toUpperCase()} maxHeight="36rem" />
          )}

          {tab === 'modify' && (
            <div className="space-y-5">
              <Section title="Richiesta revisione">
                <Field label="Prompt modifica">
                  <textarea
                    value={modifyPrompt}
                    onChange={(e) => setModifyPrompt(e.target.value)}
                    className={`${textareaCls} h-28`}
                    placeholder="Esempio: aggiungi trailing stop, richiedi conferma RSI e non tradare 30 minuti prima o dopo news USD ad alto impatto."
                  />
                </Field>
                <div className="flex flex-wrap gap-2">
                  {PROMPT_PRESETS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setModifyPrompt(preset)}
                      className="border border-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-600"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
                <Alert type="info" title="Pipeline revisione strutturata">
                  Bot originale → parse locale → validazione prompt → revisione mirata → nuova analisi locale → confronto versione vecchia vs aggiornata.
                </Alert>
                <button
                  onClick={modify}
                  disabled={loadingAnalyze || loadingModify}
                  className="border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 transition-all duration-200 hover:-translate-y-0.5 hover:bg-white hover:shadow-[0_10px_28px_rgba(255,255,255,0.08)] disabled:opacity-50"
                >
                  {loadingModify ? 'Costruzione versione rivista...' : 'Migliora bot'}
                </button>
              </Section>

              {loadingModify && (
                <div className="border border-slate-800 bg-slate-950/70 p-6">
                  <Spinner label="Claude sta applicando la revisione approvata..." />
                </div>
              )}

              {modifyResult && modifyResult.status !== 'VALID' && (
                <Alert type="error" title="Revisione bloccata">
                  {(modifyResult.ambiguities || []).join(' · ') || modifyResult.message}
                </Alert>
              )}

              {modifyResult?.status === 'VALID' && (
                <div className="space-y-4">
                  <Alert type="success" title="Versione rivista pronta">
                    {modifyResult.message}
                  </Alert>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                      <div className="text-slate-200 font-semibold text-sm">Riepilogo modifiche</div>
                      {(modifyResult.change_summary || []).map((item, index) => (
                        <div key={index} className="text-xs text-slate-400">• {item}</div>
                      ))}
                    </div>
                    <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                      <div className="text-slate-200 font-semibold text-sm">Diff concettuale</div>
                      {(modifyResult.conceptual_diff || []).map((item, index) => (
                        <div key={index} className="text-xs text-slate-400">• {item}</div>
                      ))}
                    </div>
                  </div>

                  {modifyResult.modified_code && (
                    <CodeBlock code={modifyResult.modified_code} language={analysis.file_info.language.toUpperCase()} maxHeight="32rem" />
                  )}

                  {exportSaveFailed && (
                    <Alert type="warning" title="Salvataggio parziale fallito">
                      La logica modificata è stata generata correttamente, ma il salvataggio nella cartella sicura di export è fallito. Potresti non riuscire a scaricare subito il `.mq5`.
                    </Alert>
                  )}

                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={runModifiedBacktest}
                      disabled={modifiedBacktest.isRunning || !modifyResult.session_id}
                      className="border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
                    >
                      Esegui backtest rivisto
                    </button>
                    <button
                      onClick={() => {
                        if (!modifyResult.session_id) return
                        const anchor = document.createElement('a')
                        anchor.href = exportApi.downloadMql5Url(modifyResult.session_id)
                        anchor.download = `VisariTradingRoom_${modifyResult.session_id.slice(0, 8)}.mq5`
                        document.body.appendChild(anchor)
                        anchor.click()
                        document.body.removeChild(anchor)
                      }}
                      disabled={!modifyResult.session_id || !modifyResult.code_validation?.is_valid || modifiedExportBlocked}
                      className="border border-slate-800 px-4 py-3 text-slate-300 disabled:opacity-40"
                    >
                      Scarica bot rivisto
                    </button>
                    <button
                      onClick={() => {
                        if (!modifyResult.session_id) return
                        const anchor = document.createElement('a')
                        anchor.href = exportApi.bundleSetupUrl(modifyResult.session_id)
                        document.body.appendChild(anchor)
                        anchor.click()
                        document.body.removeChild(anchor)
                      }}
                      disabled={!modifyResult.session_id || !modifyResult.code_validation?.is_valid || modifiedExportBlocked}
                      className="border border-slate-800 px-4 py-3 text-slate-300 disabled:opacity-40"
                    >
                      Scarica guida setup
                    </button>
                  </div>

                  {modifiedBacktest.isRunning && (
                    <div className="border border-slate-800 bg-slate-950/70 p-6">
                      <Spinner label={modifiedBacktest.phaseLabel} />
                    </div>
                  )}

                  {modifiedBacktest.results && <BacktestMiniSummary title="Backtest bot rivisto" results={modifiedBacktest.results} />}
                  {modifiedExportBlocked && (
                    <Alert type="warning" title="Export bloccato dal verdetto di validazione">
                      {(modifiedVerdict?.blockers || modifiedVerdict?.reasons || []).join(' · ') || 'La versione rivista non è stata promossa.'}
                    </Alert>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === 'compare' && (
            <div className="space-y-6">
              {!modifyResult?.modified_analysis && (
                <EmptyState
                  icon="COMPARE"
                  title="Vista confronto non ancora disponibile"
                  description="Genera prima una versione rivista per ispezionare le differenze logiche e confrontare le performance."
                />
              )}

              {modifyResult?.modified_analysis && (
                <>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                      <div className="text-slate-200 font-semibold text-sm">Originale</div>
                      <div className="text-xs text-slate-400">stile: {analysis.bot_profile.strategy_style}</div>
                      <div className="text-xs text-slate-400">protezioni: {analysis.code_summary.protections.join(', ') || 'n/d'}</div>
                      <div className="text-xs text-slate-400">indicatori: {analysis.code_summary.indicators.map((item) => item.type).join(', ') || 'n/d'}</div>
                    </div>
                    <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                      <div className="text-slate-200 font-semibold text-sm">Rivisto</div>
                      <div className="text-xs text-slate-400">stile: {modifyResult.modified_analysis.bot_profile.strategy_style}</div>
                      <div className="text-xs text-slate-400">protezioni: {modifyResult.modified_analysis.code_summary.protections.join(', ') || 'n/d'}</div>
                      <div className="text-xs text-slate-400">indicatori: {modifyResult.modified_analysis.code_summary.indicators.map((item) => item.type).join(', ') || 'n/d'}</div>
                    </div>
                  </div>

                  {modifyResult.compare && (
                    <div className="border border-slate-800 bg-slate-950/70 p-4 space-y-2">
                      <div className="text-slate-200 font-semibold text-sm">Diff concettuale</div>
                      <div className="text-xs text-slate-400">Nuovi indicatori: {modifyResult.compare.new_indicators.join(', ') || 'nessuno'}</div>
                      <div className="text-xs text-slate-400">Nuove protezioni: {modifyResult.compare.new_protections.join(', ') || 'nessuna'}</div>
                      <div className="text-xs text-slate-400">Delta parametri: {modifyResult.compare.parameter_count_delta}</div>
                      <div className="text-xs text-slate-400">Filtro fondamentale aggiunto: {modifyResult.compare.fundamental_filter_added ? 'sì' : 'no'}</div>
                    </div>
                  )}

                  {originalBacktest.results && modifiedBacktest.results && compareMetrics && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <MetricCard label="Δ trade OOS" value={compareMetrics.trades} colorClass={compareMetrics.trades < 0 ? 'text-amber-400' : 'text-green-400'} />
                      <MetricCard label="Δ expectancy R" value={compareMetrics.expectancy.toFixed(2)} colorClass={compareMetrics.expectancy >= 0 ? 'text-green-400' : 'text-red-400'} />
                      <MetricCard label="Δ rendimento %" value={compareMetrics.returnPct.toFixed(2)} colorClass={compareMetrics.returnPct >= 0 ? 'text-green-400' : 'text-red-400'} />
                      <MetricCard label="Δ max DD %" value={compareMetrics.drawdown.toFixed(2)} colorClass={compareMetrics.drawdown <= 0 ? 'text-green-400' : 'text-red-400'} />
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function BacktestMiniSummary({ title, results }: { title: string; results: BacktestResult }) {
  const oos = results.out_of_sample
  const decision = results.final_decision
  const calendarContext = results.data_info?.calendar_context
  return (
    <div className="space-y-3 rounded border border-stone-800 bg-stone-900/70 p-4">
      <div className="flex items-center justify-between">
        <div className="text-stone-300 font-bold text-sm">{title}</div>
        <div className="text-xs text-stone-500">{decision.verdict}</div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Trade OOS" value={oos.total_trades} />
        <MetricCard label="Expectancy R" value={oos.expectancy_r?.toFixed(2)} colorClass={(oos.expectancy_r || 0) >= 0 ? 'text-green-400' : 'text-red-400'} />
        <MetricCard label="Rendimento %" value={oos.total_return_pct?.toFixed(2)} colorClass={(oos.total_return_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'} />
        <MetricCard label="Max DD %" value={oos.max_drawdown_pct?.toFixed(2)} colorClass={(oos.max_drawdown_pct || 0) <= 10 ? 'text-green-400' : 'text-red-400'} />
      </div>
      <div className="text-xs text-stone-400">
        {decision.reasons.slice(0, 2).join(' · ')}
      </div>
      {calendarContext?.provider && calendarContext.provider !== 'none' && (
        <div className="text-xs text-stone-500">
          Provider news: {calendarContext.provider}
          {typeof calendarContext.events_used === 'number' ? ` · eventi ${calendarContext.events_used}` : ''}
        </div>
      )}
      {(calendarContext?.warnings || []).length > 0 && (
        <div className="text-xs text-amber-300">
          {(calendarContext?.warnings || []).slice(0, 1).join('')}
        </div>
      )}
    </div>
  )
}
