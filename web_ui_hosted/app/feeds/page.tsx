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

const healthBadgeClass = (failures: number) => {
  if (failures === 0) return 'bg-green-100 text-green-800 border-green-200'
  if (failures <= 2) return 'bg-yellow-100 text-yellow-800 border-yellow-200'
  return 'bg-red-100 text-red-800 border-red-200'
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
      className={`group flex items-start gap-3 bg-white border rounded-lg px-3 py-3 shadow-sm hover:shadow-md transition-shadow ${
        isDragging ? 'ring-2 ring-blue-400' : 'border-gray-200'
      } ${!feed.active ? 'opacity-60' : ''}`}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
        className="flex-shrink-0 cursor-grab active:cursor-grabbing touch-none p-1 text-gray-400 hover:text-gray-700 select-none"
        title="Drag to reorder"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <circle cx="6" cy="5" r="1.5" /><circle cx="14" cy="5" r="1.5" />
          <circle cx="6" cy="10" r="1.5" /><circle cx="14" cy="10" r="1.5" />
          <circle cx="6" cy="15" r="1.5" /><circle cx="14" cy="15" r="1.5" />
        </svg>
      </button>

      {/* Position number */}
      <div className="flex-shrink-0 w-8 text-center text-sm font-mono text-gray-500 pt-1">
        {position}
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        {editing ? (
          <div className="space-y-2">
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
              placeholder="Feed title"
            />
            <input
              type="text"
              value={editUrl}
              onChange={(e) => setEditUrl(e.target.value)}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm font-mono"
              placeholder="Feed URL"
            />
            <div className="flex gap-2">
              <button
                onClick={() => onEditSave({ title: editTitle, feed_url: editUrl })}
                className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Save
              </button>
              <button
                onClick={onEditCancel}
                className="px-3 py-1 text-sm bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              {/* Type badge */}
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${
                  yt
                    ? 'bg-red-50 text-red-700 border-red-200'
                    : 'bg-indigo-50 text-indigo-700 border-indigo-200'
                }`}
                title={yt ? 'YouTube channel feed' : 'RSS podcast feed'}
              >
                {yt ? 'YouTube' : 'RSS'}
              </span>

              <span className="font-medium text-gray-900 truncate">{feed.title}</span>

              {yt && channelLink && (
                <a
                  href={channelLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-red-600 hover:text-red-800 underline"
                  title="Open channel on YouTube"
                >
                  open channel ↗
                </a>
              )}

              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${healthBadgeClass(
                  feed.consecutive_failures
                )}`}
              >
                {feed.consecutive_failures === 0
                  ? 'healthy'
                  : `${feed.consecutive_failures} fail${feed.consecutive_failures > 1 ? 's' : ''}`}
              </span>

              {!feed.active && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-200 text-gray-700">
                  inactive
                </span>
              )}
            </div>

            <div className="mt-1 text-xs text-gray-500 truncate font-mono">
              {feed.feed_url}
            </div>

            {feed.latest_episode_title && (
              <div className="mt-1 text-xs text-gray-600 truncate">
                Latest: <span className="italic">{feed.latest_episode_title}</span>
                {feed.last_episode_date && (
                  <span className="text-gray-400">
                    {' '}
                    · {new Date(feed.last_episode_date).toLocaleDateString()}
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Actions */}
      {!editing && (
        <div className="flex-shrink-0 flex items-center gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onCheck}
            disabled={checking}
            className="px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 rounded"
            title="Check feed now"
          >
            {checking ? '…' : 'Check'}
          </button>
          <button
            onClick={onToggleActive}
            className="px-2 py-1 text-xs text-gray-700 hover:bg-gray-100 rounded"
            title={feed.active ? 'Disable feed' : 'Enable feed'}
          >
            {feed.active ? 'Disable' : 'Enable'}
          </button>
          <button
            onClick={onEditStart}
            className="px-2 py-1 text-xs text-gray-700 hover:bg-gray-100 rounded"
          >
            Edit
          </button>
          <button
            onClick={onDelete}
            className="px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded"
          >
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
      <div className="flex items-center justify-center min-h-64">
        <div className="text-lg text-gray-600">Loading feeds...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Feeds</h1>
          <p className="mt-1 text-gray-600">
            Drag to reorder. Higher in the list = higher priority when picking
            episodes for a digest. RSS podcasts and YouTube channels are sorted
            together.
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 whitespace-nowrap"
          disabled={saving}
        >
          + Add Feed
        </button>
      </div>

      {message && (
        <div
          className={`px-4 py-2 rounded-md text-sm ${
            message.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {showAddForm && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
          <h2 className="font-semibold text-gray-900">Add new feed</h2>
          <input
            type="text"
            value={newFeed.title}
            onChange={(e) => setNewFeed({ ...newFeed, title: e.target.value })}
            placeholder="Title (e.g. 'The Bridge with Peter Mansbridge')"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <input
            type="text"
            value={newFeed.feed_url}
            onChange={(e) => setNewFeed({ ...newFeed, feed_url: e.target.value })}
            placeholder="RSS feed URL or YouTube RSS URL"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
          />
          <div className="flex gap-2">
            <button
              onClick={addFeed}
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:bg-gray-400"
            >
              {saving ? 'Adding…' : 'Add'}
            </button>
            <button
              onClick={() => {
                setShowAddForm(false)
                setNewFeed({ feed_url: '', title: '' })
              }}
              className="px-4 py-2 bg-gray-200 text-gray-800 text-sm rounded-md hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
          <p className="text-xs text-gray-500">
            For YouTube channels, use the channel's RSS URL:{' '}
            <code className="bg-white px-1 rounded">
              https://www.youtube.com/feeds/videos.xml?channel_id=...
            </code>
          </p>
        </div>
      )}

      <div className="text-sm text-gray-600">
        {feeds.length} feed{feeds.length !== 1 ? 's' : ''} · {feeds.filter(f => f.active).length} active
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={feeds.map(f => f.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-2">
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
        <div className="text-center py-12 text-gray-500">
          No feeds yet. Click "+ Add Feed" to get started.
        </div>
      )}
    </div>
  )
}
