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
type DataSource = 'auto' | 'real' | 'demo'

const tabs: Array<{ id: DeskTab; label: string }> = [
  { id: 'performance', label: 'Strategy Health' },
  { id: 'risk', label: 'Risk Exposure' },
  { id: 'execution', label: 'Execution Status' },
  { id: 'fundamentals', label: 'Macro Context' },
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
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
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
    badges.push({ label: 'STABLE', tone: 'positive' })
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
    badges.push({ label: 'HIGH RISK', tone: 'negative' })
  }
  if (
    market_panel.news_risk_active ||
    market_panel.news_events > 0 ||
    String(market_panel.macro_filter_status).toLowerCase() !== 'inactive'
  ) {
    badges.push({ label: 'MACRO SENSITIVE', tone: 'warning' })
  }
  if (
    header.strategy_health_score < 70 ||
    source_mode !== 'real' ||
    risk_panel.warnings.length > 0
  ) {
    badges.push({ label: 'RESEARCH CANDIDATE', tone: 'neutral' })
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
      'Drawdown threshold approaching',
      `Max drawdown is at ${dashboard.risk_panel.max_drawdown_pct.toFixed(1)}%. Tighten risk budget or reduce exposure before the next degradation phase.`,
      dashboard.risk_panel.max_drawdown_pct >= 14 ? 'negative' : 'warning',
    )
  }

  if (
    String(dashboard.market_panel.volatility).toLowerCase().includes('high') ||
    dashboard.risk_panel.var_proxy_pct >= 2.5
  ) {
    maybePush(
      'Volatility spike detected',
      'The desk is operating under elevated volatility pressure. Execution quality and stop placement should be reviewed before scaling risk.',
      'warning',
    )
  }

  if (
    String(dashboard.market_panel.regime).toLowerCase().includes('range') ||
    String(dashboard.market_panel.regime).toLowerCase().includes('transition')
  ) {
    maybePush(
      'Regime shift detected',
      `Current regime reads ${dashboard.market_panel.regime}. A change in market structure may invalidate assumptions that held during recent expansion phases.`,
      'warning',
    )
  }

  if (dashboard.market_panel.news_risk_active || dashboard.market_panel.news_events > 0) {
    maybePush(
      'Macro window active',
      `${dashboard.market_panel.news_events} monitored event(s) sit inside the active risk window. Confirm that macro-sensitive filters remain aligned before new entries.`,
      'warning',
    )
  }

  if (dashboard.tech_panel.jobs_running > 0) {
    maybePush(
      'Research pipeline updating',
      `${dashboard.tech_panel.jobs_running} workflow job(s) are still running. Treat the desk as supervised rather than final until the processing queue clears.`,
      'neutral',
    )
  }

  return alerts
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
        No active alerts on the command center.
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
    return <div className="text-sm text-slate-500">No signals available for the selected desk mode.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
          <tr>
            <th className="pb-3">Time</th>
            <th className="pb-3">Symbol</th>
            <th className="pb-3">Side</th>
            <th className="pb-3">Status</th>
            <th className="pb-3 text-right">Price</th>
            <th className="pb-3">Reason</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/80 text-slate-300">
          {items.map((item) => (
            <tr key={item.id}>
              <td className="py-3 pr-4 text-slate-500">{formatClock(item.timestamp)}</td>
              <td className="py-3 pr-4 font-medium text-slate-100">{item.symbol}</td>
              <td className={`py-3 pr-4 ${item.side === 'BUY' ? 'text-cyan-300' : 'text-rose-300'}`}>{item.side}</td>
              <td className="py-3 pr-4">
                <StatusPill
                  label={item.status}
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
    return <div className="text-sm text-slate-500">No open positions in the current operating mode.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
          <tr>
            <th className="pb-3">Symbol</th>
            <th className="pb-3">Side</th>
            <th className="pb-3 text-right">Size</th>
            <th className="pb-3 text-right">Entry</th>
            <th className="pb-3 text-right">PnL</th>
            <th className="pb-3 text-right">Stop</th>
            <th className="pb-3 text-right">TP</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-900/80 text-slate-300">
          {items.map((item) => (
            <tr key={item.id}>
              <td className="py-3 pr-4 font-medium text-slate-100">{item.symbol}</td>
              <td className={`py-3 pr-4 ${item.side === 'LONG' ? 'text-cyan-300' : 'text-rose-300'}`}>{item.side}</td>
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
  }, [selectedProjectId, timeframe, source, reloadToken])

  const topInsights = useMemo(() => dashboard?.insight_boxes.slice(0, 4) || [], [dashboard])
  const deskBadges = useMemo(() => (dashboard ? buildDeskBadges(dashboard) : []), [dashboard])
  const supervisoryAlerts = useMemo(() => (dashboard ? buildSupervisoryAlerts(dashboard) : []), [dashboard])

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(14,116,144,0.16),transparent_25%),radial-gradient(circle_at_top_right,rgba(15,23,42,0.36),transparent_34%),linear-gradient(180deg,#020617_0%,#020617_100%)] text-slate-100">
      <div className="border-b border-slate-800/90 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1680px] flex-col gap-5 px-6 py-5 lg:flex-row lg:items-end lg:justify-between lg:px-8">
          <div className="space-y-4 md:pl-10">
            <div className="flex flex-wrap items-center gap-3">
              <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Visari Trading Room</div>
              <StatusPill label={dashboard?.header.status || 'Command Center'} tone={dashboard?.header.status_tone || 'neutral'} />
              {dashboard && <StatusPill label={dashboard.source_mode} tone={dashboard.source_mode === 'real' ? 'positive' : 'warning'} />}
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-50 lg:text-4xl">
                Desk algoritmi
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
                Controlla salute strategica, rischio, stato operativo e contesto macro in un'unica control room.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 text-xs text-slate-500">
              <span>Progetto: {dashboard?.selected_project_title || 'Anteprima desk'}</span>
              <span>Sessione mercato: {dashboard?.header.market_session || '—'}</span>
              <span>Modalita desk: {dashboard?.header.desk_mode || '—'}</span>
              <span>Ora: {dashboard ? formatClock(dashboard.header.current_time) : '—'}</span>
            </div>
          </div>
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-end gap-3">
              <Link href="/workspace" className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-400 hover:border-slate-600 hover:text-slate-100">
                Workspace
              </Link>
              <button
                onClick={() => setReloadToken((value) => value + 1)}
                className="border border-slate-800 px-3 py-2 text-xs uppercase tracking-[0.16em] text-slate-400 hover:border-slate-600 hover:text-slate-100"
              >
                Aggiorna
              </button>
              <AuthToolbar />
            </div>
            <div className="grid gap-3 md:grid-cols-3">
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
                  <option value="real">Solo dati reali</option>
                  <option value="demo">Demo professionale</option>
                </select>
              </label>
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
                    <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Active Desk</div>
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
                    <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Strategy Health</div>
                    <div className="mt-3 text-4xl font-semibold text-slate-50">{dashboard.header.strategy_health_score}</div>
                    <div className="mt-2 text-sm text-slate-400">{dashboard.header.source_label} · Research-backed evaluation</div>
                    <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-500">
                      <div>
                        <div className="uppercase tracking-[0.14em] text-slate-600">Session</div>
                        <div className="mt-1 text-slate-300">{dashboard.header.market_session}</div>
                      </div>
                      <div>
                        <div className="uppercase tracking-[0.14em] text-slate-600">Updated</div>
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
              <PanelFrame title="Equity Curve" eyebrow="Primary performance axis">
                <LineChart
                  points={dashboard.charts.equity_curve}
                  color="#22d3ee"
                  valueFormatter={(value) => formatMoney(value)}
                />
              </PanelFrame>

              <PanelFrame title="Supervisory Alerts" eyebrow="Risk, regime and execution watchlist">
                <AlertList alerts={supervisoryAlerts} />
              </PanelFrame>
            </section>

            <section className="grid gap-4 xl:grid-cols-[0.95fr_0.55fr_0.5fr]">
              <PanelFrame title="Drawdown Profile" eyebrow="Capital compression">
                <LineChart
                  points={dashboard.charts.drawdown_curve}
                  color="#fb7185"
                  fill={false}
                  valueFormatter={(value) => `${value.toFixed(2)}%`}
                />
              </PanelFrame>

              <PanelFrame title="PnL Distribution" eyebrow="Trade outcome clustering">
                <BarChart bars={dashboard.charts.pnl_distribution} color="#38bdf8" />
              </PanelFrame>

              <PanelFrame title="Exposure Map" eyebrow="Capital allocation snapshot">
                <BarChart bars={dashboard.charts.exposure_map} color="#14b8a6" />
              </PanelFrame>
            </section>

            <section className={panelCls}>
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/90 px-4 py-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Control tabs</div>
                  <div className="mt-1 text-sm font-semibold text-slate-100">Structured supervision modules</div>
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
                  <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
                    <PanelFrame title="What Changed Today" eyebrow="Operational delta">
                      <div className="space-y-3">
                        {(dashboard.recent_changes || []).map((item, index) => (
                          <div key={`${item}-${index}`} className="border border-slate-900/80 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                            {item}
                          </div>
                        ))}
                      </div>
                    </PanelFrame>
                    <PanelFrame title="Strategy Health" eyebrow="Core desk posture">
                      <KeyValueGrid
                        items={[
                          { label: 'Operating Mode', value: dashboard.operating_mode },
                          { label: 'Source Mode', value: dashboard.source_mode.toUpperCase() },
                          { label: 'Health Score', value: `${dashboard.header.strategy_health_score}/100`, tone: dashboard.header.strategy_health_score >= 70 ? 'positive' : 'warning' },
                          { label: 'Desk Session', value: dashboard.header.market_session },
                          { label: 'Connection', value: dashboard.header.connection_status, tone: dashboard.header.connection_tone },
                          { label: 'Current Time', value: formatClock(dashboard.header.current_time) },
                        ]}
                      />
                    </PanelFrame>
                  </div>
                )}

                {activeTab === 'risk' && (
                  <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                    <PanelFrame title="Risk Exposure" eyebrow="Daily loss, exposure and kill-switch">
                      <KeyValueGrid
                        items={[
                          { label: 'Risk Usage', value: `${dashboard.risk_panel.risk_usage_pct.toFixed(1)}%`, tone: dashboard.risk_panel.risk_usage_pct >= 70 ? 'warning' : 'neutral' },
                          { label: 'VaR Proxy', value: `${dashboard.risk_panel.var_proxy_pct.toFixed(2)}%`, tone: 'warning' },
                          { label: 'Leverage Proxy', value: dashboard.risk_panel.leverage_proxy.toFixed(2) },
                          { label: 'Exposure', value: `${dashboard.risk_panel.exposure_pct.toFixed(1)}%` },
                          { label: 'Daily Loss Used', value: `${dashboard.risk_panel.daily_loss_used_pct.toFixed(1)}%`, tone: dashboard.risk_panel.daily_loss_used_pct >= 80 ? 'negative' : 'warning' },
                          { label: 'Kill Switch', value: dashboard.risk_panel.kill_switch_status, tone: dashboard.risk_panel.kill_switch_status === 'NOMINAL' ? 'positive' : 'warning' },
                          { label: 'Max Drawdown', value: `${dashboard.risk_panel.max_drawdown_pct.toFixed(2)}%`, tone: 'negative' },
                        ]}
                      />
                    </PanelFrame>
                    <PanelFrame title="Risk Notes" eyebrow="Warnings requiring human oversight">
                      {dashboard.risk_panel.warnings.length ? (
                        <div className="space-y-3">
                          {dashboard.risk_panel.warnings.map((warning, index) => (
                            <div key={`${warning}-${index}`} className="border border-amber-900/70 bg-amber-950/10 px-4 py-3 text-sm text-amber-200">
                              {warning}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-sm text-slate-500">No active risk warnings in the current desk view.</div>
                      )}
                    </PanelFrame>
                  </div>
                )}

                {activeTab === 'execution' && (
                  <div className="grid gap-4">
                    <PanelFrame title="Recent Signals" eyebrow="Latest decision flow">
                      <SignalsTable items={dashboard.recent_signals} />
                    </PanelFrame>
                    <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
                      <PanelFrame title="Open Positions" eyebrow="Runtime exposure">
                        <PositionsTable items={dashboard.open_positions} />
                      </PanelFrame>
                      <PanelFrame title="Execution Status" eyebrow="Runtime stack">
                        <KeyValueGrid
                          items={[
                            { label: 'Data Provider', value: dashboard.tech_panel.data_provider },
                            { label: 'Data Feed', value: dashboard.tech_panel.data_feed_status },
                            { label: 'Parser', value: dashboard.tech_panel.parser_status },
                            { label: 'Engine', value: dashboard.tech_panel.engine_status },
                            { label: 'Provider Status', value: dashboard.tech_panel.provider_status },
                            { label: 'Export Status', value: dashboard.tech_panel.export_status },
                            { label: 'Latency', value: `${dashboard.tech_panel.latency_ms} ms` },
                            { label: 'Artifacts Ready', value: dashboard.tech_panel.artifacts_ready },
                            { label: 'Jobs Running', value: dashboard.tech_panel.jobs_running },
                            { label: 'Last Sync', value: formatClock(dashboard.tech_panel.last_sync) },
                          ]}
                        />
                      </PanelFrame>
                    </div>
                  </div>
                )}

                {activeTab === 'fundamentals' && (
                  <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
                    <PanelFrame title="Macro Context" eyebrow="Macro-aware desk context">
                      <KeyValueGrid
                        items={[
                          { label: 'Regime', value: dashboard.market_panel.regime },
                          { label: 'Volatility', value: dashboard.market_panel.volatility },
                          { label: 'Session', value: dashboard.market_panel.session },
                          { label: 'News Risk', value: dashboard.market_panel.news_risk_active ? 'Active' : 'Inactive', tone: dashboard.market_panel.news_risk_active ? 'warning' : 'neutral' },
                          { label: 'News Provider', value: dashboard.market_panel.news_provider },
                          { label: 'Events in Window', value: dashboard.market_panel.news_events },
                          { label: 'Macro Filter', value: dashboard.market_panel.macro_filter_status },
                          { label: 'Directional Bias', value: dashboard.market_panel.directional_bias },
                        ]}
                      />
                    </PanelFrame>
                    <PanelFrame title="Macro / Provider Notes" eyebrow="Desk commentary">
                      {dashboard.market_panel.warnings.length ? (
                        <div className="space-y-3">
                          {dashboard.market_panel.warnings.map((warning, index) => (
                            <div key={`${warning}-${index}`} className="border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-300">
                              {warning}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-sm text-slate-500">No macro warnings active for the selected desk view.</div>
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
