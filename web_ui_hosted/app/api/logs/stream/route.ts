import { NextRequest, NextResponse } from 'next/server'

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const githubToken = process.env.GITHUB_TOKEN
    const githubRepo = process.env.GITHUB_REPOSITORY

    if (!githubToken || !githubRepo) {
      return NextResponse.json(
        { error: 'GitHub configuration missing' },
        { status: 500 }
      )
    }

    const url = new URL(request.url)
    const runId = url.searchParams.get('runId')

    if (!runId) {
      return NextResponse.json(
        { error: 'runId parameter required' },
        { status: 400 }
      )
    }

    // Get workflow run jobs
    const response = await fetch(
      `https://api.github.com/repos/${githubRepo}/actions/runs/${runId}/jobs`,
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
    const jobs = data.jobs || []

    // Transform jobs into log entries
    const logs = jobs.map((job: any) => {
      const steps = job.steps || []

      return {
        jobId: job.id,
        jobName: job.name,
        status: job.status,
        conclusion: job.conclusion,
        startedAt: job.started_at,
        completedAt: job.completed_at,
        steps: steps.map((step: any) => ({
          name: step.name,
          status: step.status,
          conclusion: step.conclusion,
          number: step.number,
          startedAt: step.started_at,
          completedAt: step.completed_at
        }))
      }
    })

    return NextResponse.json({
      runId,
      jobs: logs,
      totalJobs: jobs.length
    })

  } catch (error) {
    console.error('Failed to get workflow logs:', error)
    return NextResponse.json(
      { error: 'Failed to get workflow logs' },
      { status: 500 }
    )
  }
}