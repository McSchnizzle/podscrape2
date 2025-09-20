'use client'

import { useState, useEffect } from 'react'

interface Settings {
  [category: string]: {
    [key: string]: any
  }
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const response = await fetch('/api/settings')
      const data = await response.json()

      if (response.ok) {
        setSettings(data.settings || {})
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to load settings' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to connect to settings API' })
    } finally {
      setLoading(false)
    }
  }

  const updateSetting = async (category: string, key: string, value: any) => {
    setSaving(true)
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category, key, value })
      })

      const data = await response.json()

      if (response.ok) {
        // Update local state
        setSettings(prev => ({
          ...prev,
          [category]: {
            ...prev[category],
            [key]: value
          }
        }))
        setMessage({ type: 'success', text: 'Setting saved successfully' })
        setTimeout(() => setMessage(null), 3000)
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to save setting' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save setting' })
    } finally {
      setSaving(false)
    }
  }

  const getSetting = (category: string, key: string, defaultValue: any = '') => {
    return settings[category]?.[key] ?? defaultValue
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-600">Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-gray-600">Configure system parameters and processing options</p>
      </div>

      {message && (
        <div className={`p-4 rounded-md ${
          message.type === 'success'
            ? 'bg-success-50 text-success-700 border border-success-200'
            : 'bg-error-50 text-error-700 border border-error-200'
        }`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Content Filtering */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Content Filtering</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Score Threshold
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                className="input"
                value={getSetting('content_filtering', 'score_threshold', 0.65)}
                onChange={(e) => updateSetting('content_filtering', 'score_threshold', parseFloat(e.target.value))}
                disabled={saving}
              />
              <p className="text-xs text-gray-500 mt-1">
                Minimum relevance score for episodes (0.0 - 1.0)
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Episodes per Digest
              </label>
              <input
                type="number"
                min="1"
                max="20"
                className="input"
                value={getSetting('content_filtering', 'max_episodes_per_digest', 5)}
                onChange={(e) => updateSetting('content_filtering', 'max_episodes_per_digest', parseInt(e.target.value))}
                disabled={saving}
              />
            </div>
          </div>
        </div>

        {/* Audio Processing */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Audio Processing</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Chunk Duration (minutes)
              </label>
              <input
                type="number"
                min="1"
                max="30"
                className="input"
                value={getSetting('audio_processing', 'chunk_duration_minutes', 10)}
                onChange={(e) => updateSetting('audio_processing', 'chunk_duration_minutes', parseInt(e.target.value))}
                disabled={saving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Chunks per Episode
              </label>
              <input
                type="number"
                min="1"
                max="10"
                className="input"
                value={getSetting('audio_processing', 'max_chunks_per_episode', 3)}
                onChange={(e) => updateSetting('audio_processing', 'max_chunks_per_episode', parseInt(e.target.value))}
                disabled={saving}
              />
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                id="transcribe-all-chunks"
                className="h-4 w-4 text-primary-600 rounded border-gray-300"
                checked={getSetting('audio_processing', 'transcribe_all_chunks', false)}
                onChange={(e) => updateSetting('audio_processing', 'transcribe_all_chunks', e.target.checked)}
                disabled={saving}
              />
              <label htmlFor="transcribe-all-chunks" className="ml-2 text-sm text-gray-700">
                Transcribe all chunks
              </label>
            </div>
          </div>
        </div>

        {/* Pipeline Settings */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Pipeline</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Episodes per Run
              </label>
              <input
                type="number"
                min="1"
                max="20"
                className="input"
                value={getSetting('pipeline', 'max_episodes_per_run', 3)}
                onChange={(e) => updateSetting('pipeline', 'max_episodes_per_run', parseInt(e.target.value))}
                disabled={saving}
              />
            </div>
          </div>
        </div>

        {/* Retention Settings */}
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Retention</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Local MP3s (days)
              </label>
              <input
                type="number"
                min="1"
                max="90"
                className="input"
                value={getSetting('retention', 'local_mp3_days', 7)}
                onChange={(e) => updateSetting('retention', 'local_mp3_days', parseInt(e.target.value))}
                disabled={saving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Audio Cache (days)
              </label>
              <input
                type="number"
                min="1"
                max="30"
                className="input"
                value={getSetting('retention', 'audio_cache_days', 3)}
                onChange={(e) => updateSetting('retention', 'audio_cache_days', parseInt(e.target.value))}
                disabled={saving}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Logs (days)
              </label>
              <input
                type="number"
                min="1"
                max="365"
                className="input"
                value={getSetting('retention', 'logs_days', 30)}
                onChange={(e) => updateSetting('retention', 'logs_days', parseInt(e.target.value))}
                disabled={saving}
              />
            </div>
          </div>
        </div>
      </div>

      {saving && (
        <div className="fixed bottom-4 right-4 bg-primary-600 text-white px-4 py-2 rounded-md shadow-lg">
          Saving...
        </div>
      )}
    </div>
  )
}