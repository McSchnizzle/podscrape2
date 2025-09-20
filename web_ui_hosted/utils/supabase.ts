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
  setting_key: string
  setting_value: string
  value_type?: string
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
    try {
      // First get all feeds
      const { data: feeds, error: feedsError } = await supabase
        .from('feeds')
        .select('*')
        .order('created_at', { ascending: false })

      if (feedsError) throw feedsError

      // For now, return feeds without episode data to get the page working
      // We'll add episode data back once the basic functionality is confirmed
      return (feeds || []).map(feed => ({
        ...feed,
        latest_episode_title: null,
        last_episode_date: null
      })) as Feed[]
    } catch (error) {
      console.error('Database error in getFeeds:', error)
      throw error
    }
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
        setting_key: key,
        setting_value: value,
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

  async getPipelineStats() {
    try {
      const today = new Date().toISOString().split('T')[0]

      // Get episodes processed today
      const { count: episodesProcessedToday } = await supabase
        .from('episodes')
        .select('*', { count: 'exact', head: true })
        .gte('updated_at', `${today}T00:00:00Z`)
        .in('status', ['transcribed', 'scored', 'digested', 'published'])

      // Get digests generated today
      const { count: digestsGeneratedToday } = await supabase
        .from('digests')
        .select('*', { count: 'exact', head: true })
        .gte('created_at', `${today}T00:00:00Z`)

      // Get total episodes
      const { count: totalEpisodes } = await supabase
        .from('episodes')
        .select('*', { count: 'exact', head: true })

      // Get last successful digest
      const { data: lastSuccessfulDigest } = await supabase
        .from('digests')
        .select('created_at')
        .eq('status', 'published')
        .order('created_at', { ascending: false })
        .limit(1)

      return {
        episodesProcessedToday: episodesProcessedToday || 0,
        digestsGeneratedToday: digestsGeneratedToday || 0,
        totalEpisodes: totalEpisodes || 0,
        lastSuccessfulRun: lastSuccessfulDigest?.[0]?.created_at || null
      }
    } catch (error) {
      console.error('Failed to get pipeline stats:', error)
      return {
        episodesProcessedToday: 0,
        digestsGeneratedToday: 0,
        totalEpisodes: 0,
        lastSuccessfulRun: null
      }
    }
  }
}