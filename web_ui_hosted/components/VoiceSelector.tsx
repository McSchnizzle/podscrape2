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
    <div className="space-y-2">
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}

      {loading ? (
        <div className="text-sm text-gray-500">Loading voices...</div>
      ) : error ? (
        <div className="text-sm text-error-600">{error}</div>
      ) : (
        <div className="space-y-2">
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            className="input w-full"
          >
            <option value="">{placeholder}</option>
            {voices.map((voice) => (
              <option key={voice.voice_id} value={voice.voice_id}>
                {voice.name} {voice.category ? `(${voice.category})` : ''}
              </option>
            ))}
          </select>

          {selectedVoice && (
            <div className="text-xs text-gray-500 space-y-1">
              <div>
                <span className="font-medium">Voice ID:</span> {selectedVoice.voice_id}
              </div>
              {selectedVoice.description && (
                <div>
                  <span className="font-medium">Description:</span> {selectedVoice.description}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
