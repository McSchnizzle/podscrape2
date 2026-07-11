import { type NextRequest, NextResponse } from 'next/server'
import { SESSION_COOKIE_NAME, verifySessionToken } from '@/lib/session'

// Exact-match public paths.
const PUBLIC_PATHS = new Set([
  '/login',
  '/api/auth/login',
  '/api/auth/providers',
  // Google OAuth2 sign-in (kanban #2846 Phase 3) -- both legs run before any
  // session cookie exists, so they must stay reachable without one. The
  // callback still rejects on its own terms (bad/expired state, unverified
  // email, non-allowlisted email) and sends the browser to /login?error=...
  '/api/auth/google',
  '/api/auth/callback/google',
  '/api/health',
  // Has its own CRON_SECRET / x-vercel-cron check (app/api/heartbeat/route.ts)
  // and a live 5-min caller (systemd podcast-heartbeat.timer) that doesn't
  // hold a session cookie -- the session guard would otherwise block it
  // before its own auth ever runs.
  '/api/heartbeat',
  '/daily-digest.xml',
  '/ai-tech-digest.xml',
  '/favicon.ico',
])

// Prefix-match public paths.
const PUBLIC_PREFIXES = ['/api/rss/', '/_next/']

const STATIC_ASSET = /\.(?:svg|png|jpg|jpeg|gif|webp|ico)$/

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) return true
  if (PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return true
  if (STATIC_ASSET.test(pathname)) return true
  return false
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (isPublicPath(pathname)) {
    return NextResponse.next()
  }

  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value
  const authorized = await verifySessionToken(token)

  if (authorized) {
    return NextResponse.next()
  }

  if (pathname.startsWith('/api/')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // Behind the Cloudflare tunnel the origin sees Host localhost:3050, so
  // request.url-based absolute redirects would send the browser to
  // localhost. Anchor on PUBLIC_BASE_URL when set (kanban #2846).
  const loginUrl = new URL('/login', process.env.PUBLIC_BASE_URL || request.url)
  loginUrl.searchParams.set('next', pathname)
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: [
    /*
     * Run on everything except Next's static/image internals, which are
     * cheap to serve and never carry admin data.
     */
    '/((?!_next/static|_next/image).*)',
  ],
}
