import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { SESSION_COOKIE_NAME, verifySessionToken } from '@/lib/session'

export const dynamic = 'force-dynamic'

export async function GET() {
  const cookieStore = await cookies()
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value
  const authorized = await verifySessionToken(token)

  if (!authorized) {
    return NextResponse.json({ authorized: false }, { status: 401 })
  }

  return NextResponse.json({ authorized: true })
}
