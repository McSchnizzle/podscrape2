'use client'

import { useEffect, useState } from 'react'

interface EpisodeTopic {
  id: number
  episode_id: number
  episode_guid: string
  episode_title: string
  topic_name: string
  topic_slug: string
  topic_type: string
  novelty_score: number
  is_update: boolean
  parent_topic_id: number | null
  evolution_summary: string | null
  key_points: string[]
  digest_topic: string
  relevance_score: number
  included_in_digest_id: number | null
  created_at: string
  first_seen_at: string
}

interface CommonAd {
  id: number
  advertiser_name: string
  pattern_keywords: string[]
  confidence_threshold: number
  is_active: boolean
  detection_count: number
  created_at: string
  updated_at: string
}

interface Stats {
  total_topics: number
  topics_by_type: Record<string, number>
  topics_by_digest: Record<string, number>
  avg_novelty_score: number
  total_ads: number
  active_ads: number
}

const TOPIC_TYPES = [
  { value: 'model_release', label: 'Model Release', color: 'bg-blue-100 text-blue-800' },
  { value: 'use_case', label: 'Use Case', color: 'bg-green-100 text-green-800' },
  { value: 'personality', label: 'Personality', color: 'bg-purple-100 text-purple-800' },
  { value: 'research', label: 'Research', color: 'bg-indigo-100 text-indigo-800' },
  { value: 'company_news', label: 'Company News', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'regulation', label: 'Regulation', color: 'bg-red-100 text-red-800' },
  { value: 'technique', label: 'Technique', color: 'bg-cyan-100 text-cyan-800' },
  { value: 'other', label: 'Other', color: 'bg-gray-100 text-gray-800' }
]

export default function RecurringTopicsPage() {
  const [topics, setTopics] = useState<EpisodeTopic[]>([])
  const [ads, setAds] = useState<CommonAd[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'topics' | 'ads'>('topics')

  // Topic filters
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [digestFilter, setDigestFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [minNovelty, setMinNovelty] = useState<number>(0)

  // Modal states
  const [showTopicModal, setShowTopicModal] = useState(false)
  const [showAdModal, setShowAdModal] = useState(false)
  const [editingTopic, setEditingTopic] = useState<EpisodeTopic | null>(null)
  const [editingAd, setEditingAd] = useState<CommonAd | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ type: 'topic' | 'ad', id: number } | null>(null)
  const [saving, setSaving] = useState(false)

  // Merge states
  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<number>>(new Set())
  const [showMergeModal, setShowMergeModal] = useState(false)
  const [merging, setMerging] = useState(false)
  const [mergeResult, setMergeResult] = useState<{ success: boolean; message: string } | null>(null)

  // Form states
  const [topicForm, setTopicForm] = useState({
    topic_name: '',
    topic_type: 'other',
    novelty_score: 1.0,
    key_points: [''],
    digest_topic: '',
    relevance_score: 0,
    evolution_summary: ''
  })

  const [adForm, setAdForm] = useState({
    advertiser_name: '',
    pattern_keywords: [''],
    confidence_threshold: 0.8,
    is_active: true
  })

  useEffect(() => {
    loadData()
  }, [typeFilter, digestFilter, searchQuery, minNovelty])

  const loadData = async () => {
    try {
      setLoading(true)

      // Build query params
      const params = new URLSearchParams()
      if (typeFilter) params.set('type', typeFilter)
      if (digestFilter) params.set('digest', digestFilter)
      if (searchQuery) params.set('search', searchQuery)
      if (minNovelty > 0) params.set('min_novelty', minNovelty.toString())
      params.set('limit', '100')

      const [topicsRes, adsRes, statsRes] = await Promise.all([
        fetch(`/api/recurring-topics/topics?${params.toString()}`),
        fetch('/api/recurring-topics/ads'),
        fetch('/api/recurring-topics/stats')
      ])

      if (topicsRes.ok) {
        const data = await topicsRes.json()
        setTopics(data.topics || [])
      }

      if (adsRes.ok) {
        const data = await adsRes.json()
        setAds(data.ads || [])
      }

      if (statsRes.ok) {
        const data = await statsRes.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getTypeColor = (type: string) => {
    return TOPIC_TYPES.find(t => t.value === type)?.color || 'bg-gray-100 text-gray-800'
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Topic CRUD handlers
  const handleEditTopic = (topic: EpisodeTopic) => {
    setEditingTopic(topic)
    setTopicForm({
      topic_name: topic.topic_name,
      topic_type: topic.topic_type,
      novelty_score: topic.novelty_score,
      key_points: topic.key_points.length > 0 ? topic.key_points : [''],
      digest_topic: topic.digest_topic || '',
      relevance_score: topic.relevance_score,
      evolution_summary: topic.evolution_summary || ''
    })
    setShowTopicModal(true)
  }

  const handleSaveTopic = async () => {
    setSaving(true)
    try {
      const payload = {
        ...topicForm,
        key_points: topicForm.key_points.filter(kp => kp.trim() !== '')
      }

      const url = editingTopic
        ? `/api/recurring-topics/topics/${editingTopic.id}`
        : '/api/recurring-topics/topics'
      const method = editingTopic ? 'PUT' : 'POST'

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (res.ok) {
        setShowTopicModal(false)
        setEditingTopic(null)
        setTopicForm({
          topic_name: '',
          topic_type: 'other',
          novelty_score: 1.0,
          key_points: [''],
          digest_topic: '',
          relevance_score: 0,
          evolution_summary: ''
        })
        loadData()
      } else {
        const error = await res.json()
        alert(`Error: ${error.error || 'Failed to save topic'}`)
      }
    } catch (error) {
      console.error('Failed to save topic:', error)
      alert('Failed to save topic')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteTopic = async (id: number) => {
    try {
      const res = await fetch(`/api/recurring-topics/topics/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setDeleteConfirm(null)
        loadData()
      } else {
        const error = await res.json()
        alert(`Error: ${error.error || 'Failed to delete topic'}`)
      }
    } catch (error) {
      console.error('Failed to delete topic:', error)
      alert('Failed to delete topic')
    }
  }

  // Ad CRUD handlers
  const handleEditAd = (ad: CommonAd) => {
    setEditingAd(ad)
    setAdForm({
      advertiser_name: ad.advertiser_name,
      pattern_keywords: ad.pattern_keywords.length > 0 ? ad.pattern_keywords : [''],
      confidence_threshold: ad.confidence_threshold,
      is_active: ad.is_active
    })
    setShowAdModal(true)
  }

  const handleSaveAd = async () => {
    setSaving(true)
    try {
      const payload = {
        ...adForm,
        pattern_keywords: adForm.pattern_keywords.filter(kw => kw.trim() !== '')
      }

      if (payload.pattern_keywords.length === 0) {
        alert('At least one keyword is required')
        setSaving(false)
        return
      }

      const url = editingAd
        ? `/api/recurring-topics/ads/${editingAd.id}`
        : '/api/recurring-topics/ads'
      const method = editingAd ? 'PUT' : 'POST'

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (res.ok) {
        setShowAdModal(false)
        setEditingAd(null)
        setAdForm({
          advertiser_name: '',
          pattern_keywords: [''],
          confidence_threshold: 0.8,
          is_active: true
        })
        loadData()
      } else {
        const error = await res.json()
        alert(`Error: ${error.error || 'Failed to save ad'}`)
      }
    } catch (error) {
      console.error('Failed to save ad:', error)
      alert('Failed to save ad')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteAd = async (id: number) => {
    try {
      const res = await fetch(`/api/recurring-topics/ads/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setDeleteConfirm(null)
        loadData()
      } else {
        const error = await res.json()
        alert(`Error: ${error.error || 'Failed to delete ad'}`)
      }
    } catch (error) {
      console.error('Failed to delete ad:', error)
      alert('Failed to delete ad')
    }
  }

  const handleToggleAdActive = async (ad: CommonAd) => {
    try {
      const res = await fetch(`/api/recurring-topics/ads/${ad.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !ad.is_active })
      })
      if (res.ok) {
        loadData()
      }
    } catch (error) {
      console.error('Failed to toggle ad:', error)
    }
  }

  // Topic selection and merge handlers
  const handleToggleTopicSelection = (topicId: number) => {
    const newSelected = new Set(selectedTopicIds)
    if (newSelected.has(topicId)) {
      newSelected.delete(topicId)
    } else {
      newSelected.add(topicId)
    }
    setSelectedTopicIds(newSelected)
  }

  const handleSelectAllTopics = () => {
    if (selectedTopicIds.size === topics.length) {
      setSelectedTopicIds(new Set())
    } else {
      setSelectedTopicIds(new Set(topics.map(t => t.id)))
    }
  }

  const handleMergeTopics = async () => {
    if (selectedTopicIds.size < 2) {
      alert('Please select at least 2 topics to merge')
      return
    }

    setMerging(true)
    setMergeResult(null)

    try {
      const res = await fetch('/api/recurring-topics/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_ids: Array.from(selectedTopicIds) })
      })

      const data = await res.json()

      if (res.ok) {
        setMergeResult({
          success: true,
          message: `Successfully merged ${data.merge_details.topics_merged} topics into "${data.merged_topic.topic_name}"`
        })
        setSelectedTopicIds(new Set())
        loadData()
      } else {
        setMergeResult({
          success: false,
          message: data.error || 'Failed to merge topics'
        })
      }
    } catch (error) {
      console.error('Failed to merge topics:', error)
      setMergeResult({
        success: false,
        message: 'Network error - failed to merge topics'
      })
    } finally {
      setMerging(false)
    }
  }

  const getSelectedTopics = () => {
    return topics.filter(t => selectedTopicIds.has(t.id))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Recurring Topics & Ads</h1>
          <p className="mt-1 text-sm text-gray-500">
            Track extracted topics and common ad patterns
          </p>
        </div>
        <div>
          {activeTab === 'ads' && (
            <button
              onClick={() => {
                setEditingAd(null)
                setAdForm({
                  advertiser_name: '',
                  pattern_keywords: [''],
                  confidence_threshold: 0.8,
                  is_active: true
                })
                setShowAdModal(true)
              }}
              className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
            >
              Add Ad Pattern
            </button>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500">Total Topics</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">{stats.total_topics}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500">Avg Novelty</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">
              {stats.avg_novelty_score.toFixed(2)}
            </div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500">Total Ads</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">{stats.total_ads}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500">Active Ads</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">{stats.active_ads}</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('topics')}
            className={`${
              activeTab === 'topics'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Episode Topics ({topics.length})
          </button>
          <button
            onClick={() => setActiveTab('ads')}
            className={`${
              activeTab === 'ads'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Common Ads ({ads.length})
          </button>
        </nav>
      </div>

      {/* Topics Tab */}
      {activeTab === 'topics' && (
        <div className="space-y-4">
          {/* Selection Actions */}
          {selectedTopicIds.size > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center justify-between">
              <div className="text-sm text-blue-800">
                <span className="font-medium">{selectedTopicIds.size}</span> topic(s) selected
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setSelectedTopicIds(new Set())}
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  Clear Selection
                </button>
                <button
                  onClick={() => setShowMergeModal(true)}
                  disabled={selectedTopicIds.size < 2}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                >
                  Merge Selected ({selectedTopicIds.size})
                </button>
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Search
                </label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search topics..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Type
                </label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">All Types</option>
                  {TOPIC_TYPES.map(type => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Digest Topic
                </label>
                <input
                  type="text"
                  value={digestFilter}
                  onChange={(e) => setDigestFilter(e.target.value)}
                  placeholder="e.g., AI and Technology"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Min Novelty
                </label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={minNovelty}
                  onChange={(e) => setMinNovelty(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>

          {/* Topics List */}
          {loading ? (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <p className="mt-2 text-gray-500">Loading topics...</p>
            </div>
          ) : topics.length === 0 ? (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <p className="text-gray-500">No topics found</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left">
                      <input
                        type="checkbox"
                        checked={topics.length > 0 && selectedTopicIds.size === topics.length}
                        onChange={handleSelectAllTopics}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Topic
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Novelty
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Episode
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Digest Topic
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {topics.map((topic) => (
                    <tr key={topic.id} className={`hover:bg-gray-50 ${selectedTopicIds.has(topic.id) ? 'bg-blue-50' : ''}`}>
                      <td className="px-4 py-4">
                        <input
                          type="checkbox"
                          checked={selectedTopicIds.has(topic.id)}
                          onChange={() => handleToggleTopicSelection(topic.id)}
                          className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm font-medium text-gray-900">
                          {topic.topic_name}
                          {topic.is_update && (
                            <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                              UPDATE
                            </span>
                          )}
                        </div>
                        {topic.key_points.length > 0 && (
                          <div className="mt-1 text-sm text-gray-500">
                            {topic.key_points[0]}
                            {topic.key_points.length > 1 && ` (+${topic.key_points.length - 1} more)`}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(topic.topic_type)}`}>
                          {topic.topic_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="text-sm font-medium text-gray-900">
                            {topic.novelty_score.toFixed(2)}
                          </div>
                          <div className="ml-2 w-16 bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-primary-600 h-2 rounded-full"
                              style={{ width: `${topic.novelty_score * 100}%` }}
                            ></div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">{topic.episode_title}</div>
                        <div className="text-xs text-gray-500">Score: {topic.relevance_score.toFixed(2)}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">{topic.digest_topic}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleEditTopic(topic)}
                            className="text-primary-600 hover:text-primary-800"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => setDeleteConfirm({ type: 'topic', id: topic.id })}
                            className="text-red-600 hover:text-red-800"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Ads Tab */}
      {activeTab === 'ads' && (
        <div className="space-y-4">
          {loading ? (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <p className="mt-2 text-gray-500">Loading ads...</p>
            </div>
          ) : ads.length === 0 ? (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <p className="text-gray-500">No ads found</p>
              <button
                onClick={() => setShowAdModal(true)}
                className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700"
              >
                Add First Ad Pattern
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ads.map((ad) => (
                <div key={ad.id} className="bg-white p-6 rounded-lg shadow">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{ad.advertiser_name}</h3>
                      <div className="mt-1 flex items-center space-x-2">
                        <button
                          onClick={() => handleToggleAdActive(ad)}
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer transition-colors ${
                            ad.is_active
                              ? 'bg-green-100 text-green-800 hover:bg-green-200'
                              : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                          }`}
                        >
                          {ad.is_active ? 'Active' : 'Inactive'}
                        </button>
                        <span className="text-sm text-gray-500">
                          Detected: {ad.detection_count} times
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleEditAd(ad)}
                        className="text-primary-600 hover:text-primary-800 text-sm"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeleteConfirm({ type: 'ad', id: ad.id })}
                        className="text-red-600 hover:text-red-800 text-sm"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 text-right">
                    <div className="text-sm text-gray-500">Confidence Threshold</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {(ad.confidence_threshold * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="text-sm font-medium text-gray-700 mb-2">Keywords:</div>
                    <div className="flex flex-wrap gap-2">
                      {ad.pattern_keywords.map((keyword, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-700"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-gray-200 text-xs text-gray-500">
                    <div>Created: {formatDate(ad.created_at)}</div>
                    <div>Updated: {formatDate(ad.updated_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Topic Modal */}
      {showTopicModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-medium text-gray-900">
                {editingTopic ? 'Edit Topic' : 'Create Topic'}
              </h2>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Topic Name *
                </label>
                <input
                  type="text"
                  value={topicForm.topic_name}
                  onChange={(e) => setTopicForm({ ...topicForm, topic_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Type
                </label>
                <select
                  value={topicForm.topic_type}
                  onChange={(e) => setTopicForm({ ...topicForm, topic_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {TOPIC_TYPES.map(type => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Novelty Score
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={topicForm.novelty_score}
                    onChange={(e) => setTopicForm({ ...topicForm, novelty_score: parseFloat(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Relevance Score
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={topicForm.relevance_score}
                    onChange={(e) => setTopicForm({ ...topicForm, relevance_score: parseFloat(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Digest Topic
                </label>
                <input
                  type="text"
                  value={topicForm.digest_topic}
                  onChange={(e) => setTopicForm({ ...topicForm, digest_topic: e.target.value })}
                  placeholder="e.g., AI and Technology"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Key Points
                </label>
                {topicForm.key_points.map((kp, idx) => (
                  <div key={idx} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={kp}
                      onChange={(e) => {
                        const newKps = [...topicForm.key_points]
                        newKps[idx] = e.target.value
                        setTopicForm({ ...topicForm, key_points: newKps })
                      }}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <button
                      onClick={() => {
                        const newKps = topicForm.key_points.filter((_, i) => i !== idx)
                        setTopicForm({ ...topicForm, key_points: newKps.length > 0 ? newKps : [''] })
                      }}
                      className="px-2 py-2 text-red-600 hover:text-red-800"
                    >
                      X
                    </button>
                  </div>
                ))}
                <button
                  onClick={() => setTopicForm({ ...topicForm, key_points: [...topicForm.key_points, ''] })}
                  className="text-sm text-primary-600 hover:text-primary-800"
                >
                  + Add Key Point
                </button>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Evolution Summary
                </label>
                <textarea
                  value={topicForm.evolution_summary}
                  onChange={(e) => setTopicForm({ ...topicForm, evolution_summary: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowTopicModal(false)
                  setEditingTopic(null)
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveTopic}
                disabled={saving || !topicForm.topic_name}
                className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ad Modal */}
      {showAdModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-medium text-gray-900">
                {editingAd ? 'Edit Ad Pattern' : 'Create Ad Pattern'}
              </h2>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Advertiser Name *
                </label>
                <input
                  type="text"
                  value={adForm.advertiser_name}
                  onChange={(e) => setAdForm({ ...adForm, advertiser_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Pattern Keywords *
                </label>
                {adForm.pattern_keywords.map((kw, idx) => (
                  <div key={idx} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={kw}
                      onChange={(e) => {
                        const newKws = [...adForm.pattern_keywords]
                        newKws[idx] = e.target.value
                        setAdForm({ ...adForm, pattern_keywords: newKws })
                      }}
                      placeholder="Enter keyword..."
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <button
                      onClick={() => {
                        const newKws = adForm.pattern_keywords.filter((_, i) => i !== idx)
                        setAdForm({ ...adForm, pattern_keywords: newKws.length > 0 ? newKws : [''] })
                      }}
                      className="px-2 py-2 text-red-600 hover:text-red-800"
                    >
                      X
                    </button>
                  </div>
                ))}
                <button
                  onClick={() => setAdForm({ ...adForm, pattern_keywords: [...adForm.pattern_keywords, ''] })}
                  className="text-sm text-primary-600 hover:text-primary-800"
                >
                  + Add Keyword
                </button>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Confidence Threshold
                </label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={adForm.confidence_threshold}
                  onChange={(e) => setAdForm({ ...adForm, confidence_threshold: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Minimum confidence required to identify this ad pattern (0.0 - 1.0)
                </p>
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={adForm.is_active}
                  onChange={(e) => setAdForm({ ...adForm, is_active: e.target.checked })}
                  className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                />
                <label htmlFor="is_active" className="ml-2 text-sm text-gray-700">
                  Active (actively filtering this ad pattern)
                </label>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowAdModal(false)
                  setEditingAd(null)
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveAd}
                disabled={saving || !adForm.advertiser_name}
                className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Confirm Delete
            </h2>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete this {deleteConfirm.type}? This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (deleteConfirm.type === 'topic') {
                    handleDeleteTopic(deleteConfirm.id)
                  } else {
                    handleDeleteAd(deleteConfirm.id)
                  }
                }}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Merge Topics Modal */}
      {showMergeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-medium text-gray-900">
                Merge Topics with AI
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                The AI will analyze the selected topics and create a unified topic that combines the most important information.
              </p>
            </div>
            <div className="px-6 py-4">
              <div className="text-sm font-medium text-gray-700 mb-3">
                Topics to merge ({selectedTopicIds.size}):
              </div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {getSelectedTopics().map((topic) => (
                  <div key={topic.id} className="flex items-start p-3 bg-gray-50 rounded-lg">
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">{topic.topic_name}</div>
                      <div className="text-xs text-gray-500 mt-1">
                        {topic.topic_type} | Novelty: {topic.novelty_score.toFixed(2)}
                      </div>
                      {topic.key_points.length > 0 && (
                        <div className="text-xs text-gray-600 mt-1">
                          Key points: {topic.key_points.slice(0, 2).join(', ')}
                          {topic.key_points.length > 2 && '...'}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => handleToggleTopicSelection(topic.id)}
                      className="ml-2 text-gray-400 hover:text-gray-600"
                    >
                      <span className="sr-only">Remove</span>
                      X
                    </button>
                  </div>
                ))}
              </div>

              {mergeResult && (
                <div className={`mt-4 p-4 rounded-lg ${
                  mergeResult.success
                    ? 'bg-green-50 border border-green-200'
                    : 'bg-red-50 border border-red-200'
                }`}>
                  <p className={`text-sm ${mergeResult.success ? 'text-green-800' : 'text-red-800'}`}>
                    {mergeResult.message}
                  </p>
                </div>
              )}

              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="text-sm text-blue-800">
                  <strong>What happens when you merge:</strong>
                  <ul className="mt-2 list-disc list-inside space-y-1">
                    <li>AI analyzes all selected topics to find common themes</li>
                    <li>A new unified topic is created with combined key points</li>
                    <li>Original topics are linked to the new merged topic</li>
                    <li>Original topics are NOT deleted (can be removed manually)</li>
                  </ul>
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowMergeModal(false)
                  setMergeResult(null)
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                {mergeResult?.success ? 'Close' : 'Cancel'}
              </button>
              {!mergeResult?.success && (
                <button
                  onClick={handleMergeTopics}
                  disabled={merging || selectedTopicIds.size < 2}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center"
                >
                  {merging ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Merging with AI...
                    </>
                  ) : (
                    'Merge with AI'
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
