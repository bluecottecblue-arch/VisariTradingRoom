'use client'

import { featureFlags } from '@/lib/feature-flags'

export default function MonetizationSlot({ slotId }: { slotId: string }) {
  if (!featureFlags.enableAdSlots) return null

  return (
    <aside className="mt-8 rounded-xl border border-stone-800 bg-stone-900/60 px-4 py-5 text-sm text-stone-400">
      <div className="text-[10px] uppercase tracking-[0.3em] text-stone-600">Sponsored Slot</div>
      <div className="mt-2 text-stone-300">Slot monetization pronto ma disattivato nel prodotto standard.</div>
      <div className="mt-1 text-xs text-stone-500">slot_id: {slotId}</div>
    </aside>
  )
}
