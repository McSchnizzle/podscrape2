import { NextRequest, NextResponse } from 'next/server'
import { supabaseAuth, isAuthorizedUser } from '@/utils/supabase-auth'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  if (code) {
    const { data, error } = await supabaseAuth.auth.exchangeCodeForSession(code)

    if (error) {
      console.error('Auth callback error:', error)
      return NextResponse.redirect(`${origin}/login?error=auth_failed`)
    }

    if (data?.user?.email) {
      // Check if user is authorized
      if (!isAuthorizedUser(data.user.email)) {
        // Sign out unauthorized user immediately
        await supabaseAuth.auth.signOut()
        console.warn(`Unauthorized login attempt from: ${data.user.email}`)
        return NextResponse.redirect(`${origin}/login?error=unauthorized`)
      }

      // Authorized user - redirect to intended destination
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  // Fallback - redirect to login
  return NextResponse.redirect(`${origin}/login`)
}