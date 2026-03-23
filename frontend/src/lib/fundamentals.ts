import type { FundamentalFilterConfig } from '@/types'

export const DEFAULT_FUNDAMENTAL_FILTERS: FundamentalFilterConfig = {
  enabled: false,
  provider: 'none',
  api_key: '',
  currencies: ['USD'],
  impacts: ['high'],
  blackout_before_min: 30,
  blackout_after_min: 30,
  post_event_wait_min: 15,
  bias_mode: 'exclude_only',
  directional_bias: '',
  notes: '',
  manual_events: [],
}

export function summarizeFundamentalFilters(config?: FundamentalFilterConfig | null, freeText?: string): string {
  const textParts: string[] = []
  if (freeText?.trim()) {
    textParts.push(freeText.trim())
  }
  if (!config?.enabled) {
    return textParts.join(' ')
  }

  const currencies = config.currencies?.length ? config.currencies.join('/') : 'macro events rilevanti'
  const impacts = config.impacts?.length ? config.impacts.join(', ') : 'high'
  textParts.push(
    `Macro news live attivo: provider=${config.provider}; valute=${currencies}; impatto=${impacts}; ` +
      `blackout=${config.blackout_before_min}m prima / ${config.blackout_after_min}m dopo; ` +
      `post_event_wait=${config.post_event_wait_min}m; bias_mode=${config.bias_mode}` +
      (config.directional_bias ? `; directional_bias=${config.directional_bias}` : '') +
      (config.notes?.trim() ? `; notes=${config.notes.trim()}` : '')
  )
  return textParts.join(' ')
}
