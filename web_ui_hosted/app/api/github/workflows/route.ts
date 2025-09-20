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

    // Get workflow runs with aggressive cache-busting
    const cacheBreaker = `${Date.now()}-${Math.random()}`
    const response = await fetch(
      `https://api.github.com/repos/${githubRepo}/actions/runs?per_page=30&_=${cacheBreaker}`,
      {
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0',
        },
        cache: 'no-store'
      }
    )

    if (!response.ok) {
      const errorText = await response.text()
      console.error(`GitHub API error: ${response.status} - ${errorText}`)
      throw new Error(`GitHub API error: ${response.status} - ${errorText}`)
    }

    const data = await response.json()
    const runs = data.workflow_runs || []

    console.log(`GitHub API returned ${runs.length} workflow runs. First 3:`)
    runs.slice(0, 3).forEach((run: any, index: number) => {
      console.log(`  ${index + 1}. ${run.name} (ID: ${run.id}) - Status: ${run.status}/${run.conclusion} - Created: ${run.created_at} - Updated: ${run.updated_at}`)
    })

    // Transform and sort the data for frontend consumption
    const workflows = runs
      .map((run: any) => ({
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
      .sort((a: any, b: any) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()) // Sort by newest first

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