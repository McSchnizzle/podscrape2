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
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {topics.map((topic) => (
                    <tr key={topic.id} className="hover:bg-gray-50">
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
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(topic.created_at)}
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
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {ads.map((ad) => (
                <div key={ad.id} className="bg-white p-6 rounded-lg shadow">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{ad.advertiser_name}</h3>
                      <div className="mt-1 flex items-center space-x-2">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          ad.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {ad.is_active ? 'Active' : 'Inactive'}
                        </span>
                        <span className="text-sm text-gray-500">
                          Detected: {ad.detection_count} times
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-gray-500">Confidence</div>
                      <div className="text-lg font-semibold text-gray-900">
                        {(ad.confidence_threshold * 100).toFixed(0)}%
                      </div>
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
    </div>
  )
}
