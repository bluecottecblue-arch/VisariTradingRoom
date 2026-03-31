'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import AuthToolbar from '@/components/AuthToolbar'
import { dashboardApi, formatError } from '@/lib/api'
import type {
  CommandCenterDashboard,
  DashboardAlert,
  DashboardInsightBox,
  DashboardKpi,
  DashboardPosition,
  DashboardSignal,
  DashboardTone,
} from '@/types'
import { BarChart, LineChart, PanelFrame, SkeletonDesk, StatusPill, panelCls } from './visuals'

type DeskTab = 'performance' | 'risk' | 'execution' | 'fundamentals'
type DataSource = 'auto' | 'live' | 'real' | 'demo'

const tabs: Array<{ id: DeskTab; label: string }> = [
  { id: 'performance', label: 'Salute strategia' },
  { id: 'risk', label: 'Esposizione rischio' },
  { id: 'execution', label: 'Stato esecuzione' },
  { id: 'fundamentals', label: 'Contesto macro' },
]

const timeframeOptions = ['7D', '30D', '90D']

function toneText(tone: DashboardTone) {
  if (tone === 'positive') return 'text-cyan-300'
  if (tone === 'negative') return 'text-rose-300'
  if (tone === 'warning') return 'text-amber-300'
  return 'text-slate-100'
}

function toneBorder(tone: DashboardTone) {
  if (tone === 'positive') return 'border-cyan-900/70 bg-cyan-950/10'
  if (tone === 'negative') return 'border-rose-900/70 bg-rose-950/10'
  if (tone === 'warning') return 'border-amber-900/70 bg-amber-950/10'
  return 'border-slate-800 bg-slate-950/60'
}

function formatClock(value: string) {
  const date = new Date(value)
  return new Intl.DateTimeFormat('it-IT', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('it-IT', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

function formatDateInput(value: Date) {
  return value.toISOString().slice(0, 10)
}

function sourceModeLabel(mode?: string | null) {
  if (mode === 'live') return 'live'
  if (mode === 'real') return 'storico reale'
  if (mode === 'mock') return 'mock'
  return mode || 'desk'
}

function runtimeLabel(value: string) {
  const normalized = String(value || '').toUpperCase()
  if (normalized === 'BUY') return 'Compra'
  if (normalized === 'SELL') return 'Vendi'
  if (normalized === 'EXECUTED') return 'Eseguito'
  if (normalized === 'BLOCKED') return 'Bloccato'
  if (normalized === 'IGNORED') return 'Ignorato'
  if (normalized === 'LONG') return 'Long'
  if (normalized === 'SHORT') return 'Short'
  if (normalized === 'LIVE MONITOR') return 'MONITOR LIVE'
  if (normalized === 'BACKTEST REVIEW') return 'REVISIONE BACKTEST'
  if (normalized === 'DEMO DESK') return 'DESK DEMO'
  if (normalized === 'PAPER DESK') return 'DESK PAPER'
  if (normalized === 'CONNECTED') return 'Connesso'
  if (normalized === 'READY') return 'Pronto'
  if (normalized === 'ENABLED') return 'Attivo'
  if (normalized === 'INACTIVE') return 'Inattivo'
  if (normalized === 'ARMED') return 'Attivo'
  if (normalized === 'NOMINAL') return 'Nominale'
  return value
}

function buildDeskBadges(dashboard: CommandCenterDashboard) {
  const badges: Array<{ label: string; tone: DashboardTone }> = []
  const { header, risk_panel, market_panel, tech_panel, source_mode } = dashboard

  if (
    header.strategy_health_score >= 78 &&
    risk_panel.max_drawdown_pct < 10 &&
    risk_panel.daily_loss_used_pct < 70 &&
    source_mode !== 'mock'
  ) {
    badges.push({ label: 'STABILE', tone: 'positive' })
  }
  if (
    risk_panel.max_drawdown_pct >= 10 ||
    tech_panel.warnings.length > 0 ||
    String(market_panel.volatility).toLowerCase().includes('high')
  ) {
    badges.push({ label: 'FRAGILE', tone: 'warning' })
  }
  if (
    risk_panel.risk_usage_pct >= 75 ||
    risk_panel.daily_loss_used_pct >= 80 ||
    risk_panel.max_drawdown_pct >= 14
  ) {
    badges.push({ label: 'ALTO RISCHIO', tone: 'negative' })
  }
  if (
    market_panel.news_risk_active ||
    market_panel.news_events > 0 ||
    !['inactive', 'inattivo'].includes(String(market_panel.macro_filter_status).toLowerCase())
  ) {
    badges.push({ label: 'SENSIBILE AL MACRO', tone: 'warning' })
  }
  if (
    header.strategy_health_score < 70 ||
    source_mode === 'mock' ||
    risk_panel.warnings.length > 0
  ) {
    badges.push({ label: 'DA RICERCARE', tone: 'neutral' })
  }

  return badges.slice(0, 5)
}

function buildSupervisoryAlerts(dashboard: CommandCenterDashboard) {
  const alerts = [...dashboard.alerts]
  const titles = new Set(alerts.map((alert) => alert.title))
  const maybePush = (title: string, detail: string, tone: DashboardTone) => {
    if (titles.has(title)) return
    titles.add(title)
    alerts.push({ title, detail, tone })
  }

  if (dashboard.risk_panel.max_drawdown_pct >= 10) {
    maybePush(
      'Drawdown in avvicinamento',
      `Il max drawdown è a ${dashboard.risk_panel.max_drawdown_pct.toFixed(1)}%. Riduci budget di rischio o esposizione prima della prossima fase di degrado.`,
      dashboard.risk_panel.max_drawdown_pct >= 14 ? 'negative' : 'warning',
    )
  }

  if (
    String(dashboard.market_panel.volatility).toLowerCase().includes('high') ||
    dashboard.risk_panel.var_proxy_pct >= 2.5
  ) {
    maybePush(
      'Spike di volatilità',
      'Il desk sta operando sotto pressione di volatilità elevata. Rivedi qualità esecuzione e posizionamento degli stop prima di aumentare il rischio.',
      'warning',
    )
  }

  if (
    String(dashboard.market_panel.regime).toLowerCase().includes('range') ||
    String(dashboard.market_panel.regime).toLowerCase().includes('transition')
  ) {
    maybePush(
      'Cambio regime rilevato',
      `Il regime corrente è ${dashboard.market_panel.regime}. Un cambio di struttura di mercato può invalidare le assunzioni che reggevano nelle fasi recenti di espansione.`,
      'warning',
    )
  }

  if (dashboard.market_panel.news_risk_active || dashboard.market_panel.news_events > 0) {
    maybePush(
      'Finestra macro attiva',
      `${dashboard.market_panel.news_events} evento/i monitorati rientrano nella finestra di rischio attiva. Conferma che i filtri sensibili al macro siano ancora allineati prima di nuovi ingressi.`,
      'warning',
    )
  }

  if (dashboard.tech_panel.jobs_running > 0) {
    maybePush(
      'Pipeline di ricerca in aggiornamento',
      `${dashboard.tech_panel.jobs_running} job di workflow sono ancora in esecuzione. Considera il desk supervisionato, non finale, finché la coda non si svuota.`,
      'neutral',
    )
  }

  return alerts
}

function buildDriftMonitor(dashboard: CommandCenterDashboard) {
  const equity = dashboard.charts.equity_curve || []
  const drawdown = dashboard.charts.drawdown_curve || []
  const recentAnchor = equity.length >= 6 ? equity[equity.length - 6].value : equity[0]?.value || 0
  const latestEquity = equity[equity.length - 1]?.value || 0
  const recentReturn = recentAnchor ? ((latestEquity / recentAnchor) - 1) * 100 : 0
  const latestDrawdown = drawdown[drawdown.length - 1]?.value || 0

  if (dashboard.source_mode === 'mock') {
    return {
      status: 'ADAPTER PRONTO',
      tone: 'warning' as DashboardTone,
      summary: 'Il layer è pronto a confrontare live feed e profilo validato appena colleghi telemetria broker o statement.',
      metrics: [
        { label: 'Feed', value: dashboard.tech_panel.data_feed_status },
        { label: 'Export', value: dashboard.tech_panel.export_status },
        { label: 'Regime', value: dashboard.market_panel.regime },
        { label: 'Rischio', value: `${dashboard.risk_panel.risk_usage_pct.toFixed(0)}%` },
      ],
      watchItems: [
        'Collega un feed reale o uno statement importer.',
        'Confronta PnL live, drawdown e frequenza trade con la validazione.',
        'Interrompi subito se il bot si comporta fuori profilo.',
      ],
    }
  }

  let status = 'IN TRACKING'
  let tone: DashboardTone = 'positive'
  let summary = 'Traiettoria sotto controllo: il comportamento recente resta coerente con il profilo validato.'

  if (recentReturn < -1.5 || latestDrawdown <= -6 || dashboard.risk_panel.daily_loss_used_pct >= 80) {
    status = 'IN DERIVA'
    tone = 'negative'
    summary = 'Il profilo operativo sta degenerando: serve confronto immediato con la validazione prima di mantenere il bot attivo.'
  } else if (
    recentReturn < 0 ||
    dashboard.market_panel.news_risk_active ||
    String(dashboard.market_panel.volatility).toLowerCase().includes('high') ||
    dashboard.risk_panel.risk_usage_pct >= 70
  ) {
    status = 'SORVEGLIA'
    tone = 'warning'
    summary = 'Il bot richiede sorveglianza: regime, volatilità o pressione rischio possono spostare il profilo oltre il range validato.'
  }

  return {
    status,
    tone,
    summary,
    metrics: [
      { label: 'Ultime 5 barre', value: `${recentReturn >= 0 ? '+' : ''}${recentReturn.toFixed(2)}%` },
      { label: 'DD attuale', value: `${latestDrawdown.toFixed(2)}%` },
      { label: 'Regime', value: dashboard.market_panel.regime },
      { label: 'Loss guard', value: `${dashboard.risk_panel.daily_loss_used_pct.toFixed(0)}%` },
    ],
    watchItems: [
      'Confronta il PnL recente con il range atteso del backtest.',
      'Sorveglia drawdown, frequenza trade e qualità esecuzione.',
      'Metti in pausa se il regime cambia o il risk usage resta elevato.',
    ],
  }
}

function buildDeploymentGovernance(dashboard: CommandCenterDashboard) {
  const exportStatus = dashboard.tech_panel.export_status.toLowerCase()
  const providerStatus = dashboard.tech_panel.provider_status.toLowerCase()
  const exportReady = exportStatus.includes('ready') || exportStatus.includes('pronto')
  const macroStatus = dashboard.market_panel.macro_filter_status.toLowerCase()
  const macroArmed = macroStatus !== 'inactive' && macroStatus !== 'inattivo'
  const providerReady = !providerStatus.includes('no ') && !providerStatus.includes('nessun')
  const jobsClear = dashboard.tech_panel.jobs_running === 0
  const controls = [
    exportReady ? 'Pacchetto export pronto.' : 'Pacchetto export non ancora chiuso.',
    `Kill switch ${dashboard.risk_panel.kill_switch_status.toLowerCase()}.`,
    macroArmed ? 'Filtro macro attivo sul runtime.' : 'Filtro macro non attivo sul runtime.',
    jobsClear ? 'Pipeline ferma e verificabile.' : 'Chiudi i job attivi prima del deploy.',
  ]
  const pauseTriggers = [
    'Errori Journal o warning runtime persistenti.',
    'Drawdown oltre soglia o daily loss guard vicino al limite.',
    'Cambio regime con edge non confermato.',
    'Mismatch evidente tra segnali live e logica validata.',
  ]

  let stage = 'CONTROLLATO'
  let tone: DashboardTone = 'positive'
  let summary = 'La governance controlla quando il bot può restare attivo, quando va osservato e quando va fermato.'

  if (!exportReady || !providerReady || !jobsClear) {
    stage = 'PRE-LANCIO'
    tone = 'warning'
    summary = 'Il bot non è ancora in uno stato pulito di handoff operativo. Completa setup, export e feed prima del deploy.'
  }
  if (dashboard.risk_panel.kill_switch_status !== 'NOMINAL' || dashboard.risk_panel.daily_loss_used_pct >= 80) {
    stage = 'LIMITATO'
    tone = 'negative'
    summary = 'Il bot deve operare solo con presidio stretto o restare fermo finché il profilo di rischio non rientra.'
  }

  return {
    stage,
    tone,
    summary,
    cadence: stage === 'CONTROLLED'
      ? 'Review giornaliera + confronto settimanale con il profilo validato.'
      : 'Review intraday finché i controlli non rientrano.',
    controls,
    pauseTriggers,
  }
}

function DashboardKpiTile({ item }: { item: DashboardKpi }) {
  return (
    <div className={`${panelCls} px-4 py-4`}>
      <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{item.label}</div>
      <div className={`mt-3 text-2xl font-semibold ${toneText(item.tone)}`}>{item.value}</div>
      {item.detail && <div className="mt-2 text-xs leading-relaxed text-slate-500">{item.detail}</div>}
    </div>
  )
}

function InsightCard({ item }: { item: DashboardInsightBox }) {
  return (
    <div className={`border px-4 py-4 ${toneBorder(item.tone)}`}>
      <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{item.label}</div>
      <div className={`mt-2 text-xl font-semibold ${toneText(item.tone)}`}>{item.value}</div>
      <div className="mt-2 text-sm leading-relaxed text-slate-400">{item.detail}</div>
    </div>
  )
}

function AlertList({ alerts }: { alerts: DashboardAlert[] }) {
  if (!alerts.length) {
    return (
      <div className="border border-dashed border-slate-800 px-4 py-8 text-sm text-slate-500">
        Nessun avviso attivo nel command center.
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {alerts.map((alert, index) => (
        <div key={`${alert.title}-${index}`} className={`border px-4 py-4 ${toneBorder(alert.tone)}`}>
          <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{alert.title}</div>
          <div className="mt-2 text-sm leading-relaxed text-slate-300">{alert.detail}</div>
        </div>
      ))}
    </div>
  )
}

function SignalsTable({ items }: { items: DashboardSignal[] }) {
  if (!items.length) {
    return <div className="text-sm text-slate-500">Nessun segnale disponibile per la modalità desk selezionata.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
          <tr>
            <th className="pb-3">Ora</th>
            <th className="pb-3">Simbolo</th>
            <th className="pb-3">Lato</th>
            <th className="pb-3">Stato</th>
            <th className="pb-3 text-right">Prezzo</th>
            <th className="pb-3">Motivo</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/80 text-slate-300">
          {items.map((item) => (
            <tr key={item.id}>
              <td className="py-3 pr-4 text-slate-500">{formatClock(item.timestamp)}</td>
              <td className="py-3 pr-4 font-medium text-slate-100">{item.symbol}</td>
              <td className={`py-3 pr-4 ${item.side === 'BUY' ? 'text-cyan-300' : 'text-rose-300'}`}>{runtimeLabel(item.side)}</td>
              <td className="py-3 pr-4">
                <StatusPill
                  label={runtimeLabel(item.status)}
                  tone={item.status === 'EXECUTED' ? 'positive' : item.status === 'BLOCKED' ? 'warning' : 'neutral'}
                />
              </td>
              <td className="py-3 pr-4 text-right">{item.price.toFixed(4)}</td>
              <td className="py-3 text-slate-500">{item.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PositionsTable({ items }: { items: DashboardPosition[] }) {
  if (!items.length) {
    return <div className="text-sm text-slate-500">Nessuna posizione aperta nella modalità operativa corrente.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
          <tr>
            <th className="pb-3">Simbolo</th>
            <th className="pb-3">Lato</th>
            <th className="pb-3 text-right">Size</th>
            <th className="pb-3 text-right">Ingresso</th>
            <th className="pb-3 text-right">PnL</th>
            <th className="pb-3 text-right">Stop</th>
            <th className="pb-3 text-right">TP</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/80 text-slate-300">
          {items.map((item) => (
            <tr key={item.id}>
              <td className="py-3 pr-4 font-medium text-slate-100">{item.symbol}</td>
              <td className={`py-3 pr-4 ${item.side === 'LONG' ? 'text-cyan-300' : 'text-rose-300'}`}>{runtimeLabel(item.side)}</td>
              <td className="py-3 pr-4 text-right">{item.size.toFixed(2)}</td>
              <td className="py-3 pr-4 text-right">{item.entry.toFixed(4)}</td>
              <td className={`py-3 pr-4 text-right ${item.pnl >= 0 ? 'text-cyan-300' : 'text-rose-300'}`}>{formatMoney(item.pnl)}</td>
              <td className="py-3 pr-4 text-right">{item.stop.toFixed(4)}</td>
              <td className="py-3 text-right">{item.take_profit.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function KeyValueGrid({
  items,
}: {
  items: Array<{ label: string; value: string | number; tone?: DashboardTone }>
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((item) => (
        <div key={item.label} className="border border-slate-900/80 bg-slate-950/60 px-4 py-3">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{item.label}</div>
          <div className={`mt-2 text-lg font-semibold ${toneText(item.tone || 'neutral')}`}>{item.value}</div>
        </div>
      ))}
    </div>
  )
}

export default function CommandCenterClient({ initialProjectId = null }: { initialProjectId?: string | null }) {
  const [dashboard, setDashboard] = useState<CommandCenterDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(initialProjectId)
  const [timeframe, setTimeframe] = useState('30D')
  const [source, setSource] = useState<DataSource>('auto')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [activeTab, setActiveTab] = useState<DeskTab>('performance')
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const response = await dashboardApi.commandCenter({
          projectId: selectedProjectId,
          timeframe,
          source,
          dateFrom: dateFrom || undefined,
          dateTo: source === 'live' ? undefined : dateTo || undefined,
        }) as { dashboard: CommandCenterDashboard }
        if (cancelled) return
        const next = response.dashboard
        setDashboard(next)
        if (next.selected_project_id && next.selected_project_id !== selectedProjectId) {
          setSelectedProjectId(next.selected_project_id)
        }
      } catch (err) {
        if (!cancelled) {
          setError(formatError(err))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [selectedProjectId, timeframe, source, dateFrom, dateTo, reloadToken])

  const topInsights = useMemo(() => dashboard?.insight_boxes.slice(0, 4) || [], [dashboard])
  const deskBadges = useMemo(() => (dashboard ? buildDeskBadges(dashboard) : []), [dashboard])
  const supervisoryAlerts = useMemo(() => (dashboard ? buildSupervisoryAlerts(dashboard) : []), [dashboard])
  const driftMonitor = useMemo(() => (dashboard ? buildDriftMonitor(dashboard) : null), [dashboard])
  const governanceLayer = useMemo(() => (dashboard ? buildDeploymentGovernance(dashboard) : null), [dashboard])

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(14,116,144,0.16),transparent_25%),radial-gradient(circle_at_top_right,rgba(15,23,42,0.36),transparent_34%),linear-gradient(180deg,#020617_0%,#020617_100%)] text-slate-100">
      <div className="border-b border-slate-800/90 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1680px] flex-col gap-5 px-6 py-5 lg:flex-row lg:items-end lg:justify-between lg:px-8">
          <div className="space-y-4 md:pl-8">
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Visari Trading Room</div>
              <StatusPill label={runtimeLabel(dashboard?.header.status || 'Desk')} tone={dashboard?.header.status_tone || 'neutral'} />
              {dashboard && <StatusPill label={sourceModeLabel(dashboard.source_mode)} tone={dashboard.source_mode === 'mock' ? 'warning' : 'positive'} />}
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-50 lg:text-4xl">
                Desk algoritmi
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
                Governa ricerca, rischio, drift operativo e deploy in un'unica control room.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-xs text-slate-500">
              <span>Progetto: {dashboard?.selected_project_title || 'Anteprima desk'}</span>
              <span>Sessione mercato: {dashboard?.header.market_session || '—'}</span>
              <span>Modalità desk: {dashboard?.header.desk_mode || '—'}</span>
              <span>Ora: {dashboard ? formatClock(dashboard.header.current_time) : '—'}</span>
            </div>
          </div>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-end gap-3">
              <Link href="/workspace" className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-400 hover:border-slate-600 hover:text-slate-100">
                Strategie
              </Link>
              <button
                onClick={() => setReloadToken((value) => value + 1)}
                className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-400 hover:border-slate-600 hover:text-slate-100"
              >
                Aggiorna
              </button>
              <AuthToolbar />
            </div>
            <div className="grid gap-3 md:grid-cols-4">
              <label className="space-y-2">
                <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Progetto</span>
                <select
                  value={selectedProjectId || ''}
                  onChange={(event) => setSelectedProjectId(event.target.value || null)}
                  className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-600"
                >
                  <option value="">Anteprima desk</option>
                  {(dashboard?.available_projects || []).map((project) => (
                    <option key={project.project_id} value={project.project_id}>
                      {project.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Timeframe</span>
                <select
                  value={timeframe}
                  onChange={(event) => setTimeframe(event.target.value)}
                  className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-600"
                >
                  {timeframeOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Sorgente dati</span>
                <select
                  value={source}
                  onChange={(event) => setSource(event.target.value as DataSource)}
                  className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-600"
                >
                  <option value="auto">Auto / migliore disponibile</option>
                  <option value="live">Solo live</option>
                  <option value="real">Solo dati reali</option>
                  <option value="demo">Demo professionale</option>
                </select>
              </label>
              <div className="space-y-2">
                <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Monitor live</span>
                <button
                  type="button"
                  onClick={() => {
                    setSource('live')
                    setActiveTab('execution')
                    if (!dateFrom) {
                      const start = new Date()
                      start.setDate(start.getDate() - 7)
                      setDateFrom(formatDateInput(start))
                    }
                  }}
                  className="w-full border border-slate-800 px-3 py-2.5 text-sm text-slate-100 transition-colors hover:border-slate-600"
                >
                  Apri monitor live
                </button>
              </div>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                  {source === 'live' ? 'Inizio live' : 'Data inizio'}
                </span>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(event) => setDateFrom(event.target.value)}
                  className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-600"
                />
              </label>
              {source !== 'live' ? (
                <label className="space-y-2">
                  <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Data fine</span>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(event) => setDateTo(event.target.value)}
                    className="w-full border border-slate-800 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-slate-600"
                  />
                </label>
              ) : (
                <div className="space-y-2">
                  <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Data fine</span>
                  <div className="w-full border border-slate-900 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-500">Adesso</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-[1680px] px-6 py-8 lg:px-8">
        {loading && <SkeletonDesk />}

        {!loading && error && (
          <div className="border border-rose-900/80 bg-rose-950/10 px-6 py-8 text-sm text-rose-200">
            Impossibile caricare il desk algoritmi: {error}
          </div>
        )}

        {!loading && !error && dashboard && (
          <div className="space-y-6">
            <section className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
              <div className={`${panelCls} relative overflow-hidden px-5 py-5`}>
                <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-500/60 to-transparent" />
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-4">
                    <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Desk attivo</div>
                    <div className="text-3xl font-semibold tracking-tight text-slate-50">{dashboard.header.bot_label}</div>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusPill label={dashboard.header.status} tone={dashboard.header.status_tone} />
                      <StatusPill label={dashboard.header.connection_status} tone={dashboard.header.connection_tone} />
                      <StatusPill label={dashboard.header.strategy_health_label} tone={dashboard.header.strategy_health_score >= 70 ? 'positive' : 'warning'} />
                      {deskBadges.map((badge) => (
                        <StatusPill key={badge.label} label={badge.label} tone={badge.tone} />
                      ))}
                    </div>
                  </div>
                  <div className="min-w-[240px] border border-slate-900/80 bg-slate-950/70 px-4 py-4">
                    <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Salute strategia</div>
                    <div className="mt-3 text-4xl font-semibold text-slate-50">{dashboard.header.strategy_health_score}</div>
                    <div className="mt-2 text-sm text-slate-400">{dashboard.header.source_label} · Valutazione supportata dalla ricerca</div>
                    <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-500">
                      <div>
                        <div className="uppercase tracking-[0.14em] text-slate-600">Sessione</div>
                        <div className="mt-1 text-slate-300">{dashboard.header.market_session}</div>
                      </div>
                      <div>
                        <div className="uppercase tracking-[0.14em] text-slate-600">Aggiornato</div>
                        <div className="mt-1 text-slate-300">{formatClock(dashboard.as_of)}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
                {topInsights.map((item) => (
                  <InsightCard key={item.label} item={item} />
                ))}
              </div>
            </section>

            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {dashboard.kpis.map((item) => (
                <DashboardKpiTile key={item.id} item={item} />
              ))}
            </section>

            <section className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
              <PanelFrame title="Curva equity" eyebrow="Asse primario della performance">
                <LineChart
                  points={dashboard.charts.equity_curve}
                  color="#22d3ee"
                  valueFormatter={(value) => formatMoney(value)}
                />
              </PanelFrame>

              <PanelFrame title="Avvisi di supervisione" eyebrow="Watchlist rischio, regime ed esecuzione">
                <AlertList alerts={supervisoryAlerts} />
              </PanelFrame>
            </section>

            <section className="grid gap-4 xl:grid-cols-[0.95fr_0.55fr_0.5fr]">
              <PanelFrame title="Profilo drawdown" eyebrow="Compressione del capitale">
                <LineChart
                  points={dashboard.charts.drawdown_curve}
                  color="#fb7185"
                  fill={false}
                  valueFormatter={(value) => `${value.toFixed(2)}%`}
                />
              </PanelFrame>

              <PanelFrame title="Distribuzione PnL" eyebrow="Raggruppamento degli esiti">
                <BarChart bars={dashboard.charts.pnl_distribution} color="#38bdf8" />
              </PanelFrame>

              <PanelFrame title="Mappa esposizione" eyebrow="Istantanea allocazione capitale">
                <BarChart bars={dashboard.charts.exposure_map} color="#14b8a6" />
              </PanelFrame>
            </section>

            <section className={panelCls}>
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/90 px-4 py-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Tab di controllo</div>
                  <div className="mt-1 text-sm font-semibold text-slate-100">Moduli di supervisione strutturata</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {tabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`border px-3 py-2 text-[11px] uppercase tracking-[0.16em] ${
                        activeTab === tab.id
                          ? 'border-cyan-900/80 bg-cyan-950/15 text-cyan-300'
                          : 'border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-200'
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-4">
                {activeTab === 'performance' && (
                  <div className="grid gap-4 xl:grid-cols-2">
                    <PanelFrame title="Cosa è cambiato oggi" eyebrow="Delta operativo">
                      <div className="space-y-3">
                        {(dashboard.recent_changes || []).map((item, index) => (
                          <div key={`${item}-${index}`} className="border border-slate-900/80 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                            {item}
                          </div>
                        ))}
                      </div>
                    </PanelFrame>
                    <PanelFrame title="Salute strategia" eyebrow="Postura centrale del desk">
                      <KeyValueGrid
                        items={[
                          { label: 'Modalità operativa', value: dashboard.operating_mode },
                          { label: 'Sorgente', value: sourceModeLabel(dashboard.source_mode) },
                          { label: 'Punteggio salute', value: `${dashboard.header.strategy_health_score}/100`, tone: dashboard.header.strategy_health_score >= 70 ? 'positive' : 'warning' },
                          { label: 'Sessione desk', value: dashboard.header.market_session },
                          { label: 'Connessione', value: dashboard.header.connection_status, tone: dashboard.header.connection_tone },
                          { label: 'Ora corrente', value: formatClock(dashboard.header.current_time) },
                        ]}
                      />
                    </PanelFrame>
                    {driftMonitor && (
                      <PanelFrame title="Monitor drift" eyebrow="Controllo backtest-to-live">
                        <div className={`border px-4 py-4 ${toneBorder(driftMonitor.tone)}`}>
                          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{driftMonitor.status}</div>
                          <div className="mt-2 text-sm leading-relaxed text-slate-300">{driftMonitor.summary}</div>
                        </div>
                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          {driftMonitor.metrics.map((item) => (
                            <div key={item.label} className="border border-slate-900/80 bg-slate-950/60 px-4 py-3">
                              <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{item.label}</div>
                              <div className="mt-2 text-sm font-semibold text-slate-100">{item.value}</div>
                            </div>
                          ))}
                        </div>
                      </PanelFrame>
                    )}
                    {governanceLayer && (
                      <PanelFrame title="Governance deploy" eyebrow="Layer di controllo produzione">
                        <div className={`border px-4 py-4 ${toneBorder(governanceLayer.tone)}`}>
                          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{governanceLayer.stage}</div>
                          <div className="mt-2 text-sm leading-relaxed text-slate-300">{governanceLayer.summary}</div>
                          <div className="mt-3 text-xs text-slate-500">{governanceLayer.cadence}</div>
                        </div>
                        <div className="mt-4 grid gap-4 md:grid-cols-2">
                          <div className="space-y-2">
                            {governanceLayer.controls.map((item, index) => (
                              <div key={index} className="border border-slate-900/80 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">{item}</div>
                            ))}
                          </div>
                          <div className="space-y-2">
                            {governanceLayer.pauseTriggers.map((item, index) => (
                              <div key={index} className="border border-amber-900/50 bg-amber-950/10 px-4 py-3 text-sm text-amber-200">{item}</div>
                            ))}
                          </div>
                        </div>
                      </PanelFrame>
                    )}
                  </div>
                )}

                {activeTab === 'risk' && (
                  <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                    <PanelFrame title="Esposizione rischio" eyebrow="Perdita giornaliera, esposizione e kill switch">
                      <KeyValueGrid
                        items={[
                          { label: 'Uso rischio', value: `${dashboard.risk_panel.risk_usage_pct.toFixed(1)}%`, tone: dashboard.risk_panel.risk_usage_pct >= 70 ? 'warning' : 'neutral' },
                          { label: 'VaR Proxy', value: `${dashboard.risk_panel.var_proxy_pct.toFixed(2)}%`, tone: 'warning' },
                          { label: 'Leverage Proxy', value: dashboard.risk_panel.leverage_proxy.toFixed(2) },
                          { label: 'Esposizione', value: `${dashboard.risk_panel.exposure_pct.toFixed(1)}%` },
                          { label: 'Perdita giornaliera usata', value: `${dashboard.risk_panel.daily_loss_used_pct.toFixed(1)}%`, tone: dashboard.risk_panel.daily_loss_used_pct >= 80 ? 'negative' : 'warning' },
                          { label: 'Kill Switch', value: dashboard.risk_panel.kill_switch_status, tone: dashboard.risk_panel.kill_switch_status === 'NOMINAL' ? 'positive' : 'warning' },
                          { label: 'Max drawdown', value: `${dashboard.risk_panel.max_drawdown_pct.toFixed(2)}%`, tone: 'negative' },
                        ]}
                      />
                    </PanelFrame>
                    <PanelFrame title="Note rischio" eyebrow="Avvisi che richiedono supervisione umana">
                      {dashboard.risk_panel.warnings.length ? (
                        <div className="space-y-3">
                          {dashboard.risk_panel.warnings.map((warning, index) => (
                            <div key={`${warning}-${index}`} className="border border-amber-900/70 bg-amber-950/10 px-4 py-3 text-sm text-amber-200">
                              {warning}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-sm text-slate-500">Nessun avviso di rischio attivo nella vista desk corrente.</div>
                      )}
                    </PanelFrame>
                  </div>
                )}

                {activeTab === 'execution' && (
                  <div className="grid gap-4">
                    <PanelFrame title="Segnali recenti" eyebrow="Flusso decisionale più recente">
                      <SignalsTable items={dashboard.recent_signals} />
                    </PanelFrame>
                    <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
                      <PanelFrame title="Posizioni aperte" eyebrow="Esposizione runtime">
                        <PositionsTable items={dashboard.open_positions} />
                      </PanelFrame>
                      <PanelFrame title="Stato esecuzione" eyebrow="Stack runtime">
                        <KeyValueGrid
                          items={[
                            { label: 'Provider dati', value: dashboard.tech_panel.data_provider },
                            { label: 'Feed dati', value: dashboard.tech_panel.data_feed_status },
                            { label: 'Parser', value: dashboard.tech_panel.parser_status },
                            { label: 'Engine', value: dashboard.tech_panel.engine_status },
                            { label: 'Stato provider', value: dashboard.tech_panel.provider_status },
                            { label: 'Stato export', value: dashboard.tech_panel.export_status },
                            { label: 'Latenza', value: `${dashboard.tech_panel.latency_ms} ms` },
                            { label: 'Artefatti pronti', value: dashboard.tech_panel.artifacts_ready },
                            { label: 'Job attivi', value: dashboard.tech_panel.jobs_running },
                            { label: 'Ultima sync', value: formatClock(dashboard.tech_panel.last_sync) },
                          ]}
                        />
                        {dashboard.live_monitor && (
                          <div className="mt-4 space-y-3 border-t border-slate-800/80 pt-4">
                            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Collegamento live</div>
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="border border-slate-900/80 bg-slate-950/60 px-4 py-3">
                                <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Stato</div>
                                <div className="mt-2 text-sm font-semibold text-slate-100">
                                  {dashboard.live_monitor.connected ? 'Connesso' : 'Pronto'}
                                </div>
                              </div>
                              <div className="border border-slate-900/80 bg-slate-950/60 px-4 py-3">
                                <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Primo ingest</div>
                                <div className="mt-2 text-sm font-semibold text-slate-100">
                                  {dashboard.live_monitor.first_ingest_at ? formatClock(dashboard.live_monitor.first_ingest_at) : '—'}
                                </div>
                              </div>
                              <div className="border border-slate-900/80 bg-slate-950/60 px-4 py-3">
                                <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Ultimo ingest</div>
                                <div className="mt-2 text-sm font-semibold text-slate-100">
                                  {dashboard.live_monitor.last_ingest_at ? formatClock(dashboard.live_monitor.last_ingest_at) : '—'}
                                </div>
                              </div>
                              <div className="border border-slate-900/80 bg-slate-950/60 px-4 py-3">
                                <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Endpoint</div>
                                <div className="mt-2 break-all font-mono text-xs text-slate-300">{dashboard.live_monitor.ingest_path}</div>
                              </div>
                              <div className="border border-slate-900/80 bg-slate-950/60 px-4 py-3">
                                <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Token progetto</div>
                                <div className="mt-2 break-all font-mono text-xs text-slate-300">{dashboard.live_monitor.monitor_token || '—'}</div>
                              </div>
                            </div>
                          </div>
                        )}
                      </PanelFrame>
                    </div>
                  </div>
                )}

                {activeTab === 'fundamentals' && (
                  <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
                    <PanelFrame title="Contesto macro" eyebrow="Contesto desk sensibile al macro">
                      <KeyValueGrid
                        items={[
                          { label: 'Regime', value: dashboard.market_panel.regime },
                          { label: 'Volatilità', value: dashboard.market_panel.volatility },
                          { label: 'Sessione', value: dashboard.market_panel.session },
                          { label: 'Rischio news', value: dashboard.market_panel.news_risk_active ? 'Attivo' : 'Inattivo', tone: dashboard.market_panel.news_risk_active ? 'warning' : 'neutral' },
                          { label: 'Provider news', value: dashboard.market_panel.news_provider },
                          { label: 'Eventi in finestra', value: dashboard.market_panel.news_events },
                          { label: 'Filtro macro', value: dashboard.market_panel.macro_filter_status },
                          { label: 'Bias direzionale', value: dashboard.market_panel.directional_bias },
                        ]}
                      />
                    </PanelFrame>
                    <PanelFrame title="Note macro / provider" eyebrow="Commento desk">
                      {dashboard.market_panel.warnings.length ? (
                        <div className="space-y-3">
                          {dashboard.market_panel.warnings.map((warning, index) => (
                            <div key={`${warning}-${index}`} className="border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                              {warning}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-sm text-slate-500">Nessun avviso macro attivo per la vista desk selezionata.</div>
                      )}
                    </PanelFrame>
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  )
}
