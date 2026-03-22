import { NextRequest, NextResponse } from 'next/server'
import { APP_GATE_COOKIE_NAME, createGateToken, getExpectedGateToken } from '@/lib/password-gate'

export async function POST(request: NextRequest) {
  const expected = await getExpectedGateToken()
  if (!expected) {
    return NextResponse.json({ ok: true, bypassed: true })
  }

  let password = ''
  try {
    const body = await request.json()
    password = String(body?.password || '')
  } catch {
    password = ''
  }

  if (!password) {
    return NextResponse.json({ detail: 'Password obbligatoria' }, { status: 400 })
  }

  const token = await createGateToken(password)
  if (token !== expected) {
    return NextResponse.json({ detail: 'Password non valida' }, { status: 401 })
  }

  const response = NextResponse.json({ ok: true })
  response.cookies.set({
    name: APP_GATE_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: 60 * 60 * 24 * 30,
  })
  return response
}
