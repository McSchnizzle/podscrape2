'use client'

import { useEffect, useState } from 'react'
import { RefreshCw, Play, CheckCircle2, XCircle } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill, type PillTone } from '@/components/ui/Pill'

interface DigestRecord {
  id: number
  topic: string
  digest_date?: string
  episode_count?: number
  episodes?: string[]
  mp3_path?: string
  mp3_duration_seconds?: number
  mp3_title?: string
  mp3_summary?: string
  published_at?: string
  github_url?: string
  created_at: string
  updated_at: string
  generated_at?: string
}

interface PipelineRunRecord {
  id: string
  status?: string
  conclusion?: string
  workflow_name?: string
  trigger?: string
  started_at?: string
  finished_at?: string
}

const CONCLUSION_TONE: Record<string, PillTone> = {
  success: 'success',
  failure: 'danger',
}

export default function PublishingPage() {
  const [digests, setDigests] = useState<DigestRecord[]>([])
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRunRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [daysBack, setDaysBack] = useState('7')
  const [triggering, setTriggering] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  useEffect(() => {
    loadOverview()
  }, [])

  const loadOverview = async () => {
    try {
      const response = await fetch('/api/publishing')
      const data = await response.json()
      if (response.ok) {
        setDigests(data.digests || [])
        setPipelineRuns(data.pipelineRuns || [])
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to load publishing overview' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to reach publishing API' })
    } finally {
      setLoading(false)
    }
  }

  const triggerPublishing = async () => {
    setTriggering(true)
    try {
      const response = await fetch('/api/pipeline/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ daysBack })
      })

      const data = await response.json()
      if (response.ok) {
        setMessage({ type: 'success', text: data.message || 'Publishing workflow triggered' })
        setTimeout(() => setMessage(null), 4000)
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to trigger publishing' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Publishing request failed' })
    } finally {
      setTriggering(false)
    }
  }

  // Format dates in Pacific timezone (PST/PDT)
  // Database stores UTC timestamps without timezone info, so we need to explicitly treat them as UTC
  const formatDate = (value?: string) => {
    if (!value) return '—'

    // The database stores UTC timestamps without timezone info
    // So when we parse them, we need to explicitly treat them as UTC
    const parsed = new Date(value + 'Z') // Add 'Z' to indicate UTC
    if (isNaN(parsed.getTime())) return value

    return parsed.toLocaleString('en-US', {
      timeZone: 'America/Los_Angeles',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    })
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '—'
    const mins = Math.round(seconds / 60)
    return `${mins} min`
  }

  return (
    <div>
      <PageHeader
        title="Publishing"
        description="Monitor digests ready for publishing, review Supabase pipeline runs, and trigger the GitHub publishing workflow."
      />

      {message && (
        <div
          className="mb-[var(--space-5)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
          style={{
            background: message.type === 'success' ? 'var(--success-soft)' : 'var(--danger-soft)',
            color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
            font: 'var(--t-small)',
          }}
        >
          {message.text}
        </div>
      )}

      <div className="flex flex-col gap-[var(--space-6)]">
        <div className="card">
          <div className="flex flex-col gap-[var(--space-4)] md:flex-row md:items-end md:justify-between">
            <div>
              <h2 style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>Trigger Publishing Workflow</h2>
              <p className="mt-[var(--space-1)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                Dispatch the GitHub publishing-only workflow using existing MP3 assets.
              </p>
            </div>
            <div className="flex flex-col gap-[var(--space-3)] sm:flex-row sm:items-end">
              <div>
                <label className="field-label">Days back</label>
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={daysBack}
                  onChange={(e) => setDaysBack(e.target.value)}
                  className="input w-28"
                />
              </div>
              <button
                onClick={triggerPublishing}
                disabled={triggering}
                className="btn btn-primary"
              >
                <Play size={14} /> {triggering ? 'Dispatching…' : 'Run Publishing'}
              </button>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="mb-[var(--space-4)] flex items-center justify-between">
            <h2 style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>Recent Digests</h2>
            <button onClick={loadOverview} className="btn btn-secondary btn-sm">
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {loading ? (
            <div className="py-[var(--space-6)] text-center text-ink-subtle">Loading digests…</div>
          ) : digests.length === 0 ? (
            <div className="py-[var(--space-6)] text-center text-ink-subtle">No digests found.</div>
          ) : (
            <div className="table-shell overflow-x-auto">
              <table className="house-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Topic</th>
                    <th>Episodes Included</th>
                    <th>Duration</th>
                    <th>Asset</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {digests.map((digest) => (
                    <tr key={digest.id}>
                      <td className="text-ink-muted">
                        <span className="font-mono text-xs">{formatDate(digest.generated_at || digest.digest_date)}</span>
                      </td>
                      <td className="font-medium text-ink">{digest.topic}</td>
                      <td className="max-w-md">
                        {digest.episodes && digest.episodes.length > 0 ? (
                          <div className="text-ink-muted" style={{ font: 'var(--t-small)' }}>
                            <div className="mb-[var(--space-1)] font-semibold text-ink">{digest.episode_count} episodes:</div>
                            {digest.episodes.map((episode, idx) => (
                              <div key={idx} className="mb-[2px]">&bull; {episode}</div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-ink-faint" style={{ font: 'var(--t-small)' }}>No episodes</span>
                        )}
                      </td>
                      <td className="text-ink-muted">{formatDuration(digest.mp3_duration_seconds)}</td>
                      <td>
                        <Pill tone={digest.mp3_path ? 'success' : 'danger'}>
                          {digest.mp3_path ? 'Present' : 'Missing'}
                        </Pill>
                      </td>
                      <td>
                        <div className="flex items-center gap-[var(--space-3)]">
                          <button className="text-xs hover:underline" style={{ color: 'var(--accent)' }}>
                            Publish/Ensure
                          </button>
                          <button className="text-xs hover:underline" style={{ color: 'var(--danger)' }}>
                            Unpublish
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="mb-[var(--space-4)] flex items-center justify-between">
            <h2 style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>Supabase Pipeline Runs</h2>
            <button onClick={loadOverview} className="btn btn-secondary btn-sm">
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {pipelineRuns.length === 0 ? (
            <div className="py-[var(--space-5)] text-center text-ink-subtle" style={{ font: 'var(--t-small)' }}>
              No pipeline runs recorded yet.
            </div>
          ) : (
            <div className="flex flex-col gap-[var(--space-3)]">
              {pipelineRuns.map((run) => (
                <div key={run.id} className="rounded-sm border border-border p-[var(--space-3)]">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-ink" style={{ font: 'var(--t-small)' }}>
                      {run.workflow_name || 'Pipeline Run'}
                    </span>
                    <Pill tone={CONCLUSION_TONE[run.conclusion || ''] || 'neutral'}>
                      {run.conclusion === 'success' ? (
                        <CheckCircle2 size={11} />
                      ) : run.conclusion === 'failure' ? (
                        <XCircle size={11} />
                      ) : null}
                      {run.conclusion || run.status || 'unknown'}
                    </Pill>
                  </div>
                  <div className="mt-[var(--space-2)] grid grid-cols-1 gap-[var(--space-1)] text-ink-subtle md:grid-cols-3" style={{ font: 'var(--t-small)' }}>
                    <div>Trigger: {run.trigger || 'manual'}</div>
                    <div>Started: {formatDate(run.started_at)}</div>
                    <div>Finished: {formatDate(run.finished_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
