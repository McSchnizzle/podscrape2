'use client'

import { useState, useEffect } from 'react'
import { Feed } from '@/utils/supabase'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Youtube, Rss, ExternalLink, Plus, Loader2 } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill, type PillTone } from '@/components/ui/Pill'

type Message = { type: 'success' | 'error'; text: string } | null

// ---------- helpers ----------

const isYouTubeUrl = (url: string) =>
  url.includes('youtube.com') || url.includes('youtu.be')

const youtubeChannelUrl = (feedUrl: string): string | null => {
  // RSS feed URLs for YouTube channels look like:
  //   https://www.youtube.com/feeds/videos.xml?channel_id=UCxxxx
  //   https://www.youtube.com/feeds/videos.xml?user=xxx
  //   https://www.youtube.com/feeds/videos.xml?playlist_id=xxx
  try {
    const u = new URL(feedUrl)
    const channelId = u.searchParams.get('channel_id')
    if (channelId) return `https://www.youtube.com/channel/${channelId}`
    const user = u.searchParams.get('user')
    if (user) return `https://www.youtube.com/user/${user}`
    const playlist = u.searchParams.get('playlist_id')
    if (playlist) return `https://www.youtube.com/playlist?list=${playlist}`
    return feedUrl
  } catch {
    return null
  }
}

const healthTone = (failures: number): PillTone => {
  if (failures === 0) return 'success'
  if (failures <= 2) return 'warning'
  return 'danger'
}

// ---------- sortable row ----------

interface RowProps {
  feed: Feed
  position: number
  checking: boolean
  editing: boolean
  onEditStart: () => void
  onEditCancel: () => void
  onEditSave: (updates: Partial<Feed>) => void
  onToggleActive: () => void
  onCheck: () => void
  onDelete: () => void
}

function SortableFeedRow(props: RowProps) {
  const {
    feed, position, checking, editing,
    onEditStart, onEditCancel, onEditSave,
    onToggleActive, onCheck, onDelete,
  } = props

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: feed.id })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  }

  const [editTitle, setEditTitle] = useState(feed.title)
  const [editUrl, setEditUrl] = useState(feed.feed_url)

  useEffect(() => {
    setEditTitle(feed.title)
    setEditUrl(feed.feed_url)
  }, [feed.id, feed.title, feed.feed_url, editing])

  const yt = isYouTubeUrl(feed.feed_url)
  const channelLink = yt ? youtubeChannelUrl(feed.feed_url) : null

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`card card-hover group flex items-start gap-[var(--space-3)] !p-[var(--space-5)] ${
        isDragging ? 'ring-2' : ''
      } ${!feed.active ? 'opacity-60' : ''}`}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        className="mt-[2px] flex-shrink-0 cursor-grab touch-none select-none rounded-sm p-[6px] text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink-muted active:cursor-grabbing"
        title="Drag to reorder"
      >
        <GripVertical size={18} />
      </button>

      {/* Position number */}
      <div className="w-8 flex-shrink-0 pt-[6px] text-center font-mono text-ink-faint" style={{ font: 'var(--t-small)' }}>
        {position}
      </div>

      {/* Main content */}
      <div className="min-w-0 flex-1">
        {editing ? (
          <div className="flex flex-col gap-[var(--space-2)]">
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="input"
              placeholder="Feed title"
            />
            <input
              type="text"
              value={editUrl}
              onChange={(e) => setEditUrl(e.target.value)}
              className="input font-mono"
              placeholder="Feed URL"
            />
            <div className="flex gap-[var(--space-2)]">
              <button onClick={() => onEditSave({ title: editTitle, feed_url: editUrl })} className="btn btn-primary btn-sm">
                Save
              </button>
              <button onClick={onEditCancel} className="btn btn-secondary btn-sm">
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-[var(--space-2)]">
              <Pill tone={yt ? 'danger' : 'accent'}>
                {yt ? <Youtube size={11} /> : <Rss size={11} />} {yt ? 'YouTube' : 'RSS'}
              </Pill>

              <span className="truncate text-ink" style={{ font: 'var(--t-body)', fontWeight: 600 }}>
                {feed.title}
              </span>

              {yt && channelLink && (
                <a
                  href={channelLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-[2px] text-xs hover:underline"
                  style={{ color: 'var(--danger)' }}
                  title="Open channel on YouTube"
                >
                  open channel <ExternalLink size={10} />
                </a>
              )}

              <Pill tone={healthTone(feed.consecutive_failures)}>
                {feed.consecutive_failures === 0
                  ? 'healthy'
                  : `${feed.consecutive_failures} fail${feed.consecutive_failures > 1 ? 's' : ''}`}
              </Pill>

              {!feed.active && <Pill tone="neutral">inactive</Pill>}
            </div>

            <div className="mt-[var(--space-2)] truncate font-mono text-ink-faint" style={{ font: 'var(--t-small)' }}>
              {feed.feed_url}
            </div>

            {feed.latest_episode_title && (
              <div className="mt-[var(--space-1)] truncate text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                Latest: <span className="italic">{feed.latest_episode_title}</span>
                {feed.last_episode_date && (
                  <span className="text-ink-faint"> · {new Date(feed.last_episode_date).toLocaleDateString()}</span>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Actions */}
      {!editing && (
        <div className="flex flex-shrink-0 items-center gap-[var(--space-1)] opacity-60 transition-opacity group-hover:opacity-100">
          <button onClick={onCheck} disabled={checking} className="btn btn-ghost btn-sm">
            {checking ? <Loader2 size={12} className="animate-spin" /> : 'Check'}
          </button>
          <button onClick={onToggleActive} className="btn btn-ghost btn-sm">
            {feed.active ? 'Disable' : 'Enable'}
          </button>
          <button onClick={onEditStart} className="btn btn-ghost btn-sm">
            Edit
          </button>
          <button onClick={onDelete} className="btn btn-ghost btn-sm hover:text-danger">
            Delete
          </button>
        </div>
      )}
    </div>
  )
}

// ---------- page ----------

export default function FeedsPage() {
  const [feeds, setFeeds] = useState<Feed[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [checking, setChecking] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState<Message>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newFeed, setNewFeed] = useState({ feed_url: '', title: '' })

  const sensors = useSensors(
    useSensor(PointerSensor, {
      // Small drag distance so clicks on buttons still work.
      activationConstraint: { distance: 5 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  useEffect(() => {
    fetchFeeds()
  }, [])

  const showMessage = (m: Message) => {
    setMessage(m)
    if (m) setTimeout(() => setMessage(null), 3000)
  }

  const fetchFeeds = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/feeds')
      const data = await response.json()
      if (response.ok) {
        // Sort by priority ascending (server view should already be sorted,
        // but be defensive).
        const sorted = [...(data.feeds || [])].sort(
          (a: Feed, b: Feed) => (a.priority ?? 999999) - (b.priority ?? 999999)
        )
        setFeeds(sorted)
      } else {
        showMessage({ type: 'error', text: data.error || 'Failed to load feeds' })
      }
    } catch {
      showMessage({ type: 'error', text: 'Failed to connect to feeds API' })
    } finally {
      setLoading(false)
    }
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = feeds.findIndex(f => f.id === active.id)
    const newIndex = feeds.findIndex(f => f.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return

    const reordered = arrayMove(feeds, oldIndex, newIndex)
    setFeeds(reordered) // Optimistic update

    try {
      const response = await fetch('/api/feeds/reorder', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orderedIds: reordered.map(f => f.id) }),
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'reorder failed')
      }
      showMessage({ type: 'success', text: 'Priority updated' })
    } catch (e) {
      showMessage({
        type: 'error',
        text: e instanceof Error ? e.message : 'Failed to save order',
      })
      // Revert on failure
      fetchFeeds()
    }
  }

  const addFeed = async () => {
    if (!newFeed.feed_url || !newFeed.title) {
      showMessage({ type: 'error', text: 'URL and title are required' })
      return
    }
    setSaving(true)
    try {
      const response = await fetch('/api/feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newFeed),
      })
      const data = await response.json()
      if (response.ok) {
        setNewFeed({ feed_url: '', title: '' })
        setShowAddForm(false)
        showMessage({ type: 'success', text: 'Feed added' })
        await fetchFeeds()
      } else {
        showMessage({ type: 'error', text: data.error || 'Failed to add feed' })
      }
    } catch {
      showMessage({ type: 'error', text: 'Failed to add feed' })
    } finally {
      setSaving(false)
    }
  }

  const updateFeed = async (id: number, updates: Partial<Feed>) => {
    setSaving(true)
    try {
      const response = await fetch(`/api/feeds/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      const data = await response.json()
      if (response.ok) {
        setEditingId(null)
        showMessage({ type: 'success', text: 'Feed updated' })
        await fetchFeeds()
      } else {
        showMessage({ type: 'error', text: data.error || 'Failed to update feed' })
      }
    } catch {
      showMessage({ type: 'error', text: 'Failed to update feed' })
    } finally {
      setSaving(false)
    }
  }

  const deleteFeed = async (id: number) => {
    if (!confirm('Delete this feed? This cannot be undone.')) return
    setSaving(true)
    try {
      const response = await fetch(`/api/feeds/${id}`, { method: 'DELETE' })
      if (response.ok) {
        showMessage({ type: 'success', text: 'Feed deleted' })
        await fetchFeeds()
      } else {
        const data = await response.json()
        showMessage({ type: 'error', text: data.error || 'Failed to delete feed' })
      }
    } catch {
      showMessage({ type: 'error', text: 'Failed to delete feed' })
    } finally {
      setSaving(false)
    }
  }

  const checkFeedNow = async (id: number) => {
    setChecking(id)
    try {
      const response = await fetch(`/api/feeds/${id}/check`, { method: 'POST' })
      if (response.ok) {
        showMessage({ type: 'success', text: 'Feed checked' })
        await fetchFeeds()
      } else {
        const data = await response.json()
        showMessage({ type: 'error', text: data.error || 'Check failed' })
      }
    } catch {
      showMessage({ type: 'error', text: 'Check failed' })
    } finally {
      setChecking(null)
    }
  }

  if (loading) {
    return (
      <div>
        <PageHeader title="Feeds" description="Drag to reorder. Higher in the list means higher priority when picking episodes for a digest." />
        <div className="flex flex-col gap-[var(--space-2)]">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card h-16 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Feeds"
        description="Drag to reorder. Higher in the list = higher priority when picking episodes for a digest. RSS podcasts and YouTube channels are sorted together."
        actions={
          <button onClick={() => setShowAddForm(true)} disabled={saving} className="btn btn-primary">
            <Plus size={14} /> Add feed
          </button>
        }
      />

      {message && (
        <div
          className="mb-[var(--space-4)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
          style={{
            background: message.type === 'success' ? 'var(--success-soft)' : 'var(--danger-soft)',
            color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
            font: 'var(--t-small)',
          }}
        >
          {message.text}
        </div>
      )}

      {showAddForm && (
        <div className="card mb-[var(--space-5)]" style={{ borderColor: 'var(--accent)' }}>
          <h2 className="mb-[var(--space-3)]" style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
            Add new feed
          </h2>
          <div className="flex flex-col gap-[var(--space-3)]">
            <input
              type="text"
              value={newFeed.title}
              onChange={(e) => setNewFeed({ ...newFeed, title: e.target.value })}
              placeholder="Title (e.g. 'The Bridge with Peter Mansbridge')"
              className="input"
            />
            <input
              type="text"
              value={newFeed.feed_url}
              onChange={(e) => setNewFeed({ ...newFeed, feed_url: e.target.value })}
              placeholder="RSS feed URL or YouTube RSS URL"
              className="input font-mono"
            />
            <div className="flex gap-[var(--space-2)]">
              <button onClick={addFeed} disabled={saving} className="btn btn-primary">
                {saving ? 'Adding…' : 'Add'}
              </button>
              <button
                onClick={() => {
                  setShowAddForm(false)
                  setNewFeed({ feed_url: '', title: '' })
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
            <p className="field-hint">
              For YouTube channels, use the channel&apos;s RSS URL:{' '}
              <code className="rounded-sm bg-surface-2 px-[4px] py-[1px] font-mono">
                https://www.youtube.com/feeds/videos.xml?channel_id=...
              </code>
            </p>
          </div>
        </div>
      )}

      <div className="mb-[var(--space-4)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
        {feeds.length} feed{feeds.length !== 1 ? 's' : ''} · {feeds.filter(f => f.active).length} active
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={feeds.map(f => f.id)} strategy={verticalListSortingStrategy}>
          <div className="flex flex-col gap-[var(--space-2)]">
            {feeds.map((feed, idx) => (
              <SortableFeedRow
                key={feed.id}
                feed={feed}
                position={idx + 1}
                checking={checking === feed.id}
                editing={editingId === feed.id}
                onEditStart={() => setEditingId(feed.id)}
                onEditCancel={() => setEditingId(null)}
                onEditSave={(updates) => updateFeed(feed.id, updates)}
                onToggleActive={() => updateFeed(feed.id, { active: !feed.active })}
                onCheck={() => checkFeedNow(feed.id)}
                onDelete={() => deleteFeed(feed.id)}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {feeds.length === 0 && (
        <div className="card py-[var(--space-8)] text-center text-ink-subtle">
          No feeds yet. Click &quot;Add feed&quot; to get started.
        </div>
      )}
    </div>
  )
}
