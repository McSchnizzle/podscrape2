import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json({ error: 'Invalid feed ID' }, { status: 400 })
    }

    const db = new DatabaseClient()

    // Update the feed's last_checked timestamp to indicate a manual check was performed
    const updatedFeed = await db.checkFeed(id)

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