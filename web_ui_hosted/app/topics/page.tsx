'use client'

import { useState, useEffect } from 'react'
import VoiceSelector from '@/components/VoiceSelector'
import MultiVoiceConfig, { VoiceConfig } from '@/components/MultiVoiceConfig'

interface TopicRow {
  id?: number
  name: string
  slug: string
  voice_id: string
  description: string
  active: boolean
  sort_order: number
  last_generated_at?: string | null
  // Multi-voice dialogue support (v1.82)
  use_dialogue_api?: boolean
  dialogue_model?: string
  voice_config?: VoiceConfig | null
}

const slugify = (value: string) =>
  value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'topic'

const scriptLabLink = (name: string) => `/script-lab?topic=${encodeURIComponent(name)}`

export default function TopicsPage() {
  const [topics, setTopics] = useState<TopicRow[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  useEffect(() => {
    fetchTopics()
  }, [])

  const fetchTopics = async () => {
    try {
      const response = await fetch('/api/topics')
      const data = await response.json()

      if (response.ok) {
        const mapped: TopicRow[] = (data.topics || []).map((topic: any, index: number) => ({
          id: topic.id,
          name: topic.name,
          slug: topic.slug || slugify(topic.name),
          voice_id: topic.voice_id || '',
          description: topic.description || '',
          active: Boolean(topic.active ?? topic.is_active ?? true),
          sort_order: typeof topic.sort_order === 'number' ? topic.sort_order : index * 10,
          last_generated_at: topic.last_generated_at || null,
          // Multi-voice dialogue support (v1.82)
          use_dialogue_api: Boolean(topic.use_dialogue_api || false),
          dialogue_model: topic.dialogue_model || 'eleven_turbo_v2_5',
          voice_config: topic.voice_config || null,
        }))
        setTopics(mapped)
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to load topics' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to connect to topics API' })
    } finally {
      setLoading(false)
    }
  }

  const addTopic = () => {
    const sortOrder = (topics.length + 1) * 10
    setTopics([...topics, {
      name: '',
      slug: `topic-${sortOrder}`,
      voice_id: '',
      description: '',
      active: true,
      sort_order: sortOrder,
      last_generated_at: null,
      // Multi-voice dialogue support (v1.82)
      use_dialogue_api: false,
      dialogue_model: 'eleven_turbo_v2_5',
      voice_config: null,
    }])
  }

  const updateTopic = (index: number, field: keyof TopicRow, value: any) => {
    const next = [...topics]
    const current = next[index]
    if (!current) return

    if (field === 'name') {
      const newName = String(value)
      next[index] = { ...current, name: newName }
      if (!current.id) {
        next[index].slug = slugify(newName)
      }
    } else if (field === 'slug') {
      next[index] = { ...current, slug: slugify(String(value)) }
    } else if (field === 'sort_order') {
      const numeric = Number(value)
      next[index] = { ...current, sort_order: Number.isFinite(numeric) ? numeric : current.sort_order }
    } else {
      next[index] = { ...current, [field]: value }
    }
    setTopics(next)
  }

  const removeTopic = (index: number) => {
    setTopics(topics.filter((_, i) => i !== index))
  }

  const saveTopics = async () => {
    const errors: string[] = []
    topics.forEach((topic, index) => {
      if (!topic.name.trim()) {
        errors.push(`Topic ${index + 1} must have a name`)
      }
      if (!topic.slug.trim()) {
        errors.push(`Topic ${index + 1} requires a slug`)
      }
    })

    if (errors.length > 0) {
      setMessage({ type: 'error', text: errors.join('; ') })
      return
    }

    setSaving(true)
    try {
      const response = await fetch('/api/topics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topics: topics.map(topic => ({
            id: topic.id,
            name: topic.name.trim(),
            slug: topic.slug.trim(),
            voice_id: topic.voice_id.trim(),
            description: topic.description,
            active: topic.active,
            sort_order: topic.sort_order,
            // Multi-voice dialogue support (v1.82)
            use_dialogue_api: topic.use_dialogue_api || false,
            dialogue_model: topic.dialogue_model || 'eleven_turbo_v2_5',
            voice_config: topic.voice_config || null,
          }))
        })
      })

      const data = await response.json()

      if (response.ok) {
        setMessage({ type: 'success', text: 'Topics saved successfully' })
        setTimeout(() => setMessage(null), 3000)
        fetchTopics()
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to save topics' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save topics' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-600">Loading topics...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Topics</h1>
        <p className="mt-1 text-gray-600">
          Configure digest topics, voice settings, TTS models, and manage instructions via Script Lab
        </p>
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

      <div className="flex justify-end mb-4">
        <button
          onClick={addTopic}
          className="btn-secondary"
          disabled={saving}
        >
          Add Topic
        </button>
      </div>

      {topics.length === 0 ? (
        <div className="card p-6 text-center text-gray-500">
          No topics configured. Click "Add Topic" to get started.
        </div>
      ) : (
        <div className="space-y-4">
          {topics.map((topic, index) => (
            <div key={index} className="card">
              <div className="space-y-4">
                {/* Header Row */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={topic.active}
                      onChange={(e) => updateTopic(index, 'active', e.target.checked)}
                      className="h-5 w-5 text-primary-600 rounded border-gray-300 mt-1"
                      disabled={saving}
                      title="Active"
                    />
                    <div className="flex-1">
                      <input
                        type="text"
                        value={topic.name}
                        onChange={(e) => updateTopic(index, 'name', e.target.value)}
                        className="text-lg font-semibold border-0 border-b-2 border-transparent hover:border-gray-300 focus:border-primary-500 outline-none px-2 py-1 -ml-2"
                        placeholder="Topic name"
                        disabled={saving}
                        required
                      />
                      <div className="text-xs text-gray-500 px-2">
                        Slug: {topic.slug}
                        {topic.last_generated_at && (
                          <> • Last generated: {new Date(topic.last_generated_at).toLocaleString()}</>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <a
                      href={scriptLabLink(topic.name)}
                      className="text-sm text-primary-600 hover:text-primary-700"
                    >
                      Script Lab
                    </a>
                    <button
                      onClick={() => removeTopic(index)}
                      className="text-sm text-error-600 hover:text-error-700"
                      disabled={saving}
                    >
                      Remove
                    </button>
                  </div>
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description & Keywords
                  </label>
                  <textarea
                    value={topic.description}
                    onChange={(e) => updateTopic(index, 'description', e.target.value)}
                    className="input w-full h-20 resize-y"
                    placeholder="Topic description and keywords for episode scoring"
                    disabled={saving}
                  />
                </div>

                {/* TTS Configuration */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      TTS Model
                    </label>
                    <select
                      value={topic.dialogue_model || 'eleven_turbo_v2_5'}
                      onChange={(e) => updateTopic(index, 'dialogue_model', e.target.value)}
                      className="input w-full"
                      disabled={saving}
                    >
                      <option value="eleven_v3">v3 (High Quality, Dialogue Support)</option>
                      <option value="eleven_turbo_v2_5">Turbo v2.5 (Fast, Single Voice)</option>
                      <option value="eleven_flash_v2_5">Flash v2.5 (Low Latency)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Sort Order
                    </label>
                    <input
                      type="number"
                      value={topic.sort_order}
                      onChange={(e) => updateTopic(index, 'sort_order', e.target.value)}
                      className="input w-full"
                      disabled={saving}
                    />
                  </div>
                </div>

                {/* Dialogue Mode Toggle */}
                <div className="border-t pt-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={topic.use_dialogue_api || false}
                      onChange={(e) => updateTopic(index, 'use_dialogue_api', e.target.checked)}
                      className="h-4 w-4 text-primary-600 rounded border-gray-300"
                      disabled={saving}
                    />
                    <span className="text-sm font-medium text-gray-700">
                      Enable Multi-Voice Dialogue Mode
                    </span>
                    <span className="text-xs text-gray-500">
                      (Requires TTS Model: v3)
                    </span>
                  </label>
                </div>

                {/* Voice Configuration */}
                <div className="border-t pt-4">
                  {topic.use_dialogue_api ? (
                    <MultiVoiceConfig
                      value={topic.voice_config || null}
                      onChange={(config) => updateTopic(index, 'voice_config', config)}
                      disabled={saving}
                    />
                  ) : (
                    <VoiceSelector
                      value={topic.voice_id}
                      onChange={(voiceId) => updateTopic(index, 'voice_id', voiceId)}
                      disabled={saving}
                      label="Single Voice (Narrative Mode)"
                      placeholder="Select a voice for single-narrator audio"
                    />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Save Button */}
      {topics.length > 0 && (
        <div className="flex justify-end">
          <button
            onClick={saveTopics}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save All Topics'}
          </button>
        </div>
      )}
    </div>
  )
}
