import { NextResponse } from 'next/server'
import { DatabaseClient, supabase } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/settings')

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const db = DatabaseClient.getInstance()

    // Get all web settings from database
    const data = await db.getSettings()

    // Group settings by category with values and metadata
    const settings: Record<string, Record<string, any>> = {}
    const settingsMeta: Record<string, Record<string, { updated_at: string | null }>> = {}

    if (data) {
      for (const row of data) {
        if (!settings[row.category]) {
          settings[row.category] = {}
          settingsMeta[row.category] = {}
        }

        // Parse value based on data type (if available)
        let parsedValue: any = row.setting_value
        if (row.value_type) {
          if (row.value_type === 'bool' || row.value_type === 'boolean') {
            parsedValue = row.setting_value === 'true' || row.setting_value === 'True'
          } else if (row.value_type === 'int' || row.value_type === 'integer') {
            parsedValue = parseInt(row.setting_value, 10)
          } else if (row.value_type === 'float' || row.value_type === 'number') {
            parsedValue = parseFloat(row.setting_value)
          }
        }

        settings[row.category][row.setting_key] = parsedValue
        settingsMeta[row.category][row.setting_key] = {
          updated_at: row.updated_at || null
        }
      }
    }

    return NextResponse.json({ settings, settingsMeta })
  } catch (error) {
    log.error('Failed to fetch settings', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const body = await request.json()
    const { category, key, value } = body

    if (!category || !key || value === undefined) {
      return NextResponse.json(
        { error: 'Missing required fields: category, key, value' },
        { status: 400 }
      )
    }

    const db = DatabaseClient.getInstance()

    // Convert value to string for storage
    const stringValue = String(value)

    await db.updateSetting(category, key, stringValue)

    return NextResponse.json({ success: true })
  } catch (error) {
    log.error('Failed to update settings', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}