'use client'

import { useState, useEffect } from 'react'

interface DashboardResponse {
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
  timeline?: Array<{ id: string; phase: string; message: string; level: string; timestamp: string }>
  queues?: {
    awaitingScoring: any[]
    awaitingDigest: any[]
    recentDigests: any[]
    recentEpisodes: any[]
  }
}

const timeAgo = (dateString?: string | null) => {
  if (!dateString) return 'Never'
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor(diffMs / (1000 * 60))

  if (diffHours > 24) {
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
  }
  if (diffHours > 0) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  }
  if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`
  }
  return 'Just now'
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

export function PipelineStatus() {
  const [status, setStatus] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)

  useEffect(() => {
    fetchStatus()
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
        body: JSON.stringify({ daysBack: '7' })
      })

      if (response.ok) {
        alert('Pipeline triggered successfully! Check Recent Activity for progress.')
        setTimeout(fetchStatus, 2000)
      } else {
        const error = await response.json()
        alert(`Failed to trigger pipeline: ${error.error}`)
      }
    } catch (error) {
      console.error('Pipeline trigger error', error)
      alert('Failed to trigger pipeline')
    } finally {
      setTriggering(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Pipeline Status</h3>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded" />
          <div className="h-4 bg-gray-200 rounded" />
          <div className="h-4 bg-gray-200 rounded" />
        </div>
      </div>
    )
  }

  const backlog = status?.backlog ?? { awaitingScoring: 0, awaitingDigest: 0, awaitingTts: 0, awaitingPublish: 0 }
  const queues = status?.queues ?? { awaitingScoring: [], awaitingDigest: [], recentDigests: [], recentEpisodes: [] }

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Pipeline Status</h3>
          <p className="text-sm text-gray-500">Latest run {timeAgo(status?.runSummary?.startedAt)}</p>
        </div>
        <button
          onClick={triggerPipeline}
          disabled={triggering}
          className="btn btn-primary whitespace-nowrap"
        >
          {triggering ? 'Triggering…' : 'Run Pipeline'}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard label="Episodes Today" value={status?.stats.episodesProcessedToday ?? 0} />
        <SummaryCard label="Digests Today" value={status?.stats.digestsGeneratedToday ?? 0} />
        <SummaryCard label="Awaiting Scoring" value={backlog.awaitingScoring} muted />
        <SummaryCard label="Awaiting Digest" value={backlog.awaitingDigest} muted />
        <SummaryCard label="Awaiting TTS" value={backlog.awaitingTts} muted />
        <SummaryCard label="Awaiting Publish" value={backlog.awaitingPublish} muted />
      </div>

      {status?.runSummary && (
        <div className="border border-gray-200 rounded-lg p-5 space-y-4">
          <div className="space-y-3">
            <div>
              <div className="text-xs uppercase text-gray-500">Current Run</div>
              <div className="text-sm font-semibold text-gray-900">Run {status.runSummary.runId}</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-600">
              <div>
                <span className="font-medium text-gray-700">Started:</span>
                <div className="mt-0.5">{new Date(status.runSummary.startedAt).toLocaleString()}</div>
              </div>
              <div>
                <span className="font-medium text-gray-700">Duration:</span>
                <div className="mt-0.5">
                  {status.runSummary.durationSeconds ? `${Math.round(status.runSummary.durationSeconds / 60)} min` : '—'}
                </div>
              </div>
            </div>

            <div className="flex gap-4 text-sm pt-2 border-t border-gray-100">
              <span className="text-amber-600">⚠️ {status.runSummary.warnings} warnings</span>
              <span className={status.runSummary.errors > 0 ? 'text-red-600' : 'text-gray-600'}>
                ❌ {status.runSummary.errors} errors
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {status.runSummary.phases.map((phase) => (
              <div key={`${phase.phase}-${phase.timestamp}`} className="flex items-start space-x-3 border border-gray-100 rounded-md p-3">
                <span className="text-lg">{phaseIcon(phase.phase)}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-800 capitalize">{phase.phase}</span>
                    <span className="text-xs text-gray-500">{new Date(phase.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-sm text-gray-600 truncate" title={phase.message}>{phase.message}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(queues.awaitingScoring.length > 0 || queues.awaitingDigest.length > 0 || queues.recentDigests.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <QueueList title="Awaiting Scoring" items={queues.awaitingScoring} empty="No episodes waiting to be scored." />
          <QueueList title="Awaiting Digest" items={queues.awaitingDigest} empty="No scored episodes waiting for digest." />
          <QueueList title="Recent Digests" items={queues.recentDigests} empty="No recent digests." digest />
        </div>
      )}

      {status?.timeline && status.timeline.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Latest Run Timeline</h4>
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
            {status.timeline.slice().reverse().map((entry) => (
              <div key={entry.id} className="text-sm text-gray-700 flex items-start space-x-2">
                <span>{phaseIcon(entry.phase)}</span>
                <div>
                  <div className="font-medium text-gray-800 capitalize">{entry.phase}</div>
                  <div className="text-xs text-gray-500">{new Date(entry.timestamp).toLocaleTimeString()} • {entry.level}</div>
                  <div className="text-xs text-gray-600" title={entry.message}>{entry.message}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

interface SummaryCardProps {
  label: string
  value: number
  muted?: boolean
}

export function SummaryCard({ label, value, muted }: SummaryCardProps) {
  return (
    <div className={`rounded-lg p-3 ${muted ? 'bg-white border border-gray-200' : 'bg-gray-50'}`}>
      <div className="text-xs uppercase text-gray-500">{label}</div>
      <div className="text-lg font-semibold text-gray-900">{value}</div>
    </div>
  )
}

interface QueueListProps {
  title: string
  items: any[]
  empty: string
  digest?: boolean
}

function QueueList({ title, items, empty, digest = false }: QueueListProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-3 space-y-2">
      <div className="text-sm font-semibold text-gray-800">{title}</div>
      {items.length === 0 ? (
        <div className="text-xs text-gray-500">{empty}</div>
      ) : (
        <ul className="space-y-2 text-sm text-gray-700">
          {items.slice(0, 4).map((item) => (
            <li key={item.id} className="border border-gray-100 rounded-md px-2 py-2">
              <div className="font-medium text-gray-800 truncate">{digest ? item.topic : item.title}</div>
              <div className="text-xs text-gray-500">
                {digest
                  ? `Status: ${item.status}`
                  : item.feeds?.title
                    ? `Feed: ${item.feeds.title}`
                    : ''}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
