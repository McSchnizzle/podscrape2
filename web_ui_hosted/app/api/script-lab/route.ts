import { NextRequest, NextResponse } from 'next/server'
import { DatabaseClient } from '@/utils/supabase'

const editorKey = (topic: string, key: string) => `${topic}:${key}`

const voiceLabelToId: Record<string, string> = {
  'American news anchor': 'Qxm2h3F1LF2mSoFwF8Vp',
  'British man': 'VR6AewLTigWG4xSOukaG',
  'Black woman': 'EXAVITQu4vr4xnSDxMaL',
  'energetic millennial': 'pNInz6obpgDQGcFmaJgB'
}

function mapVoiceLabel(label: string): string {
  return voiceLabelToId[label] || voiceLabelToId['American news anchor']
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const topicName = searchParams.get('topic')

    if (!topicName) {
      return NextResponse.json({ error: 'Missing topic parameter' }, { status: 400 })
    }

    const db = new DatabaseClient()
    const topic = await db.getTopicByName(topicName)

    if (!topic) {
      return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
    }

    const instructions = topic.instructions_md || ''

    const settings = await db.getSettings()
    const findSetting = (category: string, key: string): string | null => {
      const setting = settings.find(s => s.category === category && s.setting_key === key)
      return setting?.setting_value || null
    }

    const typeOfShow = findSetting('editor', editorKey(topicName, 'type_of_show')) || 'newscast'
    const voiceLabel = findSetting('editor', editorKey(topicName, 'voice_label')) || 'American news anchor'
    const tone = findSetting('editor', editorKey(topicName, 'tone')) || 'neutral'
    const pace = findSetting('editor', editorKey(topicName, 'pace')) || 'moderate'

    return NextResponse.json({
      content: instructions,
      type_of_show: typeOfShow,
      voice_label: voiceLabel,
      tone,
      pace
    })
  } catch (error) {
    console.error('Script lab GET error:', error)
    return NextResponse.json({ error: 'Failed to load script lab data' }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { action, topic: topicName, content, type_of_show, voice_label, tone, pace } = body

    if (!topicName) {
      return NextResponse.json({ error: 'Missing topic' }, { status: 400 })
    }

    const db = new DatabaseClient()
    const topic = await db.getTopicByName(topicName)

    if (!topic) {
      return NextResponse.json({ error: 'Topic not found' }, { status: 404 })
    }

    if (action === 'save') {
      const voiceId = mapVoiceLabel(voice_label)

      await db.upsertTopic({
        id: topic.id,
        slug: topic.slug,
        name: topic.name,
        description: topic.description,
        voice_id: voiceId,
        voice_settings: topic.voice_settings,
        is_active: topic.is_active,
        sort_order: topic.sort_order,
        instructions_md: content
      })

      await db.addTopicInstructionVersion({
        topic_id: topic.id,
        instructions_md: content,
        change_note: 'Updated via Script Lab',
        created_by: 'web-ui'
      })

      await db.updateSetting('editor', editorKey(topicName, 'type_of_show'), type_of_show)
      await db.updateSetting('editor', editorKey(topicName, 'voice_label'), voice_label)
      await db.updateSetting('editor', editorKey(topicName, 'tone'), tone)
      await db.updateSetting('editor', editorKey(topicName, 'pace'), pace)

      return NextResponse.json({
        success: true,
        message: 'Instructions and voice saved successfully'
      })
    }

    if (action === 'preview') {
      return NextResponse.json({
        success: true,
        preview: 'Script preview generation not yet implemented - would show digest script using current instructions and scored episodes',
        message: 'Preview generated successfully'
      })
    }

    if (action === 'rewrite') {
      return NextResponse.json({
        success: true,
        content,
        message: 'Instructions rewrite not yet implemented'
      })
    }

    return NextResponse.json({ error: 'Invalid action' }, { status: 400 })
  } catch (error) {
    console.error('Script lab POST error:', error)
    return NextResponse.json({ error: 'Failed to process script lab request' }, { status: 500 })
  }
}
