'use client'

import { useState, useEffect } from 'react'

interface ErrorAnalyticsData {
  totalErrors: number
  byCategory: Record<string, number>
  byPhase: Record<string, number>
  bySeverity: Record<string, number>
  byDay: Record<string, number>
  problematicFeeds: Array<{
    feedId?: number
    feedUrl?: string
    title: string
    errorCount: number
    lastError: string
  }>
  unresolvedErrors: Array<{
    id: number
    category: string
    phase: string
    severity: string
    summary: string
    occurredAt: string
    feedUrl?: string
  }>
  trend: {
    direction: 'up' | 'down' | 'stable'
    percent: number
    recentCount: number
    previousCount: number
  }
  analyzedAt: string
}

const categoryLabels: Record<string, string> = {
  feed_error: 'Feed Issues',
  api_error: 'API Errors',
  tts_error: 'TTS Errors',
  transcription_error: 'Transcription',
  scoring_error: 'Scoring',
  script_error: 'Script Gen',
  publishing_error: 'Publishing',
  database_error: 'Database',
  system_error: 'System',
  unknown: 'Unknown'
}

const severityConfig: Record<string, { bg: string, text: string, icon: string }> = {
  warning: { bg: 'bg-yellow-100', text: 'text-yellow-800', icon: '⚠️' },
  error: { bg: 'bg-red-100', text: 'text-red-800', icon: '❌' },
  critical: { bg: 'bg-red-200', text: 'text-red-900', icon: '🚨' }
}

const timeAgo = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) {
    return `${diffDays}d ago`
  }
  if (diffHours > 0) {
    return `${diffHours}h ago`
  }
  return 'Just now'
}

export function ErrorAnalytics() {
  const [data, setData] = useState<ErrorAnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [daysBack, setDaysBack] = useState(30)

  useEffect(() => {
    fetchAnalytics()
  }, [daysBack])

  const fetchAnalytics = async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/workflow/errors?days=${daysBack}`)
      if (!response.ok) throw new Error('Failed to fetch')
      const result = await response.json()
      setData(result)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch error analytics:', err)
      setError('Failed to load error analytics')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Error Patterns</h3>
        <div className="animate-pulse space-y-3">
          <div className="h-16 bg-gray-200 rounded" />
          <div className="h-4 bg-gray-200 rounded w-3/4" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card border-red-200 bg-red-50">
        <h3 className="text-lg font-medium text-red-800 mb-2">Error Analytics</h3>
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  if (!data || data.totalErrors === 0) {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">Error Patterns</h3>
          <select
            value={daysBack}
            onChange={(e) => setDaysBack(parseInt(e.target.value))}
            className="text-xs border border-gray-300 rounded px-2 py-1"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
          </select>
        </div>
        <div className="text-center py-8 text-gray-500">
          <span className="text-4xl mb-2 block">✅</span>
          <p>No errors recorded in the last {daysBack} days</p>
        </div>
      </div>
    )
  }

  const trendIcon = data.trend.direction === 'up' ? '📈' : data.trend.direction === 'down' ? '📉' : '➡️'
  const trendColor = data.trend.direction === 'up' ? 'text-red-600' : data.trend.direction === 'down' ? 'text-green-600' : 'text-gray-600'

  // Sort categories by count
  const sortedCategories = Object.entries(data.byCategory)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Error Patterns</h3>
        <select
          value={daysBack}
          onChange={(e) => setDaysBack(parseInt(e.target.value))}
          className="text-xs border border-gray-300 rounded px-2 py-1"
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-2xl font-semibold text-gray-900">{data.totalErrors}</div>
          <div className="text-xs text-gray-500">Total Errors</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className={`text-2xl font-semibold ${trendColor}`}>
            {trendIcon} {data.trend.percent}%
          </div>
          <div className="text-xs text-gray-500">vs Previous Week</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-3">
          <div className="text-2xl font-semibold text-amber-600">
            {data.unresolvedErrors.length}
          </div>
          <div className="text-xs text-gray-500">Unresolved</div>
        </div>
      </div>

      {/* Error Categories */}
      <div className="border-t border-gray-200 pt-4">
        <h4 className="text-sm font-medium text-gray-700 mb-2">By Category</h4>
        <div className="space-y-2">
          {sortedCategories.map(([category, count]) => {
            const percentage = Math.round((count / data.totalErrors) * 100)
            return (
              <div key={category} className="flex items-center">
                <div className="w-24 text-xs text-gray-600 truncate">
                  {categoryLabels[category] || category}
                </div>
                <div className="flex-1 mx-2">
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${category === 'feed_error' ? 'bg-amber-400' : category.includes('error') ? 'bg-red-400' : 'bg-blue-400'}`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
                <div className="w-12 text-right text-xs text-gray-500">{count}</div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Problematic Feeds */}
      {data.problematicFeeds.length > 0 && (
        <div className="border-t border-gray-200 pt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Problematic Feeds</h4>
          <div className="space-y-1">
            {data.problematicFeeds.slice(0, 5).map((feed, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm py-1">
                <span className="text-gray-700 truncate flex-1 pr-2">{feed.title}</span>
                <div className="flex items-center space-x-2">
                  <span className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-xs">
                    {feed.errorCount} errors
                  </span>
                  <span className="text-xs text-gray-400">{timeAgo(feed.lastError)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Unresolved Errors */}
      {data.unresolvedErrors.length > 0 && (
        <div className="border-t border-gray-200 pt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Recent Unresolved</h4>
          <div className="space-y-2">
            {data.unresolvedErrors.slice(0, 3).map((err) => {
              const sevConfig = severityConfig[err.severity] || severityConfig.error
              return (
                <div key={err.id} className={`${sevConfig.bg} rounded p-2`}>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-1">
                      <span className="text-xs">{sevConfig.icon}</span>
                      <span className={`text-xs font-medium ${sevConfig.text}`}>
                        {categoryLabels[err.category] || err.category}
                      </span>
                      <span className="text-xs text-gray-500">in {err.phase}</span>
                    </div>
                    <span className="text-xs text-gray-400">{timeAgo(err.occurredAt)}</span>
                  </div>
                  <p className="text-xs text-gray-700 mt-1 line-clamp-2">{err.summary}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Last Updated */}
      <div className="text-xs text-gray-400 text-right pt-2 border-t border-gray-100">
        Updated: {new Date(data.analyzedAt).toLocaleString()}
      </div>
    </div>
  )
}
