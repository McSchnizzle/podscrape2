'use client'

import { useState, useEffect } from 'react'

interface TopicRow {
  id?: number
  name: string
  slug: string
  voice_id: string
  description: string
  active: boolean
  sort_order: number
  last_generated_at?: string | null
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
          Configure digest topics, voice settings, sort order, and manage instructions via Script Lab
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

      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Topic Configuration</h3>
          <button
            onClick={addTopic}
            className="btn-secondary"
            disabled={saving}
          >
            Add Topic
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full border border-gray-300 rounded-lg">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left p-3 border-b font-medium text-gray-700">Active</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Name</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Slug</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Voice ID</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Description</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Sort Order</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Last Generated</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {topics.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-6 text-center text-gray-500">
                    No topics configured. Click "Add Topic" to get started.
                  </td>
                </tr>
              ) : (
                topics.map((topic, index) => (
                  <tr key={index} className="border-t hover:bg-gray-50">
                    <td className="p-3 align-top">
                      <input
                        type="checkbox"
                        checked={topic.active}
                        onChange={(e) => updateTopic(index, 'active', e.target.checked)}
                        className="h-4 w-4 text-primary-600 rounded border-gray-300"
                        disabled={saving}
                      />
                    </td>
                    <td className="p-3 align-top">
                      <input
                        type="text"
                        value={topic.name}
                        onChange={(e) => updateTopic(index, 'name', e.target.value)}
                        className="input w-48"
                        placeholder="Topic name"
                        disabled={saving}
                        required
                      />
                    </td>
                    <td className="p-3 align-top">
                      <input
                        type="text"
                        value={topic.slug}
                        onChange={(e) => updateTopic(index, 'slug', e.target.value)}
                        className="input w-40"
                        placeholder="topic-slug"
                        disabled={saving}
                        required
                      />
                    </td>
                    <td className="p-3 align-top">
                      <input
                        type="text"
                        value={topic.voice_id}
                        onChange={(e) => updateTopic(index, 'voice_id', e.target.value)}
                        className="input w-48"
                        placeholder="ElevenLabs Voice ID"
                        disabled={saving}
                      />
                    </td>
                    <td className="p-3 align-top">
                      <textarea
                        value={topic.description}
                        onChange={(e) => updateTopic(index, 'description', e.target.value)}
                        className="input w-72 h-20 resize-y"
                        placeholder="Topic description and keywords"
                        disabled={saving}
                      />
                    </td>
                    <td className="p-3 align-top">
                      <input
                        type="number"
                        value={topic.sort_order}
                        onChange={(e) => updateTopic(index, 'sort_order', e.target.value)}
                        className="input w-24"
                        disabled={saving}
                      />
                    </td>
                    <td className="p-3 align-top text-sm text-gray-500">
                      {topic.last_generated_at ? new Date(topic.last_generated_at).toLocaleString() : '—'}
                    </td>
                    <td className="p-3 align-top">
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
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex justify-end mt-6">
          <button
            onClick={saveTopics}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Topics'}
          </button>
        </div>
      </div>
    </div>
  )
}
