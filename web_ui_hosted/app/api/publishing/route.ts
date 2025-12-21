import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/publishing')

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const db = DatabaseClient.getInstance()
    const digests = await db.getDigests(25)
    const pipelineRuns = await db.getPipelineRuns(5)

    return NextResponse.json({ digests, pipelineRuns })
  } catch (error) {
    log.error('Publishing overview error', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Failed to load publishing overview' }, { status: 500 })
  }
}
