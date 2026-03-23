import { NextRequest, NextResponse } from 'next/server'
import {
  SESSION_COOKIE_NAME,
  SESSION_ROLE_COOKIE_NAME,
  SESSION_USERNAME_COOKIE_NAME,
  getBackendBaseUrl,
} from '@/lib/auth'

function setSessionCookies(response: NextResponse, token: string, username: string, role: string) {
  const secure = process.env.NODE_ENV === 'production'
  const common = {
    httpOnly: true as const,
    sameSite: 'lax' as const,
    secure,
    path: '/',
    maxAge: 60 * 60 * 24 * 14,
  }

  response.cookies.set({ name: SESSION_COOKIE_NAME, value: token, ...common })
  response.cookies.set({ name: SESSION_ROLE_COOKIE_NAME, value: role, ...common })
  response.cookies.set({ name: SESSION_USERNAME_COOKIE_NAME, value: username, ...common })
}

export async function POST(request: NextRequest) {
  let body: { username?: string; password?: string } = {}
  try {
    body = await request.json()
  } catch {}

  const username = String(body.username || '').trim()
  const password = String(body.password || '')

  if (!username || !password) {
    return NextResponse.json({ detail: 'Username e password admin obbligatori' }, { status: 400 })
  }

  const response = await fetch(`${getBackendBaseUrl()}/api/auth/admin/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    cache: 'no-store',
  })

  let data: any = {}
  try {
    data = await response.json()
  } catch {}

  if (!response.ok) {
    return NextResponse.json(
      { detail: data.detail || 'Credenziali admin non valide' },
      { status: response.status },
    )
  }

  const nextResponse = NextResponse.json({ ok: true, username: data.username, role: data.role })
  setSessionCookies(nextResponse, String(data.token || ''), String(data.username || username), String(data.role || 'admin'))
  return nextResponse
}
