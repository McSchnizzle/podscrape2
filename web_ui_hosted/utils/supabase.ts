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
  /**
   * Episode processing status.
   * @see src/database/episode_status.py for canonical definition
   */
  status: 'pending' | 'processing' | 'transcribed' | 'scored' | 'not_relevant' | 'digested' | 'failed'
  feed_id: number
  published_date?: string
  scored_at?: string
  scores?: Record<string, number>
  created_at: string
  updated_at: string
  inclusion?: Array<{ topic: string; date: string }>
}

/**
 * Valid episode status values - keep in sync with EpisodeStatus Python enum
 * @see src/database/episode_status.py
 */
export const EPISODE_STATUSES = ['pending', 'processing', 'transcribed', 'scored', 'not_relevant', 'digested', 'failed'] as const;
export type EpisodeStatusType = typeof EPISODE_STATUSES[number];

export interface Digest {
  id: number
  topic: string
  status: 'generated' | 'audio_generated' | 'published' | 'failed'
  script_content?: string
  mp3_path?: string
  /** @deprecated Use digest_episode_links join table instead. Issue #10. */
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

export interface WorkflowErrorRecord {
  id: number
  error_date: string
  occurred_at: string
  run_id: string
  workflow_run_id?: number
  error_category: string
  phase: string
  severity: string
  feed_id?: number
  feed_url?: string
  error_code?: string
  error_message: string
  error_summary?: string
  extra?: Record<string, any>
  source_log_id?: number
  resolved: boolean
  resolved_at?: string
  resolution_notes?: string
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
      // Single query using view with pre-joined latest episode data
      // This eliminates N+1 queries (was: 1 feeds query + N episode queries)
      const { data: feeds, error } = await supabase
        .from('feeds_with_latest_episode')
        .select('*')

      if (error) throw error

      return (feeds || []) as Feed[]
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

  /**
   * @deprecated Use getSettingByCategory instead for proper category+key lookup.
   * This method only searches by setting_key and may not find settings
   * that have unique category+key combinations.
   */
  async getSetting(settingKey: string): Promise<string | null> {
    const { data, error } = await supabase
      .from('web_settings')
      .select('setting_value')
      .eq('setting_key', settingKey)
      .single()

    if (error || !data) return null
    return data.setting_value
  }

  /**
   * Get a setting value using proper category+key lookup.
   * This is the recommended method for retrieving settings.
   */
  async getSettingByCategory(category: string, key: string): Promise<string | null> {
    const { data, error } = await supabase
      .from('web_settings')
      .select('setting_value')
      .eq('category', category)
      .eq('setting_key', key)
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
    page?: number
    pageSize?: number
  } = {}): Promise<{ episodes: Episode[], totalCount: number }> {
    try {
      const {
        q = '',
        status = '',
        sortBy = 'scored_at',
        sortDir = 'desc',
        page = 0,
        pageSize = 25
      } = filters

      // Build query with count for pagination
      let query = supabase
        .from('episodes')
        .select('*', { count: 'exact' })

      // Apply status filter BEFORE order/pagination
      if (status) {
        query = query.eq('status', status)
      }

      // Apply text search on episode title (database-level)
      // Note: Feed title search not available at database level - search by episode title only
      if (q) {
        query = query.ilike('title', `%${q}%`)
      }

      // Apply ordering
      query = query.order(sortBy, { ascending: sortDir === 'asc' })

      // Apply pagination with range() instead of limit()
      const start = page * pageSize
      const end = start + pageSize - 1
      query = query.range(start, end)

      const { data, error, count } = await query

      // Debug logging
      console.log(`[Supabase] Query for status='${status}' returned ${data?.length || 0} episodes`)

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

      const processedEpisodes = episodes.map((ep: Episode) => ({
        ...ep,
        inclusion: inclusionMap[ep.id] || []
      }))

      return {
        episodes: processedEpisodes,
        totalCount: count ?? 0
      }
    } catch (error) {
      console.error('Failed to get episodes:', error)
      return { episodes: [], totalCount: 0 }
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

      const digestIds = (data || []).map((d: Digest) => d.id)
      let episodeLinks: DigestEpisodeLinkRecord[] = []
      let episodesMap: Record<number, string> = {}

      if (digestIds.length > 0) {
        // Get all links for these digests (using join table as source of truth)
        const { data: linkData, error: linkError } = await supabase
          .from('digest_episode_links')
          .select('digest_id, episode_id')
          .in('digest_id', digestIds)
          .order('position', { ascending: true })

        if (!linkError && linkData) {
          episodeLinks = linkData as DigestEpisodeLinkRecord[]
          const episodeIds = Array.from(new Set(episodeLinks.map(l => l.episode_id)))

          if (episodeIds.length > 0) {
            const { data: episodes, error: episodeError } = await supabase
              .from('episodes')
              .select('id, title')
              .in('id', episodeIds)

            if (!episodeError && episodes) {
              episodesMap = Object.fromEntries(
                episodes.map((ep: Episode) => [ep.id, ep.title])
              )
            }
          }
        }
      }

      // Build episode lists per digest from links
      const digestEpisodesMap: Record<number, string[]> = {}
      episodeLinks.forEach((link: DigestEpisodeLinkRecord) => {
        const title = episodesMap[link.episode_id]
        if (!title) return
        if (!digestEpisodesMap[link.digest_id]) {
          digestEpisodesMap[link.digest_id] = []
        }
        const truncatedTitle = title.length > 60 ? title.substring(0, 60) + '...' : title
        digestEpisodesMap[link.digest_id].push(truncatedTitle)
      })

      return (data || []).map((digest: Digest) => ({
        ...digest,
        episodes: digestEpisodesMap[digest.id] || [],
        episode_count: (digestEpisodesMap[digest.id] || []).length
      }))
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

  // ==================== WORKFLOW ANALYSIS ====================

  async getWorkflowAnalysis(hoursBack: number = 24) {
    try {
      const cutoffDate = new Date()
      cutoffDate.setHours(cutoffDate.getHours() - hoursBack)

      // Get distinct run IDs from pipeline_logs in the last 24 hours
      const { data: recentLogs, error: logsError } = await supabase
        .from('pipeline_logs')
        .select('run_id, phase, message, level, timestamp, extra')
        .gte('timestamp', cutoffDate.toISOString())
        .order('timestamp', { ascending: true })

      if (logsError) throw logsError

      // Group logs by run_id
      const runGroups: Record<string, PipelineLogRecord[]> = {}
      for (const log of recentLogs || []) {
        if (!log.run_id) continue
        if (!runGroups[log.run_id]) {
          runGroups[log.run_id] = []
        }
        runGroups[log.run_id].push(log as PipelineLogRecord)
      }

      // Get web settings for thresholds
      const { data: settings, error: settingsError } = await supabase
        .from('web_settings')
        .select('setting_key, setting_value')
        .in('setting_key', ['score_threshold', 'min_episodes_per_digest'])

      const scoreThreshold = settings?.find((s: { setting_key: string; setting_value: string }) => s.setting_key === 'score_threshold')?.setting_value || '0.65'
      const minEpisodes = settings?.find((s: { setting_key: string; setting_value: string }) => s.setting_key === 'min_episodes_per_digest')?.setting_value || '3'

      // Get active topics
      const { data: topics, error: topicsError } = await supabase
        .from('topics')
        .select('name, slug')
        .eq('is_active', true)

      if (topicsError) throw topicsError

      // Get all feeds for title lookup
      const { data: allFeeds } = await supabase
        .from('feeds')
        .select('feed_url, title')

      // Create a map of feed URL patterns to titles
      const feedUrlToTitle = new Map<string, string>()
      if (allFeeds) {
        for (const feed of allFeeds) {
          if (feed.feed_url && feed.title) {
            feedUrlToTitle.set(feed.feed_url.toLowerCase(), feed.title)
            try {
              const hostname = new URL(feed.feed_url).hostname.toLowerCase()
              if (!feedUrlToTitle.has(hostname)) {
                feedUrlToTitle.set(hostname, feed.title)
              }
            } catch {}
          }
        }
      }

      // Analyze each workflow run
      const workflows = []
      for (const [runId, logs] of Object.entries(runGroups)) {
        const analysis = this.analyzeWorkflowRun(runId, logs, topics || [], parseFloat(scoreThreshold), parseInt(minEpisodes), feedUrlToTitle)
        workflows.push(analysis)
      }

      // Sort by most recent first
      workflows.sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime())

      // Get current state analysis - episodes with status 'scored'
      const { data: scoredEpisodes, error: scoredError } = await supabase
        .from('episodes')
        .select('id, title, scores, published_date')
        .eq('status', 'scored')
        .order('published_date', { ascending: false })

      if (scoredError) throw scoredError

      const episodesBelowThreshold = (scoredEpisodes || []).map((ep: any) => {
        const scores = ep.scores || {}
        const entries = Object.entries(scores) as [string, number][]
        const highestEntry = entries.reduce((max, curr) =>
          curr[1] > (max[1] || 0) ? curr : max, ['', 0] as [string, number])

        return {
          id: ep.id,
          title: ep.title,
          scores: scores,
          highestScore: highestEntry[1],
          highestTopic: highestEntry[0],
          threshold: parseFloat(scoreThreshold),
          meetsThreshold: highestEntry[1] >= parseFloat(scoreThreshold)
        }
      })

      return {
        workflows: workflows.slice(0, 5), // Last 5 workflows
        currentState: {
          scoredEpisodesWaiting: scoredEpisodes?.length || 0,
          episodesBelowThreshold: episodesBelowThreshold,
          scoreThreshold: parseFloat(scoreThreshold),
          minEpisodesRequired: parseInt(minEpisodes)
        },
        analyzedAt: new Date().toISOString()
      }
    } catch (error) {
      console.error('Failed to get workflow analysis:', error)
      throw error
    }
  }

  private analyzeWorkflowRun(
    runId: string,
    logs: PipelineLogRecord[],
    topics: Array<{name: string, slug: string}>,
    scoreThreshold: number,
    minEpisodes: number,
    feedUrlToTitle: Map<string, string>
  ) {
    const sortedLogs = [...logs].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )

    const startedAt = sortedLogs[0]?.timestamp || new Date().toISOString()
    const finishedAt = sortedLogs[sortedLogs.length - 1]?.timestamp || startedAt

    // Count outcomes from log messages
    let episodesDiscovered = 0
    let episodesTranscribed = 0
    let episodesScored = 0
    let digestsGenerated = 0
    let audioFilesCreated = 0
    const topicsCovered: string[] = []
    const noDigestReasons: Array<{
      topic: string
      reason: string
      details: string
      episodesFound?: number
      minRequired?: number
      threshold?: number
    }> = []

    // Parse logs for outcomes
    for (const log of logs) {
      const msg = log.message.toLowerCase()

      // Discovery phase
      if (msg.includes('found') && msg.includes('episode')) {
        const match = log.message.match(/found (\d+)/i)
        if (match) episodesDiscovered = Math.max(episodesDiscovered, parseInt(match[1]))
      }

      // Audio/transcription phase
      if (msg.includes('transcribed') || msg.includes('transcription complete')) {
        const match = log.message.match(/(\d+)/i)
        if (match) episodesTranscribed = Math.max(episodesTranscribed, parseInt(match[1]))
      }

      // Scoring
      if (msg.includes('scored') && !msg.includes('below')) {
        const match = log.message.match(/(\d+)/i)
        if (match) episodesScored = Math.max(episodesScored, parseInt(match[1]))
      }

      // Digest generation outcomes
      if (msg.includes('generated digest') || msg.includes('✅ generated digest')) {
        digestsGenerated++
        // Extract topic name
        for (const topic of topics) {
          if (log.message.includes(topic.name)) {
            if (!topicsCovered.includes(topic.name)) {
              topicsCovered.push(topic.name)
            }
          }
        }
      }

      // TTS/Audio generation
      if (msg.includes('generated:') && msg.includes('mp3')) {
        const match = log.message.match(/(\d+)\s*mp3/i)
        if (match) audioFilesCreated = parseInt(match[1])
      }

      // Parse "no digest" reasons
      if (msg.includes('insufficient episodes')) {
        const topicMatch = log.message.match(/for ([^:]+):/i) || log.message.match(/for (.+?) digest/i)
        const countMatch = log.message.match(/(\d+)\s*<\s*(\d+)/i)
        if (topicMatch) {
          noDigestReasons.push({
            topic: topicMatch[1].trim(),
            reason: 'insufficient_episodes',
            details: countMatch ? `${countMatch[1]} episodes found, ${countMatch[2]} required` : 'Not enough episodes',
            episodesFound: countMatch ? parseInt(countMatch[1]) : undefined,
            minRequired: countMatch ? parseInt(countMatch[2]) : minEpisodes
          })
        }
      }

      if (msg.includes('no qualifying episodes') || msg.includes('no episodes scored')) {
        const topicMatch = log.message.match(/for ([^(]+)/i) || log.message.match(/topic:\s*([^)]+)/i)
        if (topicMatch) {
          noDigestReasons.push({
            topic: topicMatch[1].trim(),
            reason: 'scores_below_threshold',
            details: `No episodes scored ≥${scoreThreshold}`,
            threshold: scoreThreshold
          })
        }
      }

      if (msg.includes('already exists') || msg.includes('returning existing digest')) {
        const topicMatch = log.message.match(/for ([^(]+)/i) || log.message.match(/topic:\s*([^)]+)/i)
        if (topicMatch) {
          // This is not really a "no digest reason" - it means a digest already existed
          // Only add if there wasn't also a generation
          const topicName = topicMatch[1].trim()
          if (!topicsCovered.includes(topicName)) {
            noDigestReasons.push({
              topic: topicName,
              reason: 'already_digested',
              details: 'Digest already exists for this date'
            })
          }
        }
      }
    }

    // Categorize errors - some are critical, some are minor
    const errorLogs = logs.filter(l => ['ERROR', 'CRITICAL'].includes(l.level))
    const warningLogs = logs.filter(l => l.level === 'WARNING')

    // Minor errors: feed fetch failures (403, 404, timeout) - don't fail the whole workflow
    const minorErrorPatterns = [
      /failed to fetch feed/i,
      /403.*forbidden/i,
      /404.*not found/i,
      /timeout/i,
      /connection.*refused/i
    ]

    // Critical errors: TTS failures, scoring failures, pipeline crashes
    const criticalErrors = errorLogs.filter(log =>
      !minorErrorPatterns.some(pattern => pattern.test(log.message))
    )
    const minorErrors = errorLogs.filter(log =>
      minorErrorPatterns.some(pattern => pattern.test(log.message))
    )

    // Extract detailed feed error information using passed-in feed title map
    const feedErrors: Array<{title: string, url: string, error: string}> = []
    for (const log of minorErrors) {
      // Try to extract feed URL and error type
      const urlMatch = log.message.match(/url:\s*(https?:\/\/[^\s]+)/i) ||
                       log.message.match(/(https?:\/\/feeds[^\s]+)/i) ||
                       log.message.match(/(https?:\/\/[^\s]+)/i)
      const errorMatch = log.message.match(/(\d{3})\s*(Client Error|Server Error)?:?\s*(\w+)?/i)

      if (urlMatch) {
        const url = urlMatch[1].replace(/[,;)\]]+$/, '') // Clean trailing punctuation
        let hostname = 'unknown'
        try {
          hostname = new URL(url).hostname.toLowerCase().replace('www.', '')
        } catch {}

        // Look up feed title - try full URL first, then hostname
        let feedTitle = feedUrlToTitle.get(url.toLowerCase()) ||
                        feedUrlToTitle.get(hostname) ||
                        hostname // Fallback to hostname if no title found

        let errorType = 'fetch failed'
        if (errorMatch) {
          errorType = `${errorMatch[1]} ${errorMatch[3] || ''}`
        } else if (log.message.toLowerCase().includes('timeout')) {
          errorType = 'timeout'
        } else if (log.message.toLowerCase().includes('connection')) {
          errorType = 'connection refused'
        }

        // Avoid duplicates (by title)
        if (!feedErrors.some(e => e.title === feedTitle)) {
          feedErrors.push({ title: feedTitle, url: hostname, error: errorType.trim() })
        }
      }
    }

    // Determine overall status based on critical errors and output
    let status: 'success' | 'failure' | 'partial' | 'no_output' = 'success'

    if (criticalErrors.length > 0) {
      // Critical errors - but if we still produced output, it's partial success
      if (digestsGenerated > 0 || audioFilesCreated > 0) {
        status = 'partial'
      } else {
        status = 'failure'
      }
    } else if (digestsGenerated === 0 && audioFilesCreated === 0) {
      status = 'no_output'
    } else if (warningLogs.length > 0 || minorErrors.length > 0 || noDigestReasons.length > 0) {
      status = 'partial'
    }

    // Generate summary message with actual error details
    let summary = ''

    // Build error summary for display
    const errorSummaries: string[] = []
    if (criticalErrors.length > 0) {
      // Get unique error messages (truncated)
      const errorMessages = criticalErrors.map(e => {
        const msg = e.message.replace(/^[\s❌✗]+/, '').trim()
        return msg.length > 80 ? msg.substring(0, 77) + '...' : msg
      })
      const uniqueErrors = Array.from(new Set(errorMessages))
      errorSummaries.push(...uniqueErrors.slice(0, 3))
    }

    if (status === 'failure') {
      summary = errorSummaries.length > 0
        ? `Failed: ${errorSummaries.join(' | ')}`
        : 'Workflow failed with errors.'
    } else if (digestsGenerated > 0 && audioFilesCreated > 0) {
      summary = `Generated ${digestsGenerated} digest(s) and ${audioFilesCreated} audio file(s) for: ${topicsCovered.join(', ')}`
      if (errorSummaries.length > 0) {
        summary += ` (with errors: ${errorSummaries[0]})`
      }
    } else if (digestsGenerated > 0) {
      summary = `Generated ${digestsGenerated} digest script(s) but no audio files were created.`
      if (errorSummaries.length > 0) {
        summary += ` Error: ${errorSummaries[0]}`
      }
    } else if (noDigestReasons.length > 0) {
      const reasonSummary = noDigestReasons.map(r => `${r.topic}: ${r.details}`).join('; ')
      summary = `No digests generated. ${reasonSummary}`
    } else if (minorErrors.length > 0) {
      // Include feed error details with titles
      const feedErrorSummary = feedErrors.length > 0
        ? feedErrors.map(f => `${f.title} (${f.error})`).join(', ')
        : 'feed issues'
      summary = `Completed with ${minorErrors.length} feed error(s): ${feedErrorSummary}`
    } else {
      summary = 'Workflow completed but no new content was generated.'
    }

    // If no output and no digest reasons captured, add explanation for each topic
    if ((status === 'no_output' || status === 'failure') && noDigestReasons.length === 0 && topics.length > 0) {
      // Check if audio phase failed - this is the most common reason for no output
      const audioPhaseError = criticalErrors.find(e =>
        e.message.toLowerCase().includes('audio') ||
        e.message.toLowerCase().includes('whisper') ||
        e.message.toLowerCase().includes('transcri')
      )

      // Check if digest phase was skipped (didn't run due to earlier failure)
      const digestPhaseSkipped = criticalErrors.length > 0 && !logs.some(l =>
        l.message.toLowerCase().includes('digest phase') && l.message.toLowerCase().includes('completed')
      )

      for (const topic of topics) {
        if (!noDigestReasons.some(r => r.topic === topic.name)) {
          if (audioPhaseError) {
            noDigestReasons.push({
              topic: topic.name,
              reason: 'audio_phase_failed',
              details: 'Audio processing failed - digest generation may not have run'
            })
          } else if (digestPhaseSkipped && criticalErrors.length > 0) {
            noDigestReasons.push({
              topic: topic.name,
              reason: 'pipeline_failed',
              details: 'Pipeline failed before digest generation could run'
            })
          } else {
            noDigestReasons.push({
              topic: topic.name,
              reason: 'no_new_episodes',
              details: 'No new qualifying episodes found'
            })
          }
        }
      }
    }

    return {
      workflowId: runId,
      startedAt,
      finishedAt,
      durationSeconds: (new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000,
      status,
      episodesDiscovered,
      episodesTranscribed,
      episodesScored,
      digestsGenerated,
      audioFilesCreated,
      topicsCovered,
      noDigestReasons,
      feedErrors,
      summary,
      errorCount: criticalErrors.length,
      warningCount: warningLogs.length + minorErrors.length
    }
  }

  async getScoredEpisodesWithScores() {
    try {
      const { data, error } = await supabase
        .from('episodes')
        .select('id, title, scores, published_date, status')
        .eq('status', 'scored')
        .order('published_date', { ascending: false })
        .limit(20)

      if (error) throw error
      return data || []
    } catch (error) {
      console.error('Failed to get scored episodes:', error)
      return []
    }
  }

  // ==================== ERROR ANALYTICS ====================

  async getErrorAnalytics(daysBack: number = 30) {
    try {
      const cutoffDate = new Date()
      cutoffDate.setDate(cutoffDate.getDate() - daysBack)
      const cutoffStr = cutoffDate.toISOString().split('T')[0]

      // Get errors in date range
      const { data: errors, error: errorsError } = await supabase
        .from('workflow_errors')
        .select('*')
        .gte('error_date', cutoffStr)
        .order('occurred_at', { ascending: false })

      if (errorsError) throw errorsError

      // Calculate summary statistics
      const byCategory: Record<string, number> = {}
      const byPhase: Record<string, number> = {}
      const bySeverity: Record<string, number> = {}
      const byDay: Record<string, number> = {}
      const feedErrors: Record<string, { count: number, lastError: string, feedUrl?: string }> = {}

      for (const err of errors || []) {
        // By category
        byCategory[err.error_category] = (byCategory[err.error_category] || 0) + 1

        // By phase
        byPhase[err.phase] = (byPhase[err.phase] || 0) + 1

        // By severity
        bySeverity[err.severity] = (bySeverity[err.severity] || 0) + 1

        // By day
        byDay[err.error_date] = (byDay[err.error_date] || 0) + 1

        // Track problematic feeds
        if (err.feed_id || err.feed_url) {
          const feedKey = err.feed_id ? `id:${err.feed_id}` : err.feed_url || 'unknown'
          if (!feedErrors[feedKey]) {
            feedErrors[feedKey] = { count: 0, lastError: err.occurred_at, feedUrl: err.feed_url }
          }
          feedErrors[feedKey].count++
          if (new Date(err.occurred_at) > new Date(feedErrors[feedKey].lastError)) {
            feedErrors[feedKey].lastError = err.occurred_at
          }
        }
      }

      // Get feed titles for problematic feeds
      const feedIds = Object.keys(feedErrors)
        .filter(k => k.startsWith('id:'))
        .map(k => parseInt(k.replace('id:', '')))

      let feedTitles: Record<number, string> = {}
      if (feedIds.length > 0) {
        const { data: feeds } = await supabase
          .from('feeds')
          .select('id, title')
          .in('id', feedIds)

        if (feeds) {
          feedTitles = Object.fromEntries(feeds.map((f: Feed) => [f.id, f.title]))
        }
      }

      // Build problematic feeds list with titles
      const problematicFeeds = Object.entries(feedErrors)
        .map(([key, data]) => {
          const feedId = key.startsWith('id:') ? parseInt(key.replace('id:', '')) : undefined
          return {
            feedId,
            feedUrl: data.feedUrl,
            title: feedId ? feedTitles[feedId] || 'Unknown Feed' : (data.feedUrl ? new URL(data.feedUrl).hostname : 'Unknown'),
            errorCount: data.count,
            lastError: data.lastError
          }
        })
        .sort((a, b) => b.errorCount - a.errorCount)
        .slice(0, 10)

      // Calculate trend (compare last 7 days to previous 7 days)
      const sevenDaysAgo = new Date()
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
      const fourteenDaysAgo = new Date()
      fourteenDaysAgo.setDate(fourteenDaysAgo.getDate() - 14)

      const recentErrors = (errors || []).filter(
        (e: WorkflowErrorRecord) => new Date(e.occurred_at) >= sevenDaysAgo
      ).length
      const previousErrors = (errors || []).filter(
        (e: WorkflowErrorRecord) => new Date(e.occurred_at) >= fourteenDaysAgo && new Date(e.occurred_at) < sevenDaysAgo
      ).length

      const trendDirection = recentErrors > previousErrors ? 'up' : recentErrors < previousErrors ? 'down' : 'stable'
      const trendPercent = previousErrors > 0
        ? Math.round(((recentErrors - previousErrors) / previousErrors) * 100)
        : recentErrors > 0 ? 100 : 0

      // Get recent unresolved errors
      const unresolvedErrors = (errors || [])
        .filter((e: WorkflowErrorRecord) => !e.resolved)
        .slice(0, 5)
        .map((e: WorkflowErrorRecord) => ({
          id: e.id,
          category: e.error_category,
          phase: e.phase,
          severity: e.severity,
          summary: e.error_summary || e.error_message.substring(0, 100),
          occurredAt: e.occurred_at,
          feedUrl: e.feed_url
        }))

      return {
        totalErrors: errors?.length || 0,
        byCategory,
        byPhase,
        bySeverity,
        byDay,
        problematicFeeds,
        unresolvedErrors,
        trend: {
          direction: trendDirection,
          percent: Math.abs(trendPercent),
          recentCount: recentErrors,
          previousCount: previousErrors
        },
        analyzedAt: new Date().toISOString()
      }
    } catch (error) {
      console.error('Failed to get error analytics:', error)
      throw error
    }
  }
}
