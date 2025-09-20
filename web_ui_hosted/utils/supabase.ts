import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.SUPABASE_URL!
const supabaseServiceRole = process.env.SUPABASE_SERVICE_ROLE!

if (!supabaseUrl || !supabaseServiceRole) {
  throw new Error('Missing Supabase environment variables')
}

// Create Supabase client with service role for admin operations
export const supabase = createClient(supabaseUrl, supabaseServiceRole, {
  auth: {
    autoRefreshToken: false,
    persistSession: false
  }
})

// Database types (subset of main types)
export interface Feed {
  id: number
  url: string
  title: string
  health_status: 'healthy' | 'warning' | 'error'
  last_checked?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Episode {
  id: number
  guid: string
  title: string
  status: 'discovered' | 'transcribed' | 'scored' | 'digested' | 'published' | 'not_relevant' | 'failed'
  feed_id: number
  published_date?: string
  created_at: string
  updated_at: string
}

export interface Digest {
  id: number
  topic: string
  status: 'generated' | 'audio_generated' | 'published' | 'failed'
  script_content?: string
  mp3_path?: string
  created_at: string
  updated_at: string
}

export interface WebSetting {
  id: number
  category: string
  key: string
  value: string
  created_at: string
  updated_at: string
}

// Database operations
export class DatabaseClient {

  async getSystemHealth() {
    try {
      // Test database connectivity
      const { count, error } = await supabase
        .from('feeds')
        .select('*', { count: 'exact', head: true })

      if (error) throw error

      return {
        database: 'connected',
        feeds_count: count || 0
      }
    } catch (error) {
      console.error('Database health check failed:', error)
      return {
        database: 'error',
        error: error instanceof Error ? error.message : 'Unknown error'
      }
    }
  }

  async getFeeds() {
    const { data, error } = await supabase
      .from('feeds')
      .select('*')
      .order('created_at', { ascending: false })

    if (error) throw error
    return data as Feed[]
  }

  async getRecentEpisodes(limit: number = 10) {
    const { data, error } = await supabase
      .from('episodes')
      .select(`
        *,
        feeds!inner(title)
      `)
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) throw error
    return data
  }

  async getRecentDigests(limit: number = 5) {
    const { data, error } = await supabase
      .from('digests')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) throw error
    return data as Digest[]
  }

  async getSettings() {
    const { data, error } = await supabase
      .from('web_settings')
      .select('*')

    if (error) throw error
    return data as WebSetting[]
  }

  async updateSetting(category: string, key: string, value: string) {
    const { data, error } = await supabase
      .from('web_settings')
      .upsert({
        category,
        key,
        value,
        updated_at: new Date().toISOString()
      })
      .select()

    if (error) throw error
    return data?.[0] as WebSetting
  }
}