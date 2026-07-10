import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/digests')

export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const { searchParams } = new URL(request.url)
    const limit = Math.min(Number(searchParams.get('limit')) || 50, 200)

    const db = DatabaseClient.getInstance()
    const digests = await db.getDigests(limit)
    return NextResponse.json({ digests })
  } catch (error) {
    log.error('Failed to load digests', {
      error: error instanceof Error ? error.message : 'Unknown',
    })
    return NextResponse.json({ error: 'Failed to load digests' }, { status: 500 })
  }
}
