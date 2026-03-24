'use client'

import { useEffect, useState } from 'react'
import { botLabApi } from '@/lib/api'
import { Field, Section, inputCls } from '@/components/ui'
import { DEFAULT_FUNDAMENTAL_FILTERS } from '@/lib/fundamentals'
import type { CalendarProviderInfo, FundamentalFilterConfig } from '@/types'

const IMPACTS: Array<'high' | 'medium' | 'low'> = ['high', 'medium', 'low']

interface Props {
  value?: FundamentalFilterConfig
  onChange: (next: FundamentalFilterConfig) => void
  title?: string
  compact?: boolean
}

export default function FundamentalFiltersCard({
  value = DEFAULT_FUNDAMENTAL_FILTERS,
  onChange,
  title = 'Live macroeconomic calendar',
  compact = false,
}: Props) {
  const [providers, setProviders] = useState<CalendarProviderInfo[]>([])

  useEffect(() => {
    let mounted = true
    botLabApi.calendarProviders()
      .then((data: any) => {
        if (!mounted) return
        setProviders(data.providers || [])
      })
      .catch(() => {
        if (!mounted) return
        setProviders([])
      })
    return () => {
      mounted = false
    }
  }, [])

  const set = <K extends keyof FundamentalFilterConfig>(key: K, next: FundamentalFilterConfig[K]) =>
    onChange({ ...value, [key]: next })

  const toggleImpact = (impact: 'high' | 'medium' | 'low') => {
    const impacts = value.impacts.includes(impact)
      ? value.impacts.filter((item) => item !== impact)
      : [...value.impacts, impact]
    set('impacts', impacts.length ? impacts : ['high'])
  }

  return (
    <Section title={title}>
      <label className="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(e) => set('enabled', e.target.checked)}
          className="mt-0.5 w-4 h-4 accent-amber-500"
        />
        <div>
          <div className="text-stone-300 text-sm font-bold">Use live macroeconomic calendar and news filter</div>
          <div className="text-stone-500 text-xs">
            The final bot can block, confirm or delay trades based on macro events and news risk.
          </div>
        </div>
      </label>

      {value.enabled && (
        <div className="space-y-4 rounded border border-stone-800 bg-stone-900/60 p-4">
          <div className={`grid gap-4 ${compact ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-3'}`}>
            <Field label="Calendar provider">
              <select
                value={value.provider}
                onChange={(e) => set('provider', e.target.value as FundamentalFilterConfig['provider'])}
                className={inputCls}
              >
                {providers.length === 0 && (
                  <>
                    <option value="none">No provider</option>
                    <option value="manual">Manual / Demo events</option>
                    <option value="trading_economics">Trading Economics</option>
                  </>
                )}
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id} disabled={!provider.available && provider.id !== 'none'}>
                    {provider.name}
                    {provider.id !== 'none' && provider.integration_status === 'demo' ? ' (demo)' : ''}
                    {provider.id !== 'none' && provider.integration_status === 'requires_config' ? ' (requires config)' : ''}
                    {provider.id !== 'none' && provider.integration_status === 'disabled' ? ' (disabled)' : ''}
                    {!provider.available && provider.integration_status !== 'disabled' && provider.id !== 'none' ? ' (not configured)' : ''}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Currencies">
              <input
                value={value.currencies.join(',')}
                onChange={(e) => set('currencies', e.target.value.split(',').map((item) => item.trim().toUpperCase()).filter(Boolean))}
                className={inputCls}
                placeholder="USD,EUR"
              />
            </Field>
            <Field label="Trading mode">
              <select
                value={value.bias_mode}
                onChange={(e) => set('bias_mode', e.target.value as FundamentalFilterConfig['bias_mode'])}
                className={inputCls}
              >
                <option value="exclude_only">Exclude only</option>
                <option value="confirm_with_bias">Directional macro confirmation</option>
                <option value="post_event_trigger">Post-news trigger mode</option>
              </select>
            </Field>
          </div>

          {value.provider === 'trading_economics' && (
            <Field label="Calendar provider API key">
              <input
                type="password"
                value={value.api_key || ''}
                onChange={(e) => set('api_key', e.target.value)}
                className={inputCls}
                placeholder="provider client:secret"
              />
            </Field>
          )}

          <div className="space-y-2">
            <div className="text-stone-400 text-xs">Event impact to include</div>
            <div className="flex gap-2 flex-wrap">
              {IMPACTS.map((impact) => (
                <button
                  key={impact}
                  type="button"
                  onClick={() => toggleImpact(impact)}
                  className={`px-3 py-1.5 rounded text-xs font-bold border transition-colors ${
                    value.impacts.includes(impact)
                      ? 'bg-amber-500 border-amber-500 text-stone-950'
                      : 'bg-stone-950 border-stone-700 text-stone-400 hover:border-stone-500'
                  }`}
                >
                  {impact}
                </button>
              ))}
            </div>
          </div>

          <div className={`grid gap-4 ${compact ? 'grid-cols-2 md:grid-cols-4' : 'grid-cols-2 md:grid-cols-4'}`}>
            <Field label="Pre-event blackout (min)">
              <input
                type="number"
                min={0}
                max={180}
                value={value.blackout_before_min}
                onChange={(e) => set('blackout_before_min', Number(e.target.value))}
                className={inputCls}
              />
            </Field>
            <Field label="Post-event blackout (min)">
              <input
                type="number"
                min={0}
                max={180}
                value={value.blackout_after_min}
                onChange={(e) => set('blackout_after_min', Number(e.target.value))}
                className={inputCls}
              />
            </Field>
            <Field label="Wait post-news (min)">
              <input
                type="number"
                min={0}
                max={180}
                value={value.post_event_wait_min}
                onChange={(e) => set('post_event_wait_min', Number(e.target.value))}
                className={inputCls}
              />
            </Field>
            <Field label="Directional bias">
              <input
                value={value.directional_bias || ''}
                onChange={(e) => set('directional_bias', e.target.value)}
                className={inputCls}
                placeholder="e.g. bullish_usd"
              />
            </Field>
          </div>

          <Field label="News / fundamentals note">
            <input
              value={value.notes || ''}
              onChange={(e) => set('notes', e.target.value)}
              className={inputCls}
              placeholder="e.g. After FOMC, wait 15 minutes and only trade breakouts."
            />
          </Field>

          <div className="rounded border border-stone-800 bg-stone-950/70 p-3 text-xs text-stone-400">
            {providers.find((provider) => provider.id === value.provider)?.description ||
              'If no provider is configured, the platform falls back cleanly and keeps the workflow running.'}
          </div>
          {value.provider === 'trading_economics' && (
            <div className="rounded border border-amber-900/60 bg-amber-950/20 p-3 text-xs text-amber-200">
              The macro provider key always belongs to the user and is also used by the final generated bot.
            </div>
          )}
        </div>
      )}
    </Section>
  )
}
