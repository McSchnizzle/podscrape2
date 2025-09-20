import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

const db = new DatabaseClient()

export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json(
        { error: 'Invalid feed ID' },
        { status: 400 }
      )
    }

    const body = await request.json()
    const { url, title, is_active, health_status } = body

    // Validate URL if provided
    if (url) {
      try {
        new URL(url)
      } catch {
        return NextResponse.json(
          { error: 'Invalid URL format' },
          { status: 400 }
        )
      }
    }

    const updates: any = {}
    if (url !== undefined) updates.url = url
    if (title !== undefined) updates.title = title
    if (is_active !== undefined) updates.is_active = is_active
    if (health_status !== undefined) {
      updates.health_status = health_status
      updates.last_checked = new Date().toISOString()
    }

    const feed = await db.updateFeed(id, updates)
    return NextResponse.json({ feed })
  } catch (error) {
    console.error('Failed to update feed:', error)
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
  try {
    const id = parseInt(params.id)
    if (isNaN(id)) {
      return NextResponse.json(
        { error: 'Invalid feed ID' },
        { status: 400 }
      )
    }

    await db.deleteFeed(id)
    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Failed to delete feed:', error)
    return NextResponse.json(
      { error: 'Failed to delete feed' },
      { status: 500 }
    )
  }
}