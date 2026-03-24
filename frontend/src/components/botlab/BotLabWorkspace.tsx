'use client'

import { useMemo, useState } from 'react'
import { botLabApi, exportApi, formatError } from '@/lib/api'
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
  'Spiegami come funziona',
  'Miglioralo',
  'Modificalo secondo istruzioni',
  'Backtestalo',
  'Verifica se è robusto o fragile',
]

const PROMPT_PRESETS = [
  'aggiungi trailing stop',
  'usa conferma RSI',
  'non tradare durante news ad alto impatto su USD',
  'aggiungi filtro sessione Londra/New York',
  'trasforma stop loss in ATR-based',
  'ottimizza il bot per essere più conservativo',
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
  const [claudeApiKey, setClaudeApiKey] = useState('')
  const [sourceOrigin, setSourceOrigin] = useState<'user' | 'visari'>('user')
  const [actionFocus, setActionFocus] = useState(ACTIONS[0])
  const [analysis, setAnalysis] = useState<BotLabAnalysisResult | null>(null)
  const [modifyResult, setModifyResult] = useState<BotLabModifyResult | null>(null)
  const [modifyPrompt, setModifyPrompt] = useState('')
  const [loadingAnalyze, setLoadingAnalyze] = useState(false)
  const [loadingModify, setLoadingModify] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'overview' | 'code' | 'modify' | 'compare'>('overview')
  const [config, setConfig] = useState(DEFAULT_BACKTEST_CONFIG)
  const originalBacktest = useBacktest()
  const modifiedBacktest = useBacktest()
  const modifiedVerdict = modifyResult?.session_id ? modifiedBacktest.results?.final_decision : null
  const modifiedExportBlocked = Boolean(modifiedVerdict && !modifiedVerdict.export_allowed)

  const effectiveFundamentals = config.fundamental_filters.enabled
    ? config.fundamental_filters
    : DEFAULT_FUNDAMENTAL_FILTERS

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

  const handleFileSelected = async (file?: File | null) => {
    if (!file) return
    const text = await file.text()
    setFilename(file.name)
    setCode(text)
    setError(null)
  }

  const buildBacktestPayload = () => ({
    ...config,
    fundamental_filters: effectiveFundamentals,
  })

  const analyze = async () => {
    if (!code.trim()) {
      setError('Carica un file o incolla il codice del bot prima di analizzarlo.')
      return
    }
    setLoadingAnalyze(true)
    setError(null)
    try {
      const result = await botLabApi.upload({
        filename,
        content: code,
        source_origin: sourceOrigin,
        action_focus: actionFocus,
        fundamental_filters: effectiveFundamentals,
      }) as BotLabAnalysisResult
      setAnalysis(result)
      setModifyResult(null)
      originalBacktest.reset()
      modifiedBacktest.reset()
      setTab('overview')
    } catch (e) {
      setError(formatError(e))
    } finally {
      setLoadingAnalyze(false)
    }
  }

  const modify = async () => {
    if (!analysis) {
      setError('Analizza prima il bot originale.')
      return
    }
    if (!modifyPrompt.trim()) {
      setError('Scrivi una richiesta di modifica prima di generare una nuova versione.')
      return
    }
    if (!claudeApiKey.trim()) {
      setError('Inserisci la tua Claude API key personale per usare la modifica assistita del bot.')
      return
    }
    setLoadingModify(true)
    setError(null)
    try {
      const result = await botLabApi.modify({
        session_id: analysis.session_id,
        prompt: modifyPrompt,
        claude_access: {
          credential_source: 'personal',
          api_key: claudeApiKey,
        },
        fundamental_filters: effectiveFundamentals,
      }) as BotLabModifyResult
      setModifyResult(result)
      setTab(result.status === 'VALID' ? 'compare' : 'modify')
      if (result.status === 'VALID' && result.session_id && result.modified_code && result.code_validation?.is_valid) {
        await exportApi.saveMql5(result.session_id, result.modified_code).catch(() => null)
      }
    } catch (e) {
      setError(formatError(e))
    } finally {
      setLoadingModify(false)
    }
  }

  const runOriginalBacktest = () => {
    if (!analysis?.backtest_ready) {
      setError('Il parser locale non ritiene il bot abbastanza interpretabile per un backtest proxy credibile.')
      return
    }
    originalBacktest.run(analysis.session_id, buildBacktestPayload())
  }

  const runModifiedBacktest = () => {
    if (!modifyResult?.session_id || modifyResult.status !== 'VALID') {
      setError('Serve prima una versione modificata valida.')
      return
    }
    modifiedBacktest.run(modifyResult.session_id, buildBacktestPayload())
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="mb-2 text-3xl font-semibold text-slate-50">Bot Lab</h1>
        <p className="text-sm leading-relaxed text-slate-400">
          Carica un bot già esistente, analizzalo localmente, chiedi modifiche in linguaggio naturale,
          attiva filtri fondamentali/news e confronta originale vs nuova versione prima dell’export.
        </p>
      </div>

      <Section title="Claude API key personale">
        <div className="space-y-3">
          <div className="text-xs text-slate-500">
            L’analisi del bot è locale. La tua Claude API key personale serve solo quando chiedi modifiche assistite del codice.
          </div>
          <input
            type="password"
            value={claudeApiKey}
            onChange={(e) => setClaudeApiKey(e.target.value)}
            className={inputCls}
            placeholder="sk-ant-..."
          />
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.9fr]">
        <div className="space-y-6">
          <Section title="1. Carica il bot">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Nome file">
                <input
                  value={filename}
                  onChange={(e) => setFilename(e.target.value)}
                  className={inputCls}
                  placeholder="expert_advisor.mq5"
                />
              </Field>
              <Field label="Origine del bot">
                <div className="flex gap-2">
                  {[
                    { id: 'user' as const, label: 'Creato dal trader' },
                    { id: 'visari' as const, label: 'Creato da Visari' },
                  ].map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => setSourceOrigin(option.id)}
                      className={`flex-1 rounded border px-3 py-2 text-sm font-bold transition-colors ${
                        sourceOrigin === option.id
                          ? 'border-amber-500 bg-amber-950/30 text-amber-300'
                          : 'border-stone-700 bg-stone-900 text-stone-400 hover:border-stone-500'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </Field>
            </div>
            <Field label="Upload file">
              <input
                type="file"
                accept=".mq5,.txt,.py"
                onChange={(e) => handleFileSelected(e.target.files?.[0] || null)}
                className="block w-full text-sm text-stone-400"
              />
            </Field>
            <Field label="Oppure incolla il codice">
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className={`${textareaCls} h-64`}
                placeholder="Incolla qui il codice del bot..."
              />
            </Field>
            <Field label="Cosa vuoi fare">
              <select value={actionFocus} onChange={(e) => setActionFocus(e.target.value)} className={inputCls}>
                {ACTIONS.map((action) => (
                  <option key={action} value={action}>{action}</option>
                ))}
              </select>
            </Field>
            <div className="flex gap-3">
              <button
                onClick={analyze}
                disabled={loadingAnalyze}
                className="flex-1 border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
              >
                {loadingAnalyze ? 'Analisi locale in corso...' : 'Analizza il bot'}
              </button>
              <button
                onClick={() => {
                  setFilename('uploaded_bot.mq5')
                  setCode('')
                  setAnalysis(null)
                  setModifyResult(null)
                  setModifyPrompt('')
                  originalBacktest.reset()
                  modifiedBacktest.reset()
                  setError(null)
                }}
                className="border border-slate-800 px-4 py-3 text-slate-300"
              >
                Reset
              </button>
            </div>
          </Section>

          <FundamentalFiltersCard
            value={config.fundamental_filters}
            onChange={(next) => setConfig((current) => ({ ...current, fundamental_filters: next }))}
          />

          <Section title="2. Configura backtest / validation">
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
              <Field label="IS fine">
                <input type="date" value={config.date_in_sample_end} onChange={(e) => setConfig((c) => ({ ...c, date_in_sample_end: e.target.value }))} className={inputCls} />
              </Field>
              <Field label="OOS inizio">
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
              <Field label="Risk %">
                <input type="number" step={0.1} value={config.risk_per_trade_pct} onChange={(e) => setConfig((c) => ({ ...c, risk_per_trade_pct: Number(e.target.value) }))} className={inputCls} />
              </Field>
            </div>
          </Section>
        </div>

        <div className="space-y-6">
          <Section title="Feature appetibili per trader retail seri">
            <div className="space-y-2 text-sm text-stone-300">
              <div>• Bot Health Check</div>
              <div>• Explain my bot</div>
              <div>• Conservative mode / aggressive mode</div>
              <div>• News-safe mode</div>
              <div>• Compare original vs modified</div>
            </div>
          </Section>

          {!analysis && !loadingAnalyze && (
            <EmptyState
              icon="🧪"
              title="Bot Lab pronto"
              description="Carica un file .mq5/.txt/.py o incolla il codice. L’analisi iniziale è locale e non spende token."
            />
          )}

          {loadingAnalyze && (
            <div className="rounded border border-stone-800 bg-stone-900/70 p-6">
              <Spinner label="Analisi locale del bot in corso..." />
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
              { id: 'modify', label: 'Modifica' },
              { id: 'compare', label: 'Confronto' },
            ]}
            active={tab}
            onChange={setTab}
          />

          {tab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard label="Language" value={analysis.file_info.language} />
                <MetricCard label="Platform" value={analysis.file_info.platform} />
                <MetricCard label="LOC" value={analysis.file_info.line_count} />
                <MetricCard label="Health score" value={`${analysis.health_check.score}/100`} />
              </div>

              <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-stone-300 font-bold text-sm">Explain my bot</div>
                  <div className="text-xs text-emerald-300">analisi locale, token saved</div>
                </div>
                <div className="text-sm text-stone-400">{analysis.explanation.plain_language}</div>
                <ProgressBar value={analysis.health_check.score} max={100} label="Bot Health Check" />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-2">
                  <div className="text-stone-300 font-bold text-sm">Logica inferita</div>
                  {analysis.bot_profile.entry_logic.map((item, index) => (
                    <div key={index} className="text-xs text-stone-400">• {item}</div>
                  ))}
                  {analysis.bot_profile.exit_logic.map((item, index) => (
                    <div key={`exit-${index}`} className="text-xs text-stone-400">• {item}</div>
                  ))}
                </div>
                <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-2">
                  <div className="text-stone-300 font-bold text-sm">Likely issues</div>
                  {(analysis.health_check.likely_issues.length ? analysis.health_check.likely_issues : analysis.health_check.warnings).map((item, index) => (
                    <div key={index} className="text-xs text-amber-300">• {item}</div>
                  ))}
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={runOriginalBacktest}
                  disabled={originalBacktest.isRunning}
                  className="rounded bg-amber-500 px-4 py-3 font-bold text-stone-950 disabled:opacity-50"
                >
                  Backtest originale
                </button>
                <button
                  onClick={() => setTab('modify')}
                  className="rounded border border-stone-700 px-4 py-3 text-stone-300"
                >
                  Modifica via prompt
                </button>
              </div>

              {originalBacktest.isRunning && (
                <div className="rounded border border-stone-800 bg-stone-900/70 p-6">
                  <Spinner label={originalBacktest.phaseLabel} />
                </div>
              )}

              {originalBacktest.results && <BacktestMiniSummary title="Backtest originale" results={originalBacktest.results} />}
            </div>
          )}

          {tab === 'code' && (
            <CodeBlock code={code} language={analysis.file_info.language.toUpperCase()} maxHeight="36rem" />
          )}

          {tab === 'modify' && (
            <div className="space-y-5">
              <Section title="Richiesta di modifica">
                <Field label="Prompt di modifica">
                  <textarea
                    value={modifyPrompt}
                    onChange={(e) => setModifyPrompt(e.target.value)}
                    className={`${textareaCls} h-28`}
                    placeholder="Es. aggiungi trailing stop, usa conferma RSI e non tradare 30 minuti prima e dopo news rosse su USD"
                  />
                </Field>
                <div className="flex flex-wrap gap-2">
                  {PROMPT_PRESETS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setModifyPrompt(preset)}
                      className="rounded border border-stone-700 px-3 py-1.5 text-xs text-stone-300 hover:border-stone-500"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
                <Alert type="info" title="Pipeline modifica seria">
                  Original bot → parse locale → validazione prompt → modifica mirata → re-analisi locale → compare old/new.
                </Alert>
                <button
                  onClick={modify}
                  disabled={loadingModify}
                  className="border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
                >
                  {loadingModify ? 'Modifica in corso...' : 'Genera versione modificata'}
                </button>
              </Section>

              {loadingModify && (
                <div className="rounded border border-stone-800 bg-stone-900/70 p-6">
                  <Spinner label="Claude sta applicando la modifica dopo validazione locale..." />
                </div>
              )}

              {modifyResult && modifyResult.status !== 'VALID' && (
                <Alert type="error" title="Richiesta bloccata">
                  {(modifyResult.ambiguities || []).join(' · ') || modifyResult.message}
                </Alert>
              )}

              {modifyResult?.status === 'VALID' && (
                <div className="space-y-4">
                  <Alert type="success" title="Versione modificata pronta">
                    {modifyResult.message}
                  </Alert>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-2">
                      <div className="text-stone-300 font-bold text-sm">Change summary</div>
                      {(modifyResult.change_summary || []).map((item, index) => (
                        <div key={index} className="text-xs text-stone-400">• {item}</div>
                      ))}
                    </div>
                    <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-2">
                      <div className="text-stone-300 font-bold text-sm">Conceptual diff</div>
                      {(modifyResult.conceptual_diff || []).map((item, index) => (
                        <div key={index} className="text-xs text-stone-400">• {item}</div>
                      ))}
                    </div>
                  </div>

                  {modifyResult.modified_code && (
                    <CodeBlock code={modifyResult.modified_code} language={analysis.file_info.language.toUpperCase()} maxHeight="32rem" />
                  )}

                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={runModifiedBacktest}
                      disabled={modifiedBacktest.isRunning || !modifyResult.session_id}
                      className="border border-slate-200 bg-slate-100 px-4 py-3 font-semibold text-slate-950 disabled:opacity-50"
                    >
                      Backtest versione modificata
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
                      Scarica versione modificata
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
                      Setup guide
                    </button>
                  </div>

                  {modifiedBacktest.isRunning && (
                    <div className="rounded border border-stone-800 bg-stone-900/70 p-6">
                      <Spinner label={modifiedBacktest.phaseLabel} />
                    </div>
                  )}

                  {modifiedBacktest.results && <BacktestMiniSummary title="Backtest versione modificata" results={modifiedBacktest.results} />}
                  {modifiedExportBlocked && (
                    <Alert type="warning" title="Export bloccato dal research verdict">
                      {(modifiedVerdict?.blockers || modifiedVerdict?.reasons || []).join(' · ') || 'La versione modificata non è stata promossa.'}
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
                  icon="⇄"
                  title="Confronto non ancora disponibile"
                  description="Genera prima una versione modificata del bot per vedere diff concettuale e compare metrics."
                />
              )}

              {modifyResult?.modified_analysis && (
                <>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-2">
                      <div className="text-stone-300 font-bold text-sm">Originale</div>
                      <div className="text-xs text-stone-400">style: {analysis.bot_profile.strategy_style}</div>
                      <div className="text-xs text-stone-400">protections: {analysis.code_summary.protections.join(', ') || 'n/d'}</div>
                      <div className="text-xs text-stone-400">indicators: {analysis.code_summary.indicators.map((item) => item.type).join(', ') || 'n/d'}</div>
                    </div>
                    <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-2">
                      <div className="text-stone-300 font-bold text-sm">Modificato</div>
                      <div className="text-xs text-stone-400">style: {modifyResult.modified_analysis.bot_profile.strategy_style}</div>
                      <div className="text-xs text-stone-400">protections: {modifyResult.modified_analysis.code_summary.protections.join(', ') || 'n/d'}</div>
                      <div className="text-xs text-stone-400">indicators: {modifyResult.modified_analysis.code_summary.indicators.map((item) => item.type).join(', ') || 'n/d'}</div>
                    </div>
                  </div>

                  {modifyResult.compare && (
                    <div className="rounded border border-stone-800 bg-stone-900/70 p-4 space-y-2">
                      <div className="text-stone-300 font-bold text-sm">Diff concettuale</div>
                      <div className="text-xs text-stone-400">Nuovi indicatori: {modifyResult.compare.new_indicators.join(', ') || 'nessuno'}</div>
                      <div className="text-xs text-stone-400">Nuove protezioni: {modifyResult.compare.new_protections.join(', ') || 'nessuna'}</div>
                      <div className="text-xs text-stone-400">Delta parametri: {modifyResult.compare.parameter_count_delta}</div>
                      <div className="text-xs text-stone-400">Fundamental filter added: {modifyResult.compare.fundamental_filter_added ? 'sì' : 'no'}</div>
                    </div>
                  )}

                  {originalBacktest.results && modifiedBacktest.results && compareMetrics && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <MetricCard label="Δ Trade OOS" value={compareMetrics.trades} colorClass={compareMetrics.trades < 0 ? 'text-amber-400' : 'text-green-400'} />
                      <MetricCard label="Δ Expectancy R" value={compareMetrics.expectancy.toFixed(2)} colorClass={compareMetrics.expectancy >= 0 ? 'text-green-400' : 'text-red-400'} />
                      <MetricCard label="Δ Return %" value={compareMetrics.returnPct.toFixed(2)} colorClass={compareMetrics.returnPct >= 0 ? 'text-green-400' : 'text-red-400'} />
                      <MetricCard label="Δ Max DD %" value={compareMetrics.drawdown.toFixed(2)} colorClass={compareMetrics.drawdown <= 0 ? 'text-green-400' : 'text-red-400'} />
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
        <MetricCard label="Return %" value={oos.total_return_pct?.toFixed(2)} colorClass={(oos.total_return_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'} />
        <MetricCard label="Max DD %" value={oos.max_drawdown_pct?.toFixed(2)} colorClass={(oos.max_drawdown_pct || 0) <= 10 ? 'text-green-400' : 'text-red-400'} />
      </div>
      <div className="text-xs text-stone-400">
        {decision.reasons.slice(0, 2).join(' · ')}
      </div>
      {calendarContext?.provider && calendarContext.provider !== 'none' && (
        <div className="text-xs text-stone-500">
          News provider: {calendarContext.provider}
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
