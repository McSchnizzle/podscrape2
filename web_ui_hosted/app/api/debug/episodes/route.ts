import { NextResponse } from 'next/server'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/debug/episodes')

export const dynamic = 'force-dynamic'

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    log.debug('Testing Supabase environment variables')

    // Test environment variables first
    const supabaseUrl = process.env.SUPABASE_URL
    const supabaseServiceRole = process.env.SUPABASE_SERVICE_ROLE

    log.debug('Environment check', { SUPABASE_URL: supabaseUrl ? 'Set' : 'Missing', SUPABASE_SERVICE_ROLE: supabaseServiceRole ? 'Set' : 'Missing' })

    if (!supabaseUrl || !supabaseServiceRole) {
      return NextResponse.json({
        error: 'Missing environment variables',
        details: {
          SUPABASE_URL: supabaseUrl ? 'Set' : 'Missing',
          SUPABASE_SERVICE_ROLE: supabaseServiceRole ? 'Set' : 'Missing'
        }
      }, { status: 500 })
    }

    // Use singleton database client to prevent multiple instances
    const { DatabaseClient } = await import('@/utils/supabase')
    const db = DatabaseClient.getInstance()

    log.debug('Using singleton database client for tests')

    // Test system health (uses database connectivity)
    const health = await db.getSystemHealth()

    if (health.database !== 'connected') {
      return NextResponse.json({
        error: 'Database connection failed',
        details: health,
        environment: { supabaseUrl: supabaseUrl?.substring(0, 30) + '...' }
      }, { status: 500 })
    }

    // Test episode retrieval using database client methods
    const episodesResult = await db.getEpisodes({ pageSize: 3, sortBy: 'published_date', sortDir: 'desc' })

    log.debug('DatabaseClient returned episodes', { count: episodesResult.episodes?.length || 0 })

    return NextResponse.json({
      success: true,
      totalCount: health.feeds_count || 0,
      sampleEpisodes: episodesResult.episodes.slice(0, 3).map((ep: any) => ({
        id: ep.id,
        title: ep.title,
        status: ep.status,
        published_date: ep.published_date
      })),
      environment: {
        supabaseUrl: supabaseUrl?.substring(0, 30) + '...',
        hasServiceRole: !!supabaseServiceRole,
        databaseHealth: health.database
      }
    })

  } catch (error) {
    log.error('Debug API error', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({
      error: 'Debug failed',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 })
  }
}