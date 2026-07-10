import { NextRequest, NextResponse } from 'next/server'
import {
  createSessionToken,
  isSecureRequest,
  SESSION_COOKIE_NAME,
  SESSION_MAX_AGE_SECONDS,
  verifyPassword,
} from '@/lib/session'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/auth/login')

export const dynamic = 'force-dynamic'

export async function POST(request: NextRequest) {
  let password: unknown
  try {
    const body = await request.json()
    password = body?.password
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }

  if (typeof password !== 'string' || password.length === 0) {
    return NextResponse.json({ error: 'Password is required' }, { status: 400 })
  }

  const valid = await verifyPassword(password)
  if (!valid) {
    log.warn('Failed login attempt')
    return NextResponse.json({ error: 'Invalid password' }, { status: 401 })
  }

  const token = await createSessionToken()
  const response = NextResponse.json({ success: true })
  response.cookies.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: isSecureRequest(request),
    sameSite: 'lax',
    path: '/',
    maxAge: SESSION_MAX_AGE_SECONDS,
  })

  log.info('Login successful')
  return response
}
