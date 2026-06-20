import { NextResponse } from 'next/server'
import { getBackendBaseUrl } from '@/lib/auth'

export async function GET() {
  try {
    const response = await fetch(`${getBackendBaseUrl()}/api/billing/config`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(10000),
    })
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch {
    return NextResponse.json(
      { ok: false, billing_enabled: false, detail: 'Config non raggiungibile' },
      { status: 503 },
    )
  }
}
