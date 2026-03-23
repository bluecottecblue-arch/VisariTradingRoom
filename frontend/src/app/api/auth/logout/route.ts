import { NextResponse } from 'next/server'
import {
  SESSION_COOKIE_NAME,
  SESSION_ROLE_COOKIE_NAME,
  SESSION_USERNAME_COOKIE_NAME,
} from '@/lib/auth'

export async function POST() {
  const response = NextResponse.json({ ok: true })
  for (const name of [SESSION_COOKIE_NAME, SESSION_ROLE_COOKIE_NAME, SESSION_USERNAME_COOKIE_NAME]) {
    response.cookies.set({
      name,
      value: '',
      httpOnly: true,
      sameSite: 'lax',
      secure: process.env.NODE_ENV === 'production',
      path: '/',
      maxAge: 0,
    })
  }
  return response
}
