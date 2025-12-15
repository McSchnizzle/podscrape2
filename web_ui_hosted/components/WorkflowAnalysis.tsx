'use client'

import { useState, useEffect, useRef } from 'react'

interface NoDigestReason {
  topic: string
  reason: string
  details: string
  episodesFound?: number
  minRequired?: number
  threshold?: number
}

interface WorkflowRun {
  workflowId: string
  startedAt: string
  finishedAt: string
  durationSeconds: number
  status: 'success' | 'failure' | 'partial' | 'no_output'
  episodesDiscovered: number
  episodesTranscribed: number
  episodesScored: number
  digestsGenerated: number
  audioFilesCreated: number
  topicsCovered: string[]
  noDigestReasons: NoDigestReason[]
  summary: string
  errorCount: number
  warningCount: number
}

interface EpisodeBelowThreshold {
  id: number
  title: string
  scores: Record<string, number>
  highestScore: number
  highestTopic: string
  threshold: number
  meetsThreshold: boolean
}

interface WorkflowAnalysisData {
  workflows: WorkflowRun[]
  currentState: {
    scoredEpisodesWaiting: number
    episodesBelowThreshold: EpisodeBelowThreshold[]
    scoreThreshold: number
    minEpisodesRequired: number
  }
  analyzedAt: string
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

const formatDuration = (seconds: number): string => {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`
}

const statusConfig = {
  success: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    icon: '✅',
    label: 'Success',
    textColor: 'text-green-800'
  },
  partial: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    icon: '⚠️',
    label: 'Partial',
    textColor: 'text-yellow-800'
  },
  no_output: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    icon: '📭',
    label: 'No Output',
    textColor: 'text-amber-800'
  },
  failure: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    icon: '❌',
    label: 'Failed',
    textColor: 'text-red-800'
  }
}

export function WorkflowAnalysis() {
  const [data, setData] = useState<WorkflowAnalysisData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const hasDataRef = useRef(false)

  useEffect(() => {
    fetchAnalysis(true)
    const interval = setInterval(() => fetchAnalysis(false), 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  const fetchAnalysis = async (isInitialLoad: boolean) => {
    try {
      const response = await fetch('/api/workflow/analysis?hours=48')
      if (!response.ok) throw new Error('Failed to fetch')
      const result = await response.json()
      setData(result)
      setError(null)
      setLastUpdated(new Date())
      hasDataRef.current = true
    } catch (err) {
      console.error('Failed to fetch workflow analysis:', err)
      // Only set error if we don't have existing data (preserve data during refresh failures)
      if (!hasDataRef.current) {
        setError('Failed to load workflow analysis')
      }
      // Don't overwrite good data with error state during refresh
    } finally {
      if (isInitialLoad) {
        setLoading(false)
      }
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Workflow Analysis</h3>
        <div className="animate-pulse space-y-4">
          <div className="h-20 bg-gray-200 rounded" />
          <div className="h-4 bg-gray-200 rounded w-3/4" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card border-red-200 bg-red-50">
        <h3 className="text-lg font-medium text-red-800 mb-2">Workflow Analysis Error</h3>
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  if (!data || data.workflows.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Workflow Analysis</h3>
        <p className="text-gray-500">No workflow runs found in the last 48 hours.</p>
      </div>
    )
  }

  const latestWorkflow = data.workflows[0]
  const config = statusConfig[latestWorkflow.status]

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">Recent Workflow Analysis</h3>
        <span className="text-xs text-gray-500">Last 48 hours</span>
      </div>

      {/* Latest Workflow Summary */}
      <div className={`rounded-lg p-4 ${config.bg} ${config.border} border`}>
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center space-x-2">
            <span className="text-xl">{config.icon}</span>
            <div>
              <div className={`font-semibold ${config.textColor}`}>
                {new Date(latestWorkflow.startedAt).toLocaleDateString()} {new Date(latestWorkflow.startedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
              </div>
              <div className="text-xs text-gray-600">
                {timeAgo(latestWorkflow.startedAt)} · {formatDuration(latestWorkflow.durationSeconds)}
              </div>
            </div>
          </div>
          <span className={`px-2 py-1 rounded text-xs font-medium ${config.bg} ${config.textColor}`}>
            {config.label}
          </span>
        </div>

        <p className="text-sm text-gray-700 mb-3">{latestWorkflow.summary}</p>

        {/* Stats Row */}
        <div className="grid grid-cols-4 gap-2 text-center text-xs mb-3">
          <div className="bg-white/60 rounded p-2">
            <div className="font-semibold text-gray-800">{latestWorkflow.episodesDiscovered}</div>
            <div className="text-gray-500">Discovered</div>
          </div>
          <div className="bg-white/60 rounded p-2">
            <div className="font-semibold text-gray-800">{latestWorkflow.digestsGenerated}</div>
            <div className="text-gray-500">Digests</div>
          </div>
          <div className="bg-white/60 rounded p-2">
            <div className="font-semibold text-gray-800">{latestWorkflow.audioFilesCreated}</div>
            <div className="text-gray-500">Audio</div>
          </div>
          <div className="bg-white/60 rounded p-2">
            <div className={`font-semibold ${latestWorkflow.errorCount > 0 ? 'text-red-600' : 'text-gray-800'}`}>
              {latestWorkflow.errorCount}
            </div>
            <div className="text-gray-500">Errors</div>
          </div>
        </div>

        {/* No Digest Reasons */}
        {latestWorkflow.noDigestReasons.length > 0 && (
          <div className="border-t border-gray-200 pt-3 mt-3">
            <div className="text-xs font-medium text-gray-700 mb-2">Why no new digests?</div>
            <div className="space-y-2">
              {latestWorkflow.noDigestReasons.map((reason, idx) => (
                <div key={idx} className="flex items-start space-x-2 text-sm">
                  <span className="text-gray-400">•</span>
                  <div>
                    <span className="font-medium text-gray-700">{reason.topic}:</span>{' '}
                    <span className="text-gray-600">{reason.details}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Topics Covered */}
        {latestWorkflow.topicsCovered.length > 0 && (
          <div className="border-t border-gray-200 pt-3 mt-3">
            <div className="text-xs font-medium text-gray-700 mb-1">Topics covered:</div>
            <div className="flex flex-wrap gap-1">
              {latestWorkflow.topicsCovered.map((topic, idx) => (
                <span key={idx} className="px-2 py-0.5 bg-white/80 rounded text-xs text-gray-700">
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Current State - Episodes Waiting */}
      {data.currentState.scoredEpisodesWaiting > 0 && (
        <div className="border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-800">
              Episodes Waiting ({data.currentState.scoredEpisodesWaiting})
            </h4>
            <span className="text-xs text-gray-500">
              Threshold: {data.currentState.scoreThreshold} · Min: {data.currentState.minEpisodesRequired} episodes
            </span>
          </div>
          <div className="space-y-2">
            {data.currentState.episodesBelowThreshold.slice(0, 5).map((ep) => (
              <div key={ep.id} className="flex items-center justify-between text-sm py-1 border-b border-gray-100 last:border-0">
                <div className="flex-1 truncate pr-2">
                  <span className="text-gray-700">{ep.title}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-1.5 py-0.5 rounded text-xs ${
                    ep.meetsThreshold ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                  }`}>
                    {ep.highestTopic}: {ep.highestScore.toFixed(2)}
                  </span>
                  {!ep.meetsThreshold && (
                    <span className="text-xs text-gray-400">below {ep.threshold}</span>
                  )}
                </div>
              </div>
            ))}
            {data.currentState.episodesBelowThreshold.length > 5 && (
              <div className="text-xs text-gray-500 text-center pt-1">
                +{data.currentState.episodesBelowThreshold.length - 5} more
              </div>
            )}
          </div>
        </div>
      )}

      {/* Previous Workflows */}
      {data.workflows.length > 1 && (
        <div className="border-t border-gray-200 pt-4">
          <div className="text-xs font-medium text-gray-700 mb-2">Previous Runs</div>
          <div className="space-y-1">
            {data.workflows.slice(1, 4).map((workflow) => {
              const wConfig = statusConfig[workflow.status]
              return (
                <div
                  key={workflow.workflowId}
                  className="flex items-center justify-between py-1.5 px-2 hover:bg-gray-50 rounded cursor-pointer"
                  onClick={() => setExpanded(expanded === workflow.workflowId ? null : workflow.workflowId)}
                >
                  <div className="flex items-center space-x-2">
                    <span>{wConfig.icon}</span>
                    <span className="text-sm text-gray-700">
                      {new Date(workflow.startedAt).toLocaleDateString()} {new Date(workflow.startedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                    </span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-500">
                      {workflow.digestsGenerated} digests · {workflow.audioFilesCreated} audio
                    </span>
                    <span className={`text-xs ${wConfig.textColor}`}>{wConfig.label}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
