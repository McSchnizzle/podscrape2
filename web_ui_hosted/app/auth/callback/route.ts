import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/utils/supabase/server'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  console.log('OAuth callback received:', { code: !!code, next })

  if (code) {
    const supabase = createClient()

    try {
      const { error } = await supabase.auth.exchangeCodeForSession(code)

      if (error) {
        console.error('OAuth code exchange error:', error)
        return NextResponse.redirect(`${origin}/login?error=auth_failed`)
      }

      console.log('OAuth code exchange successful')
    } catch (error) {
      console.error('OAuth callback error:', error)
      return NextResponse.redirect(`${origin}/login?error=callback_failed`)
    }
  }

  // Redirect to the next URL or home page
  return NextResponse.redirect(`${origin}${next}`)
}