import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/topics')

function slugify(input: string): string {
  return input.toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'topic'
}

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    log.info('GET request');

    const db = DatabaseClient.getInstance()
    const topics = await db.getTopics()

    const response = topics.map(topic => ({
      id: topic.id,
      slug: topic.slug,
      name: topic.name,
      description: topic.description || '',
      voice_id: topic.voice_id || '',
      instructions_md: topic.instructions_md || '',
      instruction_file: `supabase://${topic.slug}`,
      active: topic.is_active,
      sort_order: topic.sort_order,
      last_generated_at: topic.last_generated_at,
      source: 'supabase',
      // Multi-voice dialogue support (v1.82)
      use_dialogue_api: topic.use_dialogue_api || false,
      dialogue_model: topic.dialogue_model || 'eleven_turbo_v2_5',
      voice_config: topic.voice_config || null
    }))

    const result = {
      topics: response,
      settings: {
        score_threshold: 0.65,
        max_words_per_script: 25000,
        default_voice_settings: {
          stability: 0.75,
          similarity_boost: 0.75,
          style: 0,
          use_speaker_boost: true
        }
      }
    }

    log.info('Returning topics', { count: result.topics.length });

    return NextResponse.json(result);
  } catch (error) {
    log.error('Failed to load topics', { error: error instanceof Error ? error.message : 'Unknown error' });
    return NextResponse.json({ error: 'Failed to load topics' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const body = await request.json()
    const rawTopics = Array.isArray(body.topics) ? body.topics : null

    if (!rawTopics) {
      return NextResponse.json({ error: 'Topics must be an array' }, { status: 400 })
    }

    const db = DatabaseClient.getInstance()
    const existing = await db.getTopics()
    const existingBySlug = new Map(existing.map(t => [t.slug, t]))
    const seenSlugs = new Set<string>()

    for (let index = 0; index < rawTopics.length; index += 1) {
      const topic = rawTopics[index]
      if (typeof topic.name !== 'string' || !topic.name.trim()) {
        return NextResponse.json({ error: 'Each topic must have a name' }, { status: 400 })
      }

      // kanban #2855: names starting with "_" are reserved for internal
      // keys stored inside episodes.scores (e.g. "_harold_rnd", the Harold
      // R&D-applicability rating) -- never a real, user-created topic. A
      // topic actually named "_harold_rnd" would let a scoring blob's
      // reserved key alias a real topic and defeat the reserved-namespace
      // guard in EpisodeRepository.get_scored_episodes_for_topic.
      if (topic.name.trim().startsWith('_')) {
        return NextResponse.json(
          { error: `Topic name cannot start with "_" (reserved): ${topic.name}` },
          { status: 400 }
        )
      }

      const slug = topic.slug || slugify(topic.name)
      seenSlugs.add(slug)

      const payload = {
        id: topic.id ?? existingBySlug.get(slug)?.id,
        slug,
        name: topic.name.trim(),
        description: topic.description || '',
        voice_id: topic.voice_id || '',
        voice_settings: topic.voice_settings || existingBySlug.get(slug)?.voice_settings,
        instructions_md: topic.instructions_md || existingBySlug.get(slug)?.instructions_md,
        is_active: topic.active !== undefined ? Boolean(topic.active) : true,
        sort_order: typeof topic.sort_order === 'number' ? topic.sort_order : index * 10,
        // Multi-voice dialogue support (v1.82)
        use_dialogue_api: topic.use_dialogue_api !== undefined ? Boolean(topic.use_dialogue_api) : (existingBySlug.get(slug)?.use_dialogue_api || false),
        dialogue_model: topic.dialogue_model || existingBySlug.get(slug)?.dialogue_model || 'eleven_turbo_v2_5',
        voice_config: topic.voice_config !== undefined ? topic.voice_config : (existingBySlug.get(slug)?.voice_config || null),
      }

      await db.upsertTopic(payload)
    }

    // Delete topics that were removed
    const toDelete = existing.filter(t => !seenSlugs.has(t.slug))
    await Promise.all(toDelete.map(t => db.deleteTopic(t.id)))

    return NextResponse.json({ success: true })
  } catch (error) {
    log.error('Failed to save topics', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json({ error: 'Failed to save topics' }, { status: 500 })
  }
}
