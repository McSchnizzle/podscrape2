'use client'

import { useEffect, useState } from 'react'
import {
  Pencil,
  Trash2,
  X,
  Plus,
  Loader2,
  GitMerge,
  Sparkles,
  Hash,
  TrendingUp,
  Megaphone,
  CheckCircle2,
} from 'lucide-react'
import { toast } from '@/components/Toast'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill, type PillTone } from '@/components/ui/Pill'
import { StatCard } from '@/components/ui/StatCard'

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
  { value: 'model_release', label: 'Model Release' },
  { value: 'use_case', label: 'Use Case' },
  { value: 'personality', label: 'Personality' },
  { value: 'research', label: 'Research' },
  { value: 'company_news', label: 'Company News' },
  { value: 'regulation', label: 'Regulation' },
  { value: 'technique', label: 'Technique' },
  { value: 'other', label: 'Other' },
]

const TOPIC_TONE: Record<string, PillTone> = {
  model_release: 'accent',
  use_case: 'accent',
  personality: 'accent',
  research: 'accent',
  company_news: 'neutral',
  regulation: 'danger',
  technique: 'accent',
  other: 'neutral',
}

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

  const getTypeTone = (type: string): PillTone => {
    return TOPIC_TONE[type] || 'neutral'
  }

  const getTypeLabel = (type: string) => {
    return TOPIC_TYPES.find(t => t.value === type)?.label || type.replace('_', ' ')
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
        toast.error('Failed to save topic', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to save topic:', error)
      toast.error('Failed to save topic', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
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
        toast.error('Failed to delete topic', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to delete topic:', error)
      toast.error('Failed to delete topic', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
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
        toast.error('Validation Error', {
          description: 'At least one keyword is required',
          duration: 5000
        })
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
        toast.error('Failed to save ad', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to save ad:', error)
      toast.error('Failed to save ad', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
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
        toast.error('Failed to delete ad', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to delete ad:', error)
      toast.error('Failed to delete ad', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
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
      toast.error('Selection Required', {
        description: 'Please select at least 2 topics to merge',
        duration: 5000
      })
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
    <div>
      <PageHeader
        title="Recurring Topics & Ads"
        description="Track extracted topics and common ad patterns across episodes."
        actions={
          activeTab === 'ads' ? (
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
              className="btn btn-primary"
            >
              <Plus size={14} /> Add ad pattern
            </button>
          ) : undefined
        }
      />

      {/* Stats */}
      {stats && (
        <div className="mb-[var(--space-6)] grid grid-cols-1 gap-[var(--space-4)] sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total topics" value={stats.total_topics} icon={<Hash size={16} />} />
          <StatCard label="Avg novelty" value={stats.avg_novelty_score.toFixed(2)} icon={<TrendingUp size={16} />} />
          <StatCard label="Total ads" value={stats.total_ads} icon={<Megaphone size={16} />} />
          <StatCard label="Active ads" value={stats.active_ads} tone="success" icon={<CheckCircle2 size={16} />} />
        </div>
      )}

      {/* Tabs */}
      <div className="mb-[var(--space-6)] flex gap-[var(--space-6)] border-b border-border">
        <button
          onClick={() => setActiveTab('topics')}
          className={`border-b-2 pb-[var(--space-3)] transition-colors ${
            activeTab === 'topics'
              ? 'border-accent text-accent'
              : 'border-transparent text-ink-subtle hover:border-border hover:text-ink-muted'
          }`}
          style={{ font: 'var(--t-small)', fontWeight: 600 }}
        >
          Episode Topics ({topics.length})
        </button>
        <button
          onClick={() => setActiveTab('ads')}
          className={`border-b-2 pb-[var(--space-3)] transition-colors ${
            activeTab === 'ads'
              ? 'border-accent text-accent'
              : 'border-transparent text-ink-subtle hover:border-border hover:text-ink-muted'
          }`}
          style={{ font: 'var(--t-small)', fontWeight: 600 }}
        >
          Common Ads ({ads.length})
        </button>
      </div>

      {/* Topics Tab */}
      {activeTab === 'topics' && (
        <div className="flex flex-col gap-[var(--space-5)]">
          {/* Selection Actions */}
          {selectedTopicIds.size > 0 && (
            <div
              className="card flex items-center justify-between gap-[var(--space-3)]"
              style={{ borderColor: 'var(--accent)', background: 'var(--accent-soft)' }}
            >
              <span style={{ font: 'var(--t-small)', color: 'var(--text)' }}>
                <strong>{selectedTopicIds.size}</strong> topic{selectedTopicIds.size === 1 ? '' : 's'} selected
              </span>
              <div className="flex items-center gap-[var(--space-3)]">
                <button onClick={() => setSelectedTopicIds(new Set())} className="btn btn-ghost btn-sm">
                  Clear selection
                </button>
                <button
                  onClick={() => setShowMergeModal(true)}
                  disabled={selectedTopicIds.size < 2}
                  className="btn btn-primary btn-sm"
                >
                  <GitMerge size={14} /> Merge selected ({selectedTopicIds.size})
                </button>
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="card">
            <div className="grid grid-cols-1 gap-[var(--space-4)] md:grid-cols-4">
              <div>
                <label className="field-label">Search</label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search topics..."
                  className="input"
                />
              </div>
              <div>
                <label className="field-label">Type</label>
                <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="select">
                  <option value="">All types</option>
                  {TOPIC_TYPES.map(type => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="field-label">Digest topic</label>
                <input
                  type="text"
                  value={digestFilter}
                  onChange={(e) => setDigestFilter(e.target.value)}
                  placeholder="e.g., AI and Technology"
                  className="input"
                />
              </div>
              <div>
                <label className="field-label">Min novelty</label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={minNovelty}
                  onChange={(e) => setMinNovelty(parseFloat(e.target.value))}
                  className="input"
                />
              </div>
            </div>
          </div>

          {/* Topics List */}
          {loading ? (
            <div className="card flex flex-col items-center gap-[var(--space-3)] py-[var(--space-8)] text-center text-ink-subtle">
              <Loader2 size={20} className="animate-spin" />
              Loading topics…
            </div>
          ) : topics.length === 0 ? (
            <div className="card py-[var(--space-8)] text-center text-ink-subtle">
              No topics found
            </div>
          ) : (
            <div className="table-shell overflow-x-auto">
              <table className="house-table">
                <thead>
                  <tr>
                    <th>
                      <input
                        type="checkbox"
                        checked={topics.length > 0 && selectedTopicIds.size === topics.length}
                        onChange={handleSelectAllTopics}
                        className="h-4 w-4 accent-[var(--accent)]"
                      />
                    </th>
                    <th>Topic</th>
                    <th>Type</th>
                    <th>Novelty</th>
                    <th>Episode</th>
                    <th>Digest Topic</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {topics.map((topic) => (
                    <tr
                      key={topic.id}
                      style={selectedTopicIds.has(topic.id) ? { background: 'var(--accent-soft)' } : undefined}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedTopicIds.has(topic.id)}
                          onChange={() => handleToggleTopicSelection(topic.id)}
                          className="h-4 w-4 accent-[var(--accent)]"
                        />
                      </td>
                      <td className="max-w-[280px]">
                        <div className="flex items-center gap-[var(--space-2)]">
                          <span style={{ font: 'var(--t-small)', fontWeight: 600, color: 'var(--text)' }}>
                            {topic.topic_name}
                          </span>
                          {topic.is_update && <Pill tone="accent">Update</Pill>}
                        </div>
                        {topic.key_points.length > 0 && (
                          <div className="mt-[var(--space-1)] truncate text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                            {topic.key_points[0]}
                            {topic.key_points.length > 1 && ` (+${topic.key_points.length - 1} more)`}
                          </div>
                        )}
                      </td>
                      <td>
                        <Pill tone={getTypeTone(topic.topic_type)}>{getTypeLabel(topic.topic_type)}</Pill>
                      </td>
                      <td>
                        <div className="flex items-center gap-[var(--space-2)]">
                          <span style={{ font: 'var(--t-small)', fontWeight: 600, color: 'var(--text)' }}>
                            {topic.novelty_score.toFixed(2)}
                          </span>
                          <div className="h-2 w-16 overflow-hidden rounded-full" style={{ background: 'var(--surface-3)' }}>
                            <div
                              className="h-full rounded-full"
                              style={{ width: `${topic.novelty_score * 100}%`, background: 'var(--accent)' }}
                            />
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="text-ink" style={{ font: 'var(--t-small)' }}>{topic.episode_title}</div>
                        <div className="text-ink-faint" style={{ font: 'var(--t-micro)' }}>
                          Score: {topic.relevance_score.toFixed(2)}
                        </div>
                      </td>
                      <td className="text-ink-muted" style={{ font: 'var(--t-small)' }}>{topic.digest_topic}</td>
                      <td>
                        <div className="flex gap-[var(--space-1)]">
                          <button onClick={() => handleEditTopic(topic)} className="btn btn-ghost btn-sm" title="Edit">
                            <Pencil size={13} />
                          </button>
                          <button
                            onClick={() => setDeleteConfirm({ type: 'topic', id: topic.id })}
                            className="btn btn-ghost btn-sm hover:text-danger"
                            title="Delete"
                          >
                            <Trash2 size={13} />
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
        <div className="flex flex-col gap-[var(--space-4)]">
          {loading ? (
            <div className="card flex flex-col items-center gap-[var(--space-3)] py-[var(--space-8)] text-center text-ink-subtle">
              <Loader2 size={20} className="animate-spin" />
              Loading ads…
            </div>
          ) : ads.length === 0 ? (
            <div className="card py-[var(--space-8)] text-center text-ink-subtle">
              <p>No ads found</p>
              <button onClick={() => setShowAdModal(true)} className="btn btn-primary mt-[var(--space-4)]">
                <Plus size={14} /> Add first ad pattern
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-[var(--space-4)] md:grid-cols-2">
              {ads.map((ad) => (
                <div key={ad.id} className="card">
                  <div className="flex items-start justify-between gap-[var(--space-3)]">
                    <div className="min-w-0">
                      <h3 className="truncate" style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
                        {ad.advertiser_name}
                      </h3>
                      <div className="mt-[var(--space-2)] flex flex-wrap items-center gap-[var(--space-2)]">
                        <button
                          onClick={() => handleToggleAdActive(ad)}
                          className={ad.is_active ? 'pill pill-success' : 'pill'}
                        >
                          {ad.is_active ? 'Active' : 'Inactive'}
                        </button>
                        <span className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                          Detected {ad.detection_count} time{ad.detection_count === 1 ? '' : 's'}
                        </span>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-[var(--space-1)]">
                      <button onClick={() => handleEditAd(ad)} className="btn btn-ghost btn-sm" title="Edit">
                        <Pencil size={13} />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm({ type: 'ad', id: ad.id })}
                        className="btn btn-ghost btn-sm hover:text-danger"
                        title="Delete"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  <div
                    className="mt-[var(--space-4)] flex items-baseline justify-between gap-[var(--space-3)] rounded-sm p-[var(--space-3)]"
                    style={{ background: 'var(--surface-2)' }}
                  >
                    <span className="micro">Confidence threshold</span>
                    <span style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
                      {(ad.confidence_threshold * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="mt-[var(--space-4)]">
                    <div className="field-label">Keywords</div>
                    <div className="flex flex-wrap gap-[var(--space-2)]">
                      {ad.pattern_keywords.map((keyword, idx) => (
                        <span key={idx} className="pill">{keyword}</span>
                      ))}
                    </div>
                  </div>

                  <div
                    className="mt-[var(--space-4)] flex flex-wrap gap-x-[var(--space-4)] border-t border-border pt-[var(--space-3)] text-ink-faint"
                    style={{ font: 'var(--t-micro)' }}
                  >
                    <span>Created {formatDate(ad.created_at)}</span>
                    <span>Updated {formatDate(ad.updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Topic Modal */}
      {showTopicModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]" style={{ background: 'var(--scrim)' }}>
          <div className="card !p-0 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="border-b border-border px-[var(--space-5)] py-[var(--space-4)]">
              <h2 style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>
                {editingTopic ? 'Edit topic' : 'Create topic'}
              </h2>
            </div>
            <div className="flex flex-col gap-[var(--space-4)] px-[var(--space-5)] py-[var(--space-4)]">
              <div>
                <label className="field-label">Topic name *</label>
                <input
                  type="text"
                  value={topicForm.topic_name}
                  onChange={(e) => setTopicForm({ ...topicForm, topic_name: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="field-label">Type</label>
                <select
                  value={topicForm.topic_type}
                  onChange={(e) => setTopicForm({ ...topicForm, topic_type: e.target.value })}
                  className="select"
                >
                  {TOPIC_TYPES.map(type => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-[var(--space-4)]">
                <div>
                  <label className="field-label">Novelty score</label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={topicForm.novelty_score}
                    onChange={(e) => setTopicForm({ ...topicForm, novelty_score: parseFloat(e.target.value) })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="field-label">Relevance score</label>
                  <input
                    type="number"
                    min="0"
                    max="1"
                    step="0.1"
                    value={topicForm.relevance_score}
                    onChange={(e) => setTopicForm({ ...topicForm, relevance_score: parseFloat(e.target.value) })}
                    className="input"
                  />
                </div>
              </div>
              <div>
                <label className="field-label">Digest topic</label>
                <input
                  type="text"
                  value={topicForm.digest_topic}
                  onChange={(e) => setTopicForm({ ...topicForm, digest_topic: e.target.value })}
                  placeholder="e.g., AI and Technology"
                  className="input"
                />
              </div>
              <div>
                <label className="field-label">Key points</label>
                <div className="flex flex-col gap-[var(--space-2)]">
                  {topicForm.key_points.map((kp, idx) => (
                    <div key={idx} className="flex gap-[var(--space-2)]">
                      <input
                        type="text"
                        value={kp}
                        onChange={(e) => {
                          const newKps = [...topicForm.key_points]
                          newKps[idx] = e.target.value
                          setTopicForm({ ...topicForm, key_points: newKps })
                        }}
                        className="input flex-1"
                      />
                      <button
                        onClick={() => {
                          const newKps = topicForm.key_points.filter((_, i) => i !== idx)
                          setTopicForm({ ...topicForm, key_points: newKps.length > 0 ? newKps : [''] })
                        }}
                        className="btn btn-ghost btn-sm hover:text-danger"
                        title="Remove key point"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setTopicForm({ ...topicForm, key_points: [...topicForm.key_points, ''] })}
                  className="mt-[var(--space-2)] inline-flex items-center gap-[4px]"
                  style={{ font: 'var(--t-small)', color: 'var(--accent)' }}
                >
                  <Plus size={12} /> Add key point
                </button>
              </div>
              <div>
                <label className="field-label">Evolution summary</label>
                <textarea
                  value={topicForm.evolution_summary}
                  onChange={(e) => setTopicForm({ ...topicForm, evolution_summary: e.target.value })}
                  rows={2}
                  className="textarea"
                />
              </div>
            </div>
            <div className="flex justify-end gap-[var(--space-3)] border-t border-border px-[var(--space-5)] py-[var(--space-4)]">
              <button
                onClick={() => {
                  setShowTopicModal(false)
                  setEditingTopic(null)
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button onClick={handleSaveTopic} disabled={saving || !topicForm.topic_name} className="btn btn-primary">
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ad Modal */}
      {showAdModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]" style={{ background: 'var(--scrim)' }}>
          <div className="card !p-0 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="border-b border-border px-[var(--space-5)] py-[var(--space-4)]">
              <h2 style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>
                {editingAd ? 'Edit ad pattern' : 'Create ad pattern'}
              </h2>
            </div>
            <div className="flex flex-col gap-[var(--space-4)] px-[var(--space-5)] py-[var(--space-4)]">
              <div>
                <label className="field-label">Advertiser name *</label>
                <input
                  type="text"
                  value={adForm.advertiser_name}
                  onChange={(e) => setAdForm({ ...adForm, advertiser_name: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="field-label">Pattern keywords *</label>
                <div className="flex flex-col gap-[var(--space-2)]">
                  {adForm.pattern_keywords.map((kw, idx) => (
                    <div key={idx} className="flex gap-[var(--space-2)]">
                      <input
                        type="text"
                        value={kw}
                        onChange={(e) => {
                          const newKws = [...adForm.pattern_keywords]
                          newKws[idx] = e.target.value
                          setAdForm({ ...adForm, pattern_keywords: newKws })
                        }}
                        placeholder="Enter keyword..."
                        className="input flex-1"
                      />
                      <button
                        onClick={() => {
                          const newKws = adForm.pattern_keywords.filter((_, i) => i !== idx)
                          setAdForm({ ...adForm, pattern_keywords: newKws.length > 0 ? newKws : [''] })
                        }}
                        className="btn btn-ghost btn-sm hover:text-danger"
                        title="Remove keyword"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setAdForm({ ...adForm, pattern_keywords: [...adForm.pattern_keywords, ''] })}
                  className="mt-[var(--space-2)] inline-flex items-center gap-[4px]"
                  style={{ font: 'var(--t-small)', color: 'var(--accent)' }}
                >
                  <Plus size={12} /> Add keyword
                </button>
              </div>
              <div>
                <label className="field-label">Confidence threshold</label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={adForm.confidence_threshold}
                  onChange={(e) => setAdForm({ ...adForm, confidence_threshold: parseFloat(e.target.value) })}
                  className="input"
                />
                <p className="field-hint">
                  Minimum confidence required to identify this ad pattern (0.0 - 1.0)
                </p>
              </div>
              <label className="flex items-center gap-[var(--space-2)] text-ink" style={{ font: 'var(--t-small)' }}>
                <input
                  type="checkbox"
                  checked={adForm.is_active}
                  onChange={(e) => setAdForm({ ...adForm, is_active: e.target.checked })}
                  className="h-4 w-4 accent-[var(--accent)]"
                />
                Active (actively filtering this ad pattern)
              </label>
            </div>
            <div className="flex justify-end gap-[var(--space-3)] border-t border-border px-[var(--space-5)] py-[var(--space-4)]">
              <button
                onClick={() => {
                  setShowAdModal(false)
                  setEditingAd(null)
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button onClick={handleSaveAd} disabled={saving || !adForm.advertiser_name} className="btn btn-primary">
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]" style={{ background: 'var(--scrim)' }}>
          <div className="card w-full max-w-md">
            <h2 className="mb-[var(--space-3)]" style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>
              Confirm delete
            </h2>
            <p className="text-ink-muted" style={{ font: 'var(--t-body)' }}>
              Are you sure you want to delete this {deleteConfirm.type}? This action cannot be undone.
            </p>
            <div className="mt-[var(--space-5)] flex justify-end gap-[var(--space-3)]">
              <button onClick={() => setDeleteConfirm(null)} className="btn btn-secondary">
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
                className="btn btn-danger"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Merge Topics Modal */}
      {showMergeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]" style={{ background: 'var(--scrim)' }}>
          <div className="card !p-0 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="border-b border-border px-[var(--space-5)] py-[var(--space-4)]">
              <h2 className="flex items-center gap-[var(--space-2)]" style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>
                <Sparkles size={18} style={{ color: 'var(--accent)' }} /> Merge topics with AI
              </h2>
              <p className="mt-[var(--space-2)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                The AI will analyze the selected topics and create a unified topic that combines the most important information.
              </p>
            </div>
            <div className="px-[var(--space-5)] py-[var(--space-4)]">
              <div className="field-label">Topics to merge ({selectedTopicIds.size})</div>
              <div className="flex max-h-64 flex-col gap-[var(--space-2)] overflow-y-auto">
                {getSelectedTopics().map((topic) => (
                  <div
                    key={topic.id}
                    className="flex items-start justify-between gap-[var(--space-3)] rounded-sm p-[var(--space-3)]"
                    style={{ background: 'var(--surface-2)' }}
                  >
                    <div className="min-w-0 flex-1">
                      <div style={{ font: 'var(--t-small)', fontWeight: 600, color: 'var(--text)' }}>{topic.topic_name}</div>
                      <div className="mt-[var(--space-1)] text-ink-faint" style={{ font: 'var(--t-micro)' }}>
                        {topic.topic_type} · Novelty: {topic.novelty_score.toFixed(2)}
                      </div>
                      {topic.key_points.length > 0 && (
                        <div className="mt-[var(--space-1)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                          Key points: {topic.key_points.slice(0, 2).join(', ')}
                          {topic.key_points.length > 2 && '…'}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={() => handleToggleTopicSelection(topic.id)}
                      className="btn btn-ghost btn-sm"
                      title="Remove from selection"
                    >
                      <X size={14} />
                      <span className="sr-only">Remove</span>
                    </button>
                  </div>
                ))}
              </div>

              {mergeResult && (
                <div
                  className="mt-[var(--space-4)] rounded-sm p-[var(--space-4)]"
                  style={{
                    background: mergeResult.success ? 'var(--success-soft)' : 'var(--danger-soft)',
                    color: mergeResult.success ? 'var(--success)' : 'var(--danger)',
                    font: 'var(--t-small)',
                  }}
                >
                  {mergeResult.message}
                </div>
              )}

              <div className="mt-[var(--space-4)] rounded-sm p-[var(--space-4)]" style={{ background: 'var(--accent-soft)' }}>
                <div style={{ font: 'var(--t-small)', color: 'var(--text)' }}>
                  <strong>What happens when you merge:</strong>
                  <ul className="mt-[var(--space-2)] list-inside list-disc" style={{ color: 'var(--text-muted)' }}>
                    <li>AI analyzes all selected topics to find common themes</li>
                    <li>A new unified topic is created with combined key points</li>
                    <li>Original topics are linked to the new merged topic</li>
                    <li>Original topics are NOT deleted (can be removed manually)</li>
                  </ul>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-[var(--space-3)] border-t border-border px-[var(--space-5)] py-[var(--space-4)]">
              <button
                onClick={() => {
                  setShowMergeModal(false)
                  setMergeResult(null)
                }}
                className="btn btn-secondary"
              >
                {mergeResult?.success ? 'Close' : 'Cancel'}
              </button>
              {!mergeResult?.success && (
                <button
                  onClick={handleMergeTopics}
                  disabled={merging || selectedTopicIds.size < 2}
                  className="btn btn-primary"
                >
                  {merging ? (
                    <>
                      <Loader2 size={14} className="animate-spin" /> Merging with AI…
                    </>
                  ) : (
                    <>
                      <Sparkles size={14} /> Merge with AI
                    </>
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
