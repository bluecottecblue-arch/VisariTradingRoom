'use client'

import type { ReactNode } from 'react'
import type { DashboardBar, DashboardPoint, DashboardTone } from '@/types'

export const panelCls =
  'border border-slate-800/90 bg-slate-950/80 shadow-[0_0_0_1px_rgba(15,23,42,0.6)]'

const toneMap: Record<DashboardTone, string> = {
  neutral: 'border-slate-700 text-slate-300',
  positive: 'border-cyan-900/80 text-cyan-300',
  negative: 'border-rose-900/80 text-rose-300',
  warning: 'border-amber-900/80 text-amber-300',
}

export function StatusPill({ label, tone = 'neutral' }: { label: string; tone?: DashboardTone }) {
  return (
    <span className={`inline-flex items-center gap-2 border px-2.5 py-1 text-[10px] uppercase tracking-[0.16em] ${toneMap[tone]}`}>
      <span className="h-1.5 w-1.5 bg-current" />
      {label}
    </span>
  )
}

export function PanelFrame({
  title,
  eyebrow,
  actions,
  children,
}: {
  title: string
  eyebrow?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={panelCls}>
      <div className="flex items-start justify-between gap-4 border-b border-slate-800/90 px-4 py-3">
        <div>
          {eyebrow && (
            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{eyebrow}</div>
          )}
          <div className="mt-1 text-sm font-semibold text-slate-100">{title}</div>
        </div>
        {actions}
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

export function LineChart({
  points,
  color = '#22d3ee',
  fill = true,
  height = 240,
  valueFormatter,
}: {
  points: DashboardPoint[]
  color?: string
  fill?: boolean
  height?: number
  valueFormatter?: (value: number) => string
}) {
  const width = 1000
  const safePoints = points.length ? points : [{ label: 'N/D', timestamp: '', value: 0 }]
  const values = safePoints.map((point) => point.value)
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const range = Math.max(1, maxValue - minValue)
  const stepX = safePoints.length > 1 ? width / (safePoints.length - 1) : width
  const yFor = (value: number) => {
    const ratio = (value - minValue) / range
    return height - ratio * (height - 18) - 10
  }

  const line = safePoints
    .map((point, index) => `${index * stepX},${yFor(point.value)}`)
    .join(' ')
  const area = `0,${height} ${line} ${width},${height}`
  const last = safePoints[safePoints.length - 1]

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-4">
        <div className="text-2xl font-semibold text-slate-50">
          {valueFormatter ? valueFormatter(last.value) : last.value.toFixed(2)}
        </div>
        <div className="text-right text-[11px] uppercase tracking-[0.14em] text-slate-500">
          {safePoints[0]?.label} → {last?.label}
        </div>
      </div>
      <div className="relative overflow-hidden border border-slate-900 bg-[linear-gradient(to_bottom,rgba(15,23,42,0.36),rgba(2,6,23,0.9))]">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-[240px] w-full">
          <defs>
            <linearGradient id={`fill-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.22} />
              <stop offset="100%" stopColor={color} stopOpacity={0.01} />
            </linearGradient>
          </defs>
          {[0.2, 0.4, 0.6, 0.8].map((marker) => (
            <line
              key={marker}
              x1="0"
              y1={height * marker}
              x2={width}
              y2={height * marker}
              stroke="rgba(51,65,85,0.45)"
              strokeDasharray="5 7"
            />
          ))}
          {fill && <polygon points={area} fill={`url(#fill-${color.replace('#', '')})`} />}
          <polyline
            fill="none"
            stroke={color}
            strokeWidth="3"
            points={line}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <circle cx={(safePoints.length - 1) * stepX} cy={yFor(last.value)} r="5" fill={color} />
        </svg>
      </div>
      <div className="grid grid-cols-3 gap-3 text-xs text-slate-500">
        <div>
          <div className="uppercase tracking-[0.14em] text-slate-600">Minimo</div>
          <div className="mt-1 text-slate-300">{valueFormatter ? valueFormatter(minValue) : minValue.toFixed(2)}</div>
        </div>
        <div>
          <div className="uppercase tracking-[0.14em] text-slate-600">Massimo</div>
          <div className="mt-1 text-slate-300">{valueFormatter ? valueFormatter(maxValue) : maxValue.toFixed(2)}</div>
        </div>
        <div className="text-right">
          <div className="uppercase tracking-[0.14em] text-slate-600">Ultimo</div>
          <div className="mt-1 text-slate-300">{valueFormatter ? valueFormatter(last.value) : last.value.toFixed(2)}</div>
        </div>
      </div>
    </div>
  )
}

export function BarChart({
  bars,
  color = '#38bdf8',
  height = 180,
}: {
  bars: DashboardBar[]
  color?: string
  height?: number
}) {
  const safeBars = bars.length ? bars : [{ label: 'N/D', value: 0 }]
  const maxValue = Math.max(1, ...safeBars.map((bar) => bar.value))
  return (
    <div className="space-y-3">
      <div className="grid gap-2">
        {safeBars.map((bar) => (
          <div key={`${bar.label}-${bar.value}`} className="space-y-1">
            <div className="flex items-center justify-between gap-4 text-[11px] uppercase tracking-[0.14em] text-slate-500">
              <span className="truncate">{bar.label}</span>
              <span className="text-slate-300">{bar.value}</span>
            </div>
            <div className="h-2 bg-slate-900">
              <div className="h-2" style={{ width: `${(bar.value / maxValue) * 100}%`, background: color }} />
            </div>
          </div>
        ))}
      </div>
      <div className="text-[11px] uppercase tracking-[0.14em] text-slate-600">Scala {height}px · max {maxValue}</div>
    </div>
  )
}

export function SkeletonDesk() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className={`${panelCls} h-28 animate-pulse bg-slate-950/80`} />
        ))}
      </div>
      <div className={`${panelCls} h-96 animate-pulse bg-slate-950/80`} />
    </div>
  )
}
