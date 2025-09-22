/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    DATABASE_URL: process.env.DATABASE_URL,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE: process.env.SUPABASE_SERVICE_ROLE,
    GITHUB_TOKEN: process.env.GITHUB_TOKEN,
    WEBUI_SECRET: process.env.WEBUI_SECRET,
    // Build-time information for footer
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
}

module.exports = nextConfig