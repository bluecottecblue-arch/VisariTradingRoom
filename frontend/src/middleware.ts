import { NextRequest, NextResponse } from 'next/server'
import { SESSION_COOKIE_NAME, SESSION_ROLE_COOKIE_NAME } from '@/lib/auth'

function isPublicPath(pathname: string): boolean {
  return (
    pathname === '/' ||
    pathname === '/login' ||
    pathname === '/admin/login' ||
    pathname.startsWith('/api/auth/') ||
    pathname.startsWith('/api/backend/') ||
    pathname.startsWith('/_next') ||
    pathname === '/favicon.ico' ||
    /\.[a-zA-Z0-9]+$/.test(pathname)
  )
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  if (pathname === '/') {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = '/login'
    loginUrl.search = ''
    return NextResponse.redirect(loginUrl)
  }
  if (isPublicPath(pathname)) {
    return NextResponse.next()
  }

  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value
  const role = request.cookies.get(SESSION_ROLE_COOKIE_NAME)?.value

  if (!token || !role || !['user', 'admin'].includes(role)) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = pathname.startsWith('/admin') ? '/admin/login' : '/login'
    loginUrl.searchParams.set('next', pathname)
    return NextResponse.redirect(loginUrl)
  }

  if (pathname.startsWith('/admin') && role !== 'admin') {
    const adminUrl = request.nextUrl.clone()
    adminUrl.pathname = '/admin/login'
    adminUrl.searchParams.set('next', pathname)
    return NextResponse.redirect(adminUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
