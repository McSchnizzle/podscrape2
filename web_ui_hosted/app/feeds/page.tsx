'use client'

import { useState, useEffect } from 'react'
import { Feed } from '@/utils/supabase'

export default function FeedsPage() {
  const [feeds, setFeeds] = useState<Feed[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingFeed, setEditingFeed] = useState<Feed | null>(null)
  const [newFeed, setNewFeed] = useState({ url: '', title: '' })

  useEffect(() => {
    fetchFeeds()
  }, [])

  const fetchFeeds = async () => {
    try {
      const response = await fetch('/api/feeds')
      const data = await response.json()

      if (response.ok) {
        setFeeds(data.feeds || [])
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to load feeds' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to connect to feeds API' })
    } finally {
      setLoading(false)
    }
  }

  const addFeed = async () => {
    if (!newFeed.url || !newFeed.title) {
      setMessage({ type: 'error', text: 'URL and title are required' })
      return
    }

    setSaving(true)
    try {
      const response = await fetch('/api/feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newFeed)
      })

      const data = await response.json()

      if (response.ok) {
        setFeeds([data.feed, ...feeds])
        setNewFeed({ url: '', title: '' })
        setShowAddForm(false)
        setMessage({ type: 'success', text: 'Feed added successfully' })
        setTimeout(() => setMessage(null), 3000)
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to add feed' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to add feed' })
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
        body: JSON.stringify(updates)
      })

      const data = await response.json()

      if (response.ok) {
        setFeeds(feeds.map(feed => feed.id === id ? data.feed : feed))
        setEditingFeed(null)
        setMessage({ type: 'success', text: 'Feed updated successfully' })
        setTimeout(() => setMessage(null), 3000)
      } else {
        setMessage({ type: 'error', text: data.error || 'Failed to update feed' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to update feed' })
    } finally {
      setSaving(false)
    }
  }

  const deleteFeed = async (id: number) => {
    if (!confirm('Are you sure you want to delete this feed? This action cannot be undone.')) {
      return
    }

    setSaving(true)
    try {
      const response = await fetch(`/api/feeds/${id}`, {
        method: 'DELETE'
      })

      if (response.ok) {
        setFeeds(feeds.filter(feed => feed.id !== id))
        setMessage({ type: 'success', text: 'Feed deleted successfully' })
        setTimeout(() => setMessage(null), 3000)
      } else {
        const data = await response.json()
        setMessage({ type: 'error', text: data.error || 'Failed to delete feed' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to delete feed' })
    } finally {
      setSaving(false)
    }
  }

  const toggleFeedActive = async (id: number, is_active: boolean) => {
    await updateFeed(id, { is_active })
  }

  const getHealthStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-success-700 bg-success-50 border-success-200'
      case 'warning': return 'text-warning-700 bg-warning-50 border-warning-200'
      case 'error': return 'text-error-700 bg-error-50 border-error-200'
      default: return 'text-gray-700 bg-gray-50 border-gray-200'
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
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">RSS Feeds</h1>
          <p className="mt-1 text-gray-600">Manage podcast RSS feeds and monitoring status</p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="btn-primary"
          disabled={saving}
        >
          Add Feed
        </button>
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

      {/* Add Feed Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Add New Feed</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  RSS Feed URL
                </label>
                <input
                  type="url"
                  className="input"
                  value={newFeed.url}
                  onChange={(e) => setNewFeed({ ...newFeed, url: e.target.value })}
                  placeholder="https://example.com/feed.xml"
                  disabled={saving}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Feed Title
                </label>
                <input
                  type="text"
                  className="input"
                  value={newFeed.title}
                  onChange={(e) => setNewFeed({ ...newFeed, title: e.target.value })}
                  placeholder="Podcast Name"
                  disabled={saving}
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowAddForm(false)
                  setNewFeed({ url: '', title: '' })
                }}
                className="btn-secondary"
                disabled={saving}
              >
                Cancel
              </button>
              <button
                onClick={addFeed}
                className="btn-primary"
                disabled={saving || !newFeed.url || !newFeed.title}
              >
                {saving ? 'Adding...' : 'Add Feed'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Feed Modal */}
      {editingFeed && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Edit Feed</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  RSS Feed URL
                </label>
                <input
                  type="url"
                  className="input"
                  value={editingFeed.url}
                  onChange={(e) => setEditingFeed({ ...editingFeed, url: e.target.value })}
                  disabled={saving}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Feed Title
                </label>
                <input
                  type="text"
                  className="input"
                  value={editingFeed.title}
                  onChange={(e) => setEditingFeed({ ...editingFeed, title: e.target.value })}
                  disabled={saving}
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => setEditingFeed(null)}
                className="btn-secondary"
                disabled={saving}
              >
                Cancel
              </button>
              <button
                onClick={() => updateFeed(editingFeed.id, {
                  url: editingFeed.url,
                  title: editingFeed.title
                })}
                className="btn-primary"
                disabled={saving || !editingFeed.url || !editingFeed.title}
              >
                {saving ? 'Updating...' : 'Update Feed'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Feeds List */}
      <div className="grid grid-cols-1 gap-4">
        {feeds.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-gray-500 text-lg">No RSS feeds configured</p>
            <p className="text-gray-400 text-sm mt-2">Add your first podcast RSS feed to get started</p>
          </div>
        ) : (
          feeds.map((feed) => (
            <div key={feed.id} className="card">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-3">
                    <h3 className="text-lg font-medium text-gray-900 truncate">
                      {feed.title}
                    </h3>
                    <span className={`px-2 py-1 text-xs font-medium rounded border ${getHealthStatusColor(feed.health_status)}`}>
                      {feed.health_status}
                    </span>
                    <span className={`px-2 py-1 text-xs font-medium rounded border ${
                      feed.is_active
                        ? 'text-success-700 bg-success-50 border-success-200'
                        : 'text-gray-700 bg-gray-50 border-gray-200'
                    }`}>
                      {feed.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1 truncate">
                    {feed.url}
                  </p>
                  {feed.last_checked && (
                    <p className="text-xs text-gray-400 mt-1">
                      Last checked: {new Date(feed.last_checked).toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="flex items-center space-x-2 ml-4">
                  <button
                    onClick={() => toggleFeedActive(feed.id, !feed.is_active)}
                    className={`btn-sm ${
                      feed.is_active
                        ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        : 'bg-success-100 text-success-700 hover:bg-success-200'
                    }`}
                    disabled={saving}
                  >
                    {feed.is_active ? 'Disable' : 'Enable'}
                  </button>
                  <button
                    onClick={() => setEditingFeed(feed)}
                    className="btn-sm btn-secondary"
                    disabled={saving}
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => deleteFeed(feed.id)}
                    className="btn-sm bg-error-100 text-error-700 hover:bg-error-200"
                    disabled={saving}
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {saving && (
        <div className="fixed bottom-4 right-4 bg-primary-600 text-white px-4 py-2 rounded-md shadow-lg">
          Processing...
        </div>
      )}
    </div>
  )
}