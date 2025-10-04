import { NextResponse } from 'next/server'
import { DatabaseClient, PipelineLogRecord } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

const sortByOldest = (logs: PipelineLogRecord[]) =>
  [...logs].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

export async function GET() {
  try {
    const db = DatabaseClient.getInstance()

    const [stats, backlog, runIds] = await Promise.all([
      db.getPipelineStats(),
      db.getEpisodeBacklogStats(),
      db.getDistinctRunIds(3)
    ])

    let runSummary: any = null
    let timeline: Array<{ id: string; phase: string; message: string; level: string; timestamp: string }> = []
    let recentRuns: Array<{ runId: string; startedAt: string; finishedAt: string | null; durationSeconds: number | null }> = []

    if (runIds.length > 0) {
      const [latestRunLogs, additionalLogs] = await Promise.all([
        db.getPipelineLogs(200, runIds[0]),
        runIds.length > 1 ? db.getPipelineLogs(200, runIds[1]) : Promise.resolve([] as PipelineLogRecord[])
      ])

      const sortedLatest = sortByOldest(latestRunLogs)

      if (sortedLatest.length > 0) {
        const startedAt = sortedLatest[0].timestamp
        const finishedAt = sortedLatest[sortedLatest.length - 1].timestamp
        const durationSeconds = (new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000
        const warnings = latestRunLogs.filter((log) => log.level === 'WARNING').length
        const errors = latestRunLogs.filter((log) => ['ERROR', 'CRITICAL'].includes(log.level)).length

        const phasesMap = new Map<string, PipelineLogRecord>()
        for (const log of latestRunLogs) {
          if (!phasesMap.has(log.phase) || new Date(log.timestamp) > new Date(phasesMap.get(log.phase)!.timestamp)) {
            phasesMap.set(log.phase, log)
          }
        }

        const phaseSnapshots = Array.from(phasesMap.entries()).map(([phase, log]) => ({
          phase,
          message: log.message,
          level: log.level,
          timestamp: log.timestamp,
        }))

        runSummary = {
          runId: runIds[0],
          startedAt,
          finishedAt,
          durationSeconds: Number.isFinite(durationSeconds) ? durationSeconds : null,
          warnings,
          errors,
          phases: phaseSnapshots,
        }

        timeline = sortedLatest.slice(-40).map((log) => ({
          id: `log-${log.id}`,
          phase: log.phase,
          message: log.message,
          level: log.level,
          timestamp: log.timestamp,
        }))
      }

      const summarizeRun = (runId: string, logs: PipelineLogRecord[]) => {
        if (logs.length === 0) return null
        const ordered = sortByOldest(logs)
        const start = ordered[0].timestamp
        const finish = ordered[ordered.length - 1].timestamp
        const seconds = (new Date(finish).getTime() - new Date(start).getTime()) / 1000
        return {
          runId,
          startedAt: start,
          finishedAt: finish,
          durationSeconds: Number.isFinite(seconds) ? seconds : null
        }
      }

      const summaries = [summarizeRun(runIds[0], latestRunLogs)]
      if (runIds.length > 1) {
        summaries.push(summarizeRun(runIds[1], additionalLogs))
      }
      recentRuns = summaries.filter(Boolean) as typeof recentRuns
    }

    const [awaitingScoringEpisodes, awaitingDigestEpisodes, recentDigests, recentEpisodes] = await Promise.all([
      db.getEpisodesAwaitingScoring(6),
      db.getEpisodesAwaitingDigest(6),
      db.getLatestDigests(6),
      db.getRecentEpisodes(6)
    ])

    return NextResponse.json({
      stats,
      backlog,
      runSummary,
      timeline,
      recentRuns,
      queues: {
        awaitingScoring: awaitingScoringEpisodes,
        awaitingDigest: awaitingDigestEpisodes,
        recentDigests,
        recentEpisodes
      }
    })

  } catch (error) {
    console.error('Failed to get pipeline status:', error)
    return NextResponse.json(
      { error: 'Failed to get pipeline status' },
      { status: 500 }
    )
  }
}
