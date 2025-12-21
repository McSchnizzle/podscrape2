import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import OpenAI from 'openai'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/recurring-topics/merge')

export const dynamic = 'force-dynamic'

function getSupabaseClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE!
  )
}

function getOpenAIClient() {
  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY not configured')
  }
  return new OpenAI({ apiKey })
}

interface EpisodeTopic {
  id: number
  topic_name: string
  topic_slug: string
  topic_type: string
  key_points: string[]
  digest_topic: string
  relevance_score: number
  novelty_score: number
  evolution_summary: string | null
  is_update: boolean
  parent_topic_id: number | null
  created_at: string
  episode_id: number
  episodes?: { title: string }
}

interface MergeResult {
  topic_name: string
  topic_type: string
  key_points: string[]
  digest_topic: string
  evolution_summary: string
  relevance_score: number
  novelty_score: number
}

// AI-powered merge of multiple topics
export async function POST(request: NextRequest) {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const supabase = getSupabaseClient()
    const body = await request.json()
    const { topic_ids } = body

    if (!topic_ids || !Array.isArray(topic_ids) || topic_ids.length < 2) {
      return NextResponse.json(
        { error: 'At least 2 topic IDs are required for merging' },
        { status: 400 }
      )
    }

    // Fetch all topics to merge
    const { data: topics, error: fetchError } = await supabase
      .from('episode_topics')
      .select(`
        *,
        episodes (
          title
        )
      `)
      .in('id', topic_ids)

    if (fetchError) {
      log.error('Error fetching topics', { error: fetchError.message })
      return NextResponse.json({ error: fetchError.message }, { status: 500 })
    }

    if (!topics || topics.length < 2) {
      return NextResponse.json(
        { error: 'Could not find at least 2 topics to merge' },
        { status: 404 }
      )
    }

    // Call OpenAI to merge the topics
    const openai = getOpenAIClient()

    const topicsDescription = topics.map((t: EpisodeTopic) => ({
      name: t.topic_name,
      type: t.topic_type,
      key_points: t.key_points,
      digest_topic: t.digest_topic,
      relevance_score: t.relevance_score,
      novelty_score: t.novelty_score,
      evolution_summary: t.evolution_summary,
      episode_title: t.episodes?.title
    }))

    const prompt = `You are analyzing multiple related topics extracted from podcast episodes. Your task is to merge these topics into a single unified topic that captures the most important information from all of them.

Here are the topics to merge:
${JSON.stringify(topicsDescription, null, 2)}

Create a merged topic with the following:
1. A unified topic_name that captures the essence of all topics (be concise but descriptive)
2. The most appropriate topic_type from: model_release, use_case, personality, research, company_news, regulation, technique, other
3. A consolidated list of key_points (combine and deduplicate, keep the most important 3-5 points)
4. The most relevant digest_topic category
5. An evolution_summary describing how this topic developed across the episodes (1-2 sentences)
6. Average relevance_score (0.0-1.0)
7. A novelty_score (0.0-1.0) reflecting how novel the merged topic is

Respond with a JSON object only, no markdown formatting:
{
  "topic_name": "string",
  "topic_type": "string",
  "key_points": ["string"],
  "digest_topic": "string",
  "evolution_summary": "string",
  "relevance_score": number,
  "novelty_score": number
}`

    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        { role: 'user', content: prompt }
      ],
      temperature: 0.7,
      max_tokens: 1000
    })

    const responseText = completion.choices[0]?.message?.content
    if (!responseText) {
      return NextResponse.json(
        { error: 'AI returned empty response' },
        { status: 500 }
      )
    }

    // Parse the AI response
    let mergeResult: MergeResult
    try {
      // Clean up the response - remove markdown code blocks if present
      const cleanedResponse = responseText
        .replace(/```json\n?/g, '')
        .replace(/```\n?/g, '')
        .trim()
      mergeResult = JSON.parse(cleanedResponse)
    } catch (parseError) {
      log.error('Failed to parse AI response', { response: responseText })
      return NextResponse.json(
        { error: 'Failed to parse AI merge result' },
        { status: 500 }
      )
    }

    // Generate slug from name
    const slug = mergeResult.topic_name.toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')

    // Get the earliest episode_id from the merged topics (for reference)
    const earliestTopic = topics.reduce((earliest: EpisodeTopic, current: EpisodeTopic) =>
      new Date(current.created_at) < new Date(earliest.created_at) ? current : earliest
    )

    // Create the merged topic
    const { data: newTopic, error: insertError } = await supabase
      .from('episode_topics')
      .insert({
        episode_id: earliestTopic.episode_id,
        topic_name: mergeResult.topic_name,
        topic_slug: slug,
        topic_type: mergeResult.topic_type,
        key_points: mergeResult.key_points,
        digest_topic: mergeResult.digest_topic || topics[0].digest_topic,
        relevance_score: mergeResult.relevance_score,
        novelty_score: mergeResult.novelty_score,
        evolution_summary: mergeResult.evolution_summary,
        is_update: false,
        parent_topic_id: null,
        first_seen_at: earliestTopic.first_seen_at || earliestTopic.created_at,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .select()
      .single()

    if (insertError) {
      log.error('Error creating merged topic', { error: insertError.message })
      return NextResponse.json({ error: insertError.message }, { status: 500 })
    }

    // Update original topics to point to the merged topic as parent
    const { error: updateError } = await supabase
      .from('episode_topics')
      .update({
        parent_topic_id: newTopic.id,
        updated_at: new Date().toISOString()
      })
      .in('id', topic_ids)

    if (updateError) {
      log.warn('Error updating original topics', { error: updateError.message })
      // Don't fail - the merge succeeded, we just couldn't update the parent references
    }

    return NextResponse.json({
      success: true,
      merged_topic: newTopic,
      original_topics_updated: !updateError,
      merge_details: {
        topics_merged: topics.length,
        original_topic_ids: topic_ids
      }
    }, { status: 201 })

  } catch (error) {
    log.error('Error in merge topics', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    )
  }
}
