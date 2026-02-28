import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/story-arcs/arcs/merge')

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

// Merge duplicate arcs into a primary arc
export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { primary_id, duplicate_ids } = await request.json()

    if (!primary_id || !duplicate_ids || !Array.isArray(duplicate_ids) || duplicate_ids.length === 0) {
      return NextResponse.json(
        { error: 'primary_id and duplicate_ids (non-empty array) are required' },
        { status: 400 }
      )
    }

    // Verify primary arc exists
    const { data: primary, error: primaryError } = await supabase
      .from('story_arcs')
      .select('*')
      .eq('id', primary_id)
      .single()

    if (primaryError || !primary) {
      return NextResponse.json({ error: 'Primary arc not found' }, { status: 404 })
    }

    // Verify all duplicate arcs exist
    const { data: duplicates, error: dupError } = await supabase
      .from('story_arcs')
      .select('*')
      .in('id', duplicate_ids)

    if (dupError || !duplicates || duplicates.length !== duplicate_ids.length) {
      return NextResponse.json({ error: 'One or more duplicate arcs not found' }, { status: 404 })
    }

    let eventsMoved = 0
    let coveragesMoved = 0

    for (const dupId of duplicate_ids) {
      // Move events from duplicate to primary
      const { data: movedEvents } = await supabase
        .from('story_arc_events')
        .update({ story_arc_id: primary_id })
        .eq('story_arc_id', dupId)
        .select('id')

      eventsMoved += movedEvents?.length || 0

      // Move coverage records (skip duplicates via upsert-like approach)
      const { data: dupCoverages } = await supabase
        .from('story_arc_coverage')
        .select('*')
        .eq('story_arc_id', dupId)

      if (dupCoverages) {
        for (const cov of dupCoverages) {
          // Check if primary already has coverage for this digest
          const { data: existing } = await supabase
            .from('story_arc_coverage')
            .select('id')
            .eq('story_arc_id', primary_id)
            .eq('digest_id', cov.digest_id)
            .maybeSingle()

          if (!existing) {
            await supabase
              .from('story_arc_coverage')
              .update({ story_arc_id: primary_id })
              .eq('id', cov.id)

            coveragesMoved++
          } else {
            // Delete the duplicate coverage
            await supabase
              .from('story_arc_coverage')
              .delete()
              .eq('id', cov.id)
          }
        }
      }

      // Delete the duplicate arc (remaining events/coverage cascade)
      await supabase
        .from('story_arcs')
        .delete()
        .eq('id', dupId)
    }

    // Recalculate primary arc stats
    const { count: totalEvents } = await supabase
      .from('story_arc_events')
      .select('*', { count: 'exact', head: true })
      .eq('story_arc_id', primary_id)

    const { data: events } = await supabase
      .from('story_arc_events')
      .select('source_feed_id, event_date')
      .eq('story_arc_id', primary_id)

    const uniqueSources = new Set(events?.map(e => e.source_feed_id).filter(Boolean))
    const dates = events?.map(e => new Date(e.event_date).getTime()) || []

    const { count: coverageCount } = await supabase
      .from('story_arc_coverage')
      .select('*', { count: 'exact', head: true })
      .eq('story_arc_id', primary_id)

    // Update primary with recalculated stats
    await supabase
      .from('story_arcs')
      .update({
        event_count: totalEvents || 0,
        source_count: uniqueSources.size,
        started_at: dates.length > 0 ? new Date(Math.min(...dates)).toISOString() : primary.started_at,
        last_updated_at: dates.length > 0 ? new Date(Math.max(...dates)).toISOString() : primary.last_updated_at,
        saturation_score: Math.min(1.0, (coverageCount || 0) * 0.3),
        updated_at: new Date().toISOString()
      })
      .eq('id', primary_id)

    log.info('Arcs merged', {
      primary_id,
      duplicates_merged: duplicate_ids.length,
      events_moved: eventsMoved,
      coverages_moved: coveragesMoved
    })

    return NextResponse.json({
      success: true,
      primary_id,
      duplicates_merged: duplicate_ids.length,
      events_moved: eventsMoved,
      coverages_moved: coveragesMoved
    })
  } catch (error) {
    log.error('Error merging arcs', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
