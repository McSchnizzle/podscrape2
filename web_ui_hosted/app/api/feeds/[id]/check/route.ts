import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { revalidateTag } from 'next/cache'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/feeds/[id]/check')

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json({ error: 'Invalid feed ID' }, { status: 400 })
    }

    const db = DatabaseClient.getInstance()

    // Update the feed's last_checked timestamp to indicate a manual check was performed
    const updatedFeed = await db.checkFeed(id)

    // Invalidate feeds cache after checking feed
    revalidateTag('feeds-data')
    log.info('Feeds cache invalidated after checking feed', { id })

    return NextResponse.json({
      success: true,
      feed: updatedFeed,
      message: 'Feed check initiated successfully'
    })
  } catch (error) {
    log.error('Error checking feed', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to check feed' },
      { status: 500 }
    )
  }
}