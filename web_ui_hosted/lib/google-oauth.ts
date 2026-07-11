/**
 * Google OAuth2 sign-in for the admin UI (kanban #2846 Phase 3), replacing
 * the password-only login with a direct (non-Supabase) OAuth flow that
 * mints the SAME signed session cookie as /api/auth/login (see
 * lib/session.ts). The password form stays as a break-glass fallback.
 *
 * Pure helpers only -- no Next.js imports -- so this module is unit
 * testable without a request/response cycle. Uses the Web Crypto API (not
 * Node's `crypto`) for the same reason lib/session.ts does: it has to run
 * unmodified under the Next.js Node runtime the API routes use.
 */

import { fromHex, getSessionSecret, importHmacKey, toHex } from './session'

export const GOOGLE_AUTH_ENDPOINT = 'https://accounts.google.com/o/oauth2/v2/auth'
export const GOOGLE_TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
export const GOOGLE_TOKENINFO_ENDPOINT = 'https://oauth2.googleapis.com/tokeninfo'

const DEFAULT_PUBLIC_BASE_URL = 'https://podcast.paulrbrown.org'
const DEFAULT_ALLOWED_EMAILS = 'brownpr0@gmail.com'
const DEFAULT_NEXT_PATH = '/dashboard'
const STATE_MAX_AGE_MS = 10 * 60 * 1000 // 10 minutes, per kanban #2846 spec

export function getPublicBaseUrl(): string {
  const raw = process.env.PUBLIC_BASE_URL || DEFAULT_PUBLIC_BASE_URL
  return raw.replace(/\/+$/, '')
}

export function getGoogleRedirectUri(): string {
  return `${getPublicBaseUrl()}/api/auth/callback/google`
}

export function isGoogleOAuthConfigured(): boolean {
  return Boolean(process.env.GOOGLE_OAUTH_CLIENT_ID && process.env.GOOGLE_OAUTH_CLIENT_SECRET)
}

/**
 * Constrain a post-login redirect to a same-origin relative path. Server-side
 * counterpart of the client-only safeNextPath in app/login/page.tsx -- same
 * rejection rules (protocol-relative, absolute, unparseable), but a
 * /dashboard default since this is only ever invoked once a Google sign-in
 * has actually succeeded (the plain password flow keeps its own '/' default).
 */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith('/')) return DEFAULT_NEXT_PATH
  try {
    const resolved = new URL(raw, 'http://localhost')
    if (resolved.origin !== 'http://localhost') return DEFAULT_NEXT_PATH
    return resolved.pathname + resolved.search + resolved.hash
  } catch {
    return DEFAULT_NEXT_PATH
  }
}

export interface OAuthState {
  nonce: string
  ts: number
  next: string
}

function randomNonce(): string {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return toHex(bytes.buffer)
}

function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64UrlToBytes(b64url: string): Uint8Array | null {
  if (!/^[A-Za-z0-9_-]*$/.test(b64url)) return null
  try {
    const padded = b64url.replace(/-/g, '+').replace(/_/g, '/')
    const pad = (4 - (padded.length % 4)) % 4
    const binary = atob(padded + '='.repeat(pad))
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    return bytes
  } catch {
    return null
  }
}

/** Mint a signed, time-boxed CSRF state token carrying the post-login redirect. */
export async function signState(next: string): Promise<{ token: string; nonce: string }> {
  const nonce = randomNonce()
  const state: OAuthState = { nonce, ts: Date.now(), next }
  const payload = bytesToBase64Url(new TextEncoder().encode(JSON.stringify(state)))
  const key = await importHmacKey(getSessionSecret(), ['sign'])
  const signature = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(payload))
  return { token: `${payload}.${toHex(signature)}`, nonce }
}

/** Cookie that binds the OAuth state to the initiating browser (codex review,
 *  #2846 Phase 3): the callback requires state.nonce === this cookie's value
 *  and clears it on use, so a signed state token cannot be replayed from
 *  another browser or reused within its validity window. */
export const OAUTH_NONCE_COOKIE = 'podcast_oauth_nonce'

/** Verify a state token from the OAuth callback. Returns null for missing/expired/tampered tokens. */
export async function verifyState(token: string | null | undefined): Promise<OAuthState | null> {
  if (!token) return null

  const parts = token.split('.')
  if (parts.length !== 2) return null
  const [payload, signatureHex] = parts

  const signatureBytes = fromHex(signatureHex)
  if (!signatureBytes) return null

  const key = await importHmacKey(getSessionSecret(), ['verify'])
  const valid = await crypto.subtle.verify(
    'HMAC',
    key,
    signatureBytes,
    new TextEncoder().encode(payload)
  )
  if (!valid) return null

  const payloadBytes = base64UrlToBytes(payload)
  if (!payloadBytes) return null

  let state: OAuthState
  try {
    state = JSON.parse(new TextDecoder().decode(payloadBytes))
  } catch {
    return null
  }

  if (
    typeof state !== 'object' ||
    state === null ||
    typeof state.nonce !== 'string' ||
    typeof state.ts !== 'number' ||
    typeof state.next !== 'string'
  ) {
    return null
  }

  if (!Number.isFinite(state.ts) || Date.now() - state.ts > STATE_MAX_AGE_MS || state.ts > Date.now() + 60_000) {
    return null
  }

  return state
}

export interface GoogleTokenInfo {
  aud?: string
  email?: string
  email_verified?: string | boolean
  exp?: string | number
  iss?: string
  sub?: string
  [key: string]: unknown
}

export type IdTokenValidationResult = { ok: true; email: string } | { ok: false; reason: string }

const VALID_ISSUERS = new Set(['accounts.google.com', 'https://accounts.google.com'])

/**
 * Validate the payload from GET .../tokeninfo?id_token=... (kanban #2846
 * spec: aud must match our client, email must be verified, exp must be in
 * the future, iss must be Google).
 */
export function validateIdTokenInfo(
  info: GoogleTokenInfo | null | undefined,
  expectedClientId: string
): IdTokenValidationResult {
  if (!info) return { ok: false, reason: 'missing_tokeninfo' }
  if (!expectedClientId || info.aud !== expectedClientId) return { ok: false, reason: 'aud_mismatch' }

  const emailVerified = info.email_verified === true || info.email_verified === 'true'
  if (!emailVerified) return { ok: false, reason: 'email_not_verified' }

  if (!info.iss || !VALID_ISSUERS.has(info.iss)) return { ok: false, reason: 'bad_issuer' }

  const exp = typeof info.exp === 'string' ? Number(info.exp) : info.exp
  if (typeof exp !== 'number' || !Number.isFinite(exp) || Date.now() / 1000 >= exp) {
    return { ok: false, reason: 'expired' }
  }

  if (!info.email) return { ok: false, reason: 'missing_email' }

  return { ok: true, email: info.email }
}

/**
 * Case-insensitive membership check against ALLOWED_EMAILS (comma-separated).
 * Defaults to the single pre-deletion-gate allowlist entry
 * (brownpr0@gmail.com, formerly utils/supabase-auth.ts ALLOWED_EMAIL) when
 * the env var is unset.
 */
export function isAllowedEmail(email: string | null | undefined, allowlistCsv: string | undefined): boolean {
  if (!email) return false
  const list = (allowlistCsv || DEFAULT_ALLOWED_EMAILS)
    .split(',')
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean)
  return list.includes(email.trim().toLowerCase())
}
