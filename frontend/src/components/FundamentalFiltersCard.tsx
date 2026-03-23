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
  title = 'Calendario macroeconomico live',
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
          <div className="text-stone-300 text-sm font-bold">Use live macroeconomic calendar / news filter</div>
          <div className="text-stone-500 text-xs">
            Il bot finale userà il calendario macro per bloccare, confermare o ritardare i trade.
          </div>
        </div>
      </label>

      {value.enabled && (
        <div className="space-y-4 rounded border border-stone-800 bg-stone-900/60 p-4">
          <div className={`grid gap-4 ${compact ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-3'}`}>
            <Field label="Provider calendario">
              <select
                value={value.provider}
                onChange={(e) => set('provider', e.target.value as FundamentalFilterConfig['provider'])}
                className={inputCls}
              >
                {providers.length === 0 && (
                  <>
                    <option value="none">Nessun provider</option>
                    <option value="manual">Manual / Demo events</option>
                    <option value="trading_economics">Trading Economics</option>
                  </>
                )}
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id} disabled={!provider.available && provider.id !== 'none'}>
                    {provider.name}
                    {provider.id !== 'none' && provider.integration_status === 'demo' ? ' (demo)' : ''}
                    {provider.id !== 'none' && provider.integration_status === 'requires_config' ? ' (richiede config)' : ''}
                    {provider.id !== 'none' && provider.integration_status === 'disabled' ? ' (disattivato)' : ''}
                    {!provider.available && provider.integration_status !== 'disabled' && provider.id !== 'none' ? ' (non configurato)' : ''}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Valute interessate">
              <input
                value={value.currencies.join(',')}
                onChange={(e) => set('currencies', e.target.value.split(',').map((item) => item.trim().toUpperCase()).filter(Boolean))}
                className={inputCls}
                placeholder="USD,EUR"
              />
            </Field>
            <Field label="Bias operativo">
              <select
                value={value.bias_mode}
                onChange={(e) => set('bias_mode', e.target.value as FundamentalFilterConfig['bias_mode'])}
                className={inputCls}
              >
                <option value="exclude_only">Solo filtro di esclusione</option>
                <option value="confirm_with_bias">Conferma direzionale macro</option>
                <option value="post_event_trigger">Event-driven post-news</option>
              </select>
            </Field>
          </div>

          {value.provider === 'trading_economics' && (
            <Field label="API key provider calendario">
              <input
                type="password"
                value={value.api_key || ''}
                onChange={(e) => set('api_key', e.target.value)}
                className={inputCls}
                placeholder="client:secret del provider macro"
              />
            </Field>
          )}

          <div className="space-y-2">
            <div className="text-stone-400 text-xs">Impatto da considerare</div>
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
            <Field label="Blackout prima (min)">
              <input
                type="number"
                min={0}
                max={180}
                value={value.blackout_before_min}
                onChange={(e) => set('blackout_before_min', Number(e.target.value))}
                className={inputCls}
              />
            </Field>
            <Field label="Blackout dopo (min)">
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
            <Field label="Bias direzionale">
              <input
                value={value.directional_bias || ''}
                onChange={(e) => set('directional_bias', e.target.value)}
                className={inputCls}
                placeholder="Es. bullish_usd"
              />
            </Field>
          </div>

          <Field label="Nota news / fundamentals">
            <input
              value={value.notes || ''}
              onChange={(e) => set('notes', e.target.value)}
              className={inputCls}
              placeholder="Es. Dopo FOMC aspetto 15 minuti e tradare solo breakout."
            />
          </Field>

          <div className="rounded border border-stone-800 bg-stone-950/70 p-3 text-xs text-stone-400">
            {providers.find((provider) => provider.id === value.provider)?.description ||
              'Se nessun provider è configurato, il sistema non crasha: segnala il fallback e continua.'}
          </div>
          {value.provider === 'trading_economics' && (
            <div className="rounded border border-amber-900/60 bg-amber-950/20 p-3 text-xs text-amber-200">
              La chiave del provider macro è sempre dell’utente e viene usata anche dal bot finale generato.
            </div>
          )}
        </div>
      )}
    </Section>
  )
}
