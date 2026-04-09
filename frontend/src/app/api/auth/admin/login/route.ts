import { NextRequest, NextResponse } from 'next/server'
import crypto from 'crypto'
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

function normalizeAdminUsername(): string {
  return String(process.env.ADMIN_USERNAME || '').trim().toLowerCase()
}

function normalizeAdminPassword(): string {
  return String(process.env.ADMIN_PASSWORD || '').trim()
}

function getSessionSecret(): string {
  return String(process.env.SESSION_SECRET || 'dev-session-secret-change-me')
}

function b64urlEncode(raw: Buffer): string {
  return raw.toString('base64url')
}

function createSessionToken(username: string, role: string, ttlSeconds = 60 * 60 * 24 * 14): string {
  const payload = {
    sub: username,
    role,
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
  }
  const encodedPayload = b64urlEncode(Buffer.from(JSON.stringify(payload)))
  const signature = crypto
    .createHmac('sha256', getSessionSecret())
    .update(encodedPayload)
    .digest()
  return `${encodedPayload}.${b64urlEncode(signature)}`
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

  const expectedUsername = normalizeAdminUsername()
  const expectedPassword = normalizeAdminPassword()
  if (expectedUsername && expectedPassword) {
    const ok =
      username.trim().toLowerCase() === expectedUsername &&
      password.trim() === expectedPassword

    if (!ok) {
      return NextResponse.json({ detail: 'Credenziali admin non valide' }, { status: 401 })
    }

    const token = createSessionToken(expectedUsername, 'admin')
    const nextResponse = NextResponse.json({ ok: true, username: expectedUsername, role: 'admin' })
    setSessionCookies(nextResponse, token, expectedUsername, 'admin')
    return nextResponse
  }

  let response: Response
  try {
    response = await fetch(`${getBackendBaseUrl()}/api/auth/admin/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      cache: 'no-store',
      signal: AbortSignal.timeout(60000),
    })
  } catch {
    return NextResponse.json(
      { detail: 'Servizio di autenticazione non raggiungibile. Riprova tra pochi secondi.' },
      { status: 503 },
    )
  }

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
