'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, FileText, Loader2 } from 'lucide-react'
import VoiceSelector from '@/components/VoiceSelector'
import MultiVoiceConfig, { VoiceConfig } from '@/components/MultiVoiceConfig'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import generatedSchema from '@/generated/settings-schema.json'

// Generated from src/config/models.py::CATALOG (scripts/regen-settings-schema.sh).
// The dialogue_model picker used to hardcode 3 of the 7 ElevenLabs models the
// schema knows about, so four were unreachable from the UI.
const elevenLabsModels = Object.entries(
  (generatedSchema.ai_models as Record<string, Record<string, { display_name?: string }>>).elevenlabs ?? {}
).map(([id, info]) => ({ id, display_name: info.display_name ?? id }))

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
  // Topic tracking and deduplication (v2.00)
  enable_topic_tracking?: boolean
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
          // Topic tracking and deduplication (v2.00)
          enable_topic_tracking: Boolean(topic.enable_topic_tracking || false),
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
      // Topic tracking and deduplication (v2.00)
      enable_topic_tracking: false,
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
      <div>
        <PageHeader title="Topics" description="Configure digest topics, voice settings, TTS models, and manage instructions via Script Lab." />
        <div className="flex flex-col gap-[var(--space-3)]">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card h-32 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Topics"
        description="Configure digest topics, voice settings, TTS models, and manage instructions via Script Lab."
        actions={
          <button onClick={addTopic} disabled={saving} className="btn btn-secondary">
            <Plus size={14} /> Add Topic
          </button>
        }
      />

      {message && (
        <div
          className="mb-[var(--space-5)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
          style={{
            background: message.type === 'success' ? 'var(--success-soft)' : 'var(--danger-soft)',
            color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
            font: 'var(--t-small)',
          }}
        >
          {message.text}
        </div>
      )}

      {topics.length === 0 ? (
        <div className="card py-[var(--space-8)] text-center text-ink-subtle">
          No topics configured. Click &quot;Add Topic&quot; to get started.
        </div>
      ) : (
        <div className="flex flex-col gap-[var(--space-4)]">
          {topics.map((topic, index) => (
            <div key={index} className="card">
              <div className="flex flex-col gap-[var(--space-4)]">
                {/* Header Row */}
                <div className="flex items-start justify-between gap-[var(--space-3)]">
                  <div className="flex items-start gap-[var(--space-3)]">
                    <input
                      type="checkbox"
                      checked={topic.active}
                      onChange={(e) => updateTopic(index, 'active', e.target.checked)}
                      className="mt-[6px] h-4 w-4 accent-[var(--accent)]"
                      disabled={saving}
                      title="Active"
                    />
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-[var(--space-2)]">
                        <input
                          type="text"
                          value={topic.name}
                          onChange={(e) => updateTopic(index, 'name', e.target.value)}
                          className="border-0 border-b-2 border-transparent bg-transparent px-[var(--space-1)] py-[2px] text-ink outline-none transition-colors hover:border-border-strong focus:border-accent"
                          style={{ font: 'var(--t-h3)' }}
                          placeholder="Topic name"
                          disabled={saving}
                          required
                        />
                        <Pill tone={topic.active ? 'success' : 'neutral'}>{topic.active ? 'Active' : 'Inactive'}</Pill>
                      </div>
                      <div className="mt-[var(--space-1)] px-[var(--space-1)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                        Slug: {topic.slug}
                        {topic.last_generated_at && (
                          <> &middot; Last generated: {new Date(topic.last_generated_at).toLocaleString()}</>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-[var(--space-2)]">
                    <a href={scriptLabLink(topic.name)} className="btn btn-ghost btn-sm">
                      <FileText size={13} /> Script Lab
                    </a>
                    <button
                      onClick={() => removeTopic(index)}
                      className="btn btn-ghost btn-sm hover:text-danger"
                      disabled={saving}
                    >
                      <Trash2 size={13} /> Remove
                    </button>
                  </div>
                </div>

                {/* Description */}
                <div>
                  <label className="field-label">Description &amp; Keywords</label>
                  <textarea
                    value={topic.description}
                    onChange={(e) => updateTopic(index, 'description', e.target.value)}
                    className="textarea h-20 resize-y"
                    placeholder="Topic description and keywords for episode scoring"
                    disabled={saving}
                  />
                </div>

                {/* TTS Configuration */}
                <div className="grid grid-cols-1 gap-[var(--space-4)] sm:grid-cols-2">
                  <div>
                    <label className="field-label">TTS Model</label>
                    <select
                      value={topic.dialogue_model || 'eleven_turbo_v2_5'}
                      onChange={(e) => updateTopic(index, 'dialogue_model', e.target.value)}
                      className="select"
                      disabled={saving}
                    >
                      {/* Generated from src/config/models.py::CATALOG. Was 3 hardcoded
                          options, a subset of the 7 the schema knows about. */}
                      {elevenLabsModels.map((m) => (
                        <option key={m.id} value={m.id}>{m.display_name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="field-label">Sort Order</label>
                    <input
                      type="number"
                      value={topic.sort_order}
                      onChange={(e) => updateTopic(index, 'sort_order', e.target.value)}
                      className="input"
                      disabled={saving}
                    />
                  </div>
                </div>

                {/* Feature Toggles */}
                <div className="flex flex-col gap-[var(--space-3)] border-t border-border pt-[var(--space-4)]">
                  <label className="flex cursor-pointer items-center gap-[var(--space-2)]">
                    <input
                      type="checkbox"
                      checked={topic.use_dialogue_api || false}
                      onChange={(e) => updateTopic(index, 'use_dialogue_api', e.target.checked)}
                      className="h-4 w-4 accent-[var(--accent)]"
                      disabled={saving}
                    />
                    <span className="text-ink" style={{ font: 'var(--t-small)', fontWeight: 600 }}>
                      Enable Multi-Voice Dialogue Mode
                    </span>
                    <span className="text-ink-faint" style={{ font: 'var(--t-small)' }}>
                      (Requires TTS Model: v3)
                    </span>
                  </label>

                  <label className="flex cursor-pointer items-center gap-[var(--space-2)]">
                    <input
                      type="checkbox"
                      checked={topic.enable_topic_tracking || false}
                      onChange={(e) => updateTopic(index, 'enable_topic_tracking', e.target.checked)}
                      className="h-4 w-4 accent-[var(--accent)]"
                      disabled={saving}
                    />
                    <span className="text-ink" style={{ font: 'var(--t-small)', fontWeight: 600 }}>
                      Enable Topic Tracking &amp; Deduplication
                    </span>
                    <span className="text-ink-faint" style={{ font: 'var(--t-small)' }}>
                      (Extracts topics and avoids repetitive content)
                    </span>
                  </label>
                </div>

                {/* Voice Configuration */}
                <div className="border-t border-border pt-[var(--space-4)]">
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
        <div className="mt-[var(--space-5)] flex justify-end">
          <button
            onClick={saveTopics}
            className="btn btn-primary"
            disabled={saving}
          >
            {saving ? (
              <>
                <Loader2 size={14} className="animate-spin" /> Saving…
              </>
            ) : (
              'Save All Topics'
            )}
          </button>
        </div>
      )}
    </div>
  )
}
