'use client'

import { useEffect, useState } from 'react'

interface RunSummary {
  runId: string
  startedAt: string
  finishedAt: string | null
  durationSeconds: number | null
  warnings: number
  errors: number
}

interface LogEntry {
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

export default function LogsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [selectedRun, setSelectedRun] = useState<RunSummary | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [loadingLogs, setLoadingLogs] = useState(false)

  useEffect(() => {
    fetchRuns()
  }, [])

  const fetchRuns = async () => {
    setLoadingRuns(true)
    try {
      const response = await fetch('/api/pipeline/runs')
      if (response.ok) {
        const data = await response.json()
        setRuns(data.runs || [])
        if (data.runs?.length) {
          selectRun(data.runs[0])
        }
      }
    } catch (error) {
      console.error('Failed to load pipeline runs:', error)
    } finally {
      setLoadingRuns(false)
    }
  }

  const selectRun = async (run: RunSummary) => {
    setSelectedRun(run)
    setLoadingLogs(true)
    try {
      const response = await fetch(`/api/pipeline/activity?runId=${run.runId}`)
      if (response.ok) {
        const data = await response.json()
        setLogs(data.activities || [])
      }
    } catch (error) {
      console.error('Failed to load run logs:', error)
    } finally {
      setLoadingLogs(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pipeline Logs</h1>
        <p className="mt-1 text-sm text-gray-500">
          Review recent pipeline runs and phase-level events captured in Supabase.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card lg:col-span-1">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium text-gray-900">Recent Runs</h2>
            <button onClick={fetchRuns} className="btn-secondary text-sm">Refresh</button>
          </div>
          {loadingRuns ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, idx) => (
                <div key={idx} className="h-16 animate-pulse bg-gray-100 rounded-md" />
              ))}
            </div>
          ) : runs.length ? (
            <div className="space-y-2">
              {runs.map((run) => (
                <button
                  key={run.runId}
                  onClick={() => selectRun(run)}
                  className={`w-full text-left border rounded-md px-3 py-2 transition ${
                    selectedRun?.runId === run.runId
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between text-sm text-gray-800">
                    <span className="font-semibold">Run {run.runId}</span>
                    <span className="text-xs text-gray-500">{run.durationSeconds ? `${Math.round(run.durationSeconds / 60)} min` : '—'}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">Started {formatDate(run.startedAt)}</div>
                  <div className="mt-1 text-xs text-gray-500 flex gap-3">
                    <span className="text-amber-600">⚠️ {run.warnings}</span>
                    <span className={run.errors > 0 ? 'text-red-600' : 'text-gray-500'}>❌ {run.errors}</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-500">No pipeline runs recorded.</div>
          )}
        </div>

        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-medium text-gray-900">Run Timeline</h2>
            {selectedRun && (
              <span className="text-xs text-gray-500">Run {selectedRun.runId}</span>
            )}
          </div>

          {loadingLogs ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, idx) => (
                <div key={idx} className="h-12 animate-pulse bg-gray-100 rounded-md" />
              ))}
            </div>
          ) : logs.length ? (
            <div className="space-y-3 max-h-[32rem] overflow-y-auto pr-1">
              {logs.slice().reverse().map((log) => (
                <div key={log.id} className="flex items-start space-x-3 border border-gray-100 rounded-md px-3 py-2">
                  <span>{phaseIcon(log.phase)}</span>
                  <div className="flex-1 text-sm text-gray-700">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-800 capitalize">{log.phase}</span>
                      <span className="text-xs text-gray-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div className="text-xs text-gray-600" title={log.message}>{log.message}</div>
                    <div className="text-xs text-gray-400 mt-1">Level {log.level}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-500">Select a pipeline run to view its timeline.</div>
          )}
        </div>
      </div>
    </div>
  )
}
