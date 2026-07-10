import { NextRequest, NextResponse } from 'next/server'
import { supabase as sharedSupabase } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/recurring-topics/topics')

export const dynamic = 'force-dynamic'

// Server-only client against the local PostgREST stack (kanban #2846).
// Kept as a function (not a direct import at call sites) to avoid
// touching the existing getSupabaseClient() call sites in this file.
function getSupabaseClient() {
  return sharedSupabase
}

// Create a new episode topic
export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const body = await request.json()

    const {
      episode_id,
      topic_name,
      topic_slug,
      key_points,
      digest_topic,
      relevance_score,
      topic_type,
      novelty_score,
      is_update,
      parent_topic_id,
      evolution_summary
    } = body

    if (!topic_name) {
      return NextResponse.json({ error: 'topic_name is required' }, { status: 400 })
    }

    // Generate slug if not provided
    const slug = topic_slug || topic_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

    const { data, error } = await supabase
      .from('episode_topics')
      .insert({
        episode_id,
        topic_name,
        topic_slug: slug,
        key_points: key_points || [],
        digest_topic,
        relevance_score: relevance_score || 0,
        topic_type: topic_type || 'other',
        novelty_score: novelty_score || 1.0,
        is_update: is_update || false,
        parent_topic_id,
        evolution_summary,
        first_seen_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .select()
      .single()

    if (error) {
      log.error('Error creating topic', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ topic: data }, { status: 201 })
  } catch (error) {
    log.error('Error in POST topics', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function GET(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

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
      log.error('Error fetching topics', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Transform data to include episode_title
    const topics = data?.map((topic: any) => ({
      ...topic,
      episode_title: topic.episodes?.title || 'Unknown Episode'
    })) || []

    return NextResponse.json({ topics })
  } catch (error) {
    log.error('Error in topics API', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
