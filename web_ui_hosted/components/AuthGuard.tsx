'use client'

import { useAuth } from './AuthProvider'
import { usePathname } from 'next/navigation'

interface AuthGuardProps {
  children: React.ReactNode
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading } = useAuth()
  const pathname = usePathname()

  // Don't apply auth guard to login page and auth callback
  const publicPaths = ['/login', '/auth/callback']
  const isPublicPath = publicPaths.includes(pathname)

  if (isPublicPath) {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        {children}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    // Will be redirected to login by AuthProvider
    return null
  }

  return (
    <div className="min-h-screen flex flex-col">
      {children}
    </div>
  )
}