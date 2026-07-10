/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    // next.config.js `env` values get inlined into ANY bundle that
    // references them, including client bundles -- unlike NEXT_PUBLIC_*,
    // there's no scoping. Only list values here that are meant to be
    // client-visible. Server code (API routes, utils/supabase.ts,
    // utils/db.ts) reads secrets via process.env directly at runtime and
    // does not need them listed here (kanban #2846 codex review).
    //
    // Build-time information for the footer (components/Footer.tsx, a
    // client component) -- not secrets, safe to inline.
    BUILD_TIME: process.env.BUILD_TIME || new Date().toISOString(),
    VERCEL_GIT_COMMIT_SHA: process.env.VERCEL_GIT_COMMIT_SHA,
    GITHUB_SHA: process.env.GITHUB_SHA,
  },
  async redirects() {
    return [
      {
        source: '/',
        destination: '/dashboard',
        permanent: true,
      },
    ]
  },
  async rewrites() {
    return [
      { source: '/daily-digest.xml',   destination: '/api/rss/daily-digest' },
      { source: '/ai-tech-digest.xml', destination: '/api/rss/ai-tech-digest' },
    ]
  },
}

module.exports = nextConfig