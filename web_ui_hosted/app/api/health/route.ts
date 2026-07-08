/**
 * PUBLIC ROUTE - No authentication required
 * This endpoint is intentionally public for health monitoring and uptime checks.
 */

import { NextResponse } from 'next/server'
import { getPool } from '@/utils/db'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/health')

export async function GET() {
  try {
    await getPool().query('SELECT 1')

    return NextResponse.json({
      status: 'ok',
      timestamp: new Date().toISOString(),
      database: 'connected',
      environment: process.env.NODE_ENV || 'unknown'
    })
  } catch (error) {
    log.error('Health check failed', { error: error instanceof Error ? error.message : 'Unknown error' })

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