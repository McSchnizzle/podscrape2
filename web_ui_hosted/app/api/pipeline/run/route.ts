import { NextRequest, NextResponse } from 'next/server'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/pipeline/run')

export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

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
    const { dryRun = "false" } = body

    // Trigger the validated full pipeline workflow
    const response = await fetch(
      `https://api.github.com/repos/${githubRepo}/actions/workflows/validated-full-pipeline.yml/dispatches`,
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
            dry_run: dryRun
          }
        })
      }
    )

    if (!response.ok) {
      const errorText = await response.text()
      log.error('GitHub API error', { status: response.status, error: errorText })
      return NextResponse.json(
        { error: `GitHub API error: ${response.status}` },
        { status: response.status }
      )
    }

    return NextResponse.json({
      success: true,
      message: 'Validated pipeline workflow triggered successfully',
      inputs: { dryRun }
    })

  } catch (error) {
    log.error('Failed to trigger pipeline', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to trigger pipeline' },
      { status: 500 }
    )
  }
}