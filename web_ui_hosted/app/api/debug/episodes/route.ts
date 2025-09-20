import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    console.log('Testing Supabase environment variables...')

    // Test environment variables first
    const supabaseUrl = process.env.SUPABASE_URL
    const supabaseServiceRole = process.env.SUPABASE_SERVICE_ROLE

    console.log('SUPABASE_URL:', supabaseUrl ? 'Set' : 'Missing')
    console.log('SUPABASE_SERVICE_ROLE:', supabaseServiceRole ? 'Set' : 'Missing')

    if (!supabaseUrl || !supabaseServiceRole) {
      return NextResponse.json({
        error: 'Missing environment variables',
        details: {
          SUPABASE_URL: supabaseUrl ? 'Set' : 'Missing',
          SUPABASE_SERVICE_ROLE: supabaseServiceRole ? 'Set' : 'Missing'
        }
      }, { status: 500 })
    }

    // Now try to create client
    const { createClient } = await import('@supabase/supabase-js')
    const supabase = createClient(supabaseUrl, supabaseServiceRole, {
      auth: {
        autoRefreshToken: false,
        persistSession: false
      }
    })

    console.log('Supabase client created, testing simple count...')

    // Test simple count
    const { count, error: countError } = await supabase
      .from('episodes')
      .select('*', { count: 'exact', head: true })

    if (countError) {
      console.error('Count error:', countError)
      return NextResponse.json({
        error: 'Count failed',
        details: countError,
        environment: { supabaseUrl: supabaseUrl?.substring(0, 30) + '...' }
      }, { status: 500 })
    }

    console.log(`Count successful: ${count} episodes`)

    // Test simple select
    const { data: simpleData, error: simpleError } = await supabase
      .from('episodes')
      .select('id, title, status, published_date')
      .order('published_date', { ascending: false })
      .limit(3)

    if (simpleError) {
      console.error('Simple select error:', simpleError)
      return NextResponse.json({
        error: 'Simple select failed',
        details: simpleError
      }, { status: 500 })
    }

    console.log(`Simple select returned ${simpleData?.length || 0} episodes`)

    return NextResponse.json({
      success: true,
      totalCount: count,
      sampleEpisodes: simpleData,
      environment: {
        supabaseUrl: supabaseUrl?.substring(0, 30) + '...',
        hasServiceRole: !!supabaseServiceRole
      }
    })

  } catch (error) {
    console.error('Debug API error:', error)
    return NextResponse.json({
      error: 'Debug failed',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 })
  }
}