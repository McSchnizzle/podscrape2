/**
 * Unit tests for the pure Google OAuth helpers (kanban #2846 Phase 3). Run
 * with `npm run test:unit` (tsx --test, matching repo convention -- no
 * jest/vitest was already installed here).
 */
import { test, describe } from 'node:test'
import assert from 'node:assert/strict'

process.env.SESSION_SECRET = 'test-session-secret-not-for-production'

import {
  isAllowedEmail,
  safeNextPath,
  signState,
  validateIdTokenInfo,
  verifyState,
} from './google-oauth'

describe('safeNextPath', () => {
  test('accepts a plain relative path', () => {
    assert.equal(safeNextPath('/settings'), '/settings')
  })

  test('accepts a relative path with query and hash', () => {
    assert.equal(safeNextPath('/episodes?status=scored#top'), '/episodes?status=scored#top')
  })

  test('defaults to /dashboard for null/undefined/empty', () => {
    assert.equal(safeNextPath(null), '/dashboard')
    assert.equal(safeNextPath(undefined), '/dashboard')
    assert.equal(safeNextPath(''), '/dashboard')
  })

  test('rejects protocol-relative URLs', () => {
    assert.equal(safeNextPath('//evil.example.com'), '/dashboard')
  })

  test('rejects absolute URLs', () => {
    assert.equal(safeNextPath('https://evil.example.com'), '/dashboard')
  })

  test('rejects backslash tricks', () => {
    assert.equal(safeNextPath('/\\evil.example.com'), '/dashboard')
  })

  test('rejects paths not starting with /', () => {
    assert.equal(safeNextPath('dashboard'), '/dashboard')
  })
})

describe('signState / verifyState', () => {
  test('round-trips a freshly signed state', async () => {
    const { token } = await signState('/settings')
    const state = await verifyState(token)
    assert.ok(state)
    assert.equal(state?.next, '/settings')
    assert.equal(typeof state?.nonce, 'string')
    assert.ok(state!.nonce.length > 0)
  })

  test('two signed states have different nonces', async () => {
    const a = await verifyState((await signState('/dashboard')).token)
    const b = await verifyState((await signState('/dashboard')).token)
    assert.notEqual(a?.nonce, b?.nonce)
  })

  test('rejects a missing token', async () => {
    assert.equal(await verifyState(null), null)
    assert.equal(await verifyState(undefined), null)
    assert.equal(await verifyState(''), null)
  })

  test('rejects a malformed token', async () => {
    assert.equal(await verifyState('not-a-valid-token'), null)
    assert.equal(await verifyState('too.many.parts.here'), null)
  })

  test('rejects a tampered signature', async () => {
    const { token } = await signState('/dashboard')
    const [payload, signature] = token.split('.')
    const flipped = signature[0] === 'a' ? 'b' : 'a'
    const tampered = `${payload}.${flipped}${signature.slice(1)}`
    assert.equal(await verifyState(tampered), null)
  })

  test('rejects a tampered payload', async () => {
    const { token } = await signState('/dashboard')
    const [, signature] = token.split('.')
    const tampered = `${Buffer.from(JSON.stringify({ nonce: 'x', ts: Date.now(), next: '/settings' })).toString('base64url')}.${signature}`
    assert.equal(await verifyState(tampered), null)
  })

  test('rejects an expired state', async () => {
    const originalNow = Date.now
    try {
      Date.now = () => 1_000_000_000_000
      const { token } = await signState('/dashboard')
      Date.now = () => 1_000_000_000_000 + 11 * 60 * 1000 // 11 minutes later
      assert.equal(await verifyState(token), null)
    } finally {
      Date.now = originalNow
    }
  })

  test('accepts a state just under the 10-minute window', async () => {
    const originalNow = Date.now
    try {
      Date.now = () => 1_000_000_000_000
      const { token } = await signState('/dashboard')
      Date.now = () => 1_000_000_000_000 + 9 * 60 * 1000 // 9 minutes later
      assert.ok(await verifyState(token))
    } finally {
      Date.now = originalNow
    }
  })
})

describe('validateIdTokenInfo', () => {
  const clientId = 'test-client-id.apps.googleusercontent.com'
  const futureExp = Math.floor(Date.now() / 1000) + 3600

  function goodInfo(overrides: Record<string, unknown> = {}) {
    return {
      aud: clientId,
      email: 'brownpr0@gmail.com',
      email_verified: 'true',
      exp: String(futureExp),
      iss: 'accounts.google.com',
      sub: '12345',
      ...overrides,
    }
  }

  test('accepts a well-formed, matching token', () => {
    const result = validateIdTokenInfo(goodInfo(), clientId)
    assert.equal(result.ok, true)
    if (result.ok) assert.equal(result.email, 'brownpr0@gmail.com')
  })

  test('accepts boolean email_verified too', () => {
    const result = validateIdTokenInfo(goodInfo({ email_verified: true }), clientId)
    assert.equal(result.ok, true)
  })

  test('rejects a missing tokeninfo payload', () => {
    assert.equal(validateIdTokenInfo(null, clientId).ok, false)
    assert.equal(validateIdTokenInfo(undefined, clientId).ok, false)
  })

  test('rejects aud mismatch', () => {
    const result = validateIdTokenInfo(goodInfo({ aud: 'someone-elses-client-id' }), clientId)
    assert.equal(result.ok, false)
    if (!result.ok) assert.equal(result.reason, 'aud_mismatch')
  })

  test('rejects unverified email', () => {
    const result = validateIdTokenInfo(goodInfo({ email_verified: 'false' }), clientId)
    assert.equal(result.ok, false)
    if (!result.ok) assert.equal(result.reason, 'email_not_verified')
  })

  test('rejects a bad issuer', () => {
    const result = validateIdTokenInfo(goodInfo({ iss: 'evil.example.com' }), clientId)
    assert.equal(result.ok, false)
    if (!result.ok) assert.equal(result.reason, 'bad_issuer')
  })

  test('rejects an expired token', () => {
    const pastExp = Math.floor(Date.now() / 1000) - 3600
    const result = validateIdTokenInfo(goodInfo({ exp: String(pastExp) }), clientId)
    assert.equal(result.ok, false)
    if (!result.ok) assert.equal(result.reason, 'expired')
  })

  test('rejects a missing email', () => {
    const result = validateIdTokenInfo(goodInfo({ email: undefined }), clientId)
    assert.equal(result.ok, false)
    if (!result.ok) assert.equal(result.reason, 'missing_email')
  })
})

describe('isAllowedEmail', () => {
  test('defaults to brownpr0@gmail.com when ALLOWED_EMAILS is unset', () => {
    assert.equal(isAllowedEmail('brownpr0@gmail.com', undefined), true)
    assert.equal(isAllowedEmail('someone.else@gmail.com', undefined), false)
  })

  test('is case-insensitive', () => {
    assert.equal(isAllowedEmail('BrownPR0@Gmail.com', undefined), true)
  })

  test('honors a custom comma-separated allowlist', () => {
    const csv = 'alice@example.com, bob@example.com'
    assert.equal(isAllowedEmail('alice@example.com', csv), true)
    assert.equal(isAllowedEmail('bob@example.com', csv), true)
    assert.equal(isAllowedEmail('brownpr0@gmail.com', csv), false)
  })

  test('rejects a missing email', () => {
    assert.equal(isAllowedEmail(null, undefined), false)
    assert.equal(isAllowedEmail(undefined, undefined), false)
    assert.equal(isAllowedEmail('', undefined), false)
  })
})
