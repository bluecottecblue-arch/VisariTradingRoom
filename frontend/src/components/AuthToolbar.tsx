'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

type SessionInfo = {
  authenticated: boolean
  username: string | null
  role: string | null
}

export default function AuthToolbar() {
  const router = useRouter()
  const [session, setSession] = useState<SessionInfo | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/auth/me', { cache: 'no-store' })
      .then(async (response) => {
        const body = await response.json().catch(() => null)
        if (!cancelled) setSession(body)
      })
      .catch(() => {
        if (!cancelled) setSession(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' })
    router.replace('/login')
    router.refresh()
  }

  if (!session?.authenticated) {
    return null
  }

  return (
    <div className="flex items-center gap-3 text-xs text-slate-400">
      <span className="hidden sm:inline">
        {session.username}
        {session.role === 'admin' ? ' · admin' : ''}
      </span>
      {session.role === 'admin' && (
        <Link href="/admin" className="border border-slate-800 px-3 py-1.5 hover:border-slate-600 hover:text-slate-100">
          Admin
        </Link>
      )}
      <button
        onClick={logout}
        className="border border-slate-800 px-3 py-1.5 hover:border-slate-600 hover:text-slate-100"
      >
        Logout
      </button>
    </div>
  )
}
