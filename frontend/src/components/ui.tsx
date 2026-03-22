'use client'

import { useState } from 'react'
import type { ReactNode } from 'react'

// ─── Section header ────────────────────────────────────────────────────────────
export function Section({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-stone-300 font-bold text-sm uppercase tracking-wider border-b border-stone-800 pb-2">
        {title}
      </h2>
      {children}
    </div>
  )
}

// ─── Form field wrapper ────────────────────────────────────────────────────────
export function Field({
  label,
  children,
  required,
  tooltip,
}: {
  label: string
  children: ReactNode
  required?: boolean
  tooltip?: string
}) {
  const [showTip, setShowTip] = useState(false)
  return (
    <div className="space-y-1">
      <label className="flex items-center gap-2 text-stone-400 text-xs">
        <span>{label}</span>
        {required && <span className="text-amber-500">*</span>}
        {tooltip && (
          <span
            className="relative text-stone-600 hover:text-stone-400 cursor-help"
            onMouseEnter={() => setShowTip(true)}
            onMouseLeave={() => setShowTip(false)}
          >
            ⓘ
            {showTip && (
              <span className="absolute left-6 top-0 z-10 w-64 px-3 py-2 bg-stone-800 border border-stone-600 rounded text-stone-300 text-xs font-normal whitespace-normal shadow-xl">
                {tooltip}
              </span>
            )}
          </span>
        )}
      </label>
      {children}
    </div>
  )
}

// ─── Input styles ──────────────────────────────────────────────────────────────
export const inputCls =
  'w-full bg-stone-900 border border-stone-700 focus:border-amber-500 outline-none rounded px-3 py-2 text-stone-100 text-sm placeholder-stone-600'

export const textareaCls = `${inputCls} resize-none`

// ─── Metric card ───────────────────────────────────────────────────────────────
export function MetricCard({
  label,
  value,
  colorClass = 'text-stone-200',
  sub,
}: {
  label: string
  value: string | number | null | undefined
  colorClass?: string
  sub?: string
}) {
  return (
    <div className="px-3 py-3 bg-stone-900 border border-stone-800 rounded">
      <div className="text-stone-500 text-xs mb-1">{label}</div>
      <div className={`text-lg font-bold font-mono ${colorClass}`}>
        {value ?? '—'}
      </div>
      {sub && <div className="text-stone-600 text-xs mt-0.5">{sub}</div>}
    </div>
  )
}

// ─── Alert banner ─────────────────────────────────────────────────────────────
export function Alert({
  type = 'warning',
  title,
  children,
}: {
  type?: 'warning' | 'error' | 'info' | 'success'
  title?: string
  children: ReactNode
}) {
  const styles = {
    warning: 'border-amber-800/50 bg-amber-950/20 text-amber-300',
    error:   'border-red-800/50 bg-red-950/20 text-red-300',
    info:    'border-blue-800/50 bg-blue-950/20 text-blue-300',
    success: 'border-green-800/50 bg-green-950/20 text-green-300',
  }
  const icons = { warning: '⚠️', error: '❌', info: 'ℹ️', success: '✅' }
  return (
    <div className={`px-4 py-3 border rounded space-y-1 ${styles[type]}`}>
      {title && (
        <div className="font-bold text-sm">
          {icons[type]} {title}
        </div>
      )}
      <div className="text-sm">{children}</div>
    </div>
  )
}

// ─── Progress bar ─────────────────────────────────────────────────────────────
export function ProgressBar({
  value,
  max = 1,
  label,
}: {
  value: number
  max?: number
  label?: string
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const color =
    pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs text-stone-400">
          <span>{label}</span>
          <span className="font-bold">{pct.toFixed(0)}%</span>
        </div>
      )}
      <div className="w-full bg-stone-800 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ─── Code block ───────────────────────────────────────────────────────────────
export function CodeBlock({
  code,
  language = 'mql5',
  maxHeight = '24rem',
}: {
  code: string
  language?: string
  maxHeight?: string
}) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between px-3 py-1.5 bg-stone-800 border-b border-stone-700 rounded-t text-xs text-stone-400">
        <span>{language}</span>
        <button
          onClick={copy}
          className="hover:text-stone-200 transition-colors"
        >
          {copied ? '✓ Copiato' : 'Copia'}
        </button>
      </div>
      <pre
        className="p-4 bg-stone-950 border border-t-0 border-stone-800 rounded-b text-xs text-green-300 font-mono overflow-x-auto overflow-y-auto leading-relaxed"
        style={{ maxHeight }}
      >
        {code}
      </pre>
    </div>
  )
}

// ─── Spinner ──────────────────────────────────────────────────────────────────
export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-8">
      <div className="w-8 h-8 border-2 border-stone-700 border-t-amber-400 rounded-full animate-spin" />
      {label && <p className="text-stone-400 text-sm">{label}</p>}
    </div>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────
export function EmptyState({
  icon,
  title,
  description,
}: {
  icon: string
  title: string
  description?: string
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <div className="text-4xl">{icon}</div>
      <h3 className="text-stone-300 font-bold">{title}</h3>
      {description && (
        <p className="text-stone-500 text-sm max-w-sm">{description}</p>
      )}
    </div>
  )
}

// ─── Tab bar ──────────────────────────────────────────────────────────────────
export function TabBar<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: string }[]
  active: T
  onChange: (id: T) => void
}) {
  return (
    <div className="flex border-b border-stone-800">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm font-bold transition-colors ${
            active === tab.id
              ? 'text-amber-400 border-b-2 border-amber-400 -mb-px'
              : 'text-stone-500 hover:text-stone-300'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

// ─── Nav buttons ──────────────────────────────────────────────────────────────
export function NavButtons({
  onBack,
  onNext,
  nextLabel = 'Continua →',
  disabled = false,
  loading = false,
  backLabel = '← Indietro',
}: {
  onBack?: () => void
  onNext?: () => void
  nextLabel?: string
  disabled?: boolean
  loading?: boolean
  backLabel?: string
}) {
  return (
    <div className="flex gap-4 pt-4">
      {onBack && (
        <button
          onClick={onBack}
          disabled={loading}
          className="px-6 py-3 border border-stone-700 text-stone-400 hover:text-stone-200 rounded transition-colors disabled:opacity-40"
        >
          {backLabel}
        </button>
      )}
      {onNext && (
        <button
          onClick={onNext}
          disabled={disabled || loading}
          className="flex-1 py-3 bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-stone-700 border-t-stone-950 rounded-full animate-spin" />
              Elaborazione...
            </span>
          ) : (
            nextLabel
          )}
        </button>
      )}
    </div>
  )
}
