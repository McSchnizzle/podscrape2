/**
 * Signed session cookie for the admin UI (kanban #2846), replacing the dead
 * Supabase Google OAuth flow.
 *
 * Implemented with the Web Crypto API (globalThis.crypto.subtle) rather than
 * Node's `crypto` module so the same code works unmodified in both the
 * Next.js middleware Edge runtime and ordinary Node.js API routes -- Next
 * 14's middleware only supports the Edge runtime, which has Web Crypto but
 * not Node's `crypto`.
 */

export const SESSION_COOKIE_NAME = 'podcast_admin_session'
export const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30 // 30 days

const SUBJECT = 'admin'

/**
 * Whether to mark the session cookie Secure. Deliberately NOT based on
 * NODE_ENV -- `next start` always runs in production mode (including in
 * local smoke tests over plain http), and in real production the app sits
 * behind a Cloudflare Tunnel that terminates TLS before forwarding to the
 * origin over plain http, so the Next.js request itself is never https even
 * though the browser's connection is. Trust the standard forwarded-proto
 * header the tunnel sets, falling back to the request's own protocol for a
 * direct https deployment.
 */
export function isSecureRequest(request: { headers: Headers; nextUrl?: { protocol?: string }; url?: string }): boolean {
  const forwardedProto = request.headers.get('x-forwarded-proto')
  if (forwardedProto) {
    return forwardedProto.split(',')[0].trim() === 'https'
  }
  if (request.nextUrl?.protocol) {
    return request.nextUrl.protocol === 'https:'
  }
  if (request.url) {
    return request.url.startsWith('https:')
  }
  return false
}

function getSessionSecret(): string {
  const secret = process.env.SESSION_SECRET
  if (!secret) {
    throw new Error('SESSION_SECRET is not set')
  }
  return secret
}

function toHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

function fromHex(hex: string): Uint8Array<ArrayBuffer> | null {
  if (hex.length === 0 || hex.length % 2 !== 0 || !/^[0-9a-f]+$/i.test(hex)) {
    return null
  }
  const out = new Uint8Array(hex.length / 2)
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(hex.substr(i * 2, 2), 16)
  }
  return out
}

async function importHmacKey(secret: string, usages: KeyUsage[]): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    usages
  )
}

/** Mint a new signed session token (not yet set as a cookie). */
export async function createSessionToken(): Promise<string> {
  const expires = Date.now() + SESSION_MAX_AGE_SECONDS * 1000
  const payload = `${SUBJECT}.${expires}`
  const key = await importHmacKey(getSessionSecret(), ['sign'])
  const signature = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(payload))
  return `${payload}.${toHex(signature)}`
}

/** Verify a session token from a cookie. Returns false for missing/expired/tampered tokens. */
export async function verifySessionToken(token: string | undefined | null): Promise<boolean> {
  if (!token) return false

  const parts = token.split('.')
  if (parts.length !== 3) return false
  const [subject, expiresRaw, signatureHex] = parts
  if (subject !== SUBJECT) return false

  const expires = Number(expiresRaw)
  if (!Number.isFinite(expires) || Date.now() > expires) return false

  const signatureBytes = fromHex(signatureHex)
  if (!signatureBytes) return false

  const key = await importHmacKey(getSessionSecret(), ['verify'])
  return crypto.subtle.verify(
    'HMAC',
    key,
    signatureBytes,
    new TextEncoder().encode(`${subject}.${expiresRaw}`)
  )
}

/**
 * Constant-time password check. Compares HMAC digests (fixed-length, 32
 * bytes) rather than the raw candidate/expected strings so differing input
 * lengths don't short-circuit a plain string comparison.
 */
export async function verifyPassword(candidate: string): Promise<boolean> {
  const expected = process.env.ADMIN_PASSWORD
  if (!expected) return false

  const key = await importHmacKey(getSessionSecret(), ['sign'])
  const [a, b] = await Promise.all([
    crypto.subtle.sign('HMAC', key, new TextEncoder().encode(candidate)),
    crypto.subtle.sign('HMAC', key, new TextEncoder().encode(expected)),
  ])

  const aBytes = new Uint8Array(a)
  const bBytes = new Uint8Array(b)
  let diff = 0
  for (let i = 0; i < aBytes.length; i++) {
    diff |= aBytes[i] ^ bBytes[i]
  }
  return diff === 0
}
