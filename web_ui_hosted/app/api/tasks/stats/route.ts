import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

// GET /api/tasks/stats - Get task statistics
export async function GET() {
  try {
    const db = DatabaseClient.getInstance()
    const stats = await db.getTaskStats()

    return NextResponse.json(stats)
  } catch (error) {
    console.error('Failed to get task stats:', error)
    return NextResponse.json(
      { error: 'Failed to get task stats' },
      { status: 500 }
    )
  }
}
