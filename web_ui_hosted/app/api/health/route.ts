import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export async function GET() {
  try {
    const db = DatabaseClient.getInstance()
    const health = await db.getSystemHealth()

    return NextResponse.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      database: health.database,
      environment: process.env.NODE_ENV || 'unknown'
    })
  } catch (error) {
    console.error('Health check failed:', error)

    return NextResponse.json(
      {
        status: 'error',
        timestamp: new Date().toISOString(),
        error: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    )
  }
}