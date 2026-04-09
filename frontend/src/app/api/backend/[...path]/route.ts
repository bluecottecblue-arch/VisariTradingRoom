import { NextRequest, NextResponse } from 'next/server'
import { SESSION_COOKIE_NAME, getBackendBaseUrl } from '@/lib/auth'

type RouteContext = {
  params: {
    path: string[]
  }
}

const FORWARDED_RESPONSE_HEADERS = [
  'content-type',
  'content-disposition',
  'cache-control',
]

async function forward(request: NextRequest, context: RouteContext) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value
  if (!token) {
    return NextResponse.json({ detail: 'Login richiesto' }, { status: 401 })
  }

  const upstream = new URL(`${getBackendBaseUrl()}/${context.params.path.join('/')}`)
  request.nextUrl.searchParams.forEach((value, key) => {
    upstream.searchParams.append(key, value)
  })

  const headers = new Headers()
  const accept = request.headers.get('accept')
  const contentType = request.headers.get('content-type')
  if (accept) headers.set('accept', accept)
  if (contentType) headers.set('content-type', contentType)
  headers.set('authorization', `Bearer ${token}`)

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: 'no-store',
    signal: AbortSignal.timeout(60000),
  }

  if (!['GET', 'HEAD'].includes(request.method)) {
    const body = await request.arrayBuffer()
    init.body = body.byteLength ? body : undefined
  }

  let response: Response
  try {
    response = await fetch(upstream.toString(), init)
  } catch {
    return NextResponse.json(
      { detail: 'Backend non raggiungibile. Riprova tra pochi secondi.' },
      { status: 503 },
    )
  }
  const payload = await response.arrayBuffer()
  const outHeaders = new Headers()

  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name)
    if (value) outHeaders.set(name, value)
  }

  return new NextResponse(payload, {
    status: response.status,
    headers: outHeaders,
  })
}

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest, context: RouteContext) {
  return forward(request, context)
}

export async function POST(request: NextRequest, context: RouteContext) {
  return forward(request, context)
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return forward(request, context)
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return forward(request, context)
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return forward(request, context)
}
