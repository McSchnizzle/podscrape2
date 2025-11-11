import { NextResponse } from 'next/server'

export interface ElevenLabsVoice {
  voice_id: string
  name: string
  labels?: Record<string, string>
  category?: string
  description?: string
}

export async function GET() {
  try {
    const apiKey = process.env.ELEVENLABS_API_KEY

    if (!apiKey) {
      console.error('ELEVENLABS_API_KEY not configured')
      return NextResponse.json(
        { error: 'ElevenLabs API key not configured' },
        { status: 500 }
      )
    }

    console.log('Fetching ElevenLabs voices...')

    const response = await fetch('https://api.elevenlabs.io/v1/voices', {
      method: 'GET',
      headers: {
        'xi-api-key': apiKey,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('ElevenLabs API error:', response.status, errorText)
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

    console.log(`Successfully fetched ${voices.length} ElevenLabs voices`)

    return NextResponse.json({ voices })
  } catch (error) {
    console.error('Voices API error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch voices' },
      { status: 500 }
    )
  }
}
