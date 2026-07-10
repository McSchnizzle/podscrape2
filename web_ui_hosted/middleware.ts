import { type NextRequest, NextResponse } from 'next/server'
import { SESSION_COOKIE_NAME, verifySessionToken } from '@/lib/session'

// Exact-match public paths.
const PUBLIC_PATHS = new Set([
  '/login',
  '/api/auth/login',
  '/api/health',
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

  const loginUrl = new URL('/login', request.url)
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
