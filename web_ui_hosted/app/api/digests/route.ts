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
    const rawLimit = searchParams.get('limit')
    const limit = rawLimit === null ? 50 : Number(rawLimit)
    if (!Number.isInteger(limit) || limit < 1 || limit > 200) {
      return NextResponse.json({ error: 'limit must be an integer between 1 and 200' }, { status: 400 })
    }

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
