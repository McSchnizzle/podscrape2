import { NextRequest, NextResponse } from 'next/server'
import {
  GOOGLE_AUTH_ENDPOINT,
  getGoogleRedirectUri,
  isGoogleOAuthConfigured,
  safeNextPath,
  signState,
} from '@/lib/google-oauth'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/auth/google')

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const clientId = process.env.GOOGLE_OAUTH_CLIENT_ID

  if (!isGoogleOAuthConfigured() || !clientId) {
    log.warn('Google sign-in requested but GOOGLE_OAUTH_* env is not configured')
    return NextResponse.json(
      { error: 'Google sign-in is not configured on this server' },
      { status: 503 }
    )
  }

  const next = safeNextPath(request.nextUrl.searchParams.get('next'))
  const state = await signState(next)

  const url = new URL(GOOGLE_AUTH_ENDPOINT)
  url.searchParams.set('client_id', clientId)
  url.searchParams.set('redirect_uri', getGoogleRedirectUri())
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('scope', 'openid email')
  url.searchParams.set('prompt', 'select_account')
  url.searchParams.set('state', state)

  return NextResponse.redirect(url.toString())
}
