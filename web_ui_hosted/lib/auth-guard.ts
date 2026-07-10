import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'
import { SESSION_COOKIE_NAME, verifySessionToken } from '@/lib/session'

export interface AuthResult {
  authorized: boolean
  error?: NextResponse
}

/**
 * Server-side authentication guard for API routes. Validates the signed
 * session cookie set by /api/auth/login (kanban #2846).
 *
 * The Next.js middleware (middleware.ts) already blocks unauthenticated
 * requests to non-public routes before they reach here -- this guard is a
 * second, route-local check for routes that call it directly (all but the
 * 4 intentionally public ones: health, heartbeat, and the two RSS feeds).
 *
 * Usage:
 * ```
 * export async function GET() {
 *   const auth = await requireAuth()
 *   if (!auth.authorized) return auth.error
 *
 *   // ... rest of handler
 * }
 * ```
 */
export async function requireAuth(): Promise<AuthResult> {
  const cookieStore = await cookies()
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value
  const authorized = await verifySessionToken(token)

  if (!authorized) {
    return {
      authorized: false,
      error: NextResponse.json({ error: 'Unauthorized - No valid session' }, { status: 401 }),
    }
  }

  return { authorized: true }
}
