import { NextRequest, NextResponse } from 'next/server'
import { supabaseAuth, isAuthorizedUser } from '@/utils/supabase-auth'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  console.log('Auth callback received:', { code: code?.substring(0, 10) + '...', origin, next })

  if (code) {
    try {
      // Exchange the auth code for a session (this creates the session server-side)
      const { data, error } = await supabaseAuth.auth.exchangeCodeForSession(code)

      if (error) {
        console.error('Auth callback error:', error.message, error)
        return NextResponse.redirect(`${origin}/login?error=auth_failed`)
      }

      // Check authorization before proceeding
      if (data?.user?.email && !isAuthorizedUser(data.user.email)) {
        await supabaseAuth.auth.signOut()
        console.warn(`Unauthorized login attempt from: ${data.user.email}`)
        return NextResponse.redirect(`${origin}/login?error=unauthorized`)
      }

      console.log('Auth exchange successful, rendering callback page')

      // Return HTML that will handle the client-side session restoration
      return new NextResponse(
        `<!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8">
            <title>Authentication complete</title>
            <script>
              // Wait a moment for session to be established, then redirect
              setTimeout(() => {
                window.location.href = '${origin}${next}';
              }, 1000);
            </script>
          </head>
          <body>
            <p>Authentication successful! Redirecting...</p>
          </body>
        </html>`,
        {
          headers: {
            'Content-Type': 'text/html',
          },
        }
      )
    } catch (authError) {
      console.error('Auth callback exception:', authError)
      return NextResponse.redirect(`${origin}/login?error=auth_failed`)
    }
  }

  // Fallback - redirect to login
  return NextResponse.redirect(`${origin}/login`)
}