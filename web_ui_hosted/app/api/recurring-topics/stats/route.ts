import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE!
)

export async function GET() {
  try {
    // Get total topics
    const { count: totalTopics, error: countError } = await supabase
      .from('episode_topics')
      .select('*', { count: 'exact', head: true })

    if (countError) {
      console.error('Error counting topics:', countError)
    }

    // Get average novelty score
    const { data: noveltyData, error: noveltyError } = await supabase
      .from('episode_topics')
      .select('novelty_score')

    let avgNoveltyScore = 0
    if (!noveltyError && noveltyData && noveltyData.length > 0) {
      const sum = noveltyData.reduce((acc, row) => acc + (row.novelty_score || 0), 0)
      avgNoveltyScore = sum / noveltyData.length
    }

    // Get topics by type
    const { data: typeData, error: typeError } = await supabase
      .from('episode_topics')
      .select('topic_type')

    const topicsByType: Record<string, number> = {}
    if (!typeError && typeData) {
      typeData.forEach(row => {
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
      digestData.forEach(row => {
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
    console.error('Error in stats API:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
