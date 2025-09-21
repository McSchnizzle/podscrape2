'use client'

import { useEffect, useState } from 'react'

interface DigestRecord {
  id: number
  topic: string
  digest_date?: string
  episode_count?: number
  mp3_path?: string
  mp3_duration_seconds?: number
  mp3_title?: string
  mp3_summary?: string
  published_at?: string
  github_url?: string
  created_at: string
  updated_at: string
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

  const formatDate = (value?: string) => {
    if (!value) return '—'
    const parsed = new Date(value)
    return isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '—'
    const mins = Math.round(seconds / 60)
    return `${mins} min`
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Publishing</h1>
        <p className="mt-1 text-gray-600">
          Monitor digests ready for publishing, review Supabase pipeline runs, and trigger the GitHub publishing workflow.
        </p>
      </div>

      {message && (
        <div className={`p-4 rounded-md ${
          message.type === 'success'
            ? 'bg-success-50 text-success-700 border border-success-200'
            : 'bg-error-50 text-error-700 border border-error-200'
        }`}>
          {message.text}
        </div>
      )}

      <div className="card">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Trigger Publishing Workflow</h2>
            <p className="text-sm text-gray-600">Dispatch the GitHub publishing-only workflow using existing MP3 assets.</p>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <label className="flex flex-col text-sm text-gray-700">
              Days back
              <input
                type="number"
                min={1}
                max={30}
                value={daysBack}
                onChange={(e) => setDaysBack(e.target.value)}
                className="input mt-1 w-28"
              />
            </label>
            <button
              onClick={triggerPublishing}
              disabled={triggering}
              className="btn btn-primary"
            >
              {triggering ? 'Dispatching...' : 'Run Publishing'}
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Recent Digests</h2>
          <button
            onClick={loadOverview}
            className="btn-secondary text-sm"
          >
            Refresh
          </button>
        </div>
        {loading ? (
          <div className="py-10 text-center text-gray-500">Loading digests...</div>
        ) : digests.length === 0 ? (
          <div className="py-10 text-center text-gray-500">No digests found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">Topic</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">Digest Date</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">Episodes</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">Audio</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">Published</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">GitHub</th>
                </tr>
              </thead>
              <tbody>
                {digests.map((digest) => (
                  <tr key={digest.id} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium text-gray-800">{digest.topic}</td>
                    <td className="px-3 py-2 text-gray-600">{formatDate(digest.digest_date || digest.created_at)}</td>
                    <td className="px-3 py-2 text-gray-600">{digest.episode_count ?? '—'}</td>
                    <td className="px-3 py-2 text-gray-600">
                      {digest.mp3_path ? (
                        <div className="flex flex-col">
                          <span className="truncate" title={digest.mp3_path}>{digest.mp3_path}</span>
                          <span className="text-xs text-gray-500">{formatDuration(digest.mp3_duration_seconds)}</span>
                        </div>
                      ) : '—'}
                    </td>
                    <td className="px-3 py-2">
                      {digest.published_at ? (
                        <span className="text-success-600">{formatDate(digest.published_at)}</span>
                      ) : (
                        <span className="text-gray-500">Pending</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {digest.github_url ? (
                        <a
                          href={digest.github_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary-600 hover:text-primary-700"
                        >
                          View Release
                        </a>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Supabase Pipeline Runs</h2>
          <button onClick={loadOverview} className="btn-secondary text-sm">Refresh</button>
        </div>
        {pipelineRuns.length === 0 ? (
          <div className="py-6 text-gray-500 text-center text-sm">No pipeline runs recorded yet.</div>
        ) : (
          <div className="space-y-3">
            {pipelineRuns.map((run) => (
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
        )}
      </div>
    </div>
  )
}
