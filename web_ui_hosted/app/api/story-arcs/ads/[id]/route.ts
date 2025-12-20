import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { requireAuth } from '@/lib/auth-guard'

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

// Get a single ad by ID
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
      .from('common_ads')
      .select('*')
      .eq('id', id)
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: 'Ad not found' }, { status: 404 })
      }
      console.error('Error fetching ad:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ ad: data })
  } catch (error) {
    console.error('Error in GET ad:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// Update an ad
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
      advertiser_name,
      pattern_keywords,
      confidence_threshold,
      is_active
    } = body

    // Build update object with only provided fields
    const updateData: Record<string, unknown> = {
      updated_at: new Date().toISOString()
    }

    if (advertiser_name !== undefined) updateData.advertiser_name = advertiser_name
    if (pattern_keywords !== undefined) updateData.pattern_keywords = pattern_keywords
    if (confidence_threshold !== undefined) updateData.confidence_threshold = confidence_threshold
    if (is_active !== undefined) updateData.is_active = is_active

    const { data, error } = await supabase
      .from('common_ads')
      .update(updateData)
      .eq('id', id)
      .select()
      .single()

    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: 'Ad not found' }, { status: 404 })
      }
      console.error('Error updating ad:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ ad: data })
  } catch (error) {
    console.error('Error in PUT ad:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// Delete an ad
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { id } = await params

    // First check if ad exists
    const { data: existing, error: fetchError } = await supabase
      .from('common_ads')
      .select('id')
      .eq('id', id)
      .single()

    if (fetchError || !existing) {
      return NextResponse.json({ error: 'Ad not found' }, { status: 404 })
    }

    // Delete the ad
    const { error } = await supabase
      .from('common_ads')
      .delete()
      .eq('id', id)

    if (error) {
      console.error('Error deleting ad:', error)
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error in DELETE ad:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
