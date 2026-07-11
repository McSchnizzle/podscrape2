import { NextRequest, NextResponse } from 'next/server'
import {
  GOOGLE_TOKEN_ENDPOINT,
  OAUTH_NONCE_COOKIE,
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

function loginRedirect(
  request: NextRequest,
  error: string,
  opts: { clearNonce?: boolean } = {}
): NextResponse {
  const url = new URL('/login', request.url)
  url.searchParams.set('error', error)
  const response = NextResponse.redirect(url)
  if (opts.clearNonce) {
    response.cookies.set(OAUTH_NONCE_COOKIE, '', { path: '/api/auth', maxAge: 0 })
  }
  return response
}

export async function GET(request: NextRequest) {
  const clientId = process.env.GOOGLE_OAUTH_CLIENT_ID
  const clientSecret = process.env.GOOGLE_OAUTH_CLIENT_SECRET

  if (!clientId || !clientSecret) {
    log.warn('OAuth callback hit but GOOGLE_OAUTH_* env is not configured')
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  const params = request.nextUrl.searchParams
  const oauthError = params.get('error')
  if (oauthError) {
    log.warn('Google returned an OAuth error', { oauthError })
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  const state = await verifyState(params.get('state'))
  if (!state) {
    log.warn('OAuth state missing, expired, or invalid')
    return loginRedirect(request, 'state_invalid')
  }

  // Browser binding + single use (codex review, #2846 Phase 3): the state is
  // only accepted from the browser that initiated the flow, and the binding
  // cookie is consumed on every callback attempt so a state token cannot be
  // replayed.
  const boundNonce = request.cookies.get(OAUTH_NONCE_COOKIE)?.value
  if (!boundNonce || boundNonce !== state.nonce) {
    log.warn('OAuth state nonce is not bound to this browser', { hasCookie: Boolean(boundNonce) })
    return loginRedirect(request, 'state_invalid', { clearNonce: true })
  }

  const code = params.get('code')
  if (!code) {
    log.warn('OAuth callback missing code param')
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
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
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  if (!tokenResponse.ok) {
    log.warn('Token exchange rejected by Google', { status: tokenResponse.status })
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  const tokenBody = (await tokenResponse.json().catch(() => null)) as { id_token?: string } | null
  const idToken = tokenBody?.id_token
  if (!idToken) {
    log.warn('Token exchange response missing id_token')
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  let tokenInfoResponse: Response
  try {
    tokenInfoResponse = await fetch(
      `${GOOGLE_TOKENINFO_ENDPOINT}?id_token=${encodeURIComponent(idToken)}`
    )
  } catch (err) {
    log.error('tokeninfo request failed', { message: err instanceof Error ? err.message : String(err) })
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  if (!tokenInfoResponse.ok) {
    log.warn('tokeninfo rejected the id_token', { status: tokenInfoResponse.status })
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  const tokenInfo = await tokenInfoResponse.json().catch(() => null)
  const validation = validateIdTokenInfo(tokenInfo, clientId)
  if (!validation.ok) {
    log.warn('id_token failed validation', { reason: validation.reason })
    return loginRedirect(request, 'oauth_failed', { clearNonce: true })
  }

  if (!isAllowedEmail(validation.email, process.env.ALLOWED_EMAILS)) {
    log.warn('Blocked Google sign-in from a non-allowlisted email', { email: validation.email })
    return loginRedirect(request, 'not_allowed', { clearNonce: true })
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
  // Consume the browser-binding nonce: each state token is single-use.
  response.cookies.set(OAUTH_NONCE_COOKIE, '', { path: '/api/auth', maxAge: 0 })

  log.info('Google login successful', { email: validation.email })
  return response
}
