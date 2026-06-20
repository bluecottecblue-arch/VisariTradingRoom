import { NextRequest, NextResponse } from 'next/server'
import { getBackendBaseUrl } from '@/lib/auth'

export async function POST(request: NextRequest) {
  let body: { email?: string; password?: string; referral_code?: string } = {}
  try {
    body = await request.json()
  } catch {}

  const email = String(body.email || '').trim().toLowerCase()
  const password = String(body.password || '')
  const referral_code = String(body.referral_code || '').trim() || undefined

  if (!email || !password) {
    return NextResponse.json({ detail: 'Email e password obbligatori' }, { status: 400 })
  }

  let response: Response
  try {
    response = await fetch(`${getBackendBaseUrl()}/api/billing/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, referral_code }),
      cache: 'no-store',
      signal: AbortSignal.timeout(20000),
    })
  } catch {
    return NextResponse.json(
      { detail: 'Servizio non raggiungibile. Riprova tra pochi secondi.' },
      { status: 503 },
    )
  }

  let data: any = {}
  try {
    data = await response.json()
  } catch {}

  return NextResponse.json(data, { status: response.status })
}
