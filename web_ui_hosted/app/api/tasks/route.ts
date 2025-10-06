import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

export const dynamic = 'force-dynamic'

// GET /api/tasks - List tasks with filtering, sorting, and pagination
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)

    // Parse filters
    const filters: any = {}

    const status = searchParams.getAll('status')
    if (status.length > 0) filters.status = status

    const priority = searchParams.getAll('priority')
    if (priority.length > 0) filters.priority = priority

    const category = searchParams.getAll('category')
    if (category.length > 0) filters.category = category

    const tags = searchParams.getAll('tags')
    if (tags.length > 0) filters.tags = tags

    const search = searchParams.get('search')
    if (search) filters.search = search

    // Parse sorting
    const sortField = searchParams.get('sortField') || 'submission_date'
    const sortOrder = (searchParams.get('sortOrder') || 'desc') as 'asc' | 'desc'

    // Parse pagination
    const page = parseInt(searchParams.get('page') || '0')
    const pageSize = parseInt(searchParams.get('pageSize') || '50')

    const db = DatabaseClient.getInstance()
    const result = await db.getTasks(
      Object.keys(filters).length > 0 ? filters : undefined,
      { field: sortField, order: sortOrder },
      { page, pageSize }
    )

    return NextResponse.json(result)
  } catch (error) {
    console.error('Failed to get tasks:', error)
    return NextResponse.json(
      { error: 'Failed to get tasks' },
      { status: 500 }
    )
  }
}

// POST /api/tasks - Create new task
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Validate required fields
    if (!body.title) {
      return NextResponse.json(
        { error: 'Title is required' },
        { status: 400 }
      )
    }

    const db = DatabaseClient.getInstance()
    const task = await db.createTask(body)

    return NextResponse.json(task, { status: 201 })
  } catch (error) {
    console.error('Failed to create task:', error)
    return NextResponse.json(
      { error: 'Failed to create task' },
      { status: 500 }
    )
  }
}
