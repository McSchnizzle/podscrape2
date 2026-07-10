'use client'

import { useEffect, useMemo, useState } from 'react'
import { Star, Github, Clock, FileText, Loader2, AlertTriangle } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill, type PillTone } from '@/components/ui/Pill'

interface DigestRow {
  id: number
  topic: string
  digest_date: string
  status: string
  mp3_title: string | null
  mp3_duration_seconds: number | null
  mp3_path: string | null
  github_url: string | null
  generated_at: string | null
  published_at: string | null
  is_favorite: boolean
  episode_count: number
  episodes: string[]
}

const STATUS_TONE: Record<string, PillTone> = {
  draft: 'neutral',
  generated: 'neutral',
  audio_generated: 'accent',
  published: 'success',
  failed: 'danger',
}

function formatDuration(seconds: number | null): string {
  if (!seconds && seconds !== 0) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function DigestsPage() {
  const [digests, setDigests] = useState<DigestRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [pendingId, setPendingId] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/digests?limit=100', { cache: 'no-store' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = await r.json()
      setDigests(data.digests || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load digests')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const toggleFavorite = async (digest: DigestRow) => {
    setPendingId(digest.id)
    // Optimistic update.
    setDigests((prev) => prev.map((d) => (d.id === digest.id ? { ...d, is_favorite: !d.is_favorite } : d)))
    try {
      const r = await fetch(`/api/digests/${digest.id}/favorite`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_favorite: !digest.is_favorite }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
    } catch {
      // Revert on failure.
      setDigests((prev) => prev.map((d) => (d.id === digest.id ? { ...d, is_favorite: digest.is_favorite } : d)))
      setError('Failed to update favorite')
    } finally {
      setPendingId(null)
    }
  }

  const visible = useMemo(
    () => (favoritesOnly ? digests.filter((d) => d.is_favorite) : digests),
    [digests, favoritesOnly]
  )

  return (
    <div>
      <PageHeader
        title="Digests"
        description="Generated podcast digests — favorite the ones worth keeping around; favorites are exempt from retention cleanup."
        actions={
          <button
            onClick={() => setFavoritesOnly((v) => !v)}
            className={`btn btn-sm ${favoritesOnly ? 'btn-primary' : 'btn-secondary'}`}
          >
            <Star size={13} fill={favoritesOnly ? 'currentColor' : 'none'} />
            {favoritesOnly ? 'Showing favorites' : 'Favorites only'}
          </button>
        }
      />

      {error && (
        <div
          className="mb-[var(--space-5)] flex items-center gap-[var(--space-2)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
          style={{ background: 'var(--danger-soft)', color: 'var(--danger)', font: 'var(--t-small)' }}
        >
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-[var(--space-2)] text-ink-subtle">
          <Loader2 size={16} className="animate-spin" /> Loading digests…
        </div>
      ) : visible.length === 0 ? (
        <div className="card py-[var(--space-8)] text-center text-ink-subtle">
          {favoritesOnly ? 'No favorited digests yet.' : 'No digests yet.'}
        </div>
      ) : (
        <div className="flex flex-col gap-[var(--space-3)]">
          {visible.map((digest) => (
            <div key={digest.id} className="card card-hover">
              <div className="flex flex-wrap items-start justify-between gap-[var(--space-3)]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-[var(--space-2)]">
                    <h3 className="truncate" style={{ font: 'var(--t-h3)', color: 'var(--text)' }} title={digest.mp3_title || undefined}>
                      {digest.mp3_title || `Digest #${digest.id}`}
                    </h3>
                    <Pill tone={STATUS_TONE[digest.status] || 'neutral'}>{digest.status.replace('_', ' ')}</Pill>
                  </div>
                  <div className="mt-[var(--space-2)] flex flex-wrap items-center gap-x-[var(--space-4)] gap-y-[var(--space-1)] text-ink-muted" style={{ font: 'var(--t-small)' }}>
                    <span className="flex items-center gap-[6px]">
                      <FileText size={13} className="text-ink-faint" /> {digest.topic} · {formatDate(digest.digest_date)}
                    </span>
                    <span className="flex items-center gap-[6px]">
                      <Clock size={13} className="text-ink-faint" /> {formatDuration(digest.mp3_duration_seconds)}
                    </span>
                    <span>
                      {digest.episode_count} episode{digest.episode_count === 1 ? '' : 's'}
                    </span>
                  </div>
                  {digest.episodes.length > 0 && (
                    <p className="mt-[var(--space-2)] truncate text-ink-subtle" style={{ font: 'var(--t-small)' }} title={digest.episodes.join(' · ')}>
                      {digest.episodes.join(' · ')}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-[var(--space-2)]">
                  {digest.github_url && (
                    <a href={digest.github_url} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
                      <Github size={13} /> Release
                    </a>
                  )}
                  <button
                    onClick={() => toggleFavorite(digest)}
                    disabled={pendingId === digest.id}
                    className="btn btn-sm"
                    style={
                      digest.is_favorite
                        ? { background: 'var(--warm-soft)', borderColor: 'var(--warm)', color: 'var(--warm)' }
                        : undefined
                    }
                    title={digest.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                  >
                    <Star size={14} fill={digest.is_favorite ? 'currentColor' : 'none'} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
