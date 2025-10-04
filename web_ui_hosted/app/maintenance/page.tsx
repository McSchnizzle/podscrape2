'use client'

import { useEffect, useState } from 'react'

import { SummaryCard } from '@/components/PipelineStatus'

interface MaintenanceStatus {
  stats: {
    episodesProcessedToday: number
    digestsGeneratedToday: number
    lastSuccessfulRun: string | null
    totalEpisodes: number
  }
  backlog: {
    awaitingScoring: number
    awaitingDigest: number
    awaitingTts: number
    awaitingPublish: number
  }
  runSummary?: {
    runId: string
    startedAt: string
    finishedAt: string | null
    durationSeconds: number | null
    warnings: number
    errors: number
    phases: Array<{ phase: string; message: string; level: string; timestamp: string }>
  } | null
  recentRuns?: Array<{ runId: string; startedAt: string; finishedAt: string | null; durationSeconds: number | null }>
}

interface ActivityEntry {
  id: string
  phase: string
  message: string
  level: string
  time: string
  timestamp: string
  runId: string
}

const phaseIcon = (phase: string) => {
  switch (phase) {
    case 'discovery': return '🔍'
    case 'audio': return '🎧'
    case 'digest': return '📝'
    case 'tts': return '🎙️'
    case 'publishing': return '📡'
    case 'retention': return '🧹'
    default: return '⚙️'
  }
}

const formatDate = (value?: string | null) => {
  if (!value) return '—'
  const parsed = new Date(value)
  return isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

export default function MaintenancePage() {
  const [status, setStatus] = useState<MaintenanceStatus | null>(null)
  const [activities, setActivities] = useState<ActivityEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [triggeringPipeline, setTriggeringPipeline] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [statusResponse, activityResponse] = await Promise.all([
        fetch('/api/pipeline/status'),
        fetch('/api/pipeline/activity')
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
        setTimeout(loadData, 2000)
      }
    } catch (error) {
      alert('Pipeline trigger failed')
    } finally {
      setTriggeringPipeline(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Maintenance</h1>
        <p className="mt-1 text-gray-600">
          Operations dashboard for Supabase-backed pipeline runs and manual controls.
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
            {triggeringPipeline ? 'Dispatching…' : 'Trigger Full Pipeline'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">Pipeline Backlog</h2>
            <button onClick={loadData} className="btn-secondary text-sm">Refresh</button>
          </div>
          {status ? (
            <div className="grid grid-cols-2 gap-4">
              <BacklogCard label="Awaiting Scoring" value={status.backlog.awaitingScoring} icon="📝" />
              <BacklogCard label="Awaiting Digest" value={status.backlog.awaitingDigest} icon="🧠" />
              <BacklogCard label="Awaiting TTS" value={status.backlog.awaitingTts} icon="🎙️" />
              <BacklogCard label="Awaiting Publish" value={status.backlog.awaitingPublish} icon="📡" />
            </div>
          ) : (
            <div className="py-6 text-center text-gray-500">Backlog metrics unavailable.</div>
          )}
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-gray-900">Latest Pipeline Activity</h2>
            <button onClick={loadData} className="btn-secondary text-sm">Refresh</button>
          </div>
          {loading ? (
            <div className="py-6 text-center text-gray-500">Loading activity…</div>
          ) : activities.length > 0 ? (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {activities.map((activity) => (
                <div key={activity.id} className="border border-gray-200 rounded-md p-3 flex items-start space-x-3">
                  <span>{phaseIcon(activity.phase)}</span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold text-gray-800 capitalize">{activity.phase}</span>
                      <span className="text-xs text-gray-500">{activity.time}</span>
                    </div>
                    <div className="text-xs text-gray-600" title={activity.message}>{activity.message}</div>
                    <div className="text-xs text-gray-400 mt-1">Run {activity.runId} • Level {activity.level}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-6 text-center text-gray-500 text-sm">No recent pipeline activity.</div>
          )}
        </div>
      </div>

      <div className="card space-y-4">
        <h2 className="text-lg font-medium text-gray-900">System Stats</h2>
        {status ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <SummaryCard label="Episodes Today" value={status.stats.episodesProcessedToday} />
            <SummaryCard label="Digests Today" value={status.stats.digestsGeneratedToday} />
            <SummaryCard label="Total Episodes" value={status.stats.totalEpisodes} />
            <div className="border border-gray-200 rounded-md p-4">
              <div className="text-sm font-semibold text-gray-800">Last Successful Run</div>
              <div className="mt-2 text-sm text-gray-600">{formatDate(status.stats.lastSuccessfulRun)}</div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-gray-500">Pipeline statistics unavailable.</div>
        )}

        {status?.runSummary && (
          <div className="border border-gray-200 rounded-md p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-gray-700">
              <span className="font-semibold text-gray-900">Run {status.runSummary.runId}</span>
              <span>Started: {formatDate(status.runSummary.startedAt)}</span>
              <span>Duration: {status.runSummary.durationSeconds ? `${Math.round(status.runSummary.durationSeconds / 60)} min` : '—'}</span>
              <span className="text-amber-600">Warnings: {status.runSummary.warnings}</span>
              <span className={status.runSummary.errors > 0 ? 'text-red-600' : 'text-gray-600'}>Errors: {status.runSummary.errors}</span>
            </div>
            <div className="space-y-2">
              {status.runSummary.phases.map((phase) => (
                <div key={`${phase.phase}-${phase.timestamp}`} className="border border-gray-100 rounded-md px-3 py-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-gray-800 capitalize">{phase.phase}</span>
                    <span className="text-xs text-gray-500">{new Date(phase.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-xs text-gray-600" title={phase.message}>{phase.message}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function BacklogCard({ label, value, icon }: { label: string; value: number; icon: string }) {
  return (
    <div className="border border-gray-200 rounded-md p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-800">{label}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <div className="mt-2 text-2xl font-bold text-gray-900">{value}</div>
    </div>
  )
}
