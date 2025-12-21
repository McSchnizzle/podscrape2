import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/workflow/analysis')

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const { searchParams } = new URL(request.url)
    const hoursBack = parseInt(searchParams.get('hours') || '24')

    const db = DatabaseClient.getInstance()
    const analysis = await db.getWorkflowAnalysis(hoursBack)

    return NextResponse.json(analysis)
  } catch (error) {
    log.error('Failed to get workflow analysis', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to get workflow analysis' },
      { status: 500 }
    )
  }
}
