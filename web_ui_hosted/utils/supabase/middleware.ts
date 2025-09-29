import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

// Global singleton to prevent multiple server client instances
const globalForSupabase = globalThis as unknown as {
  supabaseServerClient: ReturnType<typeof createServerClient> | undefined
}

function getServerClient(request: NextRequest, supabaseResponse: NextResponse) {
  // Create client only once and reuse it
  if (!globalForSupabase.supabaseServerClient) {
    console.log('Middleware: Creating new singleton server client')
    globalForSupabase.supabaseServerClient = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return request.cookies.getAll()
          },
          setAll(cookiesToSet) {
            cookiesToSet.forEach(({ name, value, options }) => request.cookies.set(name, value))
            cookiesToSet.forEach(({ name, value, options }) =>
              supabaseResponse.cookies.set(name, value, options)
            )
          },
        },
      }
    )
  } else {
    console.log('Middleware: Reusing singleton server client')
  }

  return globalForSupabase.supabaseServerClient
}

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = getServerClient(request, supabaseResponse)

  // IMPORTANT: Avoid writing any logic between createServerClient and
  // supabase.auth.getUser(). A simple mistake could make it very hard to debug
  // issues with users being randomly logged out.

  // Just refresh the session, don't check auth (AuthProvider handles that)
  // This prevents duplicate auth checks and multiple client instances
  try {
    await supabase.auth.getSession()
    console.log('Middleware - Session refreshed for path:', request.nextUrl.pathname)
  } catch (error) {
    console.log('Middleware - Session refresh failed:', error)
  }

  // IMPORTANT: You *must* return the supabaseResponse object as it is. If you're
  // creating a new response object with NextResponse.next() make sure to:
  // 1. Pass the request in it, like so:
  //    const myNewResponse = NextResponse.next({ request })
  // 2. Copy over the cookies, like so:
  //    myNewResponse.cookies.setAll(supabaseResponse.cookies.getAll())
  // 3. Change the myNewResponse object to fit your needs, but avoid changing
  //    the cookies!
  // 4. Finally:
  //    return myNewResponse
  // If this is not done, you may be causing the browser and server to go out
  // of sync and terminate the user's session prematurely!

  return supabaseResponse
}