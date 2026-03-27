import { NextRequest, NextResponse } from 'next/server'
import {
  SESSION_COOKIE_NAME,
  SESSION_ROLE_COOKIE_NAME,
  SESSION_USERNAME_COOKIE_NAME,
  getBackendBaseUrl,
} from '@/lib/auth'

const NO_STORE_HEADERS = { 'Cache-Control': 'no-store' }

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
    }, { headers: NO_STORE_HEADERS })
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
        return NextResponse.json(body, { status: 200, headers: NO_STORE_HEADERS })
      }
    }
    if (response.status === 401 || response.status === 403) {
      return NextResponse.json(
        {
          authenticated: false,
          username: null,
          role: null,
          claude_key_configured: false,
        },
        { status: 200, headers: NO_STORE_HEADERS },
      )
    }
  } catch {
    // fall through to conservative unauthenticated response
  }

  return NextResponse.json({
    authenticated: false,
    username: null,
    role: null,
    claude_key_configured: false,
  }, { headers: NO_STORE_HEADERS })
}
