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

// Sign out
export async function signOut() {
  const { error } = await supabaseAuth.auth.signOut()
  return { error }
}

// Get current session
export async function getSession() {
  const { data: { session }, error } = await supabaseAuth.auth.getSession()
  return { session, error }
}

// Check if user is authorized (brownpr0@gmail.com only)
export function isAuthorizedUser(email?: string | null): boolean {
  return email === ALLOWED_EMAIL
}

// Validate current user authorization
export async function validateUserAuth() {
  const { session } = await getSession()

  if (!session?.user?.email) {
    return { authorized: false, reason: 'No active session' }
  }

  if (!isAuthorizedUser(session.user.email)) {
    // Sign out unauthorized users immediately
    await signOut()
    return { authorized: false, reason: 'Unauthorized email address' }
  }

  return { authorized: true, user: session.user }
}