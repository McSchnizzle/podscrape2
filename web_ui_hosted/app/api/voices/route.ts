import { NextResponse } from 'next/server'
import { requireAuth } from '@/lib/auth-guard'
import { createLogger } from '@/lib/logger'

const log = createLogger('api/voices')

export interface ElevenLabsVoice {
  voice_id: string
  name: string
  labels?: Record<string, string>
  category?: string
  description?: string
}

export async function GET() {
  const auth = await requireAuth()
  if (!auth.authorized) return auth.error!

  try {
    const apiKey = process.env.ELEVENLABS_API_KEY

    if (!apiKey) {
      log.error('ELEVENLABS_API_KEY not configured')
      return NextResponse.json(
        { error: 'ElevenLabs API key not configured' },
        { status: 500 }
      )
    }

    log.info('Fetching ElevenLabs voices')

    const response = await fetch('https://api.elevenlabs.io/v1/voices', {
      method: 'GET',
      headers: {
        'xi-api-key': apiKey,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      const errorText = await response.text()
      log.error('ElevenLabs API error', { status: response.status, error: errorText })
      return NextResponse.json(
        { error: 'Failed to fetch voices from ElevenLabs' },
        { status: response.status }
      )
    }

    const data = await response.json()

    // Transform to a simpler format
    const voices: ElevenLabsVoice[] = (data.voices || []).map((voice: any) => ({
      voice_id: voice.voice_id,
      name: voice.name,
      labels: voice.labels || {},
      category: voice.category || 'general',
      description: voice.description || ''
    }))

    log.info('Successfully fetched ElevenLabs voices', { count: voices.length })

    return NextResponse.json({ voices })
  } catch (error) {
    log.error('Voices API error', { error: error instanceof Error ? error.message : 'Unknown error' })
    return NextResponse.json(
      { error: 'Failed to fetch voices' },
      { status: 500 }
    )
  }
}
