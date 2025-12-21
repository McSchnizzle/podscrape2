import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { revalidateTag } from 'next/cache'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/feeds/[id]')
const db = DatabaseClient.getInstance()

export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json(
        { error: 'Invalid feed ID' },
        { status: 400 }
      )
    }

    const body = await request.json()
    const { feed_url, title, active, consecutive_failures } = body

    // Validate URL if provided
    if (feed_url) {
      try {
        new URL(feed_url)
      } catch {
        return NextResponse.json(
          { error: 'Invalid URL format' },
          { status: 400 }
        )
      }
    }

    const updates: any = {}
    if (feed_url !== undefined) updates.feed_url = feed_url
    if (title !== undefined) updates.title = title
    if (active !== undefined) updates.active = active
    if (consecutive_failures !== undefined) {
      updates.consecutive_failures = consecutive_failures
      updates.last_checked = new Date().toISOString()
    }

    const feed = await db.updateFeed(id, updates)

    // Invalidate feeds cache after updating feed
    revalidateTag('feeds-data')
    log.info('Feeds cache invalidated after updating feed', { id })

    return NextResponse.json({ feed })
  } catch (error) {
    log.error('Failed to update feed', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to update feed' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json(
        { error: 'Invalid feed ID' },
        { status: 400 }
      )
    }

    await db.deleteFeed(id)

    // Invalidate feeds cache after deleting feed
    revalidateTag('feeds-data')
    log.info('Feeds cache invalidated after deleting feed', { id })

    return NextResponse.json({ success: true })
  } catch (error) {
    log.error('Failed to delete feed', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to delete feed' },
      { status: 500 }
    )
  }
}