import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/story-arcs/arcs')

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

// List all story arcs with optional filters
export async function GET(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const searchParams = request.nextUrl.searchParams
    const category = searchParams.get('category')
    const digest = searchParams.get('digest')
    const search = searchParams.get('search')
    const limit = parseInt(searchParams.get('limit') || '100')

    // Build query for arcs with events
    let query = supabase
      .from('story_arcs')
      .select(`
        *,
        story_arc_events (
          id,
          event_date,
          event_summary,
          key_points,
          source_name,
          perspective,
          relevance_score,
          extracted_at
        )
      `)
      .order('last_updated_at', { ascending: false })
      .limit(limit)

    // Apply filters
    if (category) {
      query = query.eq('functional_category', category)
    }
    if (digest) {
      query = query.ilike('digest_topic', `%${digest}%`)
    }
    if (search) {
      query = query.or(`arc_name.ilike.%${search}%,arc_slug.ilike.%${search}%`)
    }

    const { data, error } = await query

    if (error) {
      log.error('Error fetching story arcs', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Sort events by date descending within each arc
    const arcs = data?.map(arc => ({
      ...arc,
      events: arc.story_arc_events?.sort((a: { event_date: string }, b: { event_date: string }) =>
        new Date(b.event_date).getTime() - new Date(a.event_date).getTime()
      ) || []
    })) || []

    return NextResponse.json({ arcs })
  } catch (error) {
    log.error('Error in story arcs API', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

// Create a new story arc
export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const body = await request.json()

    const {
      arc_name,
      functional_category,
      digest_topic,
      summary
    } = body

    if (!arc_name) {
      return NextResponse.json({ error: 'arc_name is required' }, { status: 400 })
    }

    if (!digest_topic) {
      return NextResponse.json({ error: 'digest_topic is required' }, { status: 400 })
    }

    // Generate slug from arc name
    const arc_slug = arc_name.toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')

    const now = new Date().toISOString()

    const { data, error } = await supabase
      .from('story_arcs')
      .insert({
        arc_name,
        arc_slug,
        functional_category: functional_category || 'other',
        digest_topic,
        summary: summary || null,
        started_at: now,
        last_updated_at: now,
        event_count: 0,
        source_count: 0,
        created_at: now,
        updated_at: now
      })
      .select()
      .single()

    if (error) {
      if (error.code === '23505') {
        return NextResponse.json({ error: 'A story arc with this name already exists' }, { status: 409 })
      }
      log.error('Error creating story arc', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ arc: data }, { status: 201 })
  } catch (error) {
    log.error('Error in POST story arcs', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
