'use client'

import { useEffect, useState } from 'react'

interface PipelineStatusPayload {
  stats: {
    episodesProcessedToday: number
    digestsGeneratedToday: number
    lastSuccessfulRun: string | null
    totalEpisodes: number
  }
  pipelineRuns?: Array<{
    id: string
    status?: string
    conclusion?: string
    workflow_name?: string
    trigger?: string
    started_at?: string
    finished_at?: string
  }>
}

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

export default function MaintenancePage() {
  const [status, setStatus] = useState<PipelineStatusPayload | null>(null)
  const [activities, setActivities] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)
  const [triggeringPipeline, setTriggeringPipeline] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [statusResponse, activityResponse] = await Promise.all([
        fetch('/api/pipeline/status'),
        fetch('/api/github/runs')
      ])

      if (statusResponse.ok) {
        setStatus(await statusResponse.json())
      }

      if (activityResponse.ok) {
        const data = await activityResponse.json()
        setActivities(data.activities || [])
      }
    } catch (error) {
      console.error('Maintenance data load error', error)
    } finally {
      setLoading(false)
    }
  }

  const triggerPipeline = async () => {
    setTriggeringPipeline(true)
    try {
      const response = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dryRun: 'false' })
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({ error: 'Failed to trigger pipeline' }))
        alert(data.error)
      } else {
        alert('Full pipeline workflow triggered. Monitor status in Recent Activity.')
      }
    } catch (error) {
      alert('Pipeline trigger failed')
    } finally {
      setTriggeringPipeline(false)
    }
  }

  const formatDate = (value?: string | null) => {
    if (!value) return '—'
    const parsed = new Date(value)
    return isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Maintenance</h1>
        <p className="mt-1 text-gray-600">
          Operations dashboard for Supabase-backed pipeline runs, GitHub workflow activity, and manual controls.
        </p>
      </div>

      <div className="card">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Run Full Pipeline</h2>
            <p className="text-sm text-gray-600">Dispatches the validated GitHub workflow using current Supabase configuration.</p>
          </div>
          <button
            onClick={triggerPipeline}
            disabled={triggeringPipeline}
            className="btn btn-primary"
          >
            {triggeringPipeline ? 'Dispatching...' : 'Trigger Full Pipeline'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">Supabase Pipeline Runs</h2>
            <button onClick={loadData} className="btn-secondary text-sm">Refresh</button>
          </div>
          {loading ? (
            <div className="py-6 text-center text-gray-500">Loading pipeline runs...</div>
          ) : status?.pipelineRuns && status.pipelineRuns.length > 0 ? (
            <div className="space-y-3">
              {status.pipelineRuns.slice(0, 6).map(run => (
                <div key={run.id} className="border border-gray-200 rounded-md p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-800">{run.workflow_name || 'Pipeline Run'}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      run.conclusion === 'success'
                        ? 'bg-success-100 text-success-700'
                        : run.conclusion === 'failure'
                          ? 'bg-error-100 text-error-700'
                          : 'bg-gray-100 text-gray-700'
                    }`}>
                      {run.conclusion || run.status || 'unknown'}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-gray-600">
                    <div>Trigger: {run.trigger || 'manual'}</div>
                    <div>Started: {formatDate(run.started_at)}</div>
                    <div>Finished: {formatDate(run.finished_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-6 text-center text-gray-500 text-sm">No Supabase pipeline runs recorded.</div>
          )}
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">GitHub Workflow Activity</h2>
            <button onClick={loadData} className="btn-secondary text-sm">Refresh</button>
          </div>
          {activities.length === 0 ? (
            <div className="py-6 text-center text-gray-500 text-sm">No recent GitHub Actions runs.</div>
          ) : (
            <div className="space-y-3">
              {activities.slice(0, 6).map(activity => (
                <div key={activity.id} className="border border-gray-200 rounded-md p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-800">{activity.message}</span>
                    <span className="text-xs text-gray-500">{activity.time}</span>
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-gray-600">
                    <span>Status: {activity.status}</span>
                    {activity.htmlUrl && (
                      <a
                        className="text-primary-600 hover:text-primary-700"
                        target="_blank"
                        rel="noopener noreferrer"
                        href={activity.htmlUrl}
                      >
                        View logs →
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-medium text-gray-900 mb-3">System Stats</h2>
        {status ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-md p-4">
              <div className="text-sm text-gray-500">Episodes Processed Today</div>
              <div className="mt-1 text-2xl font-semibold text-gray-900">{status.stats.episodesProcessedToday}</div>
            </div>
            <div className="bg-gray-50 rounded-md p-4">
              <div className="text-sm text-gray-500">Digests Generated Today</div>
              <div className="mt-1 text-2xl font-semibold text-gray-900">{status.stats.digestsGeneratedToday}</div>
            </div>
            <div className="bg-gray-50 rounded-md p-4">
              <div className="text-sm text-gray-500">Last Successful Run</div>
              <div className="mt-1 text-lg text-gray-900">{formatDate(status.stats.lastSuccessfulRun)}</div>
            </div>
            <div className="bg-gray-50 rounded-md p-4">
              <div className="text-sm text-gray-500">Total Episodes</div>
              <div className="mt-1 text-2xl font-semibold text-gray-900">{status.stats.totalEpisodes}</div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-500">Pipeline statistics unavailable.</div>
        )}
      </div>
    </div>
  )
}
