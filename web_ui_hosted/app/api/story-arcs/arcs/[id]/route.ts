import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/story-arcs/arcs/[id]')

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

// Get a single story arc with all events
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { id } = await params

    const { data, error } = await supabase
      .from('story_arcs')
      .select(`
        *,
        story_arc_events (
          id,
          event_date,
          event_summary,
          key_points,
          source_feed_id,
          source_episode_id,
          source_episode_guid,
          source_name,
          perspective,
          relevance_score,
          extracted_at,
          created_at
        )
      `)
      .eq('id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: 'Story arc not found' }, { status: 404 })
      }
      log.error('Error fetching story arc', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    // Sort events by date descending
    const arc = {
      ...data,
      events: data.story_arc_events?.sort((a: { event_date: string }, b: { event_date: string }) =>
        new Date(b.event_date).getTime() - new Date(a.event_date).getTime()
      ) || []
    }

    return NextResponse.json({ arc })
  } catch (error) {
    log.error('Error in GET story arc', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// Update a story arc
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { id } = await params
    const body = await request.json()

    const {
      arc_name,
      functional_category,
      digest_topic,
      summary,
      is_hot,
      hot_briefing,
      retain_until
    } = body

    // Build update object with only provided fields
    const updateData: Record<string, unknown> = {
      updated_at: new Date().toISOString()
    }

    if (arc_name !== undefined) {
      updateData.arc_name = arc_name
      // Update slug when name changes
      updateData.arc_slug = arc_name.toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
    }
    if (functional_category !== undefined) updateData.functional_category = functional_category
    if (digest_topic !== undefined) updateData.digest_topic = digest_topic
    if (summary !== undefined) updateData.summary = summary
    if (is_hot !== undefined) updateData.is_hot = is_hot
    if (hot_briefing !== undefined) updateData.hot_briefing = hot_briefing
    if (retain_until !== undefined) updateData.retain_until = retain_until

    const { data, error } = await supabase
      .from('story_arcs')
      .update(updateData)
      .eq('id', id)
      .select()
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: 'Story arc not found' }, { status: 404 })
      }
      log.error('Error updating story arc', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ arc: data })
  } catch (error) {
    log.error('Error in PUT story arc', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// Delete a story arc and its events
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { id } = await params

    // First check if arc exists
    const { data: existing, error: fetchError } = await supabase
      .from('story_arcs')
      .select('id')
      .eq('id', id)
      .single()

    if (fetchError || !existing) {
      return NextResponse.json({ error: 'Story arc not found' }, { status: 404 })
    }

    // Delete the arc (events are cascade deleted)
    const { error } = await supabase
      .from('story_arcs')
      .delete()
      .eq('id', id)

    if (error) {
      log.error('Error deleting story arc', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    log.error('Error in DELETE story arc', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
