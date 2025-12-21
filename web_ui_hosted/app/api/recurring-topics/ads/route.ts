import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/recurring-topics/ads')

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

// Create a new common ad pattern
export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const body = await request.json()

    const {
      advertiser_name,
      pattern_keywords,
      confidence_threshold,
      is_active
    } = body

    if (!advertiser_name) {
      return NextResponse.json({ error: 'advertiser_name is required' }, { status: 400 })
    }

    if (!pattern_keywords || !Array.isArray(pattern_keywords) || pattern_keywords.length === 0) {
      return NextResponse.json({ error: 'pattern_keywords array is required' }, { status: 400 })
    }

    const { data, error } = await supabase
      .from('common_ads')
      .insert({
        advertiser_name,
        pattern_keywords,
        confidence_threshold: confidence_threshold ?? 0.8,
        is_active: is_active ?? true,
        detection_count: 0,
        first_detected_at: new Date().toISOString(),
        last_detected_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .select()
      .single()

    if (error) {
      log.error('Error creating ad', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ ad: data }, { status: 201 })
  } catch (error) {
    log.error('Error in POST ads', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const { data, error } = await supabase
      .from('common_ads')
      .select('*')
      .order('detection_count', { ascending: false })

    if (error) {
      log.error('Error fetching ads', { error: error.message })
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ ads: data || [] })
  } catch (error) {
    log.error('Error in ads API', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
