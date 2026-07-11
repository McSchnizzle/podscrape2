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
    return <div className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>Loading voices...</div>
  }

  if (error) {
    return <div style={{ font: 'var(--t-small)', color: 'var(--danger)' }}>{error}</div>
  }

  return (
    <div className="flex flex-col gap-[var(--space-5)]">
      <div className="micro">Multi-Voice Dialogue Configuration</div>

      {/* Speaker 1 */}
      <div className="flex flex-col gap-[var(--space-3)] rounded-sm bg-surface-2 p-[var(--space-4)]">
        <div className="text-ink" style={{ font: 'var(--t-small)', fontWeight: 600 }}>Speaker 1</div>

        <div>
          <label className="field-label">Speaker Name (for script generation)</label>
          <input
            type="text"
            value={speaker1Name}
            onChange={(e) => handleSpeaker1NameChange(e.target.value)}
            className="input"
            placeholder="SPEAKER_1"
            disabled={disabled}
          />
        </div>

        <div>
          <label className="field-label">Voice</label>
          <select
            value={speaker1VoiceId}
            onChange={(e) => handleSpeaker1VoiceChange(e.target.value)}
            disabled={disabled}
            className="select"
          >
            <option value="">Select a voice...</option>
            {voices.map((voice) => (
              <option key={voice.voice_id} value={voice.voice_id}>
                {voice.name} {voice.category ? `(${voice.category})` : ''}
              </option>
            ))}
          </select>
          {speaker1VoiceId && <div className="field-hint">Voice ID: {speaker1VoiceId}</div>}
        </div>
      </div>

      {/* Speaker 2 */}
      <div className="flex flex-col gap-[var(--space-3)] rounded-sm bg-surface-2 p-[var(--space-4)]">
        <div className="text-ink" style={{ font: 'var(--t-small)', fontWeight: 600 }}>Speaker 2</div>

        <div>
          <label className="field-label">Speaker Name (for script generation)</label>
          <input
            type="text"
            value={speaker2Name}
            onChange={(e) => handleSpeaker2NameChange(e.target.value)}
            className="input"
            placeholder="SPEAKER_2"
            disabled={disabled}
          />
        </div>

        <div>
          <label className="field-label">Voice</label>
          <select
            value={speaker2VoiceId}
            onChange={(e) => handleSpeaker2VoiceChange(e.target.value)}
            disabled={disabled}
            className="select"
          >
            <option value="">Select a voice...</option>
            {voices.map((voice) => (
              <option key={voice.voice_id} value={voice.voice_id}>
                {voice.name} {voice.category ? `(${voice.category})` : ''}
              </option>
            ))}
          </select>
          {speaker2VoiceId && <div className="field-hint">Voice ID: {speaker2VoiceId}</div>}
        </div>
      </div>

      {/* Summary */}
      {speaker1VoiceId && speaker2VoiceId && (
        <div
          className="rounded-sm p-[var(--space-3)]"
          style={{ background: 'var(--accent-soft)', color: 'var(--text)', font: 'var(--t-small)' }}
        >
          <div className="mb-[var(--space-1)]" style={{ fontWeight: 600 }}>Configuration Summary:</div>
          <div>{speaker1Name} → {getVoiceName(speaker1VoiceId)}</div>
          <div>{speaker2Name} → {getVoiceName(speaker2VoiceId)}</div>
        </div>
      )}
    </div>
  )
}
