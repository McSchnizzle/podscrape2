import { NextRequest, NextResponse } from 'next/server'
import {
  GOOGLE_TOKEN_ENDPOINT,
  GOOGLE_TOKENINFO_ENDPOINT,
  getGoogleRedirectUri,
  isAllowedEmail,
  safeNextPath,
  validateIdTokenInfo,
  verifyState,
} from '@/lib/google-oauth'
import {
  createSessionToken,
  isSecureRequest,
  SESSION_COOKIE_NAME,
  SESSION_MAX_AGE_SECONDS,
} from '@/lib/session'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/auth/callback/google')

export const dynamic = 'force-dynamic'

function loginRedirect(request: NextRequest, error: string): NextResponse {
  const url = new URL('/login', request.url)
  url.searchParams.set('error', error)
  return NextResponse.redirect(url)
}

export async function GET(request: NextRequest) {
  const clientId = process.env.GOOGLE_OAUTH_CLIENT_ID
  const clientSecret = process.env.GOOGLE_OAUTH_CLIENT_SECRET

  if (!clientId || !clientSecret) {
    log.warn('OAuth callback hit but GOOGLE_OAUTH_* env is not configured')
    return loginRedirect(request, 'oauth_failed')
  }

  const params = request.nextUrl.searchParams
  const oauthError = params.get('error')
  if (oauthError) {
    log.warn('Google returned an OAuth error', { oauthError })
    return loginRedirect(request, 'oauth_failed')
  }

  const state = await verifyState(params.get('state'))
  if (!state) {
    log.warn('OAuth state missing, expired, or invalid')
    return loginRedirect(request, 'state_invalid')
  }

  const code = params.get('code')
  if (!code) {
    log.warn('OAuth callback missing code param')
    return loginRedirect(request, 'oauth_failed')
  }

  const redirectUri = getGoogleRedirectUri()

  let tokenResponse: Response
  try {
    tokenResponse = await fetch(GOOGLE_TOKEN_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    })
  } catch (err) {
    log.error('Token exchange request failed', { message: err instanceof Error ? err.message : String(err) })
    return loginRedirect(request, 'oauth_failed')
  }

  if (!tokenResponse.ok) {
    log.warn('Token exchange rejected by Google', { status: tokenResponse.status })
    return loginRedirect(request, 'oauth_failed')
  }

  const tokenBody = (await tokenResponse.json().catch(() => null)) as { id_token?: string } | null
  const idToken = tokenBody?.id_token
  if (!idToken) {
    log.warn('Token exchange response missing id_token')
    return loginRedirect(request, 'oauth_failed')
  }

  let tokenInfoResponse: Response
  try {
    tokenInfoResponse = await fetch(
      `${GOOGLE_TOKENINFO_ENDPOINT}?id_token=${encodeURIComponent(idToken)}`
    )
  } catch (err) {
    log.error('tokeninfo request failed', { message: err instanceof Error ? err.message : String(err) })
    return loginRedirect(request, 'oauth_failed')
  }

  if (!tokenInfoResponse.ok) {
    log.warn('tokeninfo rejected the id_token', { status: tokenInfoResponse.status })
    return loginRedirect(request, 'oauth_failed')
  }

  const tokenInfo = await tokenInfoResponse.json().catch(() => null)
  const validation = validateIdTokenInfo(tokenInfo, clientId)
  if (!validation.ok) {
    log.warn('id_token failed validation', { reason: validation.reason })
    return loginRedirect(request, 'oauth_failed')
  }

  if (!isAllowedEmail(validation.email, process.env.ALLOWED_EMAILS)) {
    log.warn('Blocked Google sign-in from a non-allowlisted email', { email: validation.email })
    return loginRedirect(request, 'not_allowed')
  }

  const token = await createSessionToken()
  const nextPath = safeNextPath(state.next)
  const response = NextResponse.redirect(new URL(nextPath, request.url))
  response.cookies.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: isSecureRequest(request),
    sameSite: 'lax',
    path: '/',
    maxAge: SESSION_MAX_AGE_SECONDS,
  })

  log.info('Google login successful', { email: validation.email })
  return response
}
