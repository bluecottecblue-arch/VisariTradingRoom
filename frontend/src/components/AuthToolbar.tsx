'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { authApi } from '@/lib/api'

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
    authApi.me()
      .then((body) => {
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
    await authApi.logout().catch(() => null)
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
      <Link href="/dashboard" className="border border-slate-800 px-3 py-1.5 hover:border-slate-600 hover:text-slate-100">
        Dashboard
      </Link>
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
