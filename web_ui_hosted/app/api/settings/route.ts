import { NextResponse } from 'next/server'
import { DatabaseClient, supabase } from '@/utils/supabase'

export async function GET() {
  try {
    const db = new DatabaseClient()

    // Get all web settings from database using the existing method
    const data = await db.getSettings()

    // Group settings by category
    const settings: Record<string, Record<string, any>> = {}

    if (data) {
      for (const row of data) {
        if (!settings[row.category]) {
          settings[row.category] = {}
        }

        // Parse value based on data type (if available)
        let parsedValue = row.value
        // For now, just store as strings since we don't have data_type in the interface
        // TODO: Add data_type to WebSetting interface and migration

        settings[row.category][row.key] = parsedValue
      }
    }

    return NextResponse.json({ settings })
  } catch (error) {
    console.error('Settings API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { category, key, value } = body

    if (!category || !key || value === undefined) {
      return NextResponse.json(
        { error: 'Missing required fields: category, key, value' },
        { status: 400 }
      )
    }

    const db = new DatabaseClient()

    // Convert value to string for storage
    const stringValue = String(value)

    await db.updateSetting(category, key, stringValue)

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Settings API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}