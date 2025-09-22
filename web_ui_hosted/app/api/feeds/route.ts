import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { unstable_cache, revalidateTag } from 'next/cache'

const db = new DatabaseClient()

// Cached function to fetch feeds data
const getCachedFeeds = unstable_cache(
  async () => {
    const db = new DatabaseClient()
    const feeds = await db.getFeeds()

    console.log(`Feeds cache: Fetched ${feeds.length} feeds from database`)

    return { feeds }
  },
  ['feeds'],
  {
    revalidate: 30, // Cache for 30 seconds
    tags: ['feeds-data']
  }
)

export async function GET() {
  try {
    console.log('Feeds API: GET request')

    // Use cached function for better performance
    const result = await getCachedFeeds()

    console.log(`Feeds API: Returning ${result.feeds.length} feeds (cached)`)

    return NextResponse.json(result)
  } catch (error) {
    console.error('Failed to fetch feeds:', error)
    console.error('Error details:', error instanceof Error ? error.message : 'Unknown error')
    return NextResponse.json(
      {
        error: 'Failed to fetch feeds',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
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

    // Invalidate feeds cache after creating new feed
    revalidateTag('feeds-data')
    console.log('Feeds cache invalidated after creating new feed')

    return NextResponse.json({ feed })
  } catch (error) {
    console.error('Failed to create feed:', error)
    return NextResponse.json(
      { error: 'Failed to create feed' },
      { status: 500 }
    )
  }
}