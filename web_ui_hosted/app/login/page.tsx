'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Disc3, Lock, Loader2 } from 'lucide-react'
import { ThemeToggle } from '@/components/ThemeToggle'

/**
 * Constrain the post-login redirect to a same-origin relative path.
 * `next` comes from an unauthenticated query param (middleware.ts sets it
 * when redirecting, but anyone can also link straight to /login?next=...),
 * so reject protocol-relative ("//evil.com"), absolute, and anything else
 * that doesn't resolve to this origin before handing it to router.push.
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

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

      const next = safeNextPath(searchParams.get('next'))
      router.push(next)
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

        <form onSubmit={handleSubmit} className="card">
          {error && (
            <div
              className="mb-[var(--space-4)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
              style={{ background: 'var(--danger-soft)', color: 'var(--danger)', font: 'var(--t-small)' }}
              role="alert"
            >
              {error}
            </div>
          )}

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
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input pl-[36px]"
              placeholder="Enter password"
            />
          </div>

          <button
            type="submit"
            disabled={loading || password.length === 0}
            className="btn btn-primary mt-[var(--space-5)] w-full justify-center"
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

          <p className="field-hint mt-[var(--space-5)] text-center">
            This application is restricted to authorized users only.
          </p>
        </form>
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
