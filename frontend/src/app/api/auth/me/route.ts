import { NextRequest, NextResponse } from 'next/server'
import {
  SESSION_COOKIE_NAME,
  SESSION_ROLE_COOKIE_NAME,
  SESSION_USERNAME_COOKIE_NAME,
} from '@/lib/auth'

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value
  const role = request.cookies.get(SESSION_ROLE_COOKIE_NAME)?.value || null
  const username = request.cookies.get(SESSION_USERNAME_COOKIE_NAME)?.value || null

  return NextResponse.json({
    authenticated: Boolean(token),
    username,
    role,
  })
}
