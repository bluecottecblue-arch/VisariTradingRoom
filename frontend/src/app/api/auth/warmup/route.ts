import { NextResponse } from 'next/server'
import { getBackendBaseUrl } from '@/lib/auth'

export async function GET() {
  try {
    const response = await fetch(`${getBackendBaseUrl()}/health`, {
      method: 'GET',
      cache: 'no-store',
      signal: AbortSignal.timeout(25000),
    })

    return NextResponse.json(
      { ok: response.ok, status: response.status },
      { status: response.ok ? 200 : 503 },
    )
  } catch {
    return NextResponse.json(
      { ok: false, detail: 'Backend in riattivazione' },
      { status: 503 },
    )
  }
}
