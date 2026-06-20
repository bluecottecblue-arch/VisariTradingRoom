'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'

type AppSidebarProps = {
  open: boolean
  onClose: () => void
}

function isActive(pathname: string, workspaceMode: string | null, href: string) {
  if (href.startsWith('/workspace?mode=')) {
    const mode = href.split('mode=')[1]
    return pathname === '/workspace' && workspaceMode === mode
  }
  return pathname === href
}

const links = [
  { href: '/workspace?mode=strategy', label: 'Strategie' },
  { href: '/builder', label: 'Builder strategia' },
  { href: '/workspace?mode=botlab', label: 'Bot Lab' },
  { href: '/dashboard', label: 'Desk algoritmi' },
  { href: '/research', label: 'Data Lab' },
  { href: '/mean-reversion', label: 'Mean Reversion Lab' },
  { href: '/team', label: 'Team' },
  { href: '/academy', label: 'Accademia' },
]

export default function AppSidebar({ open, onClose }: AppSidebarProps) {
  const pathname = usePathname()
  const [workspaceMode, setWorkspaceMode] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    setWorkspaceMode(params.get('mode'))
  }, [pathname])

  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Chiudi menu laterale"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-slate-950/72 xl:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-80 shrink-0 border-r border-slate-800 bg-slate-950 transition-transform duration-200 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="border-b border-slate-800 px-6 py-6 md:pl-[3.25rem]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.28em] text-amber-300">Visari Trading Room</div>
              <div className="mt-3 text-2xl font-semibold text-slate-50">Area operativa</div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="border border-slate-800 px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 transition-colors hover:border-slate-700 hover:text-slate-100"
            >
              Chiudi
            </button>
          </div>
        </div>

        <div className="space-y-8 overflow-y-auto px-6 py-6">
          <div className="space-y-3">
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Navigazione</div>
            {links.map((link) => {
              const active = isActive(pathname, workspaceMode, link.href)
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => {
                    if (window.innerWidth < 1280) onClose()
                  }}
                  className={`block w-full border px-4 py-3 text-left text-sm transition-colors ${
                    active
                      ? 'border-slate-500 bg-slate-900 text-slate-100'
                      : 'border-slate-800 bg-transparent text-slate-500 hover:border-slate-700 hover:text-slate-200'
                  }`}
                >
                  <div className="font-medium">{link.label}</div>
                </Link>
              )
            })}
          </div>
        </div>
      </aside>
    </>
  )
}
