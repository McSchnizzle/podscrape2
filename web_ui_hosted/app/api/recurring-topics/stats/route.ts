import { NextResponse } from 'next/server'
import { supabase as sharedSupabase } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/recurring-topics/stats')

export const dynamic = 'force-dynamic'

// Server-only client against the local PostgREST stack (kanban #2846).
// Kept as a function (not a direct import at call sites) to avoid
// touching the existing getSupabaseClient() call sites in this file.
function getSupabaseClient() {
  return sharedSupabase
}

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()

    // Get total topics
    const { count: totalTopics, error: countError } = await supabase
      .from('episode_topics')
      .select('*', { count: 'exact', head: true })

    if (countError) {
      log.warn('Error counting topics', { error: countError.message })
    }

    // Get average novelty score
    const { data: noveltyData, error: noveltyError } = await supabase
      .from('episode_topics')
      .select('novelty_score')

    let avgNoveltyScore = 0
    if (!noveltyError && noveltyData && noveltyData.length > 0) {
      const sum = noveltyData.reduce((acc: number, row: any) => acc + (row.novelty_score || 0), 0)
      avgNoveltyScore = sum / noveltyData.length
    }

    // Get topics by type
    const { data: typeData, error: typeError } = await supabase
      .from('episode_topics')
      .select('topic_type')

    const topicsByType: Record<string, number> = {}
    if (!typeError && typeData) {
      typeData.forEach((row: any) => {
        const type = row.topic_type || 'unknown'
        topicsByType[type] = (topicsByType[type] || 0) + 1
      })
    }

    // Get topics by digest
    const { data: digestData, error: digestError } = await supabase
      .from('episode_topics')
      .select('digest_topic')

    const topicsByDigest: Record<string, number> = {}
    if (!digestError && digestData) {
      digestData.forEach((row: any) => {
        const digest = row.digest_topic || 'unknown'
        topicsByDigest[digest] = (topicsByDigest[digest] || 0) + 1
      })
    }

    // Get ad stats
    const { count: totalAds, error: adsCountError } = await supabase
      .from('common_ads')
      .select('*', { count: 'exact', head: true })

    const { count: activeAds, error: activeAdsError } = await supabase
      .from('common_ads')
      .select('*', { count: 'exact', head: true })
      .eq('is_active', true)

    return NextResponse.json({
      total_topics: totalTopics || 0,
      topics_by_type: topicsByType,
      topics_by_digest: topicsByDigest,
      avg_novelty_score: avgNoveltyScore,
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
