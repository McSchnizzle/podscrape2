'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Disc3, Lock, Loader2, ChevronDown } from 'lucide-react'
import { ThemeToggle } from '@/components/ThemeToggle'

/**
 * Constrain the post-login redirect to a same-origin relative path.
 * `next` comes from an unauthenticated query param (middleware.ts sets it
 * when redirecting, but anyone can also link straight to /login?next=...),
 * so reject protocol-relative ("//evil.com"), absolute, and anything else
 * that doesn't resolve to this origin before handing it to router.push.
 *
 * Server-side counterpart (used by /api/auth/google and the OAuth callback)
 * lives in lib/google-oauth.ts -- same rejection rules, different default.
 */
function safeNextPath(raw: string | null): string {
  if (!raw || !raw.startsWith('/')) return '/'
  try {
    const resolved = new URL(raw, 'http://localhost')
    if (resolved.origin !== 'http://localhost') return '/'
    return resolved.pathname + resolved.search + resolved.hash
  } catch {
    return '/'
  }
}

const ERROR_MESSAGES: Record<string, string> = {
  not_allowed: 'That Google account is not authorized for this application.',
  oauth_failed: 'Google sign-in failed. Please try again.',
  state_invalid: 'Your sign-in attempt expired or could not be verified. Please try again.',
}

function friendlyError(code: string | null): string | null {
  if (!code) return null
  return ERROR_MESSAGES[code] || 'Sign-in failed. Please try again.'
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  )
}

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [googleEnabled, setGoogleEnabled] = useState(false)
  const [checkingProviders, setCheckingProviders] = useState(true)
  const [showPasswordForm, setShowPasswordForm] = useState(false)

  const next = searchParams.get('next')
  const safeNext = safeNextPath(next)

  useEffect(() => {
    let mounted = true
    fetch('/api/auth/providers', { cache: 'no-store' })
      .then((res) => (res.ok ? res.json() : { google: false }))
      .then((body) => {
        if (!mounted) return
        setGoogleEnabled(Boolean(body?.google))
        setCheckingProviders(false)
        // No Google provider configured -- go straight to the password
        // form instead of showing a dead-end primary button.
        if (!body?.google) setShowPasswordForm(true)
      })
      .catch(() => {
        if (!mounted) return
        setGoogleEnabled(false)
        setCheckingProviders(false)
        setShowPasswordForm(true)
      })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    setError(friendlyError(searchParams.get('error')))
  }, [searchParams])

  const googleHref = `/api/auth/google${next ? `?next=${encodeURIComponent(safeNext)}` : ''}`

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })

      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        setError(body.error || 'Invalid password')
        setLoading(false)
        return
      }

      router.push(safeNext)
      router.refresh()
    } catch (err) {
      console.error('Login error:', err)
      setError('An unexpected error occurred. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-bg px-[var(--space-5)] py-[var(--space-8)]">
      <div className="absolute right-[var(--space-5)] top-[var(--space-5)]">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-[400px]">
        <div className="mb-[var(--space-6)] flex flex-col items-center text-center">
          <div
            className="mb-[var(--space-4)] flex h-14 w-14 items-center justify-center rounded-lg shadow-md"
            style={{ background: 'var(--accent)', color: 'var(--on-accent)' }}
          >
            <Disc3 size={28} />
          </div>
          <h1 style={{ font: 'var(--t-h1)', color: 'var(--text)' }}>Podcast Digest Admin</h1>
          <p className="mt-[var(--space-2)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
            Restricted access — authorized users only
          </p>
        </div>

        <div className="card">
          {error && (
            <div
              data-testid="login-error"
              className="mb-[var(--space-4)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
              style={{ background: 'var(--danger-soft)', color: 'var(--danger)', font: 'var(--t-small)' }}
              role="alert"
            >
              {error}
            </div>
          )}

          {checkingProviders ? (
            <div className="flex items-center justify-center py-[var(--space-5)]">
              <Loader2 size={24} className="animate-spin text-accent" />
            </div>
          ) : (
            <>
              {googleEnabled && (
                <a href={googleHref} className="btn btn-primary w-full justify-center">
                  <GoogleIcon />
                  Sign in with Google
                </a>
              )}

              {googleEnabled && !showPasswordForm && (
                <button
                  type="button"
                  onClick={() => setShowPasswordForm(true)}
                  className="mt-[var(--space-4)] flex w-full items-center justify-center gap-1 text-ink-subtle"
                  style={{ font: 'var(--t-small)', background: 'transparent', border: 'none', cursor: 'pointer' }}
                >
                  Use fallback password
                  <ChevronDown size={14} />
                </button>
              )}

              {showPasswordForm && (
                <form
                  onSubmit={handleSubmit}
                  className={googleEnabled ? 'mt-[var(--space-5)] border-t border-border pt-[var(--space-5)]' : ''}
                >
                  <label htmlFor="password" className="field-label">
                    Password
                  </label>
                  <div className="relative">
                    <Lock
                      size={16}
                      className="pointer-events-none absolute left-[var(--space-3)] top-1/2 -translate-y-1/2 text-ink-faint"
                    />
                    <input
                      id="password"
                      name="password"
                      type="password"
                      autoComplete="current-password"
                      required
                      autoFocus={!googleEnabled}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="input pl-[36px]"
                      placeholder="Enter password"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading || password.length === 0}
                    className={`btn ${googleEnabled ? 'btn-secondary' : 'btn-primary'} mt-[var(--space-5)] w-full justify-center`}
                  >
                    {loading ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        Signing in…
                      </>
                    ) : (
                      'Sign in'
                    )}
                  </button>
                </form>
              )}

              <p className="field-hint mt-[var(--space-5)] text-center">
                This application is restricted to authorized users only.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-bg">
          <Loader2 size={28} className="animate-spin text-accent" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  )
}
