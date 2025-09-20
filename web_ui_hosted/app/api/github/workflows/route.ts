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

    // Get workflow runs
    const response = await fetch(
      `https://api.github.com/repos/${githubRepo}/actions/runs?per_page=20`,
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

    // Transform the data for frontend consumption
    const workflows = runs.map((run: any) => ({
      id: run.id,
      name: run.name,
      status: run.status,
      conclusion: run.conclusion,
      createdAt: run.created_at,
      updatedAt: run.updated_at,
      htmlUrl: run.html_url,
      headBranch: run.head_branch,
      event: run.event,
      workflowId: run.workflow_id
    }))

    return NextResponse.json({
      workflows,
      totalCount: data.total_count || 0
    })

  } catch (error) {
    console.error('Failed to get workflows:', error)
    return NextResponse.json(
      { error: 'Failed to get workflows' },
      { status: 500 }
    )
  }
}