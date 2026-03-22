import { NextRequest, NextResponse } from 'next/server'
import { APP_GATE_COOKIE_NAME, getExpectedGateToken } from '@/lib/password-gate'

function isPublicPath(pathname: string): boolean {
  return (
    pathname === '/unlock' ||
    pathname.startsWith('/api/auth/unlock') ||
    pathname.startsWith('/_next') ||
    pathname === '/favicon.ico' ||
    /\.[a-zA-Z0-9]+$/.test(pathname)
  )
}

export async function middleware(request: NextRequest) {
  const expected = await getExpectedGateToken()
  if (!expected || isPublicPath(request.nextUrl.pathname)) {
    return NextResponse.next()
  }

  const token = request.cookies.get(APP_GATE_COOKIE_NAME)?.value
  if (token === expected) {
    return NextResponse.next()
  }

  const unlockUrl = request.nextUrl.clone()
  unlockUrl.pathname = '/unlock'
  unlockUrl.searchParams.set('next', request.nextUrl.pathname)
  return NextResponse.redirect(unlockUrl)
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
