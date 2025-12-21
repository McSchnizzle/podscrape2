import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/story-arcs/stats')

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()

    // Get total story arcs
    const { count: totalArcs, error: arcCountError } = await supabase
      .from('story_arcs')
      .select('*', { count: 'exact', head: true })

    if (arcCountError) {
      log.warn('Error counting story arcs', { error: arcCountError.message })
    }

    // Get total events
    const { count: totalEvents, error: eventCountError } = await supabase
      .from('story_arc_events')
      .select('*', { count: 'exact', head: true })

    if (eventCountError) {
      log.warn('Error counting events', { error: eventCountError.message })
    }

    // Get arcs by category
    const { data: categoryData, error: categoryError } = await supabase
      .from('story_arcs')
      .select('functional_category')

    const arcsByCategory: Record<string, number> = {}
    if (!categoryError && categoryData) {
      categoryData.forEach(row => {
        const category = row.functional_category || 'other'
        arcsByCategory[category] = (arcsByCategory[category] || 0) + 1
      })
    }

    // Get arcs by digest topic
    const { data: digestData, error: digestError } = await supabase
      .from('story_arcs')
      .select('digest_topic')

    const arcsByDigest: Record<string, number> = {}
    if (!digestError && digestData) {
      digestData.forEach(row => {
        const digest = row.digest_topic || 'unknown'
        arcsByDigest[digest] = (arcsByDigest[digest] || 0) + 1
      })
    }

    // Get average events per arc
    const { data: avgData, error: avgError } = await supabase
      .from('story_arcs')
      .select('event_count')

    let avgEventsPerArc = 0
    if (!avgError && avgData && avgData.length > 0) {
      const sum = avgData.reduce((acc, row) => acc + (row.event_count || 0), 0)
      avgEventsPerArc = sum / avgData.length
    }

    // Get ad stats (kept for backwards compatibility)
    const { count: totalAds, error: adsCountError } = await supabase
      .from('common_ads')
      .select('*', { count: 'exact', head: true })

    if (adsCountError) {
      log.warn('Error counting ads', { error: adsCountError.message })
    }

    const { count: activeAds, error: activeAdsError } = await supabase
      .from('common_ads')
      .select('*', { count: 'exact', head: true })
      .eq('is_active', true)

    if (activeAdsError) {
      log.warn('Error counting active ads', { error: activeAdsError.message })
    }

    return NextResponse.json({
      total_arcs: totalArcs || 0,
      total_events: totalEvents || 0,
      arcs_by_category: arcsByCategory,
      arcs_by_digest: arcsByDigest,
      avg_events_per_arc: avgEventsPerArc,
      total_ads: totalAds || 0,
      active_ads: activeAds || 0
    })
  } catch (error) {
    log.error('Error in stats API', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
