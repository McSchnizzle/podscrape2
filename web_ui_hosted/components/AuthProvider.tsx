'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'

interface AuthContextType {
  authorized: boolean
  loading: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({
  authorized: false,
  loading: true,
  signOut: async () => {},
})

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: React.ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [authorized, setAuthorized] = useState(false)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    let mounted = true

    const checkAuth = async () => {
      try {
        const response = await fetch('/api/auth/me', { cache: 'no-store' })
        if (!mounted) return

        if (response.ok) {
          setAuthorized(true)
          setLoading(false)
        } else {
          setAuthorized(false)
          setLoading(false)
          if (pathname !== '/login') {
            router.push('/login')
          }
        }
      } catch (error) {
        if (!mounted) return
        console.error('Auth check failed:', error)
        setAuthorized(false)
        setLoading(false)
        if (pathname !== '/login') {
          router.push('/login')
        }
      }
    }

    checkAuth()

    return () => {
      mounted = false
    }
  }, [pathname, router])

  const handleSignOut = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' })
    } finally {
      setAuthorized(false)
      router.push('/login')
    }
  }

  const value = {
    authorized,
    loading,
    signOut: handleSignOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
