import { NextRequest, NextResponse } from 'next/server'
import { supabaseAuth, isAuthorizedUser } from '@/utils/supabase-auth'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  console.log('Auth callback received:', { code: code?.substring(0, 10) + '...', origin, next })

  if (code) {
    try {
      // Use the correct PKCE method for code exchange
      const { data, error } = await supabaseAuth.auth.exchangeCodeForSession(code)

      if (error) {
        console.error('Auth callback error:', error.message, error)
        return NextResponse.redirect(`${origin}/login?error=auth_failed`)
      }

      console.log('Auth exchange successful:', { userId: data?.user?.id, email: data?.user?.email })

        if (data?.user?.email) {
          // Check if user is authorized
          if (!isAuthorizedUser(data.user.email)) {
            // Sign out unauthorized user immediately
            await supabaseAuth.auth.signOut()
            console.warn(`Unauthorized login attempt from: ${data.user.email}`)
            return NextResponse.redirect(`${origin}/login?error=unauthorized`)
          }

          // Authorized user - redirect to intended destination
          console.log('User authorized, redirecting to:', `${origin}${next}`)
          return NextResponse.redirect(`${origin}${next}`)
        }
      } catch (authError) {
        console.error('Auth callback exception:', authError)
        return NextResponse.redirect(`${origin}/login?error=auth_failed`)
      }
    }

  // Fallback - redirect to login
  return NextResponse.redirect(`${origin}/login`)
}