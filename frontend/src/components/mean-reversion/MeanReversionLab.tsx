'use client'

import { useState, useRef, useCallback } from 'react'
import AuthToolbar from '@/components/AuthToolbar'
import AppSidebar from '@/components/layout/AppSidebar'

// ---- Tipi ----
interface AnalysisConfig {
  price_column: string
  series_transform: 'price' | 'log_price' | 'returns' | 'log_returns'
  asset_type: 'equity' | 'fx' | 'crypto' | 'index'
  fill_method: 'ffill' | 'bfill' | null
  split_method: 'ratio' | 'date' | 'none'
  split_ratio: number
  split_date: string
  adf_regression: 'c' | 'ct' | 'ctt' | 'n'
  adf_autolag: 'AIC' | 'BIC' | 't-stat' | null
  mc_n_sims: number
  mc_method: 'gbm' | 'bootstrap' | 'permutation'
  rolling_window: number
  vr_lags: string
}

const DEFAULT_CONFIG: AnalysisConfig = {
  price_column: 'close',
  series_transform: 'log_price',
  asset_type: 'equity',
  fill_method: null,
  split_method: 'ratio',
  split_ratio: 0.7,
  split_date: '',
  adf_regression: 'c',
  adf_autolag: 'AIC',
  mc_n_sims: 500,
  mc_method: 'bootstrap',
  rolling_window: 60,
  vr_lags: '2,5,10,20,60',
}

// ---- Stili ----
const input = 'w-full border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-amber-400 focus:outline-none'
const select = input + ' cursor-pointer'
const label = 'block text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1'
const btn = 'px-4 py-2 text-sm font-semibold uppercase tracking-[0.14em] transition-colors'
const btnPrimary = btn + ' bg-amber-400 text-slate-950 hover:bg-amber-300'
const btnSecondary = btn + ' border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-slate-100'
const card = 'border border-slate-800 bg-slate-900/50 p-4'
const sectionTitle = 'text-[10px] uppercase tracking-[0.18em] text-slate-500 pb-2 mb-4 border-b border-slate-800'

// ---- Helper ----
function pval(v: number | null | undefined) {
  if (v == null) return '—'
  return v < 0.001 ? '< 0.001' : v.toFixed(4)
}
function num(v: number | null | undefined, d = 4) {
  if (v == null) return '—'
  return v.toFixed(d)
}
function verdictColor(code: string) {
  if (code.includes('mean_reverting') && code.includes('strong')) return 'text-green-400'
  if (code.includes('mean_reverting')) return 'text-amber-400'
  if (code === 'random_walk') return 'text-slate-400'
  if (code.includes('trending')) return 'text-blue-400'
  if (code === 'weak') return 'text-orange-400'
  return 'text-slate-400'
}

// ---- Sub-componenti risultati ----

function QualityCard({ report }: { report: any }) {
  if (!report) return null
  return (
    <div className={card}>
      <div className={sectionTitle}>Qualità dati</div>
      <div className="grid grid-cols-3 gap-3 text-sm mb-3">
        <Stat label="Originali" value={report.n_original} />
        <Stat label="Dopo pulizia" value={report.n_after_clean} />
        <Stat label="Duplicati rimossi" value={report.n_duplicates_removed} />
        <Stat label="Riempiti" value={report.n_missing_filled} />
        <Stat label="Scartati (NaN)" value={report.n_missing_dropped} />
        <Stat label="Prezzi invalidi" value={report.n_invalid_prices} />
      </div>
      {report.timezone_note && <p className="text-[11px] text-slate-500 mb-2">{report.timezone_note}</p>}
      <Warnings items={report.warnings} level="warn" />
      <Warnings items={report.info} level="info" />
    </div>
  )
}

function Warnings({ items, level }: { items: string[], level: 'warn' | 'info' }) {
  if (!items?.length) return null
  const cls = level === 'warn' ? 'text-amber-400' : 'text-slate-400'
  const icon = level === 'warn' ? '⚠' : 'ℹ'
  return (
    <div className="space-y-1 mt-2">
      {items.map((w, i) => (
        <p key={i} className={`text-[11px] ${cls}`}>{icon} {w}</p>
      ))}
    </div>
  )
}

function Stat({ label: l, value }: { label: string, value: any }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-slate-600">{l}</div>
      <div className="text-base font-semibold text-slate-200">{value ?? '—'}</div>
    </div>
  )
}

function AdfCard({ adf }: { adf: any }) {
  if (!adf) return null

  function SampleResult({ data, title }: { data: any, title: string }) {
    if (!data) return null
    if (data.error) return <p className="text-red-400 text-sm">{data.error}</p>
    if (!data.applicable) return null
    return (
      <div className="mb-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">{title}</div>
        <div className="grid grid-cols-2 gap-3 mb-2">
          <Stat label="Statistica ADF" value={num(data.test_statistic)} />
          <Stat label="P-value" value={pval(data.p_value)} />
          <Stat label="Lag usati" value={data.lags_used} />
          <Stat label="Osservazioni" value={data.n_observations} />
        </div>
        <div className="text-[11px] text-slate-500 mb-2">
          Valori critici: 1%={num(data.critical_values?.['1%'],3)} | 5%={num(data.critical_values?.['5%'],3)} | 10%={num(data.critical_values?.['10%'],3)}
        </div>
        <div className={`text-sm font-medium ${data.reject_h0 ? 'text-green-400' : 'text-slate-400'}`}>
          {data.reject_h0 ? '✓' : '✗'} {data.verdict}
        </div>
      </div>
    )
  }

  return (
    <div className={card}>
      <div className={sectionTitle}>Test ADF — Augmented Dickey-Fuller</div>
      <p className="text-[11px] text-slate-500 mb-4">
        H₀: la serie ha una radice unitaria (non stazionaria). Rifiuto H₀ = evidenza di stazionarietà.
      </p>
      {adf.overfitting_warning && (
        <div className="border border-red-800 bg-red-950/30 px-3 py-2 mb-4 text-[11px] text-red-300">{adf.overfitting_warning}</div>
      )}
      <div className="space-y-4 divide-y divide-slate-800">
        <SampleResult data={adf.full} title="Campione completo" />
        {adf.in_sample && <div className="pt-4"><SampleResult data={adf.in_sample} title="In-sample" /></div>}
        {adf.out_of_sample && <div className="pt-4"><SampleResult data={adf.out_of_sample} title="Out-of-sample" /></div>}
      </div>
      <Warnings items={adf.full?.warnings || []} level="warn" />
    </div>
  )
}

function HurstCard({ hurst, plotRolling }: { hurst: any, plotRolling?: string }) {
  if (!hurst) return null

  function SampleResult({ data, title }: { data: any, title: string }) {
    if (!data?.applicable) return null
    return (
      <div className="mb-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">{title}</div>
        <div className="grid grid-cols-2 gap-3 mb-2">
          <Stat label="H (Hurst)" value={num(data.h)} />
          <Stat label="R² regressione" value={num(data.r_squared, 3)} />
        </div>
        <div className={`text-sm font-medium ${
          data.h < 0.45 ? 'text-green-400' : data.h > 0.55 ? 'text-blue-400' : 'text-slate-400'
        }`}>
          {data.interpretation}
        </div>
        {data.rolling && (
          <div className="mt-2 text-[10px] text-slate-600">
            Rolling H: media={num(data.rolling.mean_h, 3)} | std={num(data.rolling.std_h, 3)}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={card}>
      <div className={sectionTitle}>Esponente di Hurst</div>
      <p className="text-[11px] text-slate-500 mb-4">
        H &lt; 0.5 → mean-reverting | H ≈ 0.5 → random walk | H &gt; 0.5 → trending
      </p>
      {hurst.overfitting_warning && (
        <div className="border border-red-800 bg-red-950/30 px-3 py-2 mb-4 text-[11px] text-red-300">{hurst.overfitting_warning}</div>
      )}
      <div className="space-y-4 divide-y divide-slate-800">
        <SampleResult data={hurst.full} title="Campione completo" />
        {hurst.in_sample && <div className="pt-4"><SampleResult data={hurst.in_sample} title="In-sample" /></div>}
        {hurst.out_of_sample && <div className="pt-4"><SampleResult data={hurst.out_of_sample} title="Out-of-sample" /></div>}
      </div>
      {plotRolling && (
        <div className="mt-4">
          <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">Rolling Hurst</div>
          <img src={`data:image/png;base64,${plotRolling}`} alt="Rolling Hurst" className="w-full" />
        </div>
      )}
      <Warnings items={hurst.full?.warnings || []} level="warn" />
    </div>
  )
}

function VRCard({ vr, plotVR }: { vr: any, plotVR?: string }) {
  if (!vr?.full?.applicable) return null
  const full = vr.full

  return (
    <div className={card}>
      <div className={sectionTitle}>Variance Ratio Test — Lo-MacKinlay</div>
      <p className="text-[11px] text-slate-500 mb-4">
        VR &lt; 1 → mean-reverting | VR = 1 → random walk | VR &gt; 1 → trending/momentum
      </p>
      <div className="mb-4 text-sm font-medium text-amber-400">{full.overall_interpretation}</div>

      <div className="overflow-x-auto mb-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-[10px] uppercase tracking-widest text-slate-600">
              <th className="pb-2 text-left">q (holding period)</th>
              <th className="pb-2 text-right">VR</th>
              <th className="pb-2 text-right">z-stat</th>
              <th className="pb-2 text-right">p-value</th>
              <th className="pb-2 text-right">Sig.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {full.lags?.map((lag: any) => (
              <tr key={lag.q} className="text-slate-300">
                <td className="py-1.5 text-slate-500">{lag.q}</td>
                <td className={`py-1.5 text-right font-mono ${
                  lag.variance_ratio < 0.95 ? 'text-green-400' :
                  lag.variance_ratio > 1.05 ? 'text-blue-400' : 'text-slate-400'
                }`}>{num(lag.variance_ratio, 3)}</td>
                <td className="py-1.5 text-right font-mono">{num(lag.z_statistic, 3)}</td>
                <td className="py-1.5 text-right font-mono">{pval(lag.p_value)}</td>
                <td className={`py-1.5 text-right ${lag.reject_h0 ? 'text-green-400' : 'text-slate-600'}`}>
                  {lag.reject_h0 ? '✓' : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {plotVR && (
        <img src={`data:image/png;base64,${plotVR}`} alt="Variance Ratio" className="w-full mb-4" />
      )}

      {(vr.in_sample || vr.out_of_sample) && (
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800 mt-4 text-sm">
          {vr.in_sample?.applicable && (
            <div>
              <div className="text-[10px] text-slate-500 mb-1">In-sample</div>
              <div className="text-amber-400">{vr.in_sample.overall_interpretation}</div>
            </div>
          )}
          {vr.out_of_sample?.applicable && (
            <div>
              <div className="text-[10px] text-slate-500 mb-1">Out-of-sample</div>
              <div className="text-amber-400">{vr.out_of_sample.overall_interpretation}</div>
            </div>
          )}
        </div>
      )}
      <Warnings items={full.warnings || []} level="warn" />
    </div>
  )
}

function MCCard({ mc, plots }: { mc: any, plots: any }) {
  if (!mc?.applicable) return null

  function StatRow({ stat, key: k }: { stat: any, key: string }) {
    if (!stat) return null
    const obs = stat.observed_stat ?? stat.observed_h ?? stat.observed_vr
    const dist = stat.distribution || {}
    return (
      <div className="mb-4">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">{k.toUpperCase()}</div>
        <div className="grid grid-cols-3 gap-2 mb-2 text-sm">
          <Stat label="Osservato" value={num(obs)} />
          <Stat label="Media sim." value={num(dist.mean)} />
          <Stat label="p-value emp." value={pval(stat.empirical_pvalue)} />
        </div>
        <div className={`text-sm font-medium mb-2 ${stat.significant ? 'text-green-400' : 'text-slate-400'}`}>
          {stat.significant ? '✓ Significativo' : '✗ Compatibile col random walk'} — {stat.interpretation}
        </div>
        <div className="text-[10px] text-slate-600">
          Distribuzione sim.: P5={num(dist.p5, 3)} | P50={num(dist.p50, 3)} | P95={num(dist.p95, 3)}
        </div>
        {plots?.[`mc_${k}`] && (
          <img src={`data:image/png;base64,${plots[`mc_${k}`]}`} alt={`MC ${k}`} className="w-full mt-3" />
        )}
      </div>
    )
  }

  return (
    <div className={card}>
      <div className={sectionTitle}>Analisi Monte Carlo ({mc.n_simulations} simulazioni — {mc.method})</div>
      <p className="text-[11px] text-slate-500 mb-4">
        Confronto tra statistiche osservate e distribuzione attesa sotto un random walk.
        P-value empirico basso = evidenza più forte del caso.
      </p>
      <div className="mb-3 text-sm font-medium text-amber-400">{mc.overall_interpretation}</div>
      <div className="space-y-6 divide-y divide-slate-800">
        {mc.adf && <div className="pt-4"><StatRow stat={mc.adf} key="adf" /></div>}
        {mc.hurst && <div className="pt-4"><StatRow stat={mc.hurst} key="hurst" /></div>}
        {mc.variance_ratio && <div className="pt-4"><StatRow stat={mc.variance_ratio} key="variance_ratio" /></div>}
      </div>
      <Warnings items={mc.warnings || []} level="warn" />
    </div>
  )
}

function VerdictCard({ verdict, metadata, splitInfo }: { verdict: any, metadata: any, splitInfo: any }) {
  if (!verdict) return null
  return (
    <div className="border border-slate-700 bg-slate-900 p-6">
      <div className={sectionTitle}>Verdetto finale</div>
      <div className={`text-2xl font-bold mb-4 ${verdictColor(verdict.verdict_code)}`}>
        {verdict.verdict}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6 text-sm">
        <div>
          <div className="text-[10px] text-slate-600 mb-1">Asset / colonna</div>
          <div className="text-slate-300">{metadata?.price_column} — {metadata?.asset_type}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-600 mb-1">Trasformazione</div>
          <div className="text-slate-300">{metadata?.series_transform}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-600 mb-1">Osservazioni totali</div>
          <div className="text-slate-300">{metadata?.n_observations_total}</div>
        </div>
        <div>
          <div className="text-[10px] text-slate-600 mb-1">Periodo</div>
          <div className="text-slate-300">{metadata?.date_range_start} → {metadata?.date_range_end}</div>
        </div>
        {splitInfo?.in_sample_n > 0 && (
          <>
            <div>
              <div className="text-[10px] text-slate-600 mb-1">In-sample</div>
              <div className="text-slate-300">{splitInfo.in_sample_n} obs ({splitInfo.in_sample_start} → {splitInfo.in_sample_end})</div>
            </div>
            <div>
              <div className="text-[10px] text-slate-600 mb-1">Out-of-sample</div>
              <div className="text-slate-300">{splitInfo.out_sample_n} obs ({splitInfo.out_sample_start} → {splitInfo.out_sample_end})</div>
            </div>
          </>
        )}
      </div>

      {verdict.signals_summary?.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] text-slate-600 uppercase tracking-widest mb-2">Segnali per test</div>
          <div className="flex gap-3 flex-wrap">
            {verdict.signals_summary.map((s: any) => (
              <span key={s.test} className={`text-xs px-2 py-1 border ${
                s.signal === 'mean_reverting' ? 'border-green-800 bg-green-950/30 text-green-400' :
                s.signal === 'trending' ? 'border-blue-800 bg-blue-950/30 text-blue-400' :
                'border-slate-700 bg-slate-900 text-slate-500'
              }`}>
                {s.test.toUpperCase()}: {s.signal}
              </span>
            ))}
          </div>
        </div>
      )}

      {verdict.overfitting_warning && (
        <div className="border border-red-800 bg-red-950/30 px-3 py-2 mb-4 text-[11px] text-red-300">
          {verdict.overfitting_warning}
        </div>
      )}

      <p className="text-[11px] text-slate-500 border-t border-slate-800 pt-4 mt-4">
        {verdict.disclaimer}
      </p>
    </div>
  )
}

// ---- Componente principale ----

export default function MeanReversionLab() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [mode, setMode] = useState<'file' | 'api'>('file')
  const [config, setConfig] = useState<AnalysisConfig>(DEFAULT_CONFIG)
  const [fileData, setFileData] = useState<{ base64: string, name: string } | null>(null)
  const [apiParams, setApiParams] = useState({ provider: 'stooq', symbol: '', timeframe: '1d', start: '2020-01-01', end: '2024-12-31', api_key: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const setC = (k: keyof AnalysisConfig, v: any) => setConfig(prev => ({ ...prev, [k]: v }))
  const setA = (k: string, v: any) => setApiParams(prev => ({ ...prev, [k]: v }))

  const handleFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const b64 = (ev.target?.result as string).split(',')[1]
      setFileData({ base64: b64, name: f.name })
    }
    reader.readAsDataURL(f)
  }, [])

  const buildConfig = () => ({
    ...config,
    vr_lags: config.vr_lags
      ? config.vr_lags.split(',').map((v: string) => parseInt(v.trim())).filter((v: number) => !isNaN(v))
      : null,
    fill_method: config.fill_method || null,
    adf_autolag: config.adf_autolag || null,
    split_ratio: Number(config.split_ratio),
    mc_n_sims: Number(config.mc_n_sims),
    rolling_window: Number(config.rolling_window),
  })

  const run = async () => {
    setError(null)
    setResult(null)
    setLoading(true)

    try {
      let resp: Response
      if (mode === 'file') {
        if (!fileData) { setError('Carica prima un file.'); setLoading(false); return }
        resp = await fetch('/api/backend/api/mean-reversion/analyze-file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: fileData.name, file_base64: fileData.base64, config: buildConfig() }),
        })
      } else {
        if (!apiParams.symbol) { setError('Inserisci il simbolo.'); setLoading(false); return }
        resp = await fetch('/api/backend/api/mean-reversion/analyze-api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: apiParams.provider,
            symbol: apiParams.symbol,
            timeframe: apiParams.timeframe,
            start: apiParams.start,
            end: apiParams.end,
            api_key: apiParams.api_key || null,
            config: buildConfig(),
          }),
        })
      }

      const data = await resp.json()
      if (!resp.ok) throw new Error(data.detail || JSON.stringify(data))
      setResult(data)
      // scroll ai risultati
      setTimeout(() => document.getElementById('mr-results')?.scrollIntoView({ behavior: 'smooth' }), 100)
    } catch (e: any) {
      setError(e.message || 'Errore sconosciuto.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-200 transition-[padding] duration-200 ${sidebarOpen ? 'xl:pl-80' : 'xl:pl-0'}`}>
      <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800 bg-slate-950/90 px-6 py-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label={sidebarOpen ? 'Chiudi navigazione' : 'Apri navigazione'}
            onClick={() => setSidebarOpen(v => !v)}
            className="flex h-11 w-11 items-center justify-center border border-slate-800 text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-100"
          >
            <span className="flex flex-col gap-1.5">
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
            </span>
          </button>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-amber-400">Mean Reversion Lab</div>
            <div className="text-xl font-semibold text-slate-50">Diagnostica statistica di stazionarietà</div>
          </div>
        </div>
        <AuthToolbar />
      </header>

      <main className="mx-auto max-w-5xl space-y-8 px-6 py-8">

        {/* === SEZIONE 1: DATI === */}
        <div className={card}>
          <div className={sectionTitle}>1. Sorgente dati</div>
          <div className="flex gap-2 mb-6">
            <button onClick={() => setMode('file')} className={mode === 'file' ? btnPrimary : btnSecondary}>
              File locale
            </button>
            <button onClick={() => setMode('api')} className={mode === 'api' ? btnPrimary : btnSecondary}>
              Provider API
            </button>
          </div>

          {mode === 'file' ? (
            <div className="space-y-4">
              <div>
                <div className={label}>File CSV / Excel / Parquet</div>
                <div className="flex items-center gap-3">
                  <button onClick={() => fileRef.current?.click()} className={btnSecondary}>
                    Scegli file
                  </button>
                  {fileData && <span className="text-sm text-slate-400">{fileData.name}</span>}
                </div>
                <input ref={fileRef} type="file" className="hidden"
                  accept=".csv,.xlsx,.xls,.parquet" onChange={handleFile} />
                <p className="text-[11px] text-slate-600 mt-2">
                  Il file deve contenere almeno una colonna timestamp (date/time) e una colonna prezzo.
                  Nomi riconosciuti automaticamente: Date, Time, Datetime, Close, Open, High, Low, Volume, Adj Close.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <div className={label}>Provider</div>
                <select className={select} value={apiParams.provider} onChange={e => setA('provider', e.target.value)}>
                  <option value="stooq">Stooq (gratuito)</option>
                  <option value="yfinance">yfinance (fallback, inaffidabile)</option>
                  <option value="polygon">Polygon.io</option>
                  <option value="twelve_data">Twelve Data</option>
                  <option value="alpha_vantage">Alpha Vantage</option>
                </select>
              </div>
              <div>
                <div className={label}>Simbolo</div>
                <input className={input} placeholder="es. ^SPX, AAPL, EURUSD" value={apiParams.symbol}
                  onChange={e => setA('symbol', e.target.value)} />
              </div>
              <div>
                <div className={label}>Timeframe</div>
                <select className={select} value={apiParams.timeframe} onChange={e => setA('timeframe', e.target.value)}>
                  <option value="1d">Giornaliero (1d)</option>
                  <option value="1h">Orario (1h)</option>
                  <option value="4h">4 ore (4h)</option>
                  <option value="15m">15 minuti (15m)</option>
                  <option value="1w">Settimanale (1w)</option>
                </select>
              </div>
              <div>
                <div className={label}>Data inizio</div>
                <input type="date" className={input} value={apiParams.start} onChange={e => setA('start', e.target.value)} />
              </div>
              <div>
                <div className={label}>Data fine</div>
                <input type="date" className={input} value={apiParams.end} onChange={e => setA('end', e.target.value)} />
              </div>
              <div>
                <div className={label}>API Key (opzionale)</div>
                <input type="password" className={input} placeholder="Lascia vuoto per usare .env"
                  value={apiParams.api_key} onChange={e => setA('api_key', e.target.value)} />
              </div>
            </div>
          )}
        </div>

        {/* === SEZIONE 2: CONFIGURAZIONE === */}
        <div className={card}>
          <div className={sectionTitle}>2. Configurazione analisi</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className={label}>Colonna prezzo</div>
              <input className={input} value={config.price_column}
                onChange={e => setC('price_column', e.target.value)} />
              <p className="text-[10px] text-slate-600 mt-1">es. close, adjusted_close</p>
            </div>
            <div>
              <div className={label}>Trasformazione</div>
              <select className={select} value={config.series_transform}
                onChange={e => setC('series_transform', e.target.value as any)}>
                <option value="log_price">Log-prezzo (raccomandato)</option>
                <option value="price">Prezzo grezzo</option>
                <option value="returns">Rendimenti semplici</option>
                <option value="log_returns">Log-rendimenti</option>
              </select>
            </div>
            <div>
              <div className={label}>Tipo asset</div>
              <select className={select} value={config.asset_type}
                onChange={e => setC('asset_type', e.target.value as any)}>
                <option value="equity">Equity</option>
                <option value="fx">FX / Forex</option>
                <option value="crypto">Crypto</option>
                <option value="index">Indice</option>
              </select>
            </div>
            <div>
              <div className={label}>Gestione valori mancanti</div>
              <select className={select} value={config.fill_method ?? ''}
                onChange={e => setC('fill_method', e.target.value || null)}>
                <option value="">Rimuovi (default)</option>
                <option value="ffill">Forward fill</option>
                <option value="bfill">Backward fill</option>
              </select>
            </div>
          </div>
        </div>

        {/* === SEZIONE 3: IN/OUT SAMPLE === */}
        <div className={card}>
          <div className={sectionTitle}>3. Split In-sample / Out-of-sample</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className={label}>Metodo split</div>
              <select className={select} value={config.split_method}
                onChange={e => setC('split_method', e.target.value as any)}>
                <option value="ratio">Per proporzione</option>
                <option value="date">Per data</option>
                <option value="none">Nessuno split</option>
              </select>
            </div>
            {config.split_method === 'ratio' && (
              <div>
                <div className={label}>Ratio in-sample</div>
                <input type="number" min="0.1" max="0.95" step="0.05" className={input}
                  value={config.split_ratio} onChange={e => setC('split_ratio', parseFloat(e.target.value))} />
                <p className="text-[10px] text-slate-600 mt-1">es. 0.7 = 70% in-sample</p>
              </div>
            )}
            {config.split_method === 'date' && (
              <div>
                <div className={label}>Data di split</div>
                <input type="date" className={input} value={config.split_date}
                  onChange={e => setC('split_date', e.target.value)} />
              </div>
            )}
          </div>
        </div>

        {/* === SEZIONE 4: PARAMETRI TEST === */}
        <div className={card}>
          <div className={sectionTitle}>4. Parametri test statistici</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className={label}>ADF — Regressione</div>
              <select className={select} value={config.adf_regression}
                onChange={e => setC('adf_regression', e.target.value as any)}>
                <option value="c">Costante (c)</option>
                <option value="ct">Costante + trend (ct)</option>
                <option value="ctt">Costante + trend² (ctt)</option>
                <option value="n">Nessuno (n)</option>
              </select>
            </div>
            <div>
              <div className={label}>ADF — Autolag</div>
              <select className={select} value={config.adf_autolag ?? ''}
                onChange={e => setC('adf_autolag', e.target.value || null)}>
                <option value="AIC">AIC</option>
                <option value="BIC">BIC</option>
                <option value="t-stat">t-stat</option>
              </select>
            </div>
            <div>
              <div className={label}>Hurst — Rolling window</div>
              <input type="number" min="20" max="500" className={input}
                value={config.rolling_window} onChange={e => setC('rolling_window', parseInt(e.target.value))} />
            </div>
            <div>
              <div className={label}>VR — Lag (virgola-sep.)</div>
              <input className={input} value={config.vr_lags}
                onChange={e => setC('vr_lags', e.target.value)} />
            </div>
            <div>
              <div className={label}>Monte Carlo — Simulazioni</div>
              <input type="number" min="50" max="2000" step="50" className={input}
                value={config.mc_n_sims} onChange={e => setC('mc_n_sims', parseInt(e.target.value))} />
            </div>
            <div>
              <div className={label}>Monte Carlo — Metodo</div>
              <select className={select} value={config.mc_method}
                onChange={e => setC('mc_method', e.target.value as any)}>
                <option value="bootstrap">Bootstrap (raccomandato)</option>
                <option value="gbm">GBM (Browniano)</option>
                <option value="permutation">Permutation</option>
              </select>
            </div>
          </div>
        </div>

        {/* === AZIONE === */}
        <div className="flex items-center gap-4">
          <button onClick={run} disabled={loading} className={`${btnPrimary} px-8 py-3 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {loading ? 'Analisi in corso...' : 'Esegui analisi'}
          </button>
          {loading && (
            <p className="text-sm text-slate-400 animate-pulse">
              Calcolo in corso (ADF · Hurst · VR · Monte Carlo)...
            </p>
          )}
        </div>

        {error && (
          <div className="border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* === RISULTATI === */}
        {result && (
          <div id="mr-results" className="space-y-6">
            <div className="border-b border-slate-800 pb-3">
              <h2 className="text-lg font-semibold text-slate-100">Risultati dell'analisi</h2>
            </div>

            {/* Grafico serie storica */}
            {result.plots?.price && (
              <div className={card}>
                <div className={sectionTitle}>Serie storica</div>
                <img src={`data:image/png;base64,${result.plots.price}`} alt="Serie storica" className="w-full" />
              </div>
            )}

            {/* Verdetto */}
            <VerdictCard
              verdict={result.verdict}
              metadata={result.metadata}
              splitInfo={result.split_info}
            />

            {/* Pre-warnings */}
            {result.pre_warnings?.length > 0 && (
              <div className={card}>
                <div className={sectionTitle}>Avvisi pre-analisi</div>
                <Warnings items={result.pre_warnings} level="warn" />
              </div>
            )}

            {/* Qualità dati */}
            <QualityCard report={result.quality_report} />

            {/* Test ADF */}
            <AdfCard adf={result.adf} />

            {/* Hurst */}
            <HurstCard hurst={result.hurst} plotRolling={result.plots?.rolling_hurst} />

            {/* Variance Ratio */}
            <VRCard vr={result.variance_ratio} plotVR={result.plots?.variance_ratio} />

            {/* Monte Carlo */}
            <MCCard mc={result.monte_carlo} plots={result.plots} />

            {/* Data source info */}
            {result.data_source && (
              <div className={card}>
                <div className={sectionTitle}>Sorgente dati</div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <Stat label="Provider" value={result.data_source.provider} />
                  <Stat label="Simbolo" value={result.data_source.symbol} />
                  <Stat label="Timeframe" value={result.data_source.timeframe} />
                  <Stat label="Da" value={result.data_source.start} />
                  <Stat label="A" value={result.data_source.end} />
                </div>
              </div>
            )}
          </div>
        )}

      </main>
    </div>
  )
}
