import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

export const dynamic = 'force-dynamic'

const log = createLogger('api/digests/favorite')

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } },
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const id = Number(params.id)
    if (!Number.isInteger(id) || id <= 0) {
      return NextResponse.json({ error: 'valid digest id required' }, { status: 400 })
    }

    const body = await request.json()
    const isFavorite = Boolean(body.is_favorite)

    const db = DatabaseClient.getInstance()
    await db.setDigestFavorite(id, isFavorite)

    log.info('Digest favorite toggled', { id, is_favorite: isFavorite })
    return NextResponse.json({ id, is_favorite: isFavorite })
  } catch (error) {
    log.error('Failed to toggle favorite', {
      error: error instanceof Error ? error.message : 'Unknown',
    })
    return NextResponse.json({ error: 'Failed to toggle favorite' }, { status: 500 })
  }
}
