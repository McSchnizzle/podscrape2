'use client'

import { Suspense, useState } from 'react'
import { WorkflowAnalysis } from '@/components/WorkflowAnalysis'
import { EnhancedRecentActivity } from '@/components/EnhancedRecentActivity'
import { TranscriptAnalytics } from '@/components/TranscriptAnalytics'
import { PerformanceInsights } from '@/components/PerformanceInsights'
import { ErrorAnalytics } from '@/components/ErrorAnalytics'
import { toast } from '@/components/Toast'

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
        toast.success('Pipeline triggered successfully!', {
          description: 'Check Recent Activity for progress.',
          action: {
            label: 'View Logs',
            onClick: () => window.location.href = '/logs'
          },
          duration: 6000
        })
      } else {
        const errorData = await response.json()
        toast.error('Failed to trigger pipeline', {
          description: errorData.error,
          duration: 8000
        })
      }
    } catch (err) {
      toast.error('Failed to trigger full pipeline', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
      console.error('Pipeline trigger error:', err)
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
        toast.success('Publishing workflow triggered!', {
          description: 'Check Recent Activity for progress.',
          action: {
            label: 'View Logs',
            onClick: () => window.location.href = '/logs'
          },
          duration: 6000
        })
      } else {
        const errorData = await response.json()
        toast.error('Failed to trigger publishing', {
          description: errorData.error,
          duration: 8000
        })
      }
    } catch (err) {
      toast.error('Failed to trigger publishing', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
      console.error('Publishing trigger error:', err)
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

      {/* Workflow Analysis - Full Width at Top */}
      <Suspense fallback={<div className="card animate-pulse h-48" />}>
        <WorkflowAnalysis />
      </Suspense>

      {/* Main Dashboard Grid: Two columns with analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Recent Activity, Transcript Analytics */}
        <div className="space-y-6">
          <Suspense fallback={<div className="card animate-pulse h-64" />}>
            <EnhancedRecentActivity />
          </Suspense>

          <Suspense fallback={<div className="card animate-pulse h-64" />}>
            <TranscriptAnalytics />
          </Suspense>
        </div>

        {/* Right Column: Performance Insights, Error Analytics */}
        <div className="space-y-6">
          <Suspense fallback={<div className="card animate-pulse h-64" />}>
            <PerformanceInsights />
          </Suspense>

          <Suspense fallback={<div className="card animate-pulse h-64" />}>
            <ErrorAnalytics />
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