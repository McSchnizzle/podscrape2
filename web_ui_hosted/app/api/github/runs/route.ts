import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

const timeAgo = (dateString: string) => {
  const createdAt = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - createdAt.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor(diffMs / (1000 * 60))

  if (diffHours > 24) {
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
  }

  if (diffHours > 0) {
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  }

  if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`
  }

  return 'Just now'
}

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

    // Pull recent Supabase pipeline runs (database is required; fail loudly if unavailable)
    const db = new DatabaseClient()
    const supabaseRuns = await db.getPipelineRuns(10)

    const pipelineActivities = supabaseRuns.map(run => {
      const history = Array.isArray(run.phase?.history) ? run.phase!.history : []
      const latestPhase = history.length > 0 ? history[history.length - 1] : null

      let message = run.workflow_name || 'Pipeline run'
      if (latestPhase) {
        message += ` • ${latestPhase.phase} ${latestPhase.status}`
      } else if (run.status) {
        message += ` • ${run.status}`
      }

      return {
        id: `supabase-${run.id}`,
        type: 'pipeline',
        message,
        time: run.started_at ? timeAgo(run.started_at) : '—',
        status: run.status || 'unknown',
        conclusion: run.conclusion || 'unknown',
        htmlUrl: run.notes || '',
        createdAt: run.started_at || new Date().toISOString()
      }
    })

    // Get recent workflow runs from GitHub Actions API
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

    // Transform runs into activity format
    const githubActivities = runs.map((run: any) => {
      let activityType = 'pipeline'
      let message = `${run.name} workflow`

      if (run.name.includes('Publishing')) {
        activityType = 'publishing'
        message = 'Publishing workflow'
      } else if (run.name.includes('Full Pipeline')) {
        activityType = 'pipeline'
        message = 'Full pipeline workflow'
      }

      if (run.status === 'completed') {
        if (run.conclusion === 'success') {
          message += ' completed successfully'
        } else if (run.conclusion === 'failure') {
          message += ' failed'
        } else {
          message += ` completed (${run.conclusion})`
        }
      } else if (run.status === 'in_progress') {
        message += ' is running'
      } else {
        message += ` is ${run.status}`
      }

      return {
        id: `github-${run.id}`,
        type: activityType,
        message,
        time: timeAgo(run.created_at),
        status: run.status,
        conclusion: run.conclusion,
        htmlUrl: run.html_url,
        createdAt: run.created_at
      }
    })

    const activities = [...pipelineActivities, ...githubActivities]
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())

    return NextResponse.json({
      activities,
      totalCount: activities.length
    })

  } catch (error) {
    console.error('Failed to get workflow runs:', error)
    return NextResponse.json(
      { error: 'Failed to get workflow runs' },
      { status: 500 }
    )
  }
}
