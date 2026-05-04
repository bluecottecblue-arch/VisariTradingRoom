'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent } from 'react'
import AuthToolbar from '@/components/AuthToolbar'
import AppSidebar from '@/components/layout/AppSidebar'
import { Alert, EmptyState, MetricCard, ProgressBar, Spinner, inputCls, textareaCls } from '@/components/ui'
import { formatError, researchLabApi } from '@/lib/api'
import type {
  ProjectSummary,
  ResearchDatasetRecord,
  ResearchLabBootstrapPayload,
  ResearchModelRunRecord,
  ResearchTrainingResult,
} from '@/types'

function shortDate(value?: string | null) {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('it-IT', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function toneForScore(score: number) {
  if (score >= 78) return 'text-cyan-300'
  if (score >= 58) return 'text-amber-300'
  return 'text-rose-300'
}

export default function ResearchLabClient() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<ResearchLabBootstrapPayload | null>(null)
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const [uploadTitle, setUploadTitle] = useState('Dataset caricato')
  const [uploadCsv, setUploadCsv] = useState('')
  const [uploadProjectId, setUploadProjectId] = useState<string>('')
  const [loadedFilename, setLoadedFilename] = useState('')

  const [fetchTitle, setFetchTitle] = useState('Mercato da provider')
  const [fetchProvider, setFetchProvider] = useState('demo')
  const [fetchSymbol, setFetchSymbol] = useState('EURUSD')
  const [fetchTimeframe, setFetchTimeframe] = useState('H1')
  const [fetchDateFrom, setFetchDateFrom] = useState('2023-01-01')
  const [fetchDateTo, setFetchDateTo] = useState('2025-01-01')
  const [fetchProjectId, setFetchProjectId] = useState<string>('')

  const [runTitle, setRunTitle] = useState('Run istituzionale')
  const [horizonBars, setHorizonBars] = useState(12)
  const [thresholdBps, setThresholdBps] = useState(8)
  const [epochs, setEpochs] = useState(600)
  const [l2Penalty, setL2Penalty] = useState(0.002)

  async function loadBootstrap(preferred?: { datasetId?: string | null; runId?: string | null }) {
    setLoading(true)
    setError(null)
    try {
      const payload = (await researchLabApi.bootstrap()) as ResearchLabBootstrapPayload
      setData(payload)
      setSelectedDatasetId(
        preferred?.datasetId ||
          payload.datasets.find((dataset) => dataset.dataset_id === selectedDatasetId)?.dataset_id ||
          payload.datasets[0]?.dataset_id ||
          null,
      )
      setSelectedRunId(
        preferred?.runId ||
          payload.runs.find((run) => run.run_id === selectedRunId)?.run_id ||
          payload.runs[0]?.run_id ||
          null,
      )
    } catch (e) {
      setError(formatError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBootstrap()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectedDataset = useMemo(
    () => data?.datasets.find((dataset) => dataset.dataset_id === selectedDatasetId) || null,
    [data?.datasets, selectedDatasetId],
  )

  const selectedRun = useMemo(
    () => data?.runs.find((run) => run.run_id === selectedRunId) || null,
    [data?.runs, selectedRunId],
  )

  const selectedRunResult = selectedRun?.result as unknown as ResearchTrainingResult | undefined
  const projects = data?.projects || []

  async function handleUpload() {
    if (!uploadCsv.trim()) {
      setError('Carica o incolla un CSV prima di creare il dataset.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = (await researchLabApi.uploadDataset({
        title: uploadTitle,
        csv_text: uploadCsv,
        project_id: uploadProjectId || null,
      })) as { dataset: ResearchDatasetRecord }
      await loadBootstrap({ datasetId: response.dataset.dataset_id })
      setRunTitle(`Run ${response.dataset.title}`)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleFetch() {
    setBusy(true)
    setError(null)
    try {
      const response = (await researchLabApi.fetchDataset({
        title: fetchTitle,
        provider: fetchProvider,
        symbol: fetchSymbol,
        timeframe: fetchTimeframe,
        date_from: fetchDateFrom,
        date_to: fetchDateTo,
        project_id: fetchProjectId || null,
      })) as { dataset: ResearchDatasetRecord }
      await loadBootstrap({ datasetId: response.dataset.dataset_id })
      setRunTitle(`Run ${response.dataset.title}`)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleTrain() {
    if (!selectedDatasetId) {
      setError('Seleziona prima un dataset da usare per il training.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = (await researchLabApi.train({
        dataset_id: selectedDatasetId,
        title: runTitle,
        horizon_bars: horizonBars,
        return_threshold_bps: thresholdBps,
        epochs,
        l2_penalty: l2Penalty,
      })) as { run: ResearchModelRunRecord }
      await loadBootstrap({ datasetId: selectedDatasetId, runId: response.run.run_id })
    } catch (e) {
      setError(formatError(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    const text = await file.text()
    setUploadCsv(text)
    setLoadedFilename(file.name)
    if (!uploadTitle || uploadTitle === 'Dataset caricato') {
      setUploadTitle(file.name.replace(/\.(csv|txt)$/i, ''))
    }
  }

  const datasetWarnings = ((selectedDataset?.quality || {})['warnings'] as string[] | undefined) || []
  const latestQualityScore = selectedRunResult?.summary?.quality_score || 0

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 xl:pl-80">
        <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="p-8"><Spinner label="Caricamento Data Lab..." /></div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-100 transition-[padding] duration-200 ${sidebarOpen ? 'xl:pl-80' : 'xl:pl-0'}`}>
      <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800 bg-slate-950/90 px-6 py-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label={sidebarOpen ? 'Chiudi navigazione' : 'Apri navigazione'}
            onClick={() => setSidebarOpen((current) => !current)}
            className="flex h-11 w-11 items-center justify-center border border-slate-800 text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-100"
          >
            <span className="flex flex-col gap-1.5">
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
            </span>
          </button>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-cyan-500">Research lab</div>
            <div className="text-xl font-semibold text-slate-50">Dati, modelli e controlli anti-overfitting</div>
          </div>
        </div>
        <AuthToolbar />
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-6 py-8 lg:px-10">
        <section className="border border-slate-800 bg-slate-950/70 p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Layer istituzionale</div>
              <h1 className="mt-2 text-3xl font-semibold text-slate-50">Allena modelli su dati tuoi o su serie mercato gia recuperate dall’app</h1>
              <p className="mt-3 max-w-4xl text-sm leading-relaxed text-slate-400">
                Il Data Lab accetta CSV sporchi o dataset gia puliti, costruisce feature quantitative, separa train/validation/test, esegue controlli walk-forward e segnala subito rumore, leakage e fragilita del segnale.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard label="Dataset" value={data?.datasets.length || 0} />
              <MetricCard label="Run salvati" value={data?.runs.length || 0} />
              <MetricCard label="Quality score" value={selectedRunResult ? `${selectedRunResult.summary.quality_score}/100` : '—'} colorClass={toneForScore(latestQualityScore)} />
            </div>
          </div>
        </section>

        {error && <Alert type="error">{error}</Alert>}

        <div className="grid gap-8 xl:grid-cols-[1fr_1.1fr]">
          <section className="space-y-6">
            <div className="border border-slate-800 bg-slate-950/70 p-5">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Carica dataset</div>
              <div className="mt-4 space-y-4">
                <input value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} className={inputCls} placeholder="Dataset EURUSD da account live" />
                <select value={uploadProjectId} onChange={(event) => setUploadProjectId(event.target.value)} className={inputCls}>
                  <option value="">Nessun progetto collegato</option>
                  {projects.map((project) => (
                    <option key={project.project_id} value={project.project_id}>
                      {project.title}
                    </option>
                  ))}
                </select>
                <input type="file" accept=".csv,.txt" onChange={handleFileChange} className={`${inputCls} file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-semibold`} />
                {loadedFilename && <div className="text-xs text-slate-500">File pronto: {loadedFilename}</div>}
                <textarea
                  value={uploadCsv}
                  onChange={(event) => setUploadCsv(event.target.value)}
                  rows={8}
                  className={textareaCls}
                  placeholder="Incolla qui un CSV con timestamp/date e almeno la colonna Close. Open/High/Low/Volume verranno riconosciute se presenti."
                />
                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={busy}
                  className="w-full border border-slate-200 bg-slate-100 px-4 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-white disabled:opacity-50"
                >
                  Crea dataset da CSV
                </button>
              </div>
            </div>

            <div className="border border-slate-800 bg-slate-950/70 p-5">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Recupera dati di mercato</div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <input value={fetchTitle} onChange={(event) => setFetchTitle(event.target.value)} className={inputCls} placeholder="EURUSD H1 regime study" />
                <select value={fetchProjectId} onChange={(event) => setFetchProjectId(event.target.value)} className={inputCls}>
                  <option value="">Nessun progetto collegato</option>
                  {projects.map((project) => (
                    <option key={project.project_id} value={project.project_id}>
                      {project.title}
                    </option>
                  ))}
                </select>
                <select value={fetchProvider} onChange={(event) => setFetchProvider(event.target.value)} className={inputCls}>
                  <option value="demo">Demo sintetico</option>
                  <option value="polygon">Polygon</option>
                  <option value="dukascopy">Dukascopy</option>
                </select>
                <input value={fetchSymbol} onChange={(event) => setFetchSymbol(event.target.value.toUpperCase())} className={inputCls} placeholder="EURUSD" />
                <select value={fetchTimeframe} onChange={(event) => setFetchTimeframe(event.target.value)} className={inputCls}>
                  {['M15', 'M30', 'H1', 'H4', 'D1'].map((value) => (
                    <option key={value} value={value}>{value}</option>
                  ))}
                </select>
                <div className="grid grid-cols-2 gap-3">
                  <input type="date" value={fetchDateFrom} onChange={(event) => setFetchDateFrom(event.target.value)} className={inputCls} />
                  <input type="date" value={fetchDateTo} onChange={(event) => setFetchDateTo(event.target.value)} className={inputCls} />
                </div>
              </div>
              <button
                type="button"
                onClick={handleFetch}
                disabled={busy}
                className="mt-4 w-full border border-slate-800 px-4 py-3 text-sm font-semibold text-slate-200 transition-colors hover:border-slate-600 disabled:opacity-50"
              >
                Recupera serie da provider
              </button>
            </div>

            <div className="border border-slate-800 bg-slate-950/70 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Training statistico</div>
                  <div className="mt-2 text-lg font-semibold text-slate-50">Run con split rigoroso, walk-forward e shuffled baseline</div>
                </div>
                <button
                  type="button"
                  onClick={handleTrain}
                  disabled={busy || !selectedDatasetId}
                  className="border border-slate-200 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-white disabled:opacity-50"
                >
                  Avvia training
                </button>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <input value={runTitle} onChange={(event) => setRunTitle(event.target.value)} className={inputCls} placeholder="Run istituzionale" />
                <select value={selectedDatasetId || ''} onChange={(event) => setSelectedDatasetId(event.target.value)} className={inputCls}>
                  <option value="">Seleziona dataset</option>
                  {data?.datasets.map((dataset) => (
                    <option key={dataset.dataset_id} value={dataset.dataset_id}>
                      {dataset.title}
                    </option>
                  ))}
                </select>
                <input type="number" min={2} max={200} value={horizonBars} onChange={(event) => setHorizonBars(Number(event.target.value) || 12)} className={inputCls} placeholder="Horizon bars" />
                <input type="number" min={0} max={500} step="0.5" value={thresholdBps} onChange={(event) => setThresholdBps(Number(event.target.value) || 8)} className={inputCls} placeholder="Threshold bps" />
                <input type="number" min={120} max={4000} value={epochs} onChange={(event) => setEpochs(Number(event.target.value) || 600)} className={inputCls} placeholder="Epochs" />
                <input type="number" min={0} max={1} step="0.001" value={l2Penalty} onChange={(event) => setL2Penalty(Number(event.target.value) || 0.002)} className={inputCls} placeholder="L2 penalty" />
              </div>
              <div className="mt-4 text-sm text-slate-500">
                L’obiettivo non e solo predire pattern, ma capire se il segnale sopravvive fuori campione, batte il baseline shuffled e resta stabile in walk-forward.
              </div>
            </div>
          </section>

          <section className="space-y-6">
            <div className="border border-slate-800 bg-slate-950/70 p-5">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Dataset disponibili</div>
              <div className="mt-4 space-y-3">
                {(data?.datasets || []).map((dataset) => {
                  const active = dataset.dataset_id === selectedDatasetId
                  const qualityWarnings = (dataset.quality?.['warnings'] as string[] | undefined) || []
                  const warningCount = qualityWarnings.length
                  return (
                    <button
                      key={dataset.dataset_id}
                      type="button"
                      onClick={() => setSelectedDatasetId(dataset.dataset_id)}
                      className={`w-full border p-4 text-left transition-colors ${
                        active ? 'border-cyan-700/70 bg-cyan-950/12' : 'border-slate-800 bg-slate-950 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-base font-semibold text-slate-100">{dataset.title}</div>
                          <div className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                            {dataset.source} · {dataset.timeframe || 'custom'} · {dataset.row_count} righe
                          </div>
                        </div>
                        <div className="text-xs text-slate-500">{warningCount} warning</div>
                      </div>
                    </button>
                  )
                })}
                {!data?.datasets.length && (
                  <EmptyState
                    icon="DATA"
                    title="Nessun dataset"
                    description="Carica un CSV o scarica una serie dal provider per iniziare la ricerca quantitativa."
                  />
                )}
              </div>
            </div>

            {selectedDataset && (
              <div className="border border-slate-800 bg-slate-950/70 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Dataset selezionato</div>
                    <div className="mt-2 text-xl font-semibold text-slate-50">{selectedDataset.title}</div>
                    <div className="mt-2 text-sm text-slate-400">
                      {selectedDataset.date_from || '—'} → {selectedDataset.date_to || '—'}
                    </div>
                  </div>
                  {selectedDataset.project_id && (
                    <Link
                      href={`/builder?project_id=${selectedDataset.project_id}`}
                      className="border border-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors hover:border-slate-600"
                    >
                      Apri nel builder
                    </Link>
                  )}
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <MetricCard label="Righe" value={selectedDataset.row_count} />
                  <MetricCard label="Gap ratio" value={String(selectedDataset.quality?.['gap_ratio'] ?? '—')} />
                  <MetricCard label="Duplicati" value={String(selectedDataset.quality?.['duplicate_timestamps'] ?? '—')} />
                </div>
                {datasetWarnings.length > 0 && (
                  <Alert type="warning" title="Warning qualità dataset">
                    {datasetWarnings.join(' · ')}
                  </Alert>
                )}
              </div>
            )}

            <div className="border border-slate-800 bg-slate-950/70 p-5">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Run recenti</div>
              <div className="mt-4 space-y-3">
                {(data?.runs || []).map((run) => {
                  const active = run.run_id === selectedRunId
                  const result = run.result as unknown as ResearchTrainingResult | undefined
                  const score = result?.summary?.quality_score || 0
                  return (
                    <button
                      key={run.run_id}
                      type="button"
                      onClick={() => setSelectedRunId(run.run_id)}
                      className={`w-full border p-4 text-left transition-colors ${
                        active ? 'border-cyan-700/70 bg-cyan-950/12' : 'border-slate-800 bg-slate-950 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="text-base font-semibold text-slate-100">{run.title}</div>
                          <div className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                            {run.model_type} · {shortDate(run.updated_at)}
                          </div>
                        </div>
                        <div className={`text-lg font-semibold ${toneForScore(score)}`}>{score || '—'}</div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            {selectedRunResult ? (
              <div className="space-y-6 border border-slate-800 bg-slate-950/70 p-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Run selezionato</div>
                    <div className="mt-2 text-xl font-semibold text-slate-50">{selectedRun?.title}</div>
                    <div className="mt-2 text-sm text-slate-400">{selectedRunResult.target_definition.label_rule}</div>
                  </div>
                  <div className={`text-3xl font-semibold ${toneForScore(selectedRunResult.summary.quality_score)}`}>
                    {selectedRunResult.summary.quality_score}/100
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <MetricCard label="Verdetto" value={selectedRunResult.summary.verdict} colorClass={toneForScore(selectedRunResult.summary.quality_score)} />
                  <MetricCard label="Feature" value={selectedRunResult.summary.feature_count} />
                  <MetricCard label="Target positivo" value={`${(selectedRunResult.summary.target_positive_rate * 100).toFixed(1)}%`} />
                </div>

                <div className="grid gap-4 lg:grid-cols-3">
                  <div className="border border-slate-800 bg-slate-950 p-4">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Train</div>
                    <div className="mt-3 space-y-2 text-sm text-slate-300">
                      <div>Accuracy: {selectedRunResult.metrics.train.accuracy}</div>
                      <div>AUC: {selectedRunResult.metrics.train.auc}</div>
                      <div>Brier: {selectedRunResult.metrics.train.brier}</div>
                    </div>
                  </div>
                  <div className="border border-slate-800 bg-slate-950 p-4">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Validation</div>
                    <div className="mt-3 space-y-2 text-sm text-slate-300">
                      <div>Accuracy: {selectedRunResult.metrics.validation.accuracy}</div>
                      <div>AUC: {selectedRunResult.metrics.validation.auc}</div>
                      <div>Brier: {selectedRunResult.metrics.validation.brier}</div>
                    </div>
                  </div>
                  <div className="border border-slate-800 bg-slate-950 p-4">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Test</div>
                    <div className="mt-3 space-y-2 text-sm text-slate-300">
                      <div>Accuracy: {selectedRunResult.metrics.test.accuracy}</div>
                      <div>AUC: {selectedRunResult.metrics.test.auc}</div>
                      <div>Brier: {selectedRunResult.metrics.test.brier}</div>
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                  <div className="border border-slate-800 bg-slate-950 p-4">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Anti-overfitting</div>
                    <div className="mt-3 space-y-3 text-sm text-slate-300">
                      <div>Gap train/test: {selectedRunResult.anti_overfitting.train_test_gap}</div>
                      <div>Baseline shuffled AUC: {selectedRunResult.anti_overfitting.shuffled_baseline_auc}</div>
                      <div>Signal-to-noise: {selectedRunResult.anti_overfitting.signal_to_noise_score}</div>
                      {selectedRunResult.anti_overfitting.warnings.length > 0 ? (
                        <Alert type="warning" title="Punti da controllare">
                          {selectedRunResult.anti_overfitting.warnings.join(' · ')}
                        </Alert>
                      ) : (
                        <Alert type="success" title="Controlli puliti">
                          Nessun warning grave: il modello ha superato baseline shuffled e mantiene un profilo ragionevole fuori campione.
                        </Alert>
                      )}
                    </div>
                  </div>

                  <div className="border border-slate-800 bg-slate-950 p-4">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Walk-forward</div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      <MetricCard label="Stabilita" value={`${selectedRunResult.walk_forward.stability_score}/100`} />
                      <MetricCard label="Avg acc" value={selectedRunResult.walk_forward.average_test_accuracy} />
                      <MetricCard label="Avg AUC" value={selectedRunResult.walk_forward.average_test_auc} />
                    </div>
                    <div className="mt-4 text-sm text-slate-300">
                      Training: {selectedRunResult.split_summary.train_from || '—'} → {selectedRunResult.split_summary.train_to || '—'}
                      <br />
                      Test: {selectedRunResult.split_summary.test_from || '—'} → {selectedRunResult.split_summary.test_to || '—'}
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-[1fr_0.95fr]">
                  <div className="border border-slate-800 bg-slate-950 p-4">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Feature ranking</div>
                    <div className="mt-3 space-y-3">
                      {selectedRunResult.feature_ranking.slice(0, 8).map((feature) => (
                        <div key={feature.feature}>
                          <div className="flex items-center justify-between gap-4 text-sm">
                            <span className="text-slate-200">{feature.feature}</span>
                            <span className={feature.direction === 'positive' ? 'text-cyan-300' : feature.direction === 'negative' ? 'text-amber-300' : 'text-slate-400'}>
                              {feature.weight}
                            </span>
                          </div>
                          <ProgressBar value={Math.min(100, Math.abs(feature.weight) * 100)} max={100} />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="border border-slate-800 bg-slate-950 p-4">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Raccomandazioni</div>
                    <div className="mt-3 space-y-2 text-sm text-slate-300">
                      {selectedRunResult.recommendations.map((item) => (
                        <div key={item}>• {item}</div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState
                icon="RUN"
                title="Nessun run selezionato"
                description="Appena avvii il training vedrai qui verdetto, metriche fuori campione e controlli anti-overfitting."
              />
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
