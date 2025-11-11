import { createClient } from '@supabase/supabase-js'

// Lazy initialization to avoid build-time errors
let supabaseClient: any = null

function getSupabaseClient() {
  if (!supabaseClient) {
    const supabaseUrl = process.env.SUPABASE_URL!
    const supabaseServiceRole = process.env.SUPABASE_SERVICE_ROLE!

    if (!supabaseUrl || !supabaseServiceRole) {
      throw new Error('Missing Supabase environment variables')
    }

    supabaseClient = createClient(supabaseUrl, supabaseServiceRole, {
      auth: {
        autoRefreshToken: false,
        persistSession: false,
        detectSessionInUrl: false,
        flowType: 'implicit',
        debug: false
      },
      // Additional settings to minimize auth client creation
      global: {
        headers: {
          'x-my-custom-header': 'database-only-client'
        }
      }
    })
  }
  return supabaseClient
}

// Export getter function instead of direct client
export const supabase = new Proxy({} as any, {
  get: (target, prop) => {
    const client = getSupabaseClient()
    return client[prop]
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
  status: 'pending' | 'transcribed' | 'scored' | 'digested' | 'published' | 'not_relevant' | 'failed'
  feed_id: number
  published_date?: string
  scored_at?: string
  scores?: Record<string, number>
  created_at: string
  updated_at: string
  inclusion?: Array<{ topic: string; date: string }>
}

export interface Digest {
  id: number
  topic: string
  status: 'generated' | 'audio_generated' | 'published' | 'failed'
  script_content?: string
  mp3_path?: string
  episode_ids?: number[]
  digest_date?: string
  created_at: string
  updated_at: string
  generated_at?: string
}

export interface TopicRecord {
  id: number
  slug: string
  name: string
  description?: string
  voice_id?: string
  voice_settings?: Record<string, any>
  instructions_md?: string
  is_active: boolean
  sort_order: number
  last_generated_at?: string
  created_at: string
  updated_at: string
  // Multi-voice dialogue support (v1.82)
  use_dialogue_api?: boolean
  dialogue_model?: string
  voice_config?: Record<string, any>
}

export interface TopicInstructionVersionRecord {
  id: number
  topic_id: number
  version: number
  instructions_md: string
  change_note?: string
  created_at: string
  created_by?: string
}

export interface PipelineRunRecord {
  id: string
  workflow_run_id?: number
  workflow_name?: string
  trigger?: string
  status?: string
  conclusion?: string
  started_at?: string
  finished_at?: string
  phase?: Record<string, any>
  notes?: string
  created_at: string
  updated_at: string
}

export interface PipelineLogRecord {
  id: number
  run_id: string
  phase: string
  timestamp: string
  level: string
  logger_name: string
  module?: string
  function?: string
  line?: number
  message: string
  extra?: Record<string, any> | null
}

export interface DigestEpisodeLinkRecord {
  id: number
  digest_id: number
  episode_id: number
  topic?: string
  score?: number
  position?: number
  created_at: string
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

// Singleton database client instance
let databaseClientInstance: DatabaseClient | null = null

// Database operations
export class DatabaseClient {
  // Singleton pattern - prevent multiple instances
  constructor() {
    if (databaseClientInstance) {
      return databaseClientInstance
    }
    databaseClientInstance = this
  }

  // Static method to get singleton instance
  static getInstance(): DatabaseClient {
    if (!databaseClientInstance) {
      databaseClientInstance = new DatabaseClient()
    }
    return databaseClientInstance
  }

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

      // Get latest episode for each feed
      const feedsWithEpisodes = []

      for (const feed of feeds || []) {
        // Get the latest episode for this feed
        const { data: latestEpisode } = await supabase
          .from('episodes')
          .select('title, published_date')
          .eq('feed_id', feed.id)
          .order('published_date', { ascending: false })
          .limit(1)

        feedsWithEpisodes.push({
          ...feed,
          latest_episode_title: latestEpisode?.[0]?.title || null,
          last_episode_date: latestEpisode?.[0]?.published_date || null
        })
      }

      return feedsWithEpisodes as Feed[]
    } catch (error) {
      console.error('Database error in getFeeds:', error)
      throw error
    }
  }

  async getTopics(): Promise<TopicRecord[]> {
    const { data, error } = await supabase
      .from('topics')
      .select('*')
      .order('sort_order', { ascending: true })
      .order('name', { ascending: true })

    if (error) throw error
    return data as TopicRecord[]
  }

  async getTopicByName(name: string): Promise<TopicRecord | null> {
    const { data, error } = await supabase
      .from('topics')
      .select('*')
      .eq('name', name)
      .limit(1)
      .maybeSingle()

    if (error) throw error
    return data as TopicRecord | null
  }

  async upsertTopic(topic: Partial<TopicRecord> & { name: string }): Promise<TopicRecord> {
    const payload = {
      ...topic,
      sort_order: topic.sort_order ?? 0,
      is_active: topic.is_active ?? true,
    }

    const { data, error } = await supabase
      .from('topics')
      .upsert(payload, { onConflict: 'slug' })
      .select()
      .limit(1)
      .single()

    if (error) throw error
    return data as TopicRecord
  }

  async deleteTopic(id: number): Promise<void> {
    const { error } = await supabase
      .from('topics')
      .update({ is_active: false, updated_at: new Date().toISOString() })
      .eq('id', id)

    if (error) throw error
  }

  async addTopicInstructionVersion(params: {
    topic_id: number
    instructions_md: string
    change_note?: string
    created_by?: string
  }): Promise<TopicInstructionVersionRecord> {
    const { data: latest, error: latestError } = await supabase
      .from('topic_instruction_versions')
      .select('version')
      .eq('topic_id', params.topic_id)
      .order('version', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (latestError) throw latestError

    const nextVersion = (latest?.version ?? 0) + 1

    const { data, error } = await supabase
      .from('topic_instruction_versions')
      .insert({
        topic_id: params.topic_id,
        version: nextVersion,
        instructions_md: params.instructions_md,
        change_note: params.change_note,
        created_by: params.created_by
      })
      .select()
      .limit(1)
      .single()

    if (error) throw error
    return data as TopicInstructionVersionRecord
  }

  async getPipelineRuns(limit: number = 5): Promise<PipelineRunRecord[]> {
    const { data, error } = await supabase
      .from('pipeline_runs')
      .select('*')
      .order('started_at', { ascending: false })
      .limit(limit)

    if (error) throw error
    return data as PipelineRunRecord[]
  }

  async getPipelineLogs(limit: number = 100, runId?: string): Promise<PipelineLogRecord[]> {
    let query = supabase
      .from('pipeline_logs')
      .select('*')
      .order('timestamp', { ascending: false })
      .limit(limit)

    if (runId) {
      query = query.eq('run_id', runId)
    }

    const { data, error } = await query

    if (error) throw error
    return (data as PipelineLogRecord[]) || []
  }

  async getDistinctRunIds(limit: number = 5): Promise<string[]> {
    const { data, error } = await supabase
      .from('pipeline_logs')
      .select('run_id, timestamp')
      .order('timestamp', { ascending: false })
      .limit(limit * 5)

    if (error) throw error

    const runIds: string[] = []
    const seen = new Set<string>()
    for (const row of data || []) {
      if (row.run_id && !seen.has(row.run_id)) {
        seen.add(row.run_id)
        runIds.push(row.run_id)
        if (runIds.length >= limit) break
      }
    }
    return runIds
  }

  async getRecentEpisodes(limit: number = 10) {
    const { data, error } = await supabase
      .from('episodes')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) throw error
    return data
  }


  async getSettings() {
    const { data, error } = await supabase
      .from('web_settings')
      .select('*')

    if (error) throw error
    return data as WebSetting[]
  }


  async updateSetting(category: string, key: string, value: string) {
    // Infer value type from the value
    let value_type = 'string'
    if (value === 'true' || value === 'false') {
      value_type = 'bool'
    } else if (!isNaN(Number(value))) {
      value_type = value.includes('.') ? 'float' : 'int'
    }

    // First try to update existing record
    const { data: updateData, error: updateError } = await supabase
      .from('web_settings')
      .update({
        setting_value: value,
        value_type: value_type,
        updated_at: new Date().toISOString()
      })
      .eq('category', category)
      .eq('setting_key', key)
      .select()

    // If update didn't affect any rows, insert a new record
    if (updateData && updateData.length === 0) {
      const { data: insertData, error: insertError } = await supabase
        .from('web_settings')
        .insert({
          category,
          setting_key: key,
          setting_value: value,
          value_type: value_type,
          updated_at: new Date().toISOString()
        })
        .select()

      if (insertError) throw insertError
      return insertData?.[0] as WebSetting
    }

    if (updateError) throw updateError
    return updateData?.[0] as WebSetting
  }

  async getSetting(settingKey: string): Promise<string | null> {
    const { data, error } = await supabase
      .from('web_settings')
      .select('setting_value')
      .eq('setting_key', settingKey)
      .single()

    if (error || !data) return null
    return data.setting_value
  }

  async setSetting(settingKey: string, value: string): Promise<void> {
    // For setSetting, we'll treat category as 'general' if not specified in key
    const [category, key] = settingKey.includes('.')
      ? settingKey.split('.', 2)
      : ['general', settingKey]

    await this.updateSetting(category, key, value)
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
        .gte('generated_at', `${today}T00:00:00Z`)

      // Get total episodes
      const { count: totalEpisodes } = await supabase
        .from('episodes')
        .select('*', { count: 'exact', head: true })

      // Get last successful digest
      const { data: lastSuccessfulDigest } = await supabase
        .from('digests')
        .select('published_at')
        .eq('status', 'published')
        .order('published_at', { ascending: false })
        .limit(1)

      return {
        episodesProcessedToday: episodesProcessedToday || 0,
        digestsGeneratedToday: digestsGeneratedToday || 0,
        totalEpisodes: totalEpisodes || 0,
        lastSuccessfulRun: lastSuccessfulDigest?.[0]?.published_at || null
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

  async getEpisodeBacklogStats() {
    const countStatus = async (status: string) => {
      const { count, error } = await supabase
        .from('episodes')
        .select('*', { count: 'exact', head: true })
        .eq('status', status)

      if (error) throw error
      return count || 0
    }

    const countDigests = async (status: string) => {
      const { count, error } = await supabase
        .from('digests')
        .select('*', { count: 'exact', head: true })
        .eq('status', status)

      if (error) throw error
      return count || 0
    }

    const [pending, transcribed, scored, digestsGenerated, digestsAudioGenerated] = await Promise.all([
      countStatus('pending'),
      countStatus('transcribed'),
      countStatus('scored'),
      countDigests('generated'),
      countDigests('audio_generated')
    ])

    return {
      awaitingScoring: pending + transcribed,
      awaitingDigest: scored,
      awaitingTts: digestsGenerated,
      awaitingPublish: digestsAudioGenerated
    }
  }

  async getEpisodesAwaitingScoring(limit: number = 5) {
    const { data, error } = await supabase
      .from('episodes')
      .select('id, title, episode_guid, status, published_date, created_at')
      .in('status', ['pending', 'transcribed'])
      .order('published_date', { ascending: false })
      .limit(limit)

    if (error) throw error
    return data || []
  }

  async getEpisodesAwaitingDigest(limit: number = 5) {
    const { data, error } = await supabase
      .from('episodes')
      .select('id, title, episode_guid, status, published_date, created_at')
      .eq('status', 'scored')
      .order('scored_at', { ascending: false, nullsFirst: false })
      .limit(limit)

    if (error) throw error
    return data || []
  }

  async getLatestDigests(limit: number = 5) {
    const { data, error} = await supabase
      .from('digests')
      .select('id, topic, status, digest_date, generated_at, published_at, mp3_path')
      .order('generated_at', { ascending: false, nullsFirst: false })
      .limit(limit)

    if (error) throw error
    return data || []
  }

  // Episode operations
  async getEpisodes(filters: {
    q?: string
    status?: string
    sortBy?: string
    sortDir?: string
    limit?: number
  } = {}) {
    try {
      const {
        q = '',
        status = '',
        sortBy = 'scored_at',
        sortDir = 'desc',
        limit = 100
      } = filters

      let query = supabase
        .from('episodes')
        .select('*')
        .order(sortBy, { ascending: sortDir === 'asc' })
        .limit(limit)

      // Apply status filter
      if (status) {
        query = query.eq('status', status)
      }

      const { data, error } = await query

      if (error) throw error

      let episodes = data || []

      const episodeIds = episodes.map((ep: Episode) => ep.id).filter(Boolean)
      let digestLinks: DigestEpisodeLinkRecord[] = []
      let digestsMap: Record<number, any> = {}

      if (episodeIds.length > 0) {
        const { data: linkData, error: linkError } = await supabase
          .from('digest_episode_links')
          .select('*')
          .in('episode_id', episodeIds)

        if (!linkError && linkData) {
          digestLinks = linkData as DigestEpisodeLinkRecord[]
          const digestIds = Array.from(new Set(digestLinks.map((link: DigestEpisodeLinkRecord) => link.digest_id)))
          if (digestIds.length > 0) {
            const { data: digestData, error: digestError } = await supabase
              .from('digests')
              .select('id, topic, digest_date')
              .in('id', digestIds)

            if (!digestError && digestData) {
              digestData.forEach((d: Digest) => {
                digestsMap[d.id] = d
              })
            }
          }
        }
      }

      // Get feed titles for episodes (since we can't join due to missing FK constraint)
      if (episodes.length > 0) {
        const feedIds = Array.from(new Set(episodes.map((ep: Episode) => ep.feed_id).filter(Boolean)))
        if (feedIds.length > 0) {
          const { data: feeds, error: feedsError } = await supabase
            .from('feeds')
            .select('id, title')
            .in('id', feedIds)

          if (!feedsError && feeds) {
            const feedMap = Object.fromEntries(feeds.map((f: Feed) => [f.id, f.title]))
            episodes = episodes.map((ep: Episode) => ({
              ...ep,
              feeds: ep.feed_id ? { title: feedMap[ep.feed_id] || 'Unknown Feed' } : null
            }))
          }
        }
      }

      // Apply text search on the frontend for simplicity
      if (q) {
        const searchTerm = q.toLowerCase()
        episodes = episodes.filter((ep: Episode & { feeds?: { title: string } }) =>
          ep.title?.toLowerCase().includes(searchTerm) ||
          ep.feeds?.title?.toLowerCase().includes(searchTerm)
        )
      }

      const inclusionMap: Record<number, Array<{ topic: string; date: string }>> = {}
      digestLinks.forEach((link: DigestEpisodeLinkRecord) => {
        const digest = digestsMap[link.digest_id]
        if (!digest) return
        if (!inclusionMap[link.episode_id]) {
          inclusionMap[link.episode_id] = []
        }
        inclusionMap[link.episode_id].push({
          topic: digest.topic,
          date: digest.digest_date
        })
      })

      return episodes.map((ep: Episode) => ({
        ...ep,
        inclusion: inclusionMap[ep.id] || []
      }))
    } catch (error) {
      console.error('Failed to get episodes:', error)
      return []
    }
  }

  async getDigests(limit: number = 20) {
    try {
      const { data, error } = await supabase
        .from('digests')
        .select('*')
        .order('digest_date', { ascending: false })
        .order('topic', { ascending: true })
        .limit(limit)

      if (error) throw error

      // Enrich digests with episode information
      const enrichedDigests = await Promise.all((data || []).map(async (digest: Digest) => {
        if (digest.episode_ids && digest.episode_ids.length > 0) {
          const { data: episodes, error: episodeError } = await supabase
            .from('episodes')
            .select('id, title')
            .in('id', digest.episode_ids)

          if (!episodeError && episodes) {
            return {
              ...digest,
              episodes: episodes.map((ep: Episode) => ep.title.length > 60 ? ep.title.substring(0, 60) + '...' : ep.title),
              episode_count: episodes.length
            }
          }
        }
        return {
          ...digest,
          episodes: [],
          episode_count: 0
        }
      }))

      return enrichedDigests
    } catch (error) {
      console.error('Failed to load digests:', error)
      return []
    }
  }

  async getRecentDigests(days: number = 14) {
    try {
      const startDate = new Date()
      startDate.setDate(startDate.getDate() - days)

      const { data, error } = await supabase
        .from('digests')
        .select('*')
        .gte('generated_at', startDate.toISOString())
        .order('generated_at', { ascending: false })

      if (error) throw error
      return data || []
    } catch (error) {
      console.error('Failed to get recent digests:', error)
      return []
    }
  }

  async getDigestLinksForEpisodes(episodeIds: number[]) {
    try {
      const { data, error } = await supabase
        .from('digest_episode_links')
        .select(`
          episode_id,
          digest_id,
          topic,
          score,
          digests (
            published_at,
            generated_at
          )
        `)
        .in('episode_id', episodeIds)

      if (error) throw error
      return data || []
    } catch (error) {
      console.error('Failed to get digest links:', error)
      return []
    }
  }

  async updateEpisodeStatus(id: number, status: string) {
    try {
      const { data, error } = await supabase
        .from('episodes')
        .update({
          status,
          updated_at: new Date().toISOString()
        })
        .eq('id', id)
        .select()

      if (error) throw error
      return data?.[0] as Episode
    } catch (error) {
      console.error('Failed to update episode status:', error)
      throw error
    }
  }

  async resetEpisodeToPending(id: number) {
    try {
      // 1. Clear scores and reset status to pending
      const { error: updateError } = await supabase
        .from('episodes')
        .update({
          status: 'pending',
          scores: null,
          scored_at: null,
          updated_at: new Date().toISOString()
        })
        .eq('id', id)

      if (updateError) throw updateError

      // 2. Find all digests containing this episode
      const { data: links, error: linksError } = await supabase
        .from('digest_episode_links')
        .select('digest_id')
        .eq('episode_id', id)

      if (linksError) throw linksError

      const digestIds = links?.map((link: { digest_id: number }) => link.digest_id) || []

      // 3. Delete digest_episode_links for this episode
      const { error: deleteLinksError } = await supabase
        .from('digest_episode_links')
        .delete()
        .eq('episode_id', id)

      if (deleteLinksError) throw deleteLinksError

      // 4. For each affected digest, check if it has any other episodes
      //    If not, delete the digest
      for (const digestId of digestIds) {
        const { data: remainingLinks, error: checkError } = await supabase
          .from('digest_episode_links')
          .select('episode_id')
          .eq('digest_id', digestId)

        if (checkError) throw checkError

        // If no other episodes in this digest, delete it
        if (!remainingLinks || remainingLinks.length === 0) {
          const { error: deleteDigestError } = await supabase
            .from('digests')
            .delete()
            .eq('id', digestId)

          if (deleteDigestError) throw deleteDigestError
        }
      }

      return {
        success: true,
        digestsAffected: digestIds.length,
        message: `Episode reset to pending. ${digestIds.length} digest(s) updated.`
      }
    } catch (error) {
      console.error('Failed to reset episode to pending:', error)
      throw error
    }
  }

  // ==================== TASKS MANAGEMENT ====================

  async getTasks(filters?: {
    status?: string[]
    priority?: string[]
    category?: string[]
    tags?: string[]
    search?: string
  }, sort?: {
    field: string
    order: 'asc' | 'desc'
  }, pagination?: {
    page: number
    pageSize: number
  }) {
    try {
      let query = supabase
        .from('tasks')
        .select('*', { count: 'exact' })

      // Apply filters
      if (filters) {
        if (filters.status && filters.status.length > 0) {
          query = query.in('status', filters.status)
        }
        if (filters.priority && filters.priority.length > 0) {
          query = query.in('priority', filters.priority)
        }
        if (filters.category && filters.category.length > 0) {
          query = query.in('category', filters.category)
        }
        if (filters.tags && filters.tags.length > 0) {
          query = query.overlaps('tags', filters.tags)
        }
        if (filters.search) {
          query = query.or(`title.ilike.%${filters.search}%,description.ilike.%${filters.search}%`)
        }
      }

      // Apply sorting
      if (sort) {
        query = query.order(sort.field, { ascending: sort.order === 'asc' })
      } else {
        // Default sort: priority (P0 first), then submission_date desc
        query = query.order('priority', { ascending: true })
        query = query.order('submission_date', { ascending: false })
      }

      // Apply pagination
      if (pagination) {
        const { page, pageSize } = pagination
        const start = page * pageSize
        const end = start + pageSize - 1
        query = query.range(start, end)
      }

      const { data, error, count } = await query

      if (error) throw error

      return {
        tasks: data || [],
        totalCount: count || 0
      }
    } catch (error) {
      console.error('Failed to get tasks:', error)
      throw error
    }
  }

  async getTaskById(id: number) {
    try {
      const { data, error } = await supabase
        .from('tasks')
        .select('*')
        .eq('id', id)
        .single()

      if (error) throw error
      return data
    } catch (error) {
      console.error('Failed to get task by ID:', error)
      throw error
    }
  }

  async createTask(task: {
    title: string
    description?: string
    status?: string
    priority?: string
    category?: string
    version_introduced?: string
    files_affected?: string[]
    estimated_effort?: string
    tags?: string[]
    assigned_to?: string
  }) {
    try {
      const { data, error } = await supabase
        .from('tasks')
        .insert([{
          ...task,
          status: task.status || 'open',
          priority: task.priority || 'P3',
          submission_date: new Date().toISOString(),
          last_update_date: new Date().toISOString()
        }])
        .select()
        .single()

      if (error) throw error
      return data
    } catch (error) {
      console.error('Failed to create task:', error)
      throw error
    }
  }

  async updateTask(id: number, updates: {
    title?: string
    description?: string
    status?: string
    priority?: string
    category?: string
    version_completed?: string
    files_affected?: string[]
    completion_notes?: string
    estimated_effort?: string
    session_number?: number
    tags?: string[]
    assigned_to?: string
  }) {
    try {
      const { data, error } = await supabase
        .from('tasks')
        .update({
          ...updates,
          last_update_date: new Date().toISOString()
        })
        .eq('id', id)
        .select()
        .single()

      if (error) throw error
      return data
    } catch (error) {
      console.error('Failed to update task:', error)
      throw error
    }
  }

  async deleteTask(id: number) {
    try {
      const { error } = await supabase
        .from('tasks')
        .delete()
        .eq('id', id)

      if (error) throw error
      return { success: true }
    } catch (error) {
      console.error('Failed to delete task:', error)
      throw error
    }
  }

  async getTaskStats() {
    try {
      const { data: tasks, error } = await supabase
        .from('tasks')
        .select('status, priority')

      if (error) throw error

      const stats = {
        total: tasks?.length || 0,
        byStatus: {
          open: tasks?.filter((t: { status: string }) => t.status === 'open').length || 0,
          in_progress: tasks?.filter((t: { status: string }) => t.status === 'in_progress').length || 0,
          on_hold: tasks?.filter((t: { status: string }) => t.status === 'on_hold').length || 0,
          completed: tasks?.filter((t: { status: string }) => t.status === 'completed').length || 0,
          skipped: tasks?.filter((t: { status: string }) => t.status === 'skipped').length || 0
        },
        byPriority: {
          P0: tasks?.filter((t: { priority: string }) => t.priority === 'P0').length || 0,
          P1: tasks?.filter((t: { priority: string }) => t.priority === 'P1').length || 0,
          P2: tasks?.filter((t: { priority: string }) => t.priority === 'P2').length || 0,
          P3: tasks?.filter((t: { priority: string }) => t.priority === 'P3').length || 0
        }
      }

      return stats
    } catch (error) {
      console.error('Failed to get task stats:', error)
      throw error
    }
  }
}
