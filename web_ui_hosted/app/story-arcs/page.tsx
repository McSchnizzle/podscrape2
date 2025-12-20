'use client'

import { useEffect, useState } from 'react'
import { toast } from '@/components/Toast'

interface StoryArcEvent {
  id: number
  event_date: string
  event_summary: string
  key_points: string[]
  source_name: string | null
  perspective: string | null
  relevance_score: number | null
  extracted_at: string
}

interface StoryArc {
  id: number
  arc_name: string
  arc_slug: string
  functional_category: string
  digest_topic: string
  summary: string | null
  started_at: string
  last_updated_at: string
  event_count: number
  source_count: number
  included_in_digest_id: number | null
  included_at: string | null
  created_at: string
  events?: StoryArcEvent[]
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
  total_arcs: number
  total_events: number
  arcs_by_category: Record<string, number>
  arcs_by_digest: Record<string, number>
  avg_events_per_arc: number
  total_ads: number
  active_ads: number
}

const CATEGORY_TYPES = [
  { value: 'model_release', label: 'Model Release', color: 'bg-blue-100 text-blue-800' },
  { value: 'company_strategy', label: 'Company Strategy', color: 'bg-purple-100 text-purple-800' },
  { value: 'research', label: 'Research', color: 'bg-indigo-100 text-indigo-800' },
  { value: 'regulation', label: 'Regulation', color: 'bg-red-100 text-red-800' },
  { value: 'product_launch', label: 'Product Launch', color: 'bg-green-100 text-green-800' },
  { value: 'partnership', label: 'Partnership', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'controversy', label: 'Controversy', color: 'bg-orange-100 text-orange-800' },
  { value: 'industry_trend', label: 'Industry Trend', color: 'bg-cyan-100 text-cyan-800' },
  { value: 'technique', label: 'Technique', color: 'bg-teal-100 text-teal-800' },
  { value: 'use_case', label: 'Use Case', color: 'bg-lime-100 text-lime-800' },
  { value: 'other', label: 'Other', color: 'bg-gray-100 text-gray-800' }
]

const PERSPECTIVE_COLORS: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  negative: 'bg-red-100 text-red-700',
  neutral: 'bg-gray-100 text-gray-700',
  analytical: 'bg-blue-100 text-blue-700'
}

export default function StoryArcsPage() {
  const [arcs, setArcs] = useState<StoryArc[]>([])
  const [ads, setAds] = useState<CommonAd[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'arcs' | 'ads'>('arcs')

  // Arc filters
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [digestFilter, setDigestFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')

  // Modal states
  const [expandedArcId, setExpandedArcId] = useState<number | null>(null)
  const [showAdModal, setShowAdModal] = useState(false)
  const [editingAd, setEditingAd] = useState<CommonAd | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ type: 'arc' | 'ad', id: number } | null>(null)
  const [saving, setSaving] = useState(false)

  // Form states
  const [adForm, setAdForm] = useState({
    advertiser_name: '',
    pattern_keywords: [''],
    confidence_threshold: 0.8,
    is_active: true
  })

  useEffect(() => {
    loadData()
  }, [categoryFilter, digestFilter, searchQuery])

  const loadData = async () => {
    try {
      setLoading(true)

      // Build query params
      const params = new URLSearchParams()
      if (categoryFilter) params.set('category', categoryFilter)
      if (digestFilter) params.set('digest', digestFilter)
      if (searchQuery) params.set('search', searchQuery)
      params.set('limit', '100')

      const [arcsRes, adsRes, statsRes] = await Promise.all([
        fetch(`/api/story-arcs/arcs?${params.toString()}`),
        fetch('/api/story-arcs/ads'),
        fetch('/api/story-arcs/stats')
      ])

      if (arcsRes.ok) {
        const data = await arcsRes.json()
        setArcs(data.arcs || [])
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

  const getCategoryColor = (category: string) => {
    return CATEGORY_TYPES.find(c => c.value === category)?.color || 'bg-gray-100 text-gray-800'
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    })
  }

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Arc handlers
  const handleDeleteArc = async (id: number) => {
    try {
      const res = await fetch(`/api/story-arcs/arcs/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setDeleteConfirm(null)
        loadData()
      } else {
        const error = await res.json()
        toast.error('Failed to delete story arc', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to delete arc:', error)
      toast.error('Failed to delete story arc', {
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
        ? `/api/story-arcs/ads/${editingAd.id}`
        : '/api/story-arcs/ads'
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
      const res = await fetch(`/api/story-arcs/ads/${id}`, { method: 'DELETE' })
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
      const res = await fetch(`/api/story-arcs/ads/${ad.id}`, {
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Story Arcs & Ads</h1>
          <p className="mt-1 text-sm text-gray-500">
            Track evolving news narratives and common ad patterns
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
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500">Story Arcs</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">{stats.total_arcs}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500">Total Events</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">{stats.total_events}</div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="text-sm font-medium text-gray-500">Avg Events/Arc</div>
            <div className="mt-1 text-2xl font-semibold text-gray-900">
              {stats.avg_events_per_arc.toFixed(1)}
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
            onClick={() => setActiveTab('arcs')}
            className={`${
              activeTab === 'arcs'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Story Arcs ({arcs.length})
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

      {/* Story Arcs Tab */}
      {activeTab === 'arcs' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Search
                </label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search story arcs..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Category
                </label>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">All Categories</option>
                  {CATEGORY_TYPES.map(cat => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
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
            </div>
          </div>

          {/* Story Arcs List */}
          {loading ? (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
              <p className="mt-2 text-gray-500">Loading story arcs...</p>
            </div>
          ) : arcs.length === 0 ? (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <p className="text-gray-500">No story arcs found</p>
              <p className="mt-2 text-sm text-gray-400">Story arcs are automatically created when episodes are processed</p>
            </div>
          ) : (
            <div className="space-y-4">
              {arcs.map((arc) => (
                <div key={arc.id} className="bg-white rounded-lg shadow overflow-hidden">
                  {/* Arc Header */}
                  <div
                    className="px-6 py-4 cursor-pointer hover:bg-gray-50"
                    onClick={() => setExpandedArcId(expandedArcId === arc.id ? null : arc.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3">
                          <h3 className="text-lg font-medium text-gray-900">{arc.arc_name}</h3>
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getCategoryColor(arc.functional_category)}`}>
                            {arc.functional_category.replace('_', ' ')}
                          </span>
                          {arc.included_in_digest_id && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                              In Digest
                            </span>
                          )}
                        </div>
                        <div className="mt-1 flex items-center space-x-4 text-sm text-gray-500">
                          <span>{arc.event_count} event{arc.event_count !== 1 ? 's' : ''}</span>
                          <span>{arc.source_count} source{arc.source_count !== 1 ? 's' : ''}</span>
                          <span>Started {formatDate(arc.started_at)}</span>
                          <span>Updated {formatDate(arc.last_updated_at)}</span>
                        </div>
                        {arc.digest_topic && (
                          <div className="mt-1 text-sm text-gray-500">
                            Topic: {arc.digest_topic}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center space-x-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setDeleteConfirm({ type: 'arc', id: arc.id })
                          }}
                          className="text-red-600 hover:text-red-800 text-sm"
                        >
                          Delete
                        </button>
                        <svg
                          className={`h-5 w-5 text-gray-400 transition-transform ${expandedArcId === arc.id ? 'rotate-180' : ''}`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Timeline */}
                  {expandedArcId === arc.id && arc.events && arc.events.length > 0 && (
                    <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
                      <h4 className="text-sm font-medium text-gray-700 mb-4">Timeline</h4>
                      <div className="relative">
                        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200"></div>
                        <div className="space-y-4">
                          {arc.events.map((event, idx) => (
                            <div key={event.id} className="relative pl-10">
                              <div className="absolute left-2.5 top-1.5 w-3 h-3 bg-primary-500 rounded-full border-2 border-white"></div>
                              <div className="bg-white p-4 rounded-lg shadow-sm">
                                <div className="flex items-start justify-between">
                                  <div className="flex-1">
                                    <div className="flex items-center space-x-2">
                                      <span className="text-sm font-medium text-gray-900">
                                        {formatDate(event.event_date)}
                                      </span>
                                      {event.perspective && (
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PERSPECTIVE_COLORS[event.perspective] || 'bg-gray-100 text-gray-700'}`}>
                                          {event.perspective}
                                        </span>
                                      )}
                                    </div>
                                    <p className="mt-1 text-sm text-gray-700">{event.event_summary}</p>
                                    {event.key_points && event.key_points.length > 0 && (
                                      <ul className="mt-2 text-xs text-gray-500 list-disc list-inside">
                                        {event.key_points.slice(0, 3).map((point, i) => (
                                          <li key={i}>{point}</li>
                                        ))}
                                      </ul>
                                    )}
                                    {event.source_name && (
                                      <div className="mt-2 text-xs text-gray-400">
                                        Source: {event.source_name}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
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
                    <div>Created: {formatDateTime(ad.created_at)}</div>
                    <div>Updated: {formatDateTime(ad.updated_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
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
              Are you sure you want to delete this {deleteConfirm.type === 'arc' ? 'story arc' : 'ad'}?
              {deleteConfirm.type === 'arc' && ' All associated events will also be deleted.'}
              {' '}This action cannot be undone.
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
                  if (deleteConfirm.type === 'arc') {
                    handleDeleteArc(deleteConfirm.id)
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
    </div>
  )
}
