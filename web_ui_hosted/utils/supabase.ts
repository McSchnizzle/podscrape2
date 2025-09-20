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
  feed_url: string  // matches database field name
  title: string
  description?: string
  active: boolean   // matches database field name
  consecutive_failures: number
  last_checked?: string
  last_episode_date?: string
  latest_episode_title?: string
  total_episodes_processed: number
  total_episodes_failed: number
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
      .select(`
        *,
        episodes(
          title,
          published_date
        )
      `)
      .order('created_at', { ascending: false })

    if (error) throw error

    // Process feeds to include latest episode data
    return (data || []).map(feed => {
      const episodes = (feed as any).episodes || []
      const latestEpisode = episodes.length > 0
        ? episodes.reduce((latest: any, current: any) => {
            if (!latest.published_date) return current
            if (!current.published_date) return latest
            return new Date(current.published_date) > new Date(latest.published_date) ? current : latest
          })
        : null

      return {
        ...feed,
        latest_episode_title: latestEpisode?.title || null,
        last_episode_date: latestEpisode?.published_date || null,
        episodes: undefined // Remove the episodes array from the result
      } as Feed
    })
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

  // Feed CRUD operations
  async createFeed(feed_url: string, title: string) {
    const { data, error } = await supabase
      .from('feeds')
      .insert({
        feed_url,
        title,
        active: true,
        consecutive_failures: 0,
        total_episodes_processed: 0,
        total_episodes_failed: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .select()

    if (error) throw error
    return data?.[0] as Feed
  }

  async updateFeed(id: number, updates: Partial<Feed>) {
    const { data, error } = await supabase
      .from('feeds')
      .update({
        ...updates,
        updated_at: new Date().toISOString()
      })
      .eq('id', id)
      .select()

    if (error) throw error
    return data?.[0] as Feed
  }

  async deleteFeed(id: number) {
    const { error } = await supabase
      .from('feeds')
      .delete()
      .eq('id', id)

    if (error) throw error
    return true
  }

  async toggleFeedActive(id: number, active: boolean) {
    return this.updateFeed(id, { active })
  }

  async updateFeedHealth(id: number, consecutive_failures: number = 0) {
    return this.updateFeed(id, { consecutive_failures, last_checked: new Date().toISOString() })
  }

  async checkFeed(id: number) {
    // Update last_checked timestamp to indicate a manual check was performed
    return this.updateFeed(id, { last_checked: new Date().toISOString() })
  }
}