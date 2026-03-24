'use client'

import { useState } from 'react'
import type { ReactNode } from 'react'

export function Section({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="space-y-4">
      <h2 className="border-b border-slate-800/80 pb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {title}
      </h2>
      {children}
    </section>
  )
}

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
    <div className="space-y-2">
      <label className="flex items-center gap-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">
        <span>{label}</span>
        {required && <span className="text-amber-300">*</span>}
        {tooltip && (
          <span
            className="relative cursor-help text-slate-700 hover:text-slate-400"
            onMouseEnter={() => setShowTip(true)}
            onMouseLeave={() => setShowTip(false)}
          >
            i
            {showTip && (
              <span className="absolute left-5 top-0 z-10 w-64 border border-slate-700 bg-slate-950 px-3 py-2 text-[11px] font-normal normal-case tracking-normal text-slate-300 shadow-2xl">
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

export const inputCls =
  'w-full border border-slate-800 bg-[linear-gradient(180deg,rgba(15,23,42,0.84),rgba(2,6,23,0.92))] px-3.5 py-3 text-sm text-slate-100 outline-none transition-colors placeholder:text-slate-600 focus:border-cyan-800/70'

export const textareaCls = `${inputCls} resize-none`

export function MetricCard({
  label,
  value,
  colorClass = 'text-slate-100',
  sub,
}: {
  label: string
  value: string | number | null | undefined
  colorClass?: string
  sub?: string
}) {
  return (
    <div className="border border-slate-800/90 bg-slate-950/72 px-4 py-4">
      <div className="mb-1 text-[11px] uppercase tracking-[0.14em] text-slate-500">{label}</div>
      <div className={`text-xl font-semibold ${colorClass}`}>
        {value ?? '—'}
      </div>
      {sub && <div className="mt-1 text-xs text-slate-600">{sub}</div>}
    </div>
  )
}

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
    warning: 'border-amber-900/60 bg-amber-950/10 text-amber-200',
    error:   'border-red-950/80 bg-red-950/10 text-rose-200',
    info:    'border-slate-700 bg-slate-900 text-slate-200',
    success: 'border-emerald-950/80 bg-emerald-950/10 text-emerald-200',
  }
  return (
    <div className={`space-y-1 border px-4 py-3 ${styles[type]}`}>
      {title && (
        <div className="text-xs font-semibold uppercase tracking-[0.14em]">
          {title}
        </div>
      )}
      <div className="text-sm leading-relaxed">{children}</div>
    </div>
  )
}

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
  const color = pct >= 70 ? 'bg-cyan-400' : pct >= 40 ? 'bg-slate-400' : 'bg-amber-300'
  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs text-slate-500">
          <span>{label}</span>
          <span className="font-semibold text-slate-300">{pct.toFixed(0)}%</span>
        </div>
      )}
      <div className="h-1.5 w-full bg-slate-900">
        <div
          className={`h-1.5 transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

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
    <div className="relative border border-slate-800 bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2 text-[11px] uppercase tracking-[0.14em] text-slate-500">
        <span>{language}</span>
        <button
          onClick={copy}
          className="hover:text-slate-200 transition-colors"
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre
        className="overflow-x-auto overflow-y-auto p-4 text-xs leading-relaxed text-slate-200"
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
      <div className="h-8 w-8 animate-spin border-2 border-slate-800 border-t-slate-300 rounded-full" />
      {label && <p className="text-sm text-slate-400">{label}</p>}
    </div>
  )
}

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
    <div className="flex flex-col items-center gap-3 border border-dashed border-slate-800 py-12 text-center">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-600">{icon}</div>
      <h3 className="font-semibold text-slate-200">{title}</h3>
      {description && (
        <p className="max-w-sm text-sm text-slate-500">{description}</p>
      )}
    </div>
  )
}

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
    <div className="flex border-b border-slate-800/90">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm transition-colors ${
            active === tab.id
              ? 'border-b border-cyan-500/70 -mb-px text-slate-100'
              : 'text-slate-500 hover:text-slate-300'
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
  nextLabel = 'Continue',
  disabled = false,
  loading = false,
  backLabel = 'Back',
}: {
  onBack?: () => void
  onNext?: () => void
  nextLabel?: string
  disabled?: boolean
  loading?: boolean
  backLabel?: string
}) {
  return (
    <div className="flex gap-3 pt-4">
      {onBack && (
        <button
          onClick={onBack}
          disabled={loading}
          className="border border-slate-800 px-5 py-3 text-slate-400 transition-colors hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
        >
          {backLabel}
        </button>
      )}
      {onNext && (
        <button
          onClick={onNext}
          disabled={disabled || loading}
          className="flex-1 border border-cyan-800/70 bg-cyan-400/90 py-3 font-semibold text-slate-950 transition-colors hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="h-4 w-4 animate-spin border-2 border-slate-500 border-t-slate-950 rounded-full" />
              Processing...
            </span>
          ) : (
            nextLabel
          )}
        </button>
      )}
    </div>
  )
}


// ─── Accordion ────────────────────────────────────────────────────────────────
export function Accordion({
  title,
  children,
  defaultOpen = false,
}: {
  title: string
  children: ReactNode
  defaultOpen?: boolean
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  return (
    <div className="border border-slate-800/90 bg-slate-950/40 mt-4">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-5 py-4 text-left transition-colors hover:bg-slate-900/40"
      >
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-500">
          {title}
        </span>
        <span className="text-slate-500">
          {isOpen ? (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          ) : (
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          )}
        </span>
      </button>
      {isOpen && (
        <div className="border-t border-slate-800/50 p-5 space-y-4">
          {children}
        </div>
      )}
    </div>
  )
}

