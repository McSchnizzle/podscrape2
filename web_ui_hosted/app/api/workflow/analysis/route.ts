import { NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url)
    const hoursBack = parseInt(searchParams.get('hours') || '24')

    const db = DatabaseClient.getInstance()
    const analysis = await db.getWorkflowAnalysis(hoursBack)

    return NextResponse.json(analysis)
  } catch (error) {
    console.error('Failed to get workflow analysis:', error)
    return NextResponse.json(
      { error: 'Failed to get workflow analysis' },
      { status: 500 }
    )
  }
}
