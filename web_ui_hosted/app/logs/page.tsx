'use client'

import { useEffect, useState } from 'react'
import {
  RefreshCw,
  Search,
  Headphones,
  FileText,
  Mic,
  Radio,
  Trash2,
  Settings2,
  AlertTriangle,
  XCircle,
} from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'

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

const PhaseIcon = ({ phase }: { phase: string }) => {
  switch (phase) {
    case 'discovery': return <Search size={14} />
    case 'audio': return <Headphones size={14} />
    case 'digest': return <FileText size={14} />
    case 'tts': return <Mic size={14} />
    case 'publishing': return <Radio size={14} />
    case 'retention': return <Trash2 size={14} />
    default: return <Settings2 size={14} />
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
    <div>
      <PageHeader title="Pipeline Logs" description="Review recent pipeline runs and phase-level events captured in Supabase." />

      <div className="grid grid-cols-1 gap-[var(--space-6)] lg:grid-cols-3">
        <div className="card lg:col-span-1">
          <div className="mb-[var(--space-3)] flex items-center justify-between">
            <h2 style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>Recent Runs</h2>
            <button onClick={fetchRuns} className="btn btn-secondary btn-sm">
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {loadingRuns ? (
            <div className="flex flex-col gap-[var(--space-3)]">
              {[...Array(3)].map((_, idx) => (
                <div key={idx} className="card h-16 animate-pulse" />
              ))}
            </div>
          ) : runs.length ? (
            <div className="flex flex-col gap-[var(--space-2)]">
              {runs.map((run) => (
                <button
                  key={run.runId}
                  onClick={() => selectRun(run)}
                  className={`w-full rounded-sm border px-[var(--space-3)] py-[var(--space-2)] text-left transition-colors ${
                    selectedRun?.runId === run.runId
                      ? 'border-accent bg-accent-soft'
                      : 'border-border hover:border-border-strong hover:bg-surface-2'
                  }`}
                >
                  <div className="flex items-center justify-between text-ink" style={{ font: 'var(--t-small)' }}>
                    <span className="font-semibold">Run {run.runId}</span>
                    <span className="text-ink-subtle">{run.durationSeconds ? `${Math.round(run.durationSeconds / 60)} min` : '—'}</span>
                  </div>
                  <div className="mt-[var(--space-1)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                    Started {formatDate(run.startedAt)}
                  </div>
                  <div className="mt-[var(--space-1)] flex gap-[var(--space-3)]" style={{ font: 'var(--t-small)' }}>
                    <span className="flex items-center gap-[4px]" style={{ color: 'var(--warning)' }}>
                      <AlertTriangle size={12} /> {run.warnings}
                    </span>
                    <span
                      className="flex items-center gap-[4px]"
                      style={{ color: run.errors > 0 ? 'var(--danger)' : 'var(--text-subtle)' }}
                    >
                      <XCircle size={12} /> {run.errors}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>No pipeline runs recorded.</div>
          )}
        </div>

        <div className="card lg:col-span-2">
          <div className="mb-[var(--space-3)] flex items-center justify-between">
            <h2 style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>Run Timeline</h2>
            {selectedRun && (
              <span className="micro">Run {selectedRun.runId}</span>
            )}
          </div>

          {loadingLogs ? (
            <div className="flex flex-col gap-[var(--space-3)]">
              {[...Array(5)].map((_, idx) => (
                <div key={idx} className="card h-12 animate-pulse" />
              ))}
            </div>
          ) : logs.length ? (
            <div className="flex max-h-[32rem] flex-col gap-[var(--space-3)] overflow-y-auto pr-[var(--space-1)]">
              {logs.slice().reverse().map((log) => (
                <div key={log.id} className="flex items-start gap-[var(--space-3)] rounded-sm border border-border px-[var(--space-3)] py-[var(--space-2)]">
                  <span className="mt-[2px] text-ink-faint"><PhaseIcon phase={log.phase} /></span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-[var(--space-2)]">
                      <Pill tone="accent">{log.phase}</Pill>
                      <span className="text-ink-faint" style={{ font: 'var(--t-small)' }}>
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="mt-[var(--space-1)] text-ink-muted" style={{ font: 'var(--t-small)' }} title={log.message}>
                      {log.message}
                    </div>
                    <div className="mt-[var(--space-1)] text-ink-faint" style={{ font: 'var(--t-small)' }}>
                      Level {log.level}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>Select a pipeline run to view its timeline.</div>
          )}
        </div>
      </div>
    </div>
  )
}
