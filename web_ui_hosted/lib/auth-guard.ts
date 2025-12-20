import { createClient } from '@/utils/supabase/server'
import { NextResponse } from 'next/server'

const ALLOWED_EMAILS = ['brownpr0@gmail.com']

export interface AuthResult {
  authorized: boolean
  user?: { email: string; id: string }
  error?: NextResponse
}

/**
 * Server-side authentication guard for API routes.
 * Uses Supabase SSR to validate user sessions and check against allowed email list.
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
  const supabase = await createClient()

  const { data: { user }, error } = await supabase.auth.getUser()

  if (error || !user) {
    return {
      authorized: false,
      error: NextResponse.json(
        { error: 'Unauthorized - No valid session' },
        { status: 401 }
      )
    }
  }

  if (!user.email || !ALLOWED_EMAILS.includes(user.email)) {
    return {
      authorized: false,
      error: NextResponse.json(
        { error: 'Forbidden - Email not authorized' },
        { status: 403 }
      )
    }
  }

  return {
    authorized: true,
    user: { email: user.email, id: user.id }
  }
}
