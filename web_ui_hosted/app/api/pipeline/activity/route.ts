import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

const timeAgo = (value: string) => {
  const createdAt = new Date(value)
  const now = new Date()
  const diffMs = now.getTime() - createdAt.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor(diffMs / (1000 * 60))

  if (diffHours > 24) {
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
  }
  if (diffHours > 0) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  }
  if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`
  }
  return 'Just now'
}

export async function GET(request: Request) {
  try {
    const db = DatabaseClient.getInstance()
    const { searchParams } = new URL(request.url)
    const runId = searchParams.get('runId') || undefined
    const limit = runId ? 400 : 80
    const logs = await db.getPipelineLogs(limit, runId)

    const activities = logs.map((log) => ({
      id: `log-${log.id}`,
      phase: log.phase,
      level: log.level,
      message: log.message,
      time: timeAgo(log.timestamp),
      timestamp: log.timestamp,
      runId: log.run_id
    }))

    return NextResponse.json({
      activities,
      totalCount: activities.length
    })
  } catch (error) {
    console.error('Failed to load pipeline activity:', error)
    return NextResponse.json({ error: 'Failed to load pipeline activity' }, { status: 500 })
  }
}
