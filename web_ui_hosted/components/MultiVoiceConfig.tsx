'use client'

import { useState, useEffect } from 'react'

export interface Voice {
  voice_id: string
  name: string
  labels?: Record<string, string>
  category?: string
  description?: string
}

export interface VoiceConfig {
  speaker_1?: {
    name: string
    voice_id: string
  }
  speaker_2?: {
    name: string
    voice_id: string
  }
}

interface MultiVoiceConfigProps {
  value: VoiceConfig | null
  onChange: (config: VoiceConfig) => void
  disabled?: boolean
}

export default function MultiVoiceConfig({
  value,
  onChange,
  disabled = false
}: MultiVoiceConfigProps) {
  const [voices, setVoices] = useState<Voice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Local state for speaker names and voice IDs
  const [speaker1Name, setSpeaker1Name] = useState(value?.speaker_1?.name || 'SPEAKER_1')
  const [speaker1VoiceId, setSpeaker1VoiceId] = useState(value?.speaker_1?.voice_id || '')
  const [speaker2Name, setSpeaker2Name] = useState(value?.speaker_2?.name || 'SPEAKER_2')
  const [speaker2VoiceId, setSpeaker2VoiceId] = useState(value?.speaker_2?.voice_id || '')

  useEffect(() => {
    fetchVoices()
  }, [])

  useEffect(() => {
    // Update local state when value prop changes
    if (value) {
      setSpeaker1Name(value.speaker_1?.name || 'SPEAKER_1')
      setSpeaker1VoiceId(value.speaker_1?.voice_id || '')
      setSpeaker2Name(value.speaker_2?.name || 'SPEAKER_2')
      setSpeaker2VoiceId(value.speaker_2?.voice_id || '')
    }
  }, [value])

  const fetchVoices = async () => {
    try {
      const response = await fetch('/api/voices')
      const data = await response.json()

      if (response.ok) {
        setVoices(data.voices || [])
      } else {
        setError(data.error || 'Failed to load voices')
      }
    } catch (err) {
      setError('Failed to connect to voices API')
    } finally {
      setLoading(false)
    }
  }

  const updateConfig = (
    s1Name: string,
    s1VoiceId: string,
    s2Name: string,
    s2VoiceId: string
  ) => {
    const config: VoiceConfig = {
      speaker_1: {
        name: s1Name,
        voice_id: s1VoiceId
      },
      speaker_2: {
        name: s2Name,
        voice_id: s2VoiceId
      }
    }
    onChange(config)
  }

  const handleSpeaker1NameChange = (name: string) => {
    setSpeaker1Name(name)
    updateConfig(name, speaker1VoiceId, speaker2Name, speaker2VoiceId)
  }

  const handleSpeaker1VoiceChange = (voiceId: string) => {
    setSpeaker1VoiceId(voiceId)
    updateConfig(speaker1Name, voiceId, speaker2Name, speaker2VoiceId)
  }

  const handleSpeaker2NameChange = (name: string) => {
    setSpeaker2Name(name)
    updateConfig(speaker1Name, speaker1VoiceId, name, speaker2VoiceId)
  }

  const handleSpeaker2VoiceChange = (voiceId: string) => {
    setSpeaker2VoiceId(voiceId)
    updateConfig(speaker1Name, speaker1VoiceId, speaker2Name, voiceId)
  }

  const getVoiceName = (voiceId: string) => {
    const voice = voices.find(v => v.voice_id === voiceId)
    return voice ? voice.name : 'Unknown'
  }

  if (loading) {
    return <div className="text-sm text-gray-500">Loading voices...</div>
  }

  if (error) {
    return <div className="text-sm text-error-600">{error}</div>
  }

  return (
    <div className="space-y-6">
      <div className="text-sm font-medium text-gray-700 mb-4">
        Multi-Voice Dialogue Configuration
      </div>

      {/* Speaker 1 */}
      <div className="space-y-3 p-4 bg-gray-50 rounded-md">
        <div className="font-medium text-sm text-gray-700">Speaker 1</div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Speaker Name (for script generation)
          </label>
          <input
            type="text"
            value={speaker1Name}
            onChange={(e) => handleSpeaker1NameChange(e.target.value)}
            className="input w-full"
            placeholder="SPEAKER_1"
            disabled={disabled}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Voice
          </label>
          <select
            value={speaker1VoiceId}
            onChange={(e) => handleSpeaker1VoiceChange(e.target.value)}
            disabled={disabled}
            className="input w-full"
          >
            <option value="">Select a voice...</option>
            {voices.map((voice) => (
              <option key={voice.voice_id} value={voice.voice_id}>
                {voice.name} {voice.category ? `(${voice.category})` : ''}
              </option>
            ))}
          </select>
          {speaker1VoiceId && (
            <div className="text-xs text-gray-500 mt-1">
              Voice ID: {speaker1VoiceId}
            </div>
          )}
        </div>
      </div>

      {/* Speaker 2 */}
      <div className="space-y-3 p-4 bg-gray-50 rounded-md">
        <div className="font-medium text-sm text-gray-700">Speaker 2</div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Speaker Name (for script generation)
          </label>
          <input
            type="text"
            value={speaker2Name}
            onChange={(e) => handleSpeaker2NameChange(e.target.value)}
            className="input w-full"
            placeholder="SPEAKER_2"
            disabled={disabled}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Voice
          </label>
          <select
            value={speaker2VoiceId}
            onChange={(e) => handleSpeaker2VoiceChange(e.target.value)}
            disabled={disabled}
            className="input w-full"
          >
            <option value="">Select a voice...</option>
            {voices.map((voice) => (
              <option key={voice.voice_id} value={voice.voice_id}>
                {voice.name} {voice.category ? `(${voice.category})` : ''}
              </option>
            ))}
          </select>
          {speaker2VoiceId && (
            <div className="text-xs text-gray-500 mt-1">
              Voice ID: {speaker2VoiceId}
            </div>
          )}
        </div>
      </div>

      {/* Summary */}
      {speaker1VoiceId && speaker2VoiceId && (
        <div className="text-xs text-gray-600 p-3 bg-blue-50 border border-blue-200 rounded">
          <div className="font-medium mb-1">Configuration Summary:</div>
          <div>{speaker1Name} → {getVoiceName(speaker1VoiceId)}</div>
          <div>{speaker2Name} → {getVoiceName(speaker2VoiceId)}</div>
        </div>
      )}
    </div>
  )
}
