import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

function slugify(input: string): string {
  return input.toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'topic'
}

export async function GET() {
  try {
    const db = new DatabaseClient()
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
      source: 'supabase'
    }))

    return NextResponse.json({
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
    })
  } catch (error) {
    console.error('Topics API error:', error)
    return NextResponse.json({ error: 'Failed to load topics' }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const rawTopics = Array.isArray(body.topics) ? body.topics : null

    if (!rawTopics) {
      return NextResponse.json({ error: 'Topics must be an array' }, { status: 400 })
    }

    const db = new DatabaseClient()
    const existing = await db.getTopics()
    const existingBySlug = new Map(existing.map(t => [t.slug, t]))
    const seenSlugs = new Set<string>()

    for (let index = 0; index < rawTopics.length; index += 1) {
      const topic = rawTopics[index]
      if (typeof topic.name !== 'string' || !topic.name.trim()) {
        return NextResponse.json({ error: 'Each topic must have a name' }, { status: 400 })
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
      }

      await db.upsertTopic(payload)
    }

    // Delete topics that were removed
    const toDelete = existing.filter(t => !seenSlugs.has(t.slug))
    await Promise.all(toDelete.map(t => db.deleteTopic(t.id)))

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Topics API error:', error)
    return NextResponse.json({ error: 'Failed to save topics' }, { status: 500 })
  }
}
