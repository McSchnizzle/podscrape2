import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

const summarizeRun = (runId: string, logs: any[]) => {
  if (!logs.length) return null
  const sorted = [...logs].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  const startedAt = sorted[0].timestamp
  const finishedAt = sorted[sorted.length - 1].timestamp
  const durationSeconds = (new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000
  const warnings = logs.filter((log) => log.level === 'WARNING').length
  const errors = logs.filter((log) => ['ERROR', 'CRITICAL'].includes(log.level)).length

  return {
    runId,
    startedAt,
    finishedAt,
    durationSeconds: Number.isFinite(durationSeconds) ? durationSeconds : null,
    warnings,
    errors,
  }
}

export async function GET() {
  try {
    const db = DatabaseClient.getInstance()
    const runIds = await db.getDistinctRunIds(10)

    const runs = []
    for (const runId of runIds) {
      const logs = await db.getPipelineLogs(200, runId)
      const summary = summarizeRun(runId, logs)
      if (summary) {
        runs.push(summary)
      }
    }

    return NextResponse.json({ runs })
  } catch (error) {
    console.error('Failed to load pipeline runs', error)
    return NextResponse.json({ error: 'Failed to load pipeline runs' }, { status: 500 })
  }
}
