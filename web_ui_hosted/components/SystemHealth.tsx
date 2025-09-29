'use client'

import { useState, useEffect } from 'react'

interface HealthStatus {
  database: 'healthy' | 'error'
  environment: string
  timestamp: string
}

export function SystemHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSystemHealth()
    // Refresh every 30 seconds
    const interval = setInterval(fetchSystemHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchSystemHealth = async () => {
    try {
      const response = await fetch('/api/health')
      if (response.ok) {
        const data = await response.json()
        setHealth({
          database: data.database === 'connected' ? 'healthy' : 'error',
          environment: data.environment || 'unknown',
          timestamp: data.timestamp
        })
      } else {
        setHealth({
          database: 'error',
          environment: 'unknown',
          timestamp: new Date().toISOString()
        })
      }
    } catch (error) {
      console.error('Failed to fetch system health:', error)
      setHealth({
        database: 'error',
        environment: 'unknown',
        timestamp: new Date().toISOString()
      })
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">System Health</h3>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  if (!health) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">System Health</h3>
        <div className="text-red-600">Failed to load system health</div>
      </div>
    )
  }

  const statusColors = {
    healthy: 'status-success',
    warning: 'status-warning',
    error: 'status-error'
  }

  return (
    <div className="card">
      <h3 className="text-lg font-medium text-gray-900 mb-4">System Health</h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="text-center">
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusColors[health.database]}`}>
            Database: {health.database}
          </div>
        </div>

        <div className="text-center">
          <div className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium status-success">
            Environment: {health.environment}
          </div>
        </div>

        <div className="text-center">
          <div className="text-sm text-gray-500">
            Last check: {new Date(health.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  )
}