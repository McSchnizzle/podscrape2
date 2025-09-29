import { createClient } from '@/utils/supabase/client'

// Create client-side Supabase client for authentication
export const supabaseAuth = createClient()

// Allowed email for authentication
const ALLOWED_EMAIL = 'brownpr0@gmail.com'

// Sign in with Google OAuth
export async function signInWithGoogle() {
  const { data, error } = await supabaseAuth.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
      queryParams: {
        access_type: 'offline',
        prompt: 'consent',
      }
    }
  })
  return { data, error }
}

// Sign out and clear session cache
export async function signOut() {
  // Clear session cache to prevent stale data
  sessionCache = null
  console.log('signOut: Cleared session cache')

  const { error } = await supabaseAuth.auth.signOut()
  return { error }
}

// Session cache to prevent multiple concurrent calls
let sessionCache: { session: any; error: any; timestamp: number } | null = null
const CACHE_DURATION = 5000 // 5 seconds

// Get current session with caching and timeout
export async function getSession() {
  // Return cached session if valid
  if (sessionCache && Date.now() - sessionCache.timestamp < CACHE_DURATION) {
    console.log('getSession: Returning cached session')
    return { session: sessionCache.session, error: sessionCache.error }
  }

  const sessionPromise = supabaseAuth.auth.getSession()

  // Increased timeout to 15 seconds for better reliability
  const timeoutPromise = new Promise((_, reject) => {
    setTimeout(() => reject(new Error('Session timeout')), 15000)
  })

  try {
    const { data: { session }, error } = await Promise.race([sessionPromise, timeoutPromise]) as any

    // Cache the result
    sessionCache = {
      session,
      error,
      timestamp: Date.now()
    }

    return { session, error }
  } catch (error) {
    console.error('Session retrieval failed:', error)

    // Cache the error to prevent immediate retries
    sessionCache = {
      session: null,
      error: error as Error,
      timestamp: Date.now()
    }

    return { session: null, error: error as Error }
  }
}

// Check if user is authorized (brownpr0@gmail.com only)
export function isAuthorizedUser(email?: string | null): boolean {
  return email === ALLOWED_EMAIL
}

// Validate current user authorization
export async function validateUserAuth() {
  console.log('validateUserAuth: Starting validation...')
  const { session, error } = await getSession()
  console.log('validateUserAuth: Session result:', { hasSession: !!session, error, email: session?.user?.email })

  if (error) {
    // Clear cache on auth errors to force fresh checks
    sessionCache = null
    console.log('validateUserAuth: Cleared session cache due to error')
  }

  if (!session?.user?.email) {
    console.log('validateUserAuth: No active session')
    return { authorized: false, reason: 'No active session' }
  }

  if (!isAuthorizedUser(session.user.email)) {
    console.log('validateUserAuth: Unauthorized email:', session.user.email)
    // Sign out unauthorized users immediately
    await signOut()
    return { authorized: false, reason: 'Unauthorized email address' }
  }

  console.log('validateUserAuth: User authorized:', session.user.email)
  return { authorized: true, user: session.user }
}