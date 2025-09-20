import { NextResponse } from 'next/server'
import { supabase } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    console.log('Testing Supabase connection...')

    // Test 1: Simple count query
    const { count, error: countError } = await supabase
      .from('episodes')
      .select('*', { count: 'exact', head: true })

    if (countError) {
      console.error('Count error:', countError)
      return NextResponse.json({ error: 'Count failed', details: countError }, { status: 500 })
    }

    console.log(`Total episodes in database: ${count}`)

    // Test 2: Simple select without joins
    const { data: simpleData, error: simpleError } = await supabase
      .from('episodes')
      .select('id, title, status, published_date, scored_at')
      .order('published_date', { ascending: false })
      .limit(5)

    if (simpleError) {
      console.error('Simple select error:', simpleError)
      return NextResponse.json({ error: 'Simple select failed', details: simpleError }, { status: 500 })
    }

    console.log(`Simple select returned ${simpleData?.length || 0} episodes`)

    // Test 3: Select with join
    const { data: joinData, error: joinError } = await supabase
      .from('episodes')
      .select(`
        id,
        title,
        status,
        published_date,
        scored_at,
        feeds!feed_id (
          title
        )
      `)
      .order('published_date', { ascending: false })
      .limit(5)

    if (joinError) {
      console.error('Join select error:', joinError)
    }

    console.log(`Join select returned ${joinData?.length || 0} episodes`)

    return NextResponse.json({
      totalCount: count,
      simpleQuery: {
        count: simpleData?.length || 0,
        data: simpleData || []
      },
      joinQuery: {
        count: joinData?.length || 0,
        data: joinData || [],
        error: joinError
      }
    })

  } catch (error) {
    console.error('Debug API error:', error)
    return NextResponse.json({ error: 'Debug failed', details: error }, { status: 500 })
  }
}