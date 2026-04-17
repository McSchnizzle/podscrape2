import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

export const dynamic = 'force-dynamic'

const log = createLogger('api/watch-themes')

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const db = DatabaseClient.getInstance()
    const themes = await db.getWatchThemes()
    return NextResponse.json({ themes })
  } catch (error) {
    log.error('Failed to load watch themes', {
      error: error instanceof Error ? error.message : 'Unknown',
    })
    return NextResponse.json({ error: 'Failed to load watch themes' }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const body = await request.json()
    if (typeof body.name !== 'string' || !body.name.trim()) {
      return NextResponse.json({ error: 'name is required' }, { status: 400 })
    }
    if (typeof body.description !== 'string' || !body.description.trim()) {
      return NextResponse.json({ error: 'description is required' }, { status: 400 })
    }

    const db = DatabaseClient.getInstance()
    const saved = await db.upsertWatchTheme({
      id: typeof body.id === 'number' ? body.id : undefined,
      name: body.name.trim(),
      description: body.description.trim(),
      active: body.active !== undefined ? Boolean(body.active) : true,
      sort_order: typeof body.sort_order === 'number' ? body.sort_order : 100,
    })
    return NextResponse.json({ theme: saved })
  } catch (error) {
    log.error('Failed to save watch theme', {
      error: error instanceof Error ? error.message : 'Unknown',
    })
    return NextResponse.json({ error: 'Failed to save watch theme' }, { status: 500 })
  }
}

export async function DELETE(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const { searchParams } = new URL(request.url)
    const id = Number(searchParams.get('id'))
    if (!Number.isInteger(id) || id <= 0) {
      return NextResponse.json({ error: 'valid id required' }, { status: 400 })
    }
    const db = DatabaseClient.getInstance()
    await db.deleteWatchTheme(id)
    return NextResponse.json({ success: true })
  } catch (error) {
    log.error('Failed to delete watch theme', {
      error: error instanceof Error ? error.message : 'Unknown',
    })
    return NextResponse.json({ error: 'Failed to delete watch theme' }, { status: 500 })
  }
}
