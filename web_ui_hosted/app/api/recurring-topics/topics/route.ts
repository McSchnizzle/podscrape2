import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

export async function GET(request: NextRequest) {
  try {
    const supabase = getSupabaseClient()
    const searchParams = request.nextUrl.searchParams
    const type = searchParams.get('type')
    const digest = searchParams.get('digest')
    const search = searchParams.get('search')
    const minNovelty = searchParams.get('min_novelty')
    const limit = parseInt(searchParams.get('limit') || '100')

    // Build query
    let query = supabase
      .from('episode_topics')
      .select(`
        *,
        episodes (
          title
        )
      `)
      .order('created_at', { ascending: false })
      .limit(limit)

    // Apply filters
    if (type) {
      query = query.eq('topic_type', type)
    }
    if (digest) {
      query = query.ilike('digest_topic', `%${digest}%`)
    }
    if (search) {
      query = query.or(`topic_name.ilike.%${search}%,topic_slug.ilike.%${search}%`)
    }
    if (minNovelty) {
      query = query.gte('novelty_score', parseFloat(minNovelty))
    }

    const { data, error } = await query

    if (error) {
      console.error('Error fetching topics:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Transform data to include episode_title
    const topics = data?.map(topic => ({
      ...topic,
      episode_title: topic.episodes?.title || 'Unknown Episode'
    })) || []

    return NextResponse.json({ topics })
  } catch (error) {
    console.error('Error in topics API:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
