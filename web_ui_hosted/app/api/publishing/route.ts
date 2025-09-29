import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export async function GET() {
  try {
    const db = DatabaseClient.getInstance()
    const digests = await db.getDigests(25)
    const pipelineRuns = await db.getPipelineRuns(5)

    return NextResponse.json({ digests, pipelineRuns })
  } catch (error) {
    console.error('Publishing overview error:', error)
    return NextResponse.json({ error: 'Failed to load publishing overview' }, { status: 500 })
  }
}
