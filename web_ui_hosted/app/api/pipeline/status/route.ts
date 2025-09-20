import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export async function GET() {
  try {
    const githubToken = process.env.GITHUB_TOKEN
    const githubRepo = process.env.GITHUB_REPOSITORY

    if (!githubToken || !githubRepo) {
      return NextResponse.json(
        { error: 'GitHub configuration missing' },
        { status: 500 }
      )
    }

    // Get recent workflow runs
    const response = await fetch(
      `https://api.github.com/repos/${githubRepo}/actions/runs?per_page=10`,
      {
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
        }
      }
    )

    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status}`)
    }

    const data = await response.json()
    const runs = data.workflow_runs || []

    // Find the most recent full pipeline and publishing runs
    const fullPipelineRun = runs.find((run: any) =>
      run.name === 'Full Pipeline'
    )
    const publishingRun = runs.find((run: any) =>
      run.name === 'Publishing Only'
    )

    // Get the most recent run overall
    const latestRun = runs[0]

    // Get database stats
    const db = new DatabaseClient()
    const stats = await db.getPipelineStats()

    return NextResponse.json({
      lastRun: latestRun ? {
        id: latestRun.id,
        status: latestRun.status,
        conclusion: latestRun.conclusion,
        createdAt: latestRun.created_at,
        updatedAt: latestRun.updated_at,
        workflowName: latestRun.name,
        htmlUrl: latestRun.html_url
      } : null,
      fullPipeline: fullPipelineRun ? {
        id: fullPipelineRun.id,
        status: fullPipelineRun.status,
        conclusion: fullPipelineRun.conclusion,
        createdAt: fullPipelineRun.created_at,
        htmlUrl: fullPipelineRun.html_url
      } : null,
      publishing: publishingRun ? {
        id: publishingRun.id,
        status: publishingRun.status,
        conclusion: publishingRun.conclusion,
        createdAt: publishingRun.created_at,
        htmlUrl: publishingRun.html_url
      } : null,
      stats: {
        episodesProcessedToday: stats.episodesProcessedToday || 0,
        digestsGeneratedToday: stats.digestsGeneratedToday || 0,
        lastSuccessfulRun: stats.lastSuccessfulRun,
        totalEpisodes: stats.totalEpisodes || 0
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