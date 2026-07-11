'use client'

import { useEffect, useState } from 'react'
import {
  Play,
  Radio,
  ScrollText,
  Settings2,
  Clock,
  ExternalLink,
  Github,
  AlertTriangle,
  CircleCheck,
  Eye,
  FileText,
  Rss,
} from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import { StatCard } from '@/components/ui/StatCard'
import { toast } from '@/components/Toast'

interface LatestEpisode {
  id: number
  topic: string
  digest_date: string
  mp3_title: string | null
  mp3_duration_seconds: number | null
  mp3_path: string | null
  github_url: string | null
  generated_at: string | null
}

interface LastOutcome {
  id: number
  topic: string
  digest_date: string
  status: string
  generated_at: string | null
  script_chars: number | null
  published: boolean
}

interface FailingFeed {
  id: number
  title: string
  consecutive_failures: number
  last_checked: string | null
}

interface WatchTheme {
  id: number
  name: string
  scope: 'weekly' | 'daily' | 'both'
}

interface DashboardSummary {
  latestEpisode: LatestEpisode | null
  pipelineReadiness: {
    now: Record<string, number>
    updatedToday: Record<string, number>
  }
  lastOutcome: LastOutcome | null
  feeds: {
    active: number
    total: number
    failing: FailingFeed[]
  }
  activeWatchThemes: WatchTheme[]
  generatedAt: string
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pending',
  processing: 'Processing',
  transcribed: 'Transcribed',
  scored: 'Scored — ready for digest',
  digested: 'Digested',
  not_relevant: 'Not relevant',
  failed: 'Failed',
}

const STATUS_ORDER = ['pending', 'processing', 'transcribed', 'scored', 'digested', 'failed', 'not_relevant']

function formatDuration(seconds: number | null): string {
  if (!seconds && seconds !== 0) return '—'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

const SCOPE_LABEL: Record<string, string> = { weekly: 'Weekly', daily: 'Daily', both: 'Weekly + Daily' }

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pipelineLoading, setPipelineLoading] = useState(false)
  const [publishingLoading, setPublishingLoading] = useState(false)

  async function load() {
    try {
      const r = await fetch('/api/dashboard/summary', { cache: 'no-store' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setData(await r.json())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const triggerFullPipeline = async () => {
    setPipelineLoading(true)
    try {
      const response = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ daysBack: '7', phaseLimit: 'publishing' }),
      })
      if (response.ok) {
        toast.success('Pipeline triggered successfully!', {
          description: 'Check Logs for progress.',
          action: { label: 'View Logs', onClick: () => (window.location.href = '/logs') },
          duration: 6000,
        })
      } else {
        const errorData = await response.json()
        toast.error('Failed to trigger pipeline', { description: errorData.error, duration: 8000 })
      }
    } catch (err) {
      toast.error('Failed to trigger full pipeline', { description: 'Network error or server unavailable', duration: 8000 })
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
        body: JSON.stringify({ daysBack: '7' }),
      })
      if (response.ok) {
        toast.success('Publishing workflow triggered!', {
          description: 'Check Logs for progress.',
          action: { label: 'View Logs', onClick: () => (window.location.href = '/logs') },
          duration: 6000,
        })
      } else {
        const errorData = await response.json()
        toast.error('Failed to trigger publishing', { description: errorData.error, duration: 8000 })
      }
    } catch (err) {
      toast.error('Failed to trigger publishing', { description: 'Network error or server unavailable', duration: 8000 })
    } finally {
      setPublishingLoading(false)
    }
  }

  if (loading) {
    return (
      <div>
        <PageHeader title="Dashboard" description="Live status of the podcast digest pipeline." />
        <div className="grid grid-cols-1 gap-[var(--space-5)] md:grid-cols-2 xl:grid-cols-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card h-40 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div>
        <PageHeader title="Dashboard" description="Live status of the podcast digest pipeline." />
        <div className="card" style={{ borderColor: 'var(--danger)' }}>
          <div className="flex items-center gap-[var(--space-2)]" style={{ color: 'var(--danger)' }}>
            <AlertTriangle size={18} />
            <span style={{ font: 'var(--t-h3)' }}>Failed to load dashboard</span>
          </div>
          <p className="mt-[var(--space-2)] text-ink-subtle">{error}</p>
        </div>
      </div>
    )
  }

  const { latestEpisode, pipelineReadiness, lastOutcome, feeds, activeWatchThemes } = data
  const readyForDigest = pipelineReadiness.now['scored'] || 0
  const inQueue = (pipelineReadiness.now['pending'] || 0) + (pipelineReadiness.now['transcribed'] || 0) + (pipelineReadiness.now['processing'] || 0)
  const digestedToday = pipelineReadiness.updatedToday['digested'] || 0

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Live status of the podcast digest pipeline — every number below is a direct query, not a cached estimate."
      />

      {/* Latest published episode -- featured */}
      <div className="card card-hover relative mb-[var(--space-6)] overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-[3px]" style={{ background: 'var(--live)' }} aria-hidden />
        <div className="flex flex-col justify-between gap-[var(--space-4)] md:flex-row md:items-center">
          <div className="min-w-0">
            <div className="mb-[var(--space-2)] flex items-center gap-[var(--space-2)]">
              <Pill tone="live">
                <CircleCheck size={12} /> Latest published episode
              </Pill>
              <span className="micro">{latestEpisode?.topic}</span>
            </div>
            {latestEpisode ? (
              <>
                <h2 className="truncate" style={{ font: 'var(--t-h2)', color: 'var(--text)' }} title={latestEpisode.mp3_title || undefined}>
                  {latestEpisode.mp3_title || `Episode #${latestEpisode.id}`}
                </h2>
                <div className="mt-[var(--space-3)] flex flex-wrap items-center gap-x-[var(--space-5)] gap-y-[var(--space-2)] text-ink-muted" style={{ font: 'var(--t-small)' }}>
                  <span className="flex items-center gap-[6px]">
                    <FileText size={14} className="text-ink-faint" /> Episode #{latestEpisode.id}
                  </span>
                  <span className="flex items-center gap-[6px]">
                    <Clock size={14} className="text-ink-faint" /> {formatDate(latestEpisode.digest_date)} · {formatDuration(latestEpisode.mp3_duration_seconds)}
                  </span>
                </div>
              </>
            ) : (
              <p className="text-ink-subtle">No published episode found yet.</p>
            )}
          </div>
          {latestEpisode && (
            <div className="flex shrink-0 flex-wrap gap-[var(--space-2)]">
              <a href="/ai-tech-digest.xml" target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
                <Rss size={14} /> Feed
              </a>
              {latestEpisode.github_url && (
                <a href={latestEpisode.github_url} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
                  <Github size={14} /> Release
                </a>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-[var(--space-5)] md:grid-cols-2 xl:grid-cols-3">
        {/* Tonight's pipeline readiness */}
        <div className="card xl:col-span-1">
          <div className="mb-[var(--space-4)] flex items-center justify-between">
            <span className="micro">Tonight&apos;s pipeline readiness</span>
            <Pill tone={inQueue > 0 ? 'accent' : 'neutral'}>{inQueue} in queue</Pill>
          </div>
          <div className="flex flex-col gap-[var(--space-3)]">
            {STATUS_ORDER.filter((s) => pipelineReadiness.now[s] !== undefined).map((status) => (
              <div key={status} className="flex items-center justify-between">
                <span className="text-ink-muted" style={{ font: 'var(--t-small)' }}>
                  {STATUS_LABEL[status] || status}
                </span>
                <div className="flex items-center gap-[var(--space-2)]">
                  {pipelineReadiness.updatedToday[status] ? (
                    <span className="micro" style={{ color: 'var(--success)' }}>
                      +{pipelineReadiness.updatedToday[status]} today
                    </span>
                  ) : null}
                  <span style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>{pipelineReadiness.now[status]}</span>
                </div>
              </div>
            ))}
          </div>
          <p className="field-hint mt-[var(--space-4)]">
            {readyForDigest} episode{readyForDigest === 1 ? '' : 's'} scored and ready for tonight&apos;s digest run.
          </p>
        </div>

        {/* Last pipeline outcome */}
        <div className="card">
          <span className="micro">Last pipeline outcome</span>
          {lastOutcome ? (
            <>
              <div className="mt-[var(--space-3)] flex items-center gap-[var(--space-3)]">
                <span style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>{formatDate(lastOutcome.digest_date)}</span>
                <Pill tone={lastOutcome.published ? 'success' : 'warning'}>
                  {lastOutcome.published ? 'Published' : lastOutcome.status}
                </Pill>
              </div>
              <div className="mt-[var(--space-4)] grid grid-cols-2 gap-[var(--space-3)]">
                <div>
                  <div className="micro">Script size</div>
                  <div style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
                    {lastOutcome.script_chars ? `${lastOutcome.script_chars.toLocaleString()} chars` : '—'}
                  </div>
                </div>
                <div>
                  <div className="micro">Generated</div>
                  <div style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>{formatDateTime(lastOutcome.generated_at)}</div>
                </div>
              </div>
              <p className="field-hint mt-[var(--space-4)]">Digest #{lastOutcome.id} · {lastOutcome.topic}</p>
            </>
          ) : (
            <p className="mt-[var(--space-3)] text-ink-subtle">No digests generated yet.</p>
          )}
        </div>

        {/* Active feeds */}
        <StatCard
          label="Active feeds"
          value={`${feeds.active} / ${feeds.total}`}
          tone={feeds.failing.length > 0 ? 'warning' : 'success'}
          icon={<Radio size={16} />}
          sublabel={
            feeds.failing.length > 0 ? (
              <div className="flex flex-col gap-[var(--space-1)]">
                <span className="flex items-center gap-[6px]" style={{ color: 'var(--warning)' }}>
                  <AlertTriangle size={13} /> {feeds.failing.length} feed{feeds.failing.length === 1 ? '' : 's'} failing
                </span>
                {feeds.failing.slice(0, 3).map((f) => (
                  <span key={f.id} className="truncate text-ink-subtle">
                    {f.title} ({f.consecutive_failures}x)
                  </span>
                ))}
              </div>
            ) : (
              'No feeds currently failing'
            )
          }
        />

        {/* Active watch themes */}
        <div className="card md:col-span-2 xl:col-span-1">
          <div className="mb-[var(--space-3)] flex items-center justify-between">
            <span className="micro">Active watch themes</span>
            <Pill tone="accent">
              <Eye size={12} /> {activeWatchThemes.length}
            </Pill>
          </div>
          <div className="flex flex-col gap-[var(--space-2)]">
            {activeWatchThemes.length === 0 && <p className="text-ink-subtle">No active watch themes.</p>}
            {activeWatchThemes.map((t) => (
              <div key={t.id} className="flex items-center justify-between gap-[var(--space-3)]">
                <span className="truncate text-ink" style={{ font: 'var(--t-small)' }} title={t.name}>
                  {t.name}
                </span>
                <Pill tone="neutral">{SCOPE_LABEL[t.scope] || t.scope}</Pill>
              </div>
            ))}
          </div>
          <a href="/watch-themes" className="field-hint mt-[var(--space-4)] inline-block" style={{ color: 'var(--accent)' }}>
            Manage watch themes →
          </a>
        </div>
      </div>

      {/* Quick actions */}
      <div className="card mt-[var(--space-6)]">
        <h3 className="mb-[var(--space-4)]" style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
          Quick actions
        </h3>
        <div className="flex flex-wrap gap-[var(--space-3)]">
          <button onClick={triggerFullPipeline} disabled={pipelineLoading} className="btn btn-primary">
            <Play size={14} /> {pipelineLoading ? 'Triggering…' : 'Run full pipeline'}
          </button>
          <button onClick={triggerPublishing} disabled={publishingLoading} className="btn btn-secondary">
            <Radio size={14} /> {publishingLoading ? 'Triggering…' : 'Publishing only'}
          </button>
          <a href="/logs" className="btn btn-secondary">
            <ScrollText size={14} /> View logs
          </a>
          <a href="/feeds" className="btn btn-secondary">
            <Radio size={14} /> Manage feeds
          </a>
          <a href="/settings" className="btn btn-secondary">
            <Settings2 size={14} /> Settings
          </a>
        </div>
      </div>
    </div>
  )
}
