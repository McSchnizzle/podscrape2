'use client'

import { useEffect, useState } from 'react'

interface ActivityItem {
  id: number
  title: string
  status: string
  timestamp: string
  score: number
  scores?: Record<string, number>
  digests?: Array<{ topic: string; score: number; publishedAt?: string }>
  type: string
}

export function EnhancedRecentActivity() {
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchActivities()
    // Refresh every 30 seconds
    const interval = setInterval(fetchActivities, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchActivities = async () => {
    try {
      const response = await fetch('/api/dashboard/analytics')
      if (response.ok) {
        const data = await response.json()
        setActivities(data.recentActivity || [])
      }
    } catch (error) {
      console.error('Failed to load recent activity:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const badges: Record<string, { color: string; text: string }> = {
      discovered: { color: 'bg-blue-100 text-blue-800', text: 'Discovered' },
      downloaded: { color: 'bg-purple-100 text-purple-800', text: 'Downloaded' },
      transcribed: { color: 'bg-indigo-100 text-indigo-800', text: 'Transcribed' },
      scored: { color: 'bg-yellow-100 text-yellow-800', text: 'Scored' },
      digested: { color: 'bg-orange-100 text-orange-800', text: 'Digested' },
      published: { color: 'bg-green-100 text-green-800', text: 'Published' },
      not_relevant: { color: 'bg-gray-100 text-gray-600', text: 'Not Relevant' },
      failed: { color: 'bg-red-100 text-red-800', text: 'Failed' }
    }

    const badge = badges[status] || { color: 'bg-gray-100 text-gray-600', text: status }

    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-full ${badge.color}`}>
        {badge.text}
      </span>
    )
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor(diff / (1000 * 60))

    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    return date.toLocaleDateString()
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
        <div className="space-y-3">
          {[...Array(5)].map((_, idx) => (
            <div key={idx} className="h-16 animate-pulse bg-gray-100 rounded-md" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">Recent Activity</h3>
        <button
          onClick={fetchActivities}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ↻ Refresh
        </button>
      </div>

      {activities.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No recent activity</p>
          <p className="text-sm mt-1">Episodes will appear here as they're processed</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {activities.map((activity) => (
            <div
              key={activity.id}
              className="flex items-start justify-between p-3 border border-gray-100 rounded-lg hover:bg-gray-50 transition"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {activity.title}
                </p>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  {getStatusBadge(activity.status)}
                  <span className="text-xs text-gray-400">
                    {formatTimestamp(activity.timestamp)}
                  </span>
                </div>

                {/* Topic scores breakdown */}
                {activity.scores && Object.keys(activity.scores).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {Object.entries(activity.scores)
                      .filter(([_, score]) => score > 0)
                      .sort(([_, a], [__, b]) => b - a)
                      .map(([topic, score]) => (
                        <span
                          key={topic}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700"
                        >
                          {topic}: {score.toFixed(2)}
                        </span>
                      ))}
                  </div>
                )}

                {/* Digest inclusion info */}
                {activity.digests && activity.digests.length > 0 && (
                  <div className="mt-1 text-xs text-gray-600">
                    📝 Included in: {activity.digests.map((d: any) => {
                      const digestDate = d.publishedAt
                        ? new Date(d.publishedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                        : null
                      return digestDate ? `${d.topic} (${digestDate})` : d.topic
                    }).join(', ')}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
