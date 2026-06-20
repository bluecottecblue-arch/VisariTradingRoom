'use client'

import { useState } from 'react'
import AuthToolbar from '@/components/AuthToolbar'
import AppSidebar from '@/components/layout/AppSidebar'
import ReferralPanel from '@/components/referral/ReferralPanel'

export default function ReferralClient() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-200 transition-[padding] duration-200 ${sidebarOpen ? 'xl:pl-80' : 'xl:pl-0'}`}>
      <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800 bg-slate-950/90 px-6 py-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label={sidebarOpen ? 'Chiudi navigazione' : 'Apri navigazione'}
            onClick={() => setSidebarOpen((v) => !v)}
            className="flex h-11 w-11 items-center justify-center border border-slate-800 text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-100"
          >
            <span className="flex flex-col gap-1.5">
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
            </span>
          </button>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-amber-400">Programma Referral</div>
            <div className="text-xl font-semibold text-slate-50">Invita e guadagna mesi gratis</div>
          </div>
        </div>
        <AuthToolbar />
      </header>

      <main className="mx-auto max-w-4xl space-y-6 px-6 py-8">
        <ReferralPanel />
      </main>
    </div>
  )
}
