'use client'

import { Suspense, useState } from 'react'
import { PipelineStatus } from '@/components/PipelineStatus'
import { EnhancedRecentActivity } from '@/components/EnhancedRecentActivity'
import { TranscriptAnalytics } from '@/components/TranscriptAnalytics'
import { PerformanceInsights } from '@/components/PerformanceInsights'

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

      {/* Main Dashboard Grid: Pipeline Status on Left, Everything Else Stacked on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Pipeline Status */}
        <Suspense fallback={<div className="card animate-pulse h-64" />}>
          <PipelineStatus />
        </Suspense>

        {/* Right Column: Recent Activity, Transcript Analytics, Performance Insights */}
        <div className="space-y-6">
          <Suspense fallback={<div className="card animate-pulse h-64" />}>
            <EnhancedRecentActivity />
          </Suspense>

          <Suspense fallback={<div className="card animate-pulse h-64" />}>
            <TranscriptAnalytics />
          </Suspense>

          <Suspense fallback={<div className="card animate-pulse h-64" />}>
            <PerformanceInsights />
          </Suspense>
        </div>
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