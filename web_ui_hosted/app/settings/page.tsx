'use client'

import { useState, useEffect } from 'react'

interface Settings {
  [category: string]: {
    [key: string]: any
  }
}

interface SettingMeta {
  type: string
  default: any
  min?: number | null
  max?: number | null
}

interface SettingsSchema {
  [category: string]: {
    [key: string]: SettingMeta
  }
}

interface Section {
  id: string
  label: string
  categories: string[]
}

const SECTIONS: Section[] = [
  { id: 'content', label: 'Content Filtering', categories: ['content_filtering'] },
  { id: 'pipeline', label: 'Pipeline', categories: ['pipeline'] },
  { id: 'audio', label: 'Audio Processing', categories: ['audio_processing'] },
  { id: 'ai-scoring', label: 'AI Content Scoring', categories: ['ai_content_scoring'] },
  { id: 'ai-digest', label: 'AI Digest Generation', categories: ['ai_digest_generation'] },
  { id: 'ai-metadata', label: 'AI Metadata', categories: ['ai_metadata_generation'] },
  { id: 'ai-tts', label: 'AI TTS', categories: ['ai_tts_generation'] },
  { id: 'ai-stt', label: 'AI STT', categories: ['ai_stt_transcription'] },
  { id: 'topic-tracking', label: 'Topic Tracking', categories: ['topic_tracking'] },
  { id: 'topic-evolution', label: 'Topic Evolution', categories: ['topic_evolution'] },
  { id: 'ad-filtering', label: 'Ad Filtering', categories: ['ad_filtering'] },
  { id: 'transcript', label: 'Transcript Processing', categories: ['transcript_processing'] },
  { id: 'retention', label: 'Retention', categories: ['retention'] },
]

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({})
  const [originalSettings, setOriginalSettings] = useState<Settings>({})
  const [schema, setSchema] = useState<SettingsSchema>({})
  const [schemaLoaded, setSchemaLoaded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [activeSection, setActiveSection] = useState<string>('content')

  useEffect(() => {
    // Fetch both schema and settings in parallel
    const fetchAll = async () => {
      try {
        const [schemaResponse, settingsResponse] = await Promise.all([
          fetch('/api/settings/schema'),
          fetch('/api/settings')
        ])

        // Process schema
        if (schemaResponse.ok) {
          const schemaData = await schemaResponse.json()
          if (schemaData.settings) {
            setSchema(schemaData.settings)
            setSchemaLoaded(true)
          }
        } else {
          console.error('Failed to fetch settings schema')
        }

        // Process settings
        if (settingsResponse.ok) {
          const settingsData = await settingsResponse.json()
          setSettings(settingsData.settings || {})
          setOriginalSettings(settingsData.settings || {})
        } else {
          const data = await settingsResponse.json()
          setMessage({ type: 'error', text: data.error || 'Failed to load settings' })
        }
      } catch (error) {
        setMessage({ type: 'error', text: 'Failed to connect to settings API' })
      } finally {
        setLoading(false)
      }
    }

    fetchAll()
  }, [])

  useEffect(() => {
    // Set up intersection observer to track which section is in view
    const observerOptions = {
      root: null,
      rootMargin: '-100px 0px -66%', // Trigger when section is near top
      threshold: 0
    }

    const observerCallback: IntersectionObserverCallback = (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActiveSection(entry.target.id)
        }
      })
    }

    const observer = new IntersectionObserver(observerCallback, observerOptions)

    // Observe all section elements
    SECTIONS.forEach((section) => {
      const element = document.getElementById(section.id)
      if (element) {
        observer.observe(element)
      }
    })

    return () => observer.disconnect()
  }, [schemaLoaded]) // Re-run when schema loads and sections render

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

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveSection(sectionId)
    }
  }

  const getChangedSettingsCount = (): number => {
    let count = 0
    for (const [category, categorySettings] of Object.entries(settings)) {
      for (const [key, value] of Object.entries(categorySettings)) {
        const originalValue = originalSettings[category]?.[key]
        if (JSON.stringify(value) !== JSON.stringify(originalValue)) {
          count++
        }
      }
    }
    return count
  }

  // Get setting value, falling back to schema default
  const getSetting = (category: string, key: string) => {
    const value = settings[category]?.[key]
    if (value !== undefined && value !== null) {
      return value
    }
    // Use schema default instead of hardcoded fallback
    const schemaDefault = schema[category]?.[key]?.default
    if (schemaDefault !== undefined) {
      return schemaDefault
    }
    // If schema not loaded yet, return a safe default based on type
    return 0
  }

  // Get min/max constraints from schema for input validation
  const getMinMax = (category: string, key: string) => {
    const meta = schema[category]?.[key]
    return {
      min: meta?.min ?? 0,
      max: meta?.max ?? 99999
    }
  }

  if (loading || !schemaLoaded) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-600">Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="flex gap-8">
      {/* Left Sidebar Navigation */}
      <nav className="hidden lg:block w-56 shrink-0">
        <div className="sticky top-20 space-y-1">
          <h2 className="text-sm font-semibold text-gray-900 mb-3">Settings</h2>
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              onClick={() => scrollToSection(section.id)}
              className={`w-full text-left px-3 py-2 text-sm rounded-md transition-colors ${
                activeSection === section.id
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              {section.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 space-y-6 pb-20">
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

      <div className="space-y-6">
        {/* Content Filtering */}
        <div id="content" className="scroll-mt-24">
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
                  value={getSetting('content_filtering', 'score_threshold')}
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
                  value={getSetting('content_filtering', 'max_episodes_per_digest')}
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
                  value={getSetting('content_filtering', 'min_episodes_per_digest')}
                  onChange={(e) => updateLocalSetting('content_filtering', 'min_episodes_per_digest', parseInt(e.target.value))}
                  disabled={saving}
                />
                <p className="text-xs text-gray-500 mt-1">
                  Minimum episodes required to generate a digest (0 = always generate)
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Pipeline Settings */}
        <div id="pipeline" className="scroll-mt-24">
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
                  value={getSetting('pipeline', 'max_episodes_per_run')}
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
                  value={getSetting('pipeline', 'discovery_lookback_days')}
                  onChange={(e) => {
                    const newValue = parseInt(e.target.value)
                    updateLocalSetting('pipeline', 'discovery_lookback_days', newValue)
                    // Auto-adjust episode retention if needed
                    const currentRetention = getSetting('retention', 'episode_retention_days')
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

        {/* Audio Processing */}
        <div id="audio" className="scroll-mt-24">
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
                  value={getSetting('audio_processing', 'chunk_duration_minutes')}
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
                  value={getSetting('audio_processing', 'max_chunks_per_episode')}
                  onChange={(e) => updateLocalSetting('audio_processing', 'max_chunks_per_episode', parseInt(e.target.value))}
                  disabled={saving}
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="transcribe-all-chunks"
                  className="h-4 w-4 text-primary-600 rounded border-gray-300"
                  checked={getSetting('audio_processing', 'transcribe_all_chunks')}
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

        {/* AI Content Scoring */}
        <div id="ai-scoring" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">AI Content Scoring</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_content_scoring', 'model')}
                    onChange={(e) => updateLocalSetting('ai_content_scoring', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="gpt-5.2">GPT-5.2 Thinking</option>
                    <option value="gpt-5.2-chat-latest">GPT-5.2 Instant</option>
                    <option value="gpt-5.2-pro">GPT-5.2 Pro</option>
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
                    value={getSetting('ai_content_scoring', 'max_tokens')}
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
                    value={getSetting('ai_content_scoring', 'max_input_tokens')}
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
                    value={getSetting('ai_content_scoring', 'max_episodes_per_batch')}
                    onChange={(e) => updateLocalSetting('ai_content_scoring', 'max_episodes_per_batch', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Prompt Max Characters
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="200000"
                    className="input"
                    value={getSetting('ai_content_scoring', 'prompt_max_chars')}
                    onChange={(e) => updateLocalSetting('ai_content_scoring', 'prompt_max_chars', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum characters to include from topic prompt in scoring context
                  </p>
                </div>
              </div>
            </div>
          </div>

        {/* AI Digest Generation */}
        <div id="ai-digest" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">AI Digest Generation</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_digest_generation', 'model')}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="gpt-5.2">GPT-5.2 Thinking</option>
                    <option value="gpt-5.2-chat-latest">GPT-5.2 Instant</option>
                    <option value="gpt-5.2-pro">GPT-5.2 Pro</option>
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
                    value={getSetting('ai_digest_generation', 'max_output_tokens')}
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
                    value={getSetting('ai_digest_generation', 'max_input_tokens')}
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
                    value={getSetting('ai_digest_generation', 'transcript_buffer_percent')}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'transcript_buffer_percent', parseFloat(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Buffer percentage for transcript token calculations
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Transcript Min Characters
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="500000"
                    className="input"
                    value={getSetting('ai_digest_generation', 'transcript_min_chars')}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'transcript_min_chars', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum transcript characters required per episode
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Transcript Max Characters
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="1000000"
                    className="input"
                    value={getSetting('ai_digest_generation', 'transcript_max_chars')}
                    onChange={(e) => updateLocalSetting('ai_digest_generation', 'transcript_max_chars', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum transcript characters to include per episode in digest
                  </p>
                </div>
              </div>
            </div>
          </div>

        {/* AI Metadata Generation */}
        <div id="ai-metadata" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">AI Metadata Generation</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_metadata_generation', 'model')}
                    onChange={(e) => updateLocalSetting('ai_metadata_generation', 'model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="gpt-5.2">GPT-5.2 Thinking</option>
                    <option value="gpt-5.2-chat-latest">GPT-5.2 Instant</option>
                    <option value="gpt-5.2-pro">GPT-5.2 Pro</option>
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
                    Max Input Tokens
                  </label>
                  <input
                    type="number"
                    min="1000"
                    max="128000"
                    className="input"
                    value={getSetting('ai_metadata_generation', 'max_input_tokens')}
                    onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_input_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum input tokens for metadata generation context
                  </p>
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
                    value={getSetting('ai_metadata_generation', 'max_title_tokens')}
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
                    value={getSetting('ai_metadata_generation', 'max_summary_tokens')}
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
                    value={getSetting('ai_metadata_generation', 'max_description_tokens')}
                    onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_description_tokens', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
              </div>
            </div>
          </div>

        {/* AI TTS Generation */}
        <div id="ai-tts" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">AI TTS Generation</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_tts_generation', 'model')}
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
                    value={getSetting('ai_tts_generation', 'max_characters')}
                    onChange={(e) => updateLocalSetting('ai_tts_generation', 'max_characters', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum characters per TTS generation
                  </p>
                </div>
              </div>
            </div>
          </div>

        {/* AI STT Transcription */}
        <div id="ai-stt" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">AI STT Transcription</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('ai_stt_transcription', 'model')}
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
                    value={getSetting('ai_stt_transcription', 'max_file_size_mb')}
                    onChange={(e) => updateLocalSetting('ai_stt_transcription', 'max_file_size_mb', parseInt(e.target.value))}
                    disabled={saving}
                  />
                </div>
              </div>
            </div>
          </div>

        {/* Topic Tracking */}
        <div id="topic-tracking" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Topic Tracking</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Extraction Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('topic_tracking', 'extraction_model')}
                    onChange={(e) => updateLocalSetting('topic_tracking', 'extraction_model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="gpt-5.2">GPT-5.2 Thinking</option>
                    <option value="gpt-5.2-chat-latest">GPT-5.2 Instant</option>
                    <option value="gpt-5.2-pro">GPT-5.2 Pro</option>
                    <option value="gpt-5.1">GPT-5.1</option>
                    <option value="gpt-5">GPT-5</option>
                    <option value="gpt-5-mini">GPT-5 Mini</option>
                    <option value="gpt-5-nano">GPT-5 Nano</option>
                    <option value="gpt-4o-mini">GPT-4o Mini</option>
                    <option value="gpt-4o">GPT-4o</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Model used for extracting topics from transcripts
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Min Score for Extraction
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    className="input"
                    value={getSetting('topic_tracking', 'min_score_for_extraction')}
                    onChange={(e) => updateLocalSetting('topic_tracking', 'min_score_for_extraction', parseFloat(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum episode score required to extract topics (0.0 - 1.0)
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Topics per Episode
                  </label>
                  <input
                    type="number"
                    min="3"
                    max="20"
                    className="input"
                    value={getSetting('topic_tracking', 'max_topics_per_episode')}
                    onChange={(e) => updateLocalSetting('topic_tracking', 'max_topics_per_episode', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum number of topics to extract per episode
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Retention Days (Deduplication Window)
                  </label>
                  <input
                    type="number"
                    min="7"
                    max="90"
                    className="input"
                    value={getSetting('topic_tracking', 'retention_days')}
                    onChange={(e) => updateLocalSetting('topic_tracking', 'retention_days', parseInt(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Number of days to look back for duplicate topic detection
                  </p>
                </div>
              </div>
            </div>
          </div>

        {/* Ad Filtering */}
        <div id="ad-filtering" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Ad Filtering</h3>
              <div className="space-y-4">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="ad-filtering-enabled"
                    className="h-4 w-4 text-primary-600 rounded border-gray-300"
                    checked={getSetting('ad_filtering', 'enabled')}
                    onChange={(e) => updateLocalSetting('ad_filtering', 'enabled', e.target.checked)}
                    disabled={saving}
                  />
                  <label htmlFor="ad-filtering-enabled" className="ml-2 text-sm text-gray-700">
                    Enable ad filtering
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Confidence Threshold
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    className="input"
                    value={getSetting('ad_filtering', 'confidence_threshold')}
                    onChange={(e) => updateLocalSetting('ad_filtering', 'confidence_threshold', parseFloat(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum confidence required to filter an ad (0.0 - 1.0, higher = stricter)
                  </p>
                </div>
                <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-sm text-blue-700">
                    <strong>Note:</strong> Ad patterns are managed in the database. Enable topic tracking per topic to use deduplication.
                  </p>
                </div>
              </div>
            </div>
          </div>

        {/* Topic Evolution */}
        <div id="topic-evolution" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Topic Evolution</h3>
              <div className="space-y-4">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="enable-novelty-detection"
                    className="h-4 w-4 text-primary-600 rounded border-gray-300"
                    checked={getSetting('topic_evolution', 'enable_novelty_detection')}
                    onChange={(e) => updateLocalSetting('topic_evolution', 'enable_novelty_detection', e.target.checked)}
                    disabled={saving}
                  />
                  <label htmlFor="enable-novelty-detection" className="ml-2 text-sm text-gray-700">
                    Enable novelty detection
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Novelty Threshold
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    className="input"
                    value={getSetting('topic_evolution', 'novelty_threshold')}
                    onChange={(e) => updateLocalSetting('topic_evolution', 'novelty_threshold', parseFloat(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum novelty required to include topic (0.0-1.0, lower = more lenient)
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Embedding Model
                  </label>
                  <select
                    className="input"
                    value={getSetting('topic_evolution', 'embedding_model')}
                    onChange={(e) => updateLocalSetting('topic_evolution', 'embedding_model', e.target.value)}
                    disabled={saving}
                  >
                    <option value="text-embedding-3-small">text-embedding-3-small (Fast, $0.02/1M)</option>
                    <option value="text-embedding-3-large">text-embedding-3-large (Higher quality, $0.13/1M)</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    OpenAI embedding model for semantic similarity comparisons
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Similarity Threshold
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    min="0.5"
                    max="1"
                    className="input"
                    value={getSetting('topic_evolution', 'similarity_threshold')}
                    onChange={(e) => updateLocalSetting('topic_evolution', 'similarity_threshold', parseFloat(e.target.value))}
                    disabled={saving}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum similarity score to consider topics as duplicates (0.5-1.0, higher = stricter matching)
                  </p>
                </div>
                <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-sm text-blue-700">
                    <strong>Info:</strong> Novelty detection uses embeddings to compare topics and allow fresh content even if topic slugs match.
                    Lower threshold = more likely to include topics with similar content.
                  </p>
                </div>
              </div>
            </div>
          </div>

        {/* Transcript Processing */}
        <div id="transcript" className="scroll-mt-24">
          <div className="card">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Transcript Processing</h3>
            <div className="space-y-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="ad-trim-enabled"
                  className="h-4 w-4 text-primary-600 rounded border-gray-300"
                  checked={getSetting('transcript_processing', 'ad_trim_enabled')}
                  onChange={(e) => updateLocalSetting('transcript_processing', 'ad_trim_enabled', e.target.checked)}
                  disabled={saving}
                />
                <label htmlFor="ad-trim-enabled" className="ml-2 text-sm text-gray-700">
                  Enable ad trimming
                </label>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Trim Start (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="50"
                  className="input"
                  value={getSetting('transcript_processing', 'ad_trim_start_percent')}
                  onChange={(e) => updateLocalSetting('transcript_processing', 'ad_trim_start_percent', parseFloat(e.target.value))}
                  disabled={saving}
                />
                <p className="text-xs text-gray-500 mt-1">
                  Percentage of transcript to trim from start (for ads)
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Trim End (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="50"
                  className="input"
                  value={getSetting('transcript_processing', 'ad_trim_end_percent')}
                  onChange={(e) => updateLocalSetting('transcript_processing', 'ad_trim_end_percent', parseFloat(e.target.value))}
                  disabled={saving}
                />
                <p className="text-xs text-gray-500 mt-1">
                  Percentage of transcript to trim from end (for ads)
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Retention Settings */}
        <div id="retention" className="scroll-mt-24">
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
                        value={getSetting('retention', 'episode_retention_days')}
                        onChange={(e) => {
                          const newValue = parseInt(e.target.value)
                          const lookbackDays = getSetting('pipeline', 'discovery_lookback_days')
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
                        value={getSetting('retention', 'digest_retention_days')}
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
                        value={getSetting('retention', 'local_mp3_days')}
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
                        value={getSetting('retention', 'audio_cache_days')}
                        onChange={(e) => updateLocalSetting('retention', 'audio_cache_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete cached audio files older than this many days
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Audio Chunks (days)
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="30"
                        className="input"
                        value={getSetting('retention', 'audio_chunks_days')}
                        onChange={(e) => updateLocalSetting('retention', 'audio_chunks_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete chunked audio files older than this many days
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
                        value={getSetting('retention', 'logs_days')}
                        onChange={(e) => updateLocalSetting('retention', 'logs_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete log files older than this many days
                      </p>
                    </div>
                  </div>
                </div>

                {/* Publishing Retention */}
                <div>
                  <h4 className="text-md font-medium text-gray-800 mb-3">Publishing Cleanup</h4>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        GitHub Releases (days)
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="365"
                        className="input"
                        value={getSetting('retention', 'github_releases_days')}
                        onChange={(e) => updateLocalSetting('retention', 'github_releases_days', parseInt(e.target.value))}
                        disabled={saving}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Delete GitHub releases older than this many days (0 = keep forever)
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
      {/* End sections container and main content area */}

      {/* Sticky Save Bar */}
      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-40">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary-100 text-primary-700 text-sm font-medium">
                  {getChangedSettingsCount()}
                </span>
                <span className="text-sm text-gray-600">
                  unsaved {getChangedSettingsCount() === 1 ? 'change' : 'changes'}
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={resetSettings}
                  className="btn-secondary text-sm px-4 py-2"
                  disabled={saving}
                >
                  Reset
                </button>
                <button
                  onClick={saveAllSettings}
                  className="btn-primary text-sm px-4 py-2"
                  disabled={saving}
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Saving overlay indicator */}
      {saving && (
        <div className="fixed bottom-4 right-4 bg-primary-600 text-white px-4 py-2 rounded-md shadow-lg z-50">
          Saving...
        </div>
      )}
    </div>
  )
}
