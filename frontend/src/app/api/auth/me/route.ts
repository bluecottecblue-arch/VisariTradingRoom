import { NextRequest, NextResponse } from 'next/server'
import {
  SESSION_COOKIE_NAME,
  SESSION_ROLE_COOKIE_NAME,
  SESSION_USERNAME_COOKIE_NAME,
  getBackendBaseUrl,
} from '@/lib/auth'

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value
  const role = request.cookies.get(SESSION_ROLE_COOKIE_NAME)?.value || null
  const username = request.cookies.get(SESSION_USERNAME_COOKIE_NAME)?.value || null

  if (!token) {
    return NextResponse.json({
      authenticated: false,
      username,
      role,
      claude_key_configured: false,
    })
  }

  try {
    const response = await fetch(`${getBackendBaseUrl()}/api/auth/me`, {
      method: 'GET',
      headers: {
        authorization: `Bearer ${token}`,
        accept: 'application/json',
      },
      cache: 'no-store',
    })
    if (response.ok) {
      const body = await response.json().catch(() => null)
      if (body && typeof body === 'object') {
        return NextResponse.json(body, { status: 200 })
      }
    }
  } catch {
    // fall through to cookie-based response
  }

  return NextResponse.json({
    authenticated: Boolean(token),
    username,
    role,
    claude_key_configured: false,
  })
}
