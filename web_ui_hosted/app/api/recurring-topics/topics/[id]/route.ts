import { NextRequest, NextResponse } from 'next/server'
import { supabase as sharedSupabase } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/recurring-topics/topics/[id]')

export const dynamic = 'force-dynamic'

// Server-only client against the local PostgREST stack (kanban #2846).
// Kept as a function (not a direct import at call sites) to avoid
// touching the existing getSupabaseClient() call sites in this file.
function getSupabaseClient() {
  return sharedSupabase
}

// Get a single topic by ID
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { id } = params

    const { data, error } = await supabase
      .from('episode_topics')
      .select(`
        *,
        episodes (
          title
        )
      `)
      .eq('id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
      }
      log.error('Error fetching topic', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({
      topic: {
        ...data,
        episode_title: data.episodes?.title || 'Unknown Episode'
      }
    })
  } catch (error) {
    log.error('Error in GET topic', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// Update a topic
export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { id } = params
    const body = await request.json()

    const {
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

    // Build update object with only provided fields
    const updateData: Record<string, unknown> = {
      updated_at: new Date().toISOString()
    }

    if (topic_name !== undefined) updateData.topic_name = topic_name
    if (topic_slug !== undefined) updateData.topic_slug = topic_slug
    if (key_points !== undefined) updateData.key_points = key_points
    if (digest_topic !== undefined) updateData.digest_topic = digest_topic
    if (relevance_score !== undefined) updateData.relevance_score = relevance_score
    if (topic_type !== undefined) updateData.topic_type = topic_type
    if (novelty_score !== undefined) updateData.novelty_score = novelty_score
    if (is_update !== undefined) updateData.is_update = is_update
    if (parent_topic_id !== undefined) updateData.parent_topic_id = parent_topic_id
    if (evolution_summary !== undefined) updateData.evolution_summary = evolution_summary

    const { data, error } = await supabase
      .from('episode_topics')
      .update(updateData)
      .eq('id', id)
      .select()
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
      }
      log.error('Error updating topic', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ topic: data })
  } catch (error) {
    log.error('Error in PUT topic', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// Delete a topic
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { id } = params

    // First check if topic exists
    const { data: existing, error: fetchError } = await supabase
      .from('episode_topics')
      .select('id')
      .eq('id', id)
      .single()

    if (fetchError || !existing) {
      return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
    }

    // Clear parent_topic_id references (orphan child topics instead of cascade delete)
    await supabase
      .from('episode_topics')
      .update({ parent_topic_id: null })
      .eq('parent_topic_id', id)

    // Delete the topic
    const { error } = await supabase
      .from('episode_topics')
      .delete()
      .eq('id', id)

    if (error) {
      log.error('Error deleting topic', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    log.error('Error in DELETE topic', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
