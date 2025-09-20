import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

const db = new DatabaseClient()

export async function GET() {
  try {
    const feeds = await db.getFeeds()
    return NextResponse.json({ feeds })
  } catch (error) {
    console.error('Failed to fetch feeds:', error)
    return NextResponse.json(
      { error: 'Failed to fetch feeds' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const { feed_url, title } = await request.json()

    if (!feed_url || !title) {
      return NextResponse.json(
        { error: 'URL and title are required' },
        { status: 400 }
      )
    }

    // Basic URL validation
    try {
      new URL(feed_url)
    } catch {
      return NextResponse.json(
        { error: 'Invalid URL format' },
        { status: 400 }
      )
    }

    const feed = await db.createFeed(feed_url, title)
    return NextResponse.json({ feed })
  } catch (error) {
    console.error('Failed to create feed:', error)
    return NextResponse.json(
      { error: 'Failed to create feed' },
      { status: 500 }
    )
  }
}