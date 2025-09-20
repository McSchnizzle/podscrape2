import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

interface Topic {
  name: string
  instruction_file: string
  voice_id: string
  active: boolean
  description: string
}

interface TopicsConfig {
  topics: Topic[]
  settings: {
    score_threshold: number
    max_words_per_script: number
    default_voice_settings: {
      stability: number
      similarity_boost: number
      style: number
      use_speaker_boost: boolean
    }
  }
  last_updated: string
}

const TOPICS_CONFIG_PATH = path.join(process.cwd(), '..', 'config', 'topics.json')

function loadTopicsConfig(): TopicsConfig {
  try {
    const data = fs.readFileSync(TOPICS_CONFIG_PATH, 'utf8')
    return JSON.parse(data)
  } catch (error) {
    console.error('Failed to load topics config:', error)
    // Return default config
    return {
      topics: [],
      settings: {
        score_threshold: 0.65,
        max_words_per_script: 25000,
        default_voice_settings: {
          stability: 0.75,
          similarity_boost: 0.75,
          style: 0.0,
          use_speaker_boost: true
        }
      },
      last_updated: new Date().toISOString()
    }
  }
}

function saveTopicsConfig(config: TopicsConfig): void {
  try {
    config.last_updated = new Date().toISOString()
    fs.writeFileSync(TOPICS_CONFIG_PATH, JSON.stringify(config, null, 2))
  } catch (error) {
    console.error('Failed to save topics config:', error)
    throw new Error('Failed to save topics configuration')
  }
}

export async function GET() {
  try {
    const config = loadTopicsConfig()
    return NextResponse.json({
      topics: config.topics,
      settings: config.settings
    })
  } catch (error) {
    console.error('Topics API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { topics } = body

    if (!Array.isArray(topics)) {
      return NextResponse.json(
        { error: 'Topics must be an array' },
        { status: 400 }
      )
    }

    // Validate topics
    for (const topic of topics) {
      if (!topic.name || typeof topic.name !== 'string') {
        return NextResponse.json(
          { error: 'Each topic must have a name' },
          { status: 400 }
        )
      }
    }

    const config = loadTopicsConfig()
    config.topics = topics
    saveTopicsConfig(config)

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Topics API error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}