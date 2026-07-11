'use client'

import { useAuth } from './AuthProvider'
import { usePathname } from 'next/navigation'

interface AuthGuardProps {
  children: React.ReactNode
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { authorized, loading } = useAuth()
  const pathname = usePathname()

  // Don't apply auth guard to the login page itself
  const publicPaths = ['/login']
  const isPublicPath = publicPaths.includes(pathname)

  if (isPublicPath) {
    return <div className="min-h-screen flex flex-col bg-bg">{children}</div>
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div className="flex flex-col items-center gap-[var(--space-4)]">
          <div
            className="h-10 w-10 animate-spin rounded-full border-2 border-border-strong"
            style={{ borderTopColor: 'var(--accent)' }}
          />
          <p className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>
            Loading...
          </p>
        </div>
      </div>
    )
  }

  if (!authorized) {
    // Will be redirected to login by AuthProvider
    return null
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg md:ml-[248px]">
      {children}
    </div>
  )
}
