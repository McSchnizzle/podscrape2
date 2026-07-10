'use client'

import { useState, useEffect } from 'react'

export interface Voice {
  voice_id: string
  name: string
  labels?: Record<string, string>
  category?: string
  description?: string
}

interface VoiceSelectorProps {
  value: string
  onChange: (voiceId: string) => void
  disabled?: boolean
  label?: string
  placeholder?: string
}

export default function VoiceSelector({
  value,
  onChange,
  disabled = false,
  label = 'Voice',
  placeholder = 'Select a voice...'
}: VoiceSelectorProps) {
  const [voices, setVoices] = useState<Voice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchVoices()
  }, [])

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

  const selectedVoice = voices.find(v => v.voice_id === value)

  return (
    <div className="flex flex-col gap-[var(--space-2)]">
      {label && <label className="field-label">{label}</label>}

      {loading ? (
        <div className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>Loading voices...</div>
      ) : error ? (
        <div style={{ font: 'var(--t-small)', color: 'var(--danger)' }}>{error}</div>
      ) : (
        <div className="flex flex-col gap-[var(--space-2)]">
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            className="select"
          >
            <option value="">{placeholder}</option>
            {voices.map((voice) => (
              <option key={voice.voice_id} value={voice.voice_id}>
                {voice.name} {voice.category ? `(${voice.category})` : ''}
              </option>
            ))}
          </select>

          {selectedVoice && (
            <div className="flex flex-col gap-[var(--space-1)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
              <div>
                <span style={{ fontWeight: 600 }}>Voice ID:</span> {selectedVoice.voice_id}
              </div>
              {selectedVoice.description && (
                <div>
                  <span style={{ fontWeight: 600 }}>Description:</span> {selectedVoice.description}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
