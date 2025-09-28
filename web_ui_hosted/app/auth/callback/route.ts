import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  console.log('Auth callback received:', { code: code?.substring(0, 10) + '...', origin, next })

  if (code) {
    // Return HTML that will handle client-side PKCE exchange
    return new NextResponse(
      `<!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <title>Authentication complete</title>
          <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
          <script>
            async function handleAuth() {
              try {
                console.log('Handling client-side auth exchange');

                // Initialize Supabase client
                const supabase = window.supabase.createClient(
                  '${process.env.NEXT_PUBLIC_SUPABASE_URL}',
                  '${process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY}',
                  {
                    auth: {
                      flowType: 'pkce'
                    }
                  }
                );

                // Exchange code for session using client-side PKCE
                const { data, error } = await supabase.auth.exchangeCodeForSession('${code}');

                if (error) {
                  console.error('Auth exchange error:', error);
                  window.location.href = '${origin}/login?error=auth_failed';
                  return;
                }

                if (data?.user?.email) {
                  // Check if user is authorized (brownpr0@gmail.com only)
                  if (data.user.email !== 'brownpr0@gmail.com') {
                    console.warn('Unauthorized user:', data.user.email);
                    await supabase.auth.signOut();
                    window.location.href = '${origin}/login?error=unauthorized';
                    return;
                  }

                  console.log('Auth successful, redirecting to:', '${origin}${next}');
                  window.location.href = '${origin}${next}';
                } else {
                  window.location.href = '${origin}/login?error=no_user';
                }
              } catch (err) {
                console.error('Auth handling error:', err);
                window.location.href = '${origin}/login?error=auth_failed';
              }
            }

            // Start auth handling when page loads
            handleAuth();
          </script>
        </head>
        <body>
          <p>Authentication in progress...</p>
        </body>
      </html>`,
      {
        headers: {
          'Content-Type': 'text/html',
        },
      }
    )
  }

  // Fallback - redirect to login
  return NextResponse.redirect(`${origin}/login`)
}