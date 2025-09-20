import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const githubToken = process.env.GITHUB_TOKEN
    const githubRepo = process.env.GITHUB_REPOSITORY

    if (!githubToken || !githubRepo) {
      return NextResponse.json(
        { error: 'GitHub configuration missing' },
        { status: 500 }
      )
    }

    const body = await request.json()
    const { daysBack = "7" } = body

    // Trigger the publishing-only workflow
    const response = await fetch(
      `https://api.github.com/repos/${githubRepo}/actions/workflows/publishing-only.yml/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'Accept': 'application/vnd.github.v3+json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ref: 'main',
          inputs: {
            days_back: daysBack
          }
        })
      }
    )

    if (!response.ok) {
      const errorText = await response.text()
      console.error('GitHub API error:', response.status, errorText)
      return NextResponse.json(
        { error: `GitHub API error: ${response.status}` },
        { status: response.status }
      )
    }

    return NextResponse.json({
      success: true,
      message: 'Publishing workflow triggered successfully',
      inputs: { daysBack }
    })

  } catch (error) {
    console.error('Failed to trigger publishing:', error)
    return NextResponse.json(
      { error: 'Failed to trigger publishing' },
      { status: 500 }
    )
  }
}