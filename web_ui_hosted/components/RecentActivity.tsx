'use client'

import { useState, useEffect } from 'react'

interface Activity {
  id: string
  type: string
  message: string
  time: string
  status: string
  conclusion: string
  htmlUrl: string
  createdAt: string
}

export function RecentActivity() {
  const [activities, setActivities] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchActivities()
    // Refresh activities every 30 seconds
    const interval = setInterval(fetchActivities, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchActivities = async () => {
    try {
      const response = await fetch('/api/github/runs')
      if (response.ok) {
        const data = await response.json()
        setActivities(data.activities || [])
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error)
    } finally {
      setLoading(false)
    }
  }

  const getActivityIcon = (type: string, status: string, conclusion: string) => {
    if (status === 'in_progress') {
      return '🔄'
    } else if (status === 'completed' && conclusion === 'success') {
      switch (type) {
        case 'publishing': return '📤'
        case 'pipeline': return '⚙️'
        default: return '✅'
      }
    } else if (status === 'completed' && conclusion === 'failure') {
      return '❌'
    } else {
      switch (type) {
        case 'publishing': return '📡'
        case 'pipeline': return '⚙️'
        default: return '📋'
      }
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>

      <div className="space-y-3">
        {activities.length > 0 ? (
          activities.slice(0, 4).map((activity) => (
            <div key={activity.id} className="flex items-center space-x-3">
              <span className="text-lg">
                {getActivityIcon(activity.type, activity.status, activity.conclusion)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {activity.message}
                </p>
                <p className="text-sm text-gray-500">
                  {activity.time}
                </p>
              </div>
              {activity.htmlUrl && (
                <a
                  href={activity.htmlUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary-600 hover:text-primary-800"
                >
                  View
                </a>
              )}
            </div>
          ))
        ) : (
          <div className="text-sm text-gray-500 text-center py-4">
            No recent activity
          </div>
        )}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <a
          href={`https://github.com/${process.env.NEXT_PUBLIC_GITHUB_REPOSITORY || 'McSchnizzle/podscrape2'}/actions`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-primary-600 hover:text-primary-800"
        >
          View all activity →
        </a>
      </div>
    </div>
  )
}
