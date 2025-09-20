'use client'

import { useState, useEffect } from 'react'

interface PipelineStatus {
  lastRun: {
    id: number
    status: string
    conclusion: string
    createdAt: string
    updatedAt: string
    workflowName: string
    htmlUrl: string
  } | null
  stats: {
    episodesProcessedToday: number
    digestsGeneratedToday: number
    lastSuccessfulRun: string | null
    totalEpisodes: number
  }
}

export function PipelineStatus() {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)

  useEffect(() => {
    fetchStatus()
    // Refresh status every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/pipeline/status')
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
      }
    } catch (error) {
      console.error('Failed to fetch pipeline status:', error)
    } finally {
      setLoading(false)
    }
  }

  const triggerPipeline = async () => {
    setTriggering(true)
    try {
      const response = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ daysBack: "7" })
      })

      if (response.ok) {
        const data = await response.json()
        alert('Pipeline triggered successfully! Check the workflow page for progress.')
        // Refresh status after a short delay
        setTimeout(fetchStatus, 2000)
      } else {
        const error = await response.json()
        alert(`Failed to trigger pipeline: ${error.error}`)
      }
    } catch (error) {
      alert('Failed to trigger pipeline')
      console.error('Pipeline trigger error:', error)
    } finally {
      setTriggering(false)
    }
  }

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffMinutes = Math.floor(diffMs / (1000 * 60))

    if (diffHours > 24) {
      const diffDays = Math.floor(diffHours / 24)
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
    } else if (diffHours > 0) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
    } else if (diffMinutes > 0) {
      return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`
    } else {
      return 'Just now'
    }
  }

  const getStatusBadge = (status: string, conclusion: string) => {
    if (status === 'in_progress') {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">Running</span>
    } else if (status === 'completed') {
      if (conclusion === 'success') {
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium status-success">Success</span>
      } else if (conclusion === 'failure') {
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">Failed</span>
      } else {
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{conclusion}</span>
      }
    } else {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{status}</span>
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Pipeline Status</h3>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded"></div>
          <div className="h-4 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Pipeline Status</h3>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Last Run</span>
          <span className="text-sm text-gray-500">
            {status?.lastRun ? formatTimeAgo(status.lastRun.createdAt) : 'Never'}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Status</span>
          {status?.lastRun ? (
            getStatusBadge(status.lastRun.status, status.lastRun.conclusion)
          ) : (
            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">Unknown</span>
          )}
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Episodes Today</span>
          <span className="text-sm text-gray-500">{status?.stats.episodesProcessedToday || 0}</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Total Episodes</span>
          <span className="text-sm text-gray-500">{status?.stats.totalEpisodes || 0}</span>
        </div>
      </div>

      <div className="mt-6 pt-4 border-t border-gray-200">
        <button
          onClick={triggerPipeline}
          disabled={triggering}
          className="w-full btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {triggering ? 'Triggering...' : 'Run Pipeline Now'}
        </button>
      </div>
    </div>
  )
}