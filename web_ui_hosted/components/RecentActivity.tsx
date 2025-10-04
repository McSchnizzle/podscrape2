'use client'

import { useState, useEffect } from 'react'

interface Activity {
  id: string
  phase: string
  message: string
  level: string
  time: string
  timestamp: string
  runId: string
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
      const response = await fetch('/api/pipeline/activity')
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

  const getActivityIcon = (phase: string, level: string) => {
    if (level === 'ERROR' || level === 'CRITICAL') {
      return '❌'
    }
    if (level === 'WARNING') {
      return '⚠️'
    }
    if (phase === 'publishing') {
      return '📡'
    }
    if (phase === 'retention') {
      return '🧹'
    }
    if (phase === 'tts') {
      return '🎙️'
    }
    if (phase === 'digest') {
      return '📝'
    }
    if (phase === 'audio') {
      return '🎧'
    }
    if (phase === 'discovery') {
      return '🔍'
    }
    return '⚙️'
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
          activities.slice(0, 6).map((activity) => (
            <div key={activity.id} className="flex items-center space-x-3">
              <span className="text-lg">
                {getActivityIcon(activity.phase, activity.level)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {activity.message}
                </p>
                <p className="text-sm text-gray-500">
                  {activity.time} • Run {activity.runId}
                </p>
              </div>
            </div>
          ))
        ) : (
          <div className="text-sm text-gray-500 text-center py-4">
            No recent activity
          </div>
        )}
      </div>

    </div>
  )
}
