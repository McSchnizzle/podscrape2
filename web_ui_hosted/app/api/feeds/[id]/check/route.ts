import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { revalidateTag } from 'next/cache'

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
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
    console.log(`Feeds cache invalidated after checking feed ${id}`)

    return NextResponse.json({
      success: true,
      feed: updatedFeed,
      message: 'Feed check initiated successfully'
    })
  } catch (error) {
    console.error('Error checking feed:', error)
    return NextResponse.json(
      { error: 'Failed to check feed' },
      { status: 500 }
    )
  }
}