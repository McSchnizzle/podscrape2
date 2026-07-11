import { NextResponse } from 'next/server'
import { isGoogleOAuthConfigured } from '@/lib/google-oauth'

export const dynamic = 'force-dynamic'

/**
 * Lets the login page (a client component) decide whether to render the
 * Google sign-in button without hardcoding env presence into the client
 * bundle. Graceful degradation to password-only when GOOGLE_OAUTH_* is
 * absent (kanban #2846).
 */
export async function GET() {
  return NextResponse.json({ google: isGoogleOAuthConfigured() })
}
