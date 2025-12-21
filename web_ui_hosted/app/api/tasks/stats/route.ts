import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/tasks/stats')

export const dynamic = 'force-dynamic'

// GET /api/tasks/stats - Get task statistics
export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const db = DatabaseClient.getInstance()
    const stats = await db.getTaskStats()

    return NextResponse.json(stats)
  } catch (error) {
    log.error('Failed to get task stats', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to get task stats' },
      { status: 500 }
    )
  }
}
