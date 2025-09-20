import { NextResponse } from 'next/server'

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

    // Transform runs into activity format
    const activities = runs.map((run: any) => {
      const createdAt = new Date(run.created_at)
      const now = new Date()
      const diffMs = now.getTime() - createdAt.getTime()
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
      const diffMinutes = Math.floor(diffMs / (1000 * 60))

      let timeAgo = ''
      if (diffHours > 0) {
        timeAgo = `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
      } else if (diffMinutes > 0) {
        timeAgo = `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`
      } else {
        timeAgo = 'Just now'
      }

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
        id: run.id,
        type: activityType,
        message,
        time: timeAgo,
        status: run.status,
        conclusion: run.conclusion,
        htmlUrl: run.html_url,
        createdAt: run.created_at
      }
    })

    return NextResponse.json({
      activities,
      totalCount: data.total_count || 0
    })

  } catch (error) {
    console.error('Failed to get workflow runs:', error)
    return NextResponse.json(
      { error: 'Failed to get workflow runs' },
      { status: 500 }
    )
  }
}