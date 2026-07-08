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

// Auth is unconfigured while the admin backend is rebuilt after the Supabase
// project deletion (kanban #2710). NEXT_PUBLIC_* vars are inlined at build
// time, so this is a build-time constant.
const AUTH_CONFIGURED = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
)

function MaintenanceNotice() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-6">
      <div className="max-w-lg w-full rounded-xl border border-gray-700 bg-gray-900 p-8 shadow-2xl text-center">
        <div className="text-4xl mb-4">🔧</div>
        <h1 className="text-xl font-semibold text-gray-100 mb-3">
          Admin dashboard temporarily offline
        </h1>
        <p className="text-sm text-gray-300 leading-relaxed mb-4">
          The podcast pipeline is running normally and the public feeds are
          unaffected. The admin interface is waiting on a new login and data
          backend after the move off Supabase.
        </p>
        <p className="text-xs text-gray-500">
          Tracked as kanban #2710 · RSS: <span className="text-gray-400">/daily-digest.xml</span>
        </p>
      </div>
    </div>
  )
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (!AUTH_CONFIGURED) return

    let mounted = true
    let isAuthCheckInProgress = false

    const checkAuth = async () => {
      // Prevent concurrent auth checks
      if (isAuthCheckInProgress) {
        console.log('AuthProvider: Auth check already in progress, skipping')
        return
      }

      isAuthCheckInProgress = true
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
      } finally {
        isAuthCheckInProgress = false
      }
    }

    // Check auth on mount only
    checkAuth()

    // Listen for auth state changes
    const { data: { subscription } } = supabaseAuth.auth.onAuthStateChange(
      async (event: AuthChangeEvent, session: Session | null) => {
        if (!mounted || isAuthCheckInProgress) return

        console.log('AuthProvider: Auth state change:', event, !!session?.user)

        if (event === 'SIGNED_OUT' || !session?.user) {
          setUser(null)
          if (pathname !== '/login') {
            router.push('/login')
          }
        } else if (event === 'SIGNED_IN') {
          // Validate the signed-in user
          isAuthCheckInProgress = true
          try {
            const { authorized, user: validatedUser } = await validateUserAuth()
            if (authorized && validatedUser) {
              setUser(validatedUser)
            } else {
              setUser(null)
              router.push('/login')
            }
          } finally {
            isAuthCheckInProgress = false
          }
        }
        setLoading(false)
      }
    )

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [router]) // Removed pathname dependency to prevent re-checking on navigation

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
      {AUTH_CONFIGURED ? children : <MaintenanceNotice />}
    </AuthContext.Provider>
  )
}