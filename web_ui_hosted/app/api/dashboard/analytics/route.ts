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

    // Get today's stats using existing methods
    const pipelineStats = await db.getPipelineStats()
    todayStats.episodesProcessed = pipelineStats.episodesProcessedToday
    todayStats.digestsGenerated = pipelineStats.digestsGeneratedToday

    // Get recent episodes to count discovered today
    const recentEps = await db.getRecentEpisodes(50)
    const todayStart = new Date()
    todayStart.setHours(0, 0, 0, 0)
    todayStats.episodesDiscovered = recentEps.filter((ep: any) =>
      new Date(ep.created_at) >= todayStart
    ).length

    // Count published digests today
    const recentDigs = await db.getRecentDigests(7)
    todayStats.digestsPublished = recentDigs.filter((d: any) =>
      d.status === 'published' && new Date(d.published_at || d.generated_at) >= todayStart
    ).length

    // Get recent activity using existing method
    const recentEpisodesData = await db.getRecentEpisodes(10)

    // For digested episodes, get digest info
    const digestedEpisodeIds = recentEpisodesData
      .filter((ep: any) => ep.status === 'digested')
      .map((ep: any) => ep.id)

    const digestMap = new Map<number, any[]>()
    if (digestedEpisodeIds.length > 0) {
      const digestLinks = await db.getDigestLinksForEpisodes(digestedEpisodeIds)
      for (const link of digestLinks) {
        if (!digestMap.has(link.episode_id)) {
          digestMap.set(link.episode_id, [])
        }
        digestMap.get(link.episode_id)!.push(link)
      }
    }

    recentActivity = recentEpisodesData.map((ep: any) => {
      const maxScore = ep.scores && typeof ep.scores === 'object'
        ? Math.max(...Object.values(ep.scores as Record<string, number>))
        : 0

      const digestLinks = digestMap.get(ep.id) || []
      const digests = digestLinks.map((link: any) => {
        const digestDate = link.digests?.published_at || link.digests?.generated_at
        return {
          topic: link.topic,
          score: link.score,
          publishedAt: digestDate
        }
      })

      return {
        id: ep.id,
        title: ep.title,
        status: ep.status,
        timestamp: ep.created_at,
        score: maxScore,
        scores: ep.scores || {},
        digests,
        type: 'episode'
      }
    })

    // Transcript analytics - get episodes with transcripts
    const allEpisodes = await db.getEpisodes({ limit: 100 })
    const episodesWithTranscripts = allEpisodes.filter((ep: any) => ep.transcript_content)

    if (episodesWithTranscripts.length > 0) {
      const lengths = episodesWithTranscripts.map((ep: any) => (ep.transcript_content || '').length).filter((l: number) => l > 0)

      if (lengths.length > 0) {
        transcriptAnalytics.avgChars = Math.round(lengths.reduce((sum: number, l: number) => sum + l, 0) / lengths.length)
        transcriptAnalytics.avgTokens = Math.round(transcriptAnalytics.avgChars / 4)
        transcriptAnalytics.maxChars = Math.max(...lengths)
        transcriptAnalytics.minChars = Math.min(...lengths)
        transcriptAnalytics.totalEpisodes = lengths.length

        // Calculate truncation risk (episodes over 100K tokens)
        transcriptAnalytics.truncationRisk = lengths.filter((l: number) => l > 400000).length

        // Get episodes per digest setting
        const maxDigestEpisodes = await db.getSetting('max_digest_episodes')
        if (maxDigestEpisodes) {
          transcriptAnalytics.episodesPerDigest = parseInt(maxDigestEpisodes, 10)
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
