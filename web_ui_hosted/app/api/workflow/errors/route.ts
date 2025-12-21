import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/workflow/errors')

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const { searchParams } = new URL(request.url)
    const daysBack = parseInt(searchParams.get('days') || '30')

    const db = DatabaseClient.getInstance()
    const analytics = await db.getErrorAnalytics(daysBack)

    return NextResponse.json(analytics)
  } catch (error) {
    log.error('Failed to get error analytics', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to get error analytics' },
      { status: 500 }
    )
  }
}
