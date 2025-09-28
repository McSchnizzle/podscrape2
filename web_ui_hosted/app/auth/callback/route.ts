import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/'

  console.log('Auth callback received:', { code: code?.substring(0, 10) + '...', origin, next })

  if (code) {
    // Return HTML that will handle client-side PKCE exchange
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

    // Escape special characters for safe injection into JavaScript
    const escapeForJS = (str: string) => JSON.stringify(str).slice(1, -1)

    const html = `<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Authentication complete</title>
    <script type="module">
      import { createClient } from 'https://cdn.skypack.dev/@supabase/supabase-js@2'

      async function handleAuth() {
        try {
          console.log('Handling client-side auth exchange');

          // Configuration from server
          const config = {
            supabaseUrl: ${JSON.stringify(supabaseUrl)},
            supabaseAnonKey: ${JSON.stringify(supabaseAnonKey)},
            code: ${JSON.stringify(code)},
            origin: ${JSON.stringify(origin)},
            next: ${JSON.stringify(next)}
          };

          // Initialize Supabase client
          const supabase = createClient(
            config.supabaseUrl,
            config.supabaseAnonKey,
            {
              auth: {
                flowType: 'pkce'
              }
            }
          );

          // Exchange code for session using client-side PKCE
          const { data, error } = await supabase.auth.exchangeCodeForSession(config.code);

          if (error) {
            console.error('Auth exchange error:', error);
            window.location.href = config.origin + '/login?error=auth_failed';
            return;
          }

          if (data?.user?.email) {
            // Check if user is authorized (brownpr0@gmail.com only)
            if (data.user.email !== 'brownpr0@gmail.com') {
              console.warn('Unauthorized user:', data.user.email);
              await supabase.auth.signOut();
              window.location.href = config.origin + '/login?error=unauthorized';
              return;
            }

            console.log('Auth successful, redirecting to:', config.origin + config.next);
            window.location.href = config.origin + config.next;
          } else {
            window.location.href = config.origin + '/login?error=no_user';
          }
        } catch (err) {
          console.error('Auth handling error:', err);
          window.location.href = window.location.origin + '/login?error=auth_failed';
        }
      }

      // Start auth handling when page loads
      handleAuth();
    </script>
  </head>
  <body>
    <p>Authentication in progress...</p>
  </body>
</html>`

    return new NextResponse(html, {
      headers: {
        'Content-Type': 'text/html',
      },
    })
  }

  // Fallback - redirect to login
  return NextResponse.redirect(`${origin}/login`)
}