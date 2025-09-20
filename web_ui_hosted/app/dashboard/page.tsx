'use client'

import { Suspense, useState } from 'react'
import { SystemHealth } from '@/components/SystemHealth'
import { PipelineStatus } from '@/components/PipelineStatus'
import { RecentActivity } from '@/components/RecentActivity'

export default function DashboardPage() {
  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [publishingLoading, setPublishingLoading] = useState(false)

  const triggerFullPipeline = async () => {
    setPipelineLoading(true)
    try {
      const response = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ daysBack: "7", phaseLimit: "publishing" })
      })

      if (response.ok) {
        alert('Full pipeline triggered successfully! Check the Recent Activity section for progress.')
      } else {
        const error = await response.json()
        alert(`Failed to trigger pipeline: ${error.error}`)
      }
    } catch (error) {
      alert('Failed to trigger full pipeline')
      console.error('Pipeline trigger error:', error)
    } finally {
      setPipelineLoading(false)
    }
  }

  const triggerPublishing = async () => {
    setPublishingLoading(true)
    try {
      const response = await fetch('/api/pipeline/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ daysBack: "7" })
      })

      if (response.ok) {
        alert('Publishing workflow triggered successfully! Check the Recent Activity section for progress.')
      } else {
        const error = await response.json()
        alert(`Failed to trigger publishing: ${error.error}`)
      }
    } catch (error) {
      alert('Failed to trigger publishing')
      console.error('Publishing trigger error:', error)
    } finally {
      setPublishingLoading(false)
    }
  }

  const viewLogs = () => {
    window.location.href = '/logs'
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of your podcast digest system
        </p>
      </div>

      {/* System Health */}
      <Suspense fallback={<div className="card animate-pulse h-32" />}>
        <SystemHealth />
      </Suspense>

      {/* Pipeline Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Suspense fallback={<div className="card animate-pulse h-64" />}>
          <PipelineStatus />
        </Suspense>

        <Suspense fallback={<div className="card animate-pulse h-64" />}>
          <RecentActivity />
        </Suspense>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={triggerFullPipeline}
            disabled={pipelineLoading}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {pipelineLoading ? 'Triggering...' : 'Run Full Pipeline'}
          </button>
          <button
            onClick={triggerPublishing}
            disabled={publishingLoading}
            className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {publishingLoading ? 'Triggering...' : 'Publishing Only'}
          </button>
          <button
            onClick={viewLogs}
            className="btn btn-secondary"
          >
            View Logs
          </button>
          <a href="/feeds" className="btn btn-secondary">
            Manage Feeds
          </a>
          <a href="/settings" className="btn btn-secondary">
            Settings
          </a>
        </div>
      </div>
    </div>
  )
}