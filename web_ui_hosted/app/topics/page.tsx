'use client'

import { useState, useEffect } from 'react'

interface Topic {
  name: string
  instruction_file: string
  voice_id: string
  active: boolean
  description: string
}

interface TopicsSettings {
  score_threshold: number
  max_words_per_script: number
  default_voice_settings: {
    stability: number
    similarity_boost: number
    style: number
    use_speaker_boost: boolean
  }
}

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [settings, setSettings] = useState<TopicsSettings | null>(null)
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
        setTopics(data.topics || [])
        setSettings(data.settings || null)
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
    setTopics([...topics, {
      name: '',
      instruction_file: '',
      voice_id: '',
      active: true,
      description: ''
    }])
  }

  const updateTopic = (index: number, field: keyof Topic, value: any) => {
    const newTopics = [...topics]
    newTopics[index] = { ...newTopics[index], [field]: value }
    setTopics(newTopics)
  }

  const removeTopic = (index: number) => {
    setTopics(topics.filter((_, i) => i !== index))
  }

  const saveTopics = async () => {
    // Validate topics
    const errors: string[] = []
    topics.forEach((topic, index) => {
      if (!topic.name.trim()) {
        errors.push(`Topic ${index + 1} must have a name`)
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
        body: JSON.stringify({ topics })
      })

      const data = await response.json()

      if (response.ok) {
        setMessage({ type: 'success', text: 'Topics saved successfully' })
        setTimeout(() => setMessage(null), 3000)
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
          Configure digest topics, voice settings, and instruction files
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
                <th className="text-left p-3 border-b font-medium text-gray-700">Voice ID</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Instruction File</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Description</th>
                <th className="text-left p-3 border-b font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {topics.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-gray-500">
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
                        value={topic.voice_id}
                        onChange={(e) => updateTopic(index, 'voice_id', e.target.value)}
                        className="input w-56"
                        placeholder="ElevenLabs Voice ID"
                        disabled={saving}
                      />
                    </td>
                    <td className="p-3 align-top">
                      <input
                        type="text"
                        value={topic.instruction_file}
                        onChange={(e) => updateTopic(index, 'instruction_file', e.target.value)}
                        className="input w-64"
                        placeholder="e.g., AI and Technology.md"
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
                      <button
                        onClick={() => removeTopic(index)}
                        className="px-2 py-1 text-xs rounded border bg-error-100 text-error-700 hover:bg-error-200 border-error-300"
                        disabled={saving}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex justify-between items-center mt-6">
          <div className="text-sm text-gray-600">
            {topics.length} topic{topics.length !== 1 ? 's' : ''} configured,{' '}
            {topics.filter(t => t.active).length} active
          </div>
          <div className="flex space-x-3">
            <button
              onClick={() => window.location.reload()}
              className="btn-secondary"
              disabled={saving}
            >
              Reset
            </button>
            <button
              onClick={saveTopics}
              className="btn-primary"
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Topics'}
            </button>
          </div>
        </div>
      </div>

      {/* Settings Summary */}
      {settings && (
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Topic Settings</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-700">Score Threshold:</span>{' '}
              <span className="text-gray-600">{settings.score_threshold}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Max Words per Script:</span>{' '}
              <span className="text-gray-600">{settings.max_words_per_script.toLocaleString()}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Voice Stability:</span>{' '}
              <span className="text-gray-600">{settings.default_voice_settings.stability}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Similarity Boost:</span>{' '}
              <span className="text-gray-600">{settings.default_voice_settings.similarity_boost}</span>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-4">
            These settings are managed in the main settings page and configuration files.
          </p>
        </div>
      )}

      {saving && (
        <div className="fixed bottom-4 right-4 bg-primary-600 text-white px-4 py-2 rounded-md shadow-lg">
          Saving...
        </div>
      )}
    </div>
  )
}