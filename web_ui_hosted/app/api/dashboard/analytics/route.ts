import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

interface PhaseLog {
  phase: string
  timestamp: string
  level: string
}

interface PhaseSummary {
  phase: string
  status: 'completed' | 'failed' | 'in_progress'
  duration: number
  logCount: number
}

export async function GET() {
  try {
    const db = DatabaseClient.getInstance()

    // Get latest run information
    const runIds = await db.getDistinctRunIds(1)
    const latestRunId = runIds[0]

    let latestRun = null
    let todayStats = {
      episodesDiscovered: 0,
      episodesProcessed: 0,
      digestsGenerated: 0,
      digestsPublished: 0
    }
    let recentActivity: any[] = []
    let transcriptAnalytics = {
      avgChars: 0,
      avgTokens: 0,
      maxChars: 0,
      minChars: 0,
      totalEpisodes: 0,
      truncationRisk: 0,
      episodesPerDigest: 3, // from web_settings
      currentUtilization: 0
    }
    let performanceInsights = {
      avgProcessingTime: 0,
      bottleneckPhase: '',
      bottleneckDuration: 0,
      successRate: 0,
      totalRuns: 0
    }

    // Get latest run details with phase breakdown
    if (latestRunId) {
      const logs = await db.getPipelineLogs(1000, latestRunId)

      if (logs.length > 0) {
        const sorted = [...logs].sort((a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        )

        const startedAt = sorted[0].timestamp
        const completedAt = sorted[sorted.length - 1].timestamp

        // Group logs by phase
        const phaseGroups = logs.reduce((acc: Record<string, PhaseLog[]>, log) => {
          if (!acc[log.phase]) acc[log.phase] = []
          acc[log.phase].push(log as PhaseLog)
          return acc
        }, {})

        // Calculate phase summaries
        const phases: PhaseSummary[] = Object.entries(phaseGroups).map(([phase, phaseLogs]) => {
          const phaseSorted = [...phaseLogs].sort((a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          )
          const phaseStart = new Date(phaseSorted[0].timestamp)
          const phaseEnd = new Date(phaseSorted[phaseSorted.length - 1].timestamp)
          const duration = (phaseEnd.getTime() - phaseStart.getTime()) / 1000

          const hasErrors = phaseLogs.some(l => ['ERROR', 'CRITICAL'].includes(l.level))
          const status = hasErrors ? 'failed' : 'completed'

          return {
            phase,
            status,
            duration,
            logCount: phaseLogs.length
          }
        })

        // Find bottleneck phase
        const bottleneck = phases.reduce((max, p) => p.duration > max.duration ? p : max, phases[0] || { phase: '', duration: 0 })

        latestRun = {
          runId: latestRunId,
          status: phases.some(p => p.status === 'failed') ? 'failed' : 'completed',
          phases,
          startedAt,
          completedAt,
          totalDuration: (new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000
        }

        performanceInsights.bottleneckPhase = bottleneck.phase
        performanceInsights.bottleneckDuration = bottleneck.duration
        performanceInsights.avgProcessingTime = latestRun.totalDuration
      }
    }

    // Get today's stats from database
    const todayStart = new Date()
    todayStart.setHours(0, 0, 0, 0)

    const { data: episodesData } = await db.supabase
      .from('episodes')
      .select('id, status, created_at')
      .gte('created_at', todayStart.toISOString())

    if (episodesData) {
      todayStats.episodesDiscovered = episodesData.length
      todayStats.episodesProcessed = episodesData.filter(e =>
        ['scored', 'digested', 'published'].includes(e.status)
      ).length
    }

    const { data: digestsData } = await db.supabase
      .from('digests')
      .select('id, status, created_at')
      .gte('created_at', todayStart.toISOString())

    if (digestsData) {
      todayStats.digestsGenerated = digestsData.length
      todayStats.digestsPublished = digestsData.filter(d => d.status === 'published').length
    }

    // Get recent activity
    const { data: recentEpisodes } = await db.supabase
      .from('episodes')
      .select('id, title, status, created_at, scores, transcript_content')
      .order('created_at', { ascending: false })
      .limit(10)

    if (recentEpisodes) {
      recentActivity = recentEpisodes.map(ep => {
        const maxScore = ep.scores && typeof ep.scores === 'object'
          ? Math.max(...Object.values(ep.scores as Record<string, number>))
          : 0

        return {
          id: ep.id,
          title: ep.title,
          status: ep.status,
          timestamp: ep.created_at,
          score: maxScore,
          type: 'episode'
        }
      })
    }

    // Transcript analytics
    const { data: transcriptData } = await db.supabase
      .from('episodes')
      .select('transcript_content, transcript_word_count')
      .not('transcript_content', 'is', null)
      .order('created_at', { ascending: false })
      .limit(100)

    if (transcriptData && transcriptData.length > 0) {
      const lengths = transcriptData.map(t => (t.transcript_content || '').length).filter(l => l > 0)

      if (lengths.length > 0) {
        transcriptAnalytics.avgChars = Math.round(lengths.reduce((sum, l) => sum + l, 0) / lengths.length)
        transcriptAnalytics.avgTokens = Math.round(transcriptAnalytics.avgChars / 4)
        transcriptAnalytics.maxChars = Math.max(...lengths)
        transcriptAnalytics.minChars = Math.min(...lengths)
        transcriptAnalytics.totalEpisodes = lengths.length

        // Calculate truncation risk (episodes over 100K tokens)
        transcriptAnalytics.truncationRisk = lengths.filter(l => l > 400000).length

        // Calculate current utilization (avg chars per episode * episodes per digest)
        const { data: settings } = await db.supabase
          .from('web_settings')
          .select('max_digest_episodes')
          .single()

        if (settings?.max_digest_episodes) {
          transcriptAnalytics.episodesPerDigest = settings.max_digest_episodes
        }

        const estimatedDigestChars = transcriptAnalytics.avgChars * transcriptAnalytics.episodesPerDigest
        const estimatedDigestTokens = estimatedDigestChars / 4
        const maxTokens = 128000 // GPT-4 context limit

        transcriptAnalytics.currentUtilization = Math.round((estimatedDigestTokens / maxTokens) * 100)
      }
    }

    // Performance insights - success rate
    const allRunIds = await db.getDistinctRunIds(10)
    performanceInsights.totalRuns = allRunIds.length

    let successCount = 0
    for (const runId of allRunIds) {
      const runLogs = await db.getPipelineLogs(500, runId)
      const hasErrors = runLogs.some(l => ['ERROR', 'CRITICAL'].includes(l.level))
      if (!hasErrors) successCount++
    }

    performanceInsights.successRate = allRunIds.length > 0
      ? Math.round((successCount / allRunIds.length) * 100)
      : 0

    return NextResponse.json({
      latestRun,
      todayStats,
      recentActivity,
      transcriptAnalytics,
      performanceInsights
    })
  } catch (error) {
    console.error('Failed to load dashboard analytics', error)
    return NextResponse.json({
      error: 'Failed to load dashboard analytics',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 })
  }
}
