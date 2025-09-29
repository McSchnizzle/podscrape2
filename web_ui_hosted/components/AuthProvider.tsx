'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { User, AuthChangeEvent, Session } from '@supabase/supabase-js'
import { supabaseAuth, validateUserAuth, signOut } from '@/utils/supabase-auth'

interface AuthContextType {
  user: User | null
  loading: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  signOut: async () => {}
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
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    let mounted = true

    const checkAuth = async () => {
      try {
        console.log('AuthProvider: Starting auth check...')
        const { authorized, user: validatedUser, reason } = await validateUserAuth()
        console.log('AuthProvider: Auth result:', { authorized, hasUser: !!validatedUser, reason })

        if (!mounted) return

        if (authorized && validatedUser) {
          console.log('AuthProvider: Setting user and clearing loading')
          setUser(validatedUser)
          setLoading(false)
        } else {
          console.log('AuthProvider: No valid user, redirecting to login')
          setUser(null)
          setLoading(false)

          // Don't redirect if already on login page
          if (pathname !== '/login') {
            console.warn('Authentication failed:', reason)
            router.push('/login')
          }
        }
      } catch (error) {
        if (!mounted) return

        console.error('Auth check error:', error)
        setUser(null)
        setLoading(false)

        if (pathname !== '/login') {
          router.push('/login')
        }
      }
    }

    // Check auth on mount
    checkAuth()

    // Listen for auth state changes
    const { data: { subscription } } = supabaseAuth.auth.onAuthStateChange(
      async (event: AuthChangeEvent, session: Session | null) => {
        if (!mounted) return

        if (event === 'SIGNED_OUT' || !session?.user) {
          setUser(null)
          if (pathname !== '/login') {
            router.push('/login')
          }
        } else if (event === 'SIGNED_IN') {
          // Validate the signed-in user
          const { authorized, user: validatedUser } = await validateUserAuth()
          if (authorized && validatedUser) {
            setUser(validatedUser)
          } else {
            setUser(null)
            router.push('/login')
          }
        }
        setLoading(false)
      }
    )

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [router, pathname])

  const handleSignOut = async () => {
    await signOut()
    setUser(null)
    router.push('/login')
  }

  const value = {
    user,
    loading,
    signOut: handleSignOut
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}