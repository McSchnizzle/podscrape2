import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/feeds/reorder')

export const dynamic = 'force-dynamic'

export async function PATCH(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const body = await request.json()
    const orderedIds: unknown = body?.orderedIds

    if (!Array.isArray(orderedIds) || orderedIds.length === 0) {
      return NextResponse.json(
        { error: 'orderedIds must be a non-empty array' },
        { status: 400 }
      )
    }

    if (!orderedIds.every(id => typeof id === 'number' && Number.isInteger(id))) {
      return NextResponse.json(
        { error: 'orderedIds must contain integers' },
        { status: 400 }
      )
    }

    const db = DatabaseClient.getInstance()
    await db.reorderFeeds(orderedIds as number[])

    log.info('Reordered feeds', { count: orderedIds.length })
    return NextResponse.json({ success: true, count: orderedIds.length })
  } catch (error) {
    log.error('Failed to reorder feeds', {
      error: error instanceof Error ? error.message : 'Unknown error',
    })
    return NextResponse.json(
      {
        error: 'Failed to reorder feeds',
        details: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    )
  }
}
