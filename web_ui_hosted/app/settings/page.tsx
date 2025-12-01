'use client'

import { useState, useEffect } from 'react'

interface Settings {
  [category: string]: {
    [key: string]: any
  }
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({})
  const [originalSettings, setOriginalSettings] = useState<Settings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
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
        setOriginalSettings(data.settings || {})
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to load settings' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to connect to settings API' })
    } finally {
      setLoading(false)
    }
  }

  const updateLocalSetting = (category: string, key: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [category]: {
        ...prev[category],
        [key]: value
      }
    }))
    setHasChanges(true)
  }

  const saveAllSettings = async () => {
    setSaving(true)
    setMessage(null)

    try {
      const savePromises = []

      // Compare settings with original and save only changed ones
      for (const [category, categorySettings] of Object.entries(settings)) {
        for (const [key, value] of Object.entries(categorySettings)) {
          const originalValue = originalSettings[category]?.[key]
          if (JSON.stringify(value) !== JSON.stringify(originalValue)) {
            savePromises.push(
              fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, key, value })
              })
            )
          }
        }
      }

      if (savePromises.length === 0) {
        setMessage({ type: 'error', text: 'No changes to save' })
        setSaving(false)
        return
      }

      const responses = await Promise.all(savePromises)
      const failed = responses.filter(r => !r.ok)

      if (failed.length === 0) {
        setOriginalSettings(settings)
        setHasChanges(false)
        setMessage({ type: 'success', text: `Saved ${savePromises.length} setting${savePromises.length > 1 ? 's' : ''} successfully` })
        setTimeout(() => setMessage(null), 3000)
      } else {
        setMessage({ type: 'error', text: `Failed to save ${failed.length} setting${failed.length > 1 ? 's' : ''}` })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save settings' })
    } finally {
      setSaving(false)
    }
  }

  const resetSettings = () => {
    setSettings(originalSettings)
    setHasChanges(false)
    setMessage(null)
  }

  const getSetting = (category: string, key: string, defaultValue: any = null) => {
    const value = settings[category]?.[key]
    if (value === undefined || value === null) {
      if (defaultValue === null) {
        throw new Error(`Database setting ${category}.${key} not found and no fallback allowed`)
      }
      return defaultValue
    }
    return value
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
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="mt-1 text-gray-600">Configure system parameters and processing options</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <button
            onClick={resetSettings}
            className="btn-secondary"
            disabled={saving || !hasChanges}
          >
            Reset Changes
          </button>
          <button
            onClick={saveAllSettings}
            className={`btn-primary ${hasChanges ? 'bg-primary-600 hover:bg-primary-700' : 'bg-gray-400 cursor-not-allowed'}`}
            disabled={saving || !hasChanges}
          >
            {saving ? 'Saving...' : hasChanges ? 'Save Settings' : 'No Changes'}
          </button>
        </div>
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

      <div className="space-y-8">
        {/* Core Settings */}
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
                  onChange={(e) => updateLocalSetting('content_filtering', 'score_threshold', parseFloat(e.target.value))}
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
                  onChange={(e) => updateLocalSetting('content_filtering', 'max_episodes_per_digest', parseInt(e.target.value))}
                  disabled={saving}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Min Episodes per Digest
                </label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  className="input"
                  value={getSetting('content_filtering', 'min_episodes_per_digest', 1)}
                  onChange={(e) => updateLocalSetting('content_filtering', 'min_episodes_per_digest', parseInt(e.target.value))}
                  disabled={saving}
                />
                <p className="text-xs text-gray-500 mt-1">
                  Minimum episodes required to generate a digest (0 = always generate)
                </p>
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
                  onChange={(e) => updateLocalSetting('pipeline', 'max_episodes_per_run', parseInt(e.target.value))}
                  disabled={saving}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Days Back for Discovery
                </label>
                <input
                  type="number"
                  min="1"
                  max="30"
                  className="input"
                  value={getSetting('pipeline', 'discovery_lookback_days', 7)}
                  onChange={(e) => {
                    const newValue = parseInt(e.target.value)
                    updateLocalSetting('pipeline', 'discovery_lookback_days', newValue)
                    // Auto-adjust episode retention if needed
                    const currentRetention = getSetting('retention', 'episode_retention_days', 14)
                    if (newValue >= currentRetention) {
                      updateLocalSetting('retention', 'episode_retention_days', newValue + 1)
                    }
                  }}
                  disabled={saving}
                />
                <p className="text-xs text-gray-500 mt-1">
                  Number of days to look back when discovering new episodes
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Audio & Transcript Processing */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                  onChange={(e) => updateLocalSetting('audio_processing', 'chunk_duration_minutes', parseInt(e.target.value))}
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
                  onChange={(e) => updateLocalSetting('audio_processing', 'max_chunks_per_episode', parseInt(e.target.value))}
                  disabled={saving}
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="transcribe-all-chunks"
                  className="h-4 w-4 text-primary-600 rounded border-gray-300"
                  checked={getSetting('audio_processing', 'transcribe_all_chunks', false)}
                  onChange={(e) => updateLocalSetting('audio_processing', 'transcribe_all_chunks', e.target.checked)}
                  disabled={saving}
                />
                <label htmlFor="transcribe-all-chunks" className="ml-2 text-sm text-gray-700">
                  Transcribe all chunks
                </label>
              </div>
            </div>
          </div>

        </div>

        {/* AI Configuration */}
        <div>
          <h2 className="text-xl font-semibold text-gray-900 mb-6">AI Configuration</h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* AI Content Scoring */}
            <div className="card">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Content Scoring</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_content_scoring', 'model', null)}
                    onChange={(e) => updateLocalSetting('ai_content_scoring', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="gpt-5.1">GPT-5.1</option>
                    <option value="gpt-5">GPT-5</option>
                    <option value="gpt-5-mini">GPT-5 Mini</option>
                    <option value="gpt-5-nano">GPT-5 Nano</option>
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                    <option value="gpt-4o">GPT-4o</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Output Tokens
                  </label>
                  <input
                    type="number"
                    min="100"
                    max="4000"
                    className="input"
                    value={getSetting('ai_content_scoring', 'max_tokens', 1000)}
                    onChange={(e) => updateLocalSetting('ai_content_scoring', 'max_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Input Tokens
                  </label>
                  <input
                    type="number"
                    min="1000"
                    max="200000"
                    className="input"
                    value={getSetting('ai_content_scoring', 'max_input_tokens', 120000)}
                    onChange={(e) => updateLocalSetting('ai_content_scoring', 'max_input_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Episodes per Batch
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="20"
                    className="input"
                    value={getSetting('ai_content_scoring', 'max_episodes_per_batch', 10)}
                    onChange={(e) => updateLocalSetting('ai_content_scoring', 'max_episodes_per_batch', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
              </div>
            </div>

            {/* AI Digest Generation */}
            <div className="card">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Digest Generation</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_digest_generation', 'model', null)}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="gpt-5.1">GPT-5.1</option>
                    <option value="gpt-5">GPT-5</option>
                    <option value="gpt-5-mini">GPT-5 Mini</option>
                    <option value="gpt-5-nano">GPT-5 Nano</option>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Output Tokens
                  </label>
                  <input
                    type="number"
                    min="1000"
                    max="50000"
                    className="input"
                    value={getSetting('ai_digest_generation', 'max_output_tokens', 25000)}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'max_output_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Input Tokens
                  </label>
                  <input
                    type="number"
                    min="1000"
                    max="200000"
                    className="input"
                    value={getSetting('ai_digest_generation', 'max_input_tokens', 150000)}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'max_input_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Transcript Buffer (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="50"
                    className="input"
                    value={getSetting('ai_digest_generation', 'transcript_buffer_percent', 20.0)}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'transcript_buffer_percent', parseFloat(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Buffer percentage for transcript token calculations
                  </p>
                </div>
              </div>
            </div>

            {/* AI Metadata Generation */}
            <div className="card">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Metadata Generation</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_metadata_generation', 'model', null)}
                    onChange={(e) => updateLocalSetting('ai_metadata_generation', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="gpt-5.1">GPT-5.1</option>
                    <option value="gpt-5">GPT-5</option>
                    <option value="gpt-5-mini">GPT-5 Mini</option>
                    <option value="gpt-5-nano">GPT-5 Nano</option>
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                    <option value="gpt-4o">GPT-4o</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Title Tokens
                  </label>
                  <input
                    type="number"
                    min="10"
                    max="100"
                    className="input"
                    value={getSetting('ai_metadata_generation', 'max_title_tokens', 50)}
                    onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_title_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Summary Tokens
                  </label>
                  <input
                    type="number"
                    min="50"
                    max="500"
                    className="input"
                    value={getSetting('ai_metadata_generation', 'max_summary_tokens', 200)}
                    onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_summary_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Description Tokens
                  </label>
                  <input
                    type="number"
                    min="100"
                    max="1000"
                    className="input"
                    value={getSetting('ai_metadata_generation', 'max_description_tokens', 500)}
                    onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_description_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
              </div>
            </div>

            {/* AI TTS Generation */}
            <div className="card">
              <h3 className="text-lg font-medium text-gray-900 mb-4">TTS Generation</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_tts_generation', 'model', 'eleven_turbo_v2_5')}
                    onChange={(e) => updateLocalSetting('ai_tts_generation', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="eleven_v3">ElevenLabs v3 (Highest Quality)</option>
                    <option value="eleven_turbo_v2_5">ElevenLabs Turbo v2.5</option>
                    <option value="eleven_flash_v2_5">ElevenLabs Flash v2.5 (Low Latency)</option>
                    <option value="eleven_multilingual_v2">ElevenLabs Multilingual v2</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Characters
                  </label>
                  <input
                    type="number"
                    min="1000"
                    max="50000"
                    className="input"
                    value={getSetting('ai_tts_generation', 'max_characters', 35000)}
                    onChange={(e) => updateLocalSetting('ai_tts_generation', 'max_characters', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum characters per TTS generation
                  </p>
                </div>
              </div>
            </div>

            {/* AI STT Transcription */}
            <div className="card">
              <h3 className="text-lg font-medium text-gray-900 mb-4">STT Transcription</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_stt_transcription', 'model', 'whisper-1')}
                    onChange={(e) => updateLocalSetting('ai_stt_transcription', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="whisper-1">Whisper-1</option>
                    <option value="local-whisper">Local Whisper</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max File Size (MB)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    className="input"
                    value={getSetting('ai_stt_transcription', 'max_file_size_mb', 20)}
                    onChange={(e) => updateLocalSetting('ai_stt_transcription', 'max_file_size_mb', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
              </div>
            </div>

            {/* Retention Settings */}
            <div className="card">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Retention</h3>
              <div className="space-y-6">
                {/* Database Retention */}
                <div>
                  <h4 className="text-md font-medium text-gray-800 mb-3">Database Cleanup</h4>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Episode Retention (days)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="90"
                        className="input"
                        value={getSetting('retention', 'episode_retention_days', 14)}
                        onChange={(e) => {
                          const newValue = parseInt(e.target.value)
                          const lookbackDays = getSetting('pipeline', 'discovery_lookback_days', 7)
                          if (newValue <= lookbackDays) {
                            alert(`Episode retention days must be greater than discovery lookback days (${lookbackDays})`)
                            return
                          }
                          updateLocalSetting('retention', 'episode_retention_days', newValue)
                        }}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete episodes from database older than this many days (must be greater than discovery lookback)
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Digest Retention (days)
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="90"
                        className="input"
                        value={getSetting('retention', 'digest_retention_days', 14)}
                        onChange={(e) => updateLocalSetting('retention', 'digest_retention_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete digests from database older than this many days
                      </p>
                    </div>
                  </div>
                </div>

                {/* File/Cache Retention */}
                <div>
                  <h4 className="text-md font-medium text-gray-800 mb-3">File & Cache Cleanup</h4>
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
                        onChange={(e) => updateLocalSetting('retention', 'local_mp3_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete local MP3 files older than this many days
                      </p>
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
                        onChange={(e) => updateLocalSetting('retention', 'audio_cache_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete cached audio files older than this many days
                      </p>
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
                        onChange={(e) => updateLocalSetting('retention', 'logs_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete log files older than this many days
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Save Buttons */}
      <div className="flex flex-col sm:flex-row sm:justify-end gap-2 pt-6 border-t border-gray-200">
        <button
          onClick={resetSettings}
          className="btn-secondary"
          disabled={saving || !hasChanges}
        >
          Reset Changes
        </button>
        <button
          onClick={saveAllSettings}
          className={`btn-primary ${hasChanges ? 'bg-primary-600 hover:bg-primary-700' : 'bg-gray-400 cursor-not-allowed'}`}
          disabled={saving || !hasChanges}
        >
          {saving ? 'Saving...' : hasChanges ? 'Save Settings' : 'No Changes'}
        </button>
      </div>

      {saving && (
        <div className="fixed bottom-4 right-4 bg-primary-600 text-white px-4 py-2 rounded-md shadow-lg">
          Saving...
        </div>
      )}
    </div>
  )
}
