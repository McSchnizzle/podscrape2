'use client'

import { useState, useEffect } from 'react'
import { Feed } from '@/utils/supabase'

export default function FeedsPage() {
  const [feeds, setFeeds] = useState<Feed[]>([])
  const [rssFeeds, setRssFeeds] = useState<Feed[]>([])
  const [youtubeFeeds, setYoutubeFeeds] = useState<Feed[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [checking, setChecking] = useState<number | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingFeed, setEditingFeed] = useState<Feed | null>(null)
  const [newFeed, setNewFeed] = useState({ feed_url: '', title: '' })
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table')

  useEffect(() => {
    fetchFeeds()
  }, [])

  const fetchFeeds = async () => {
    try {
      const response = await fetch('/api/feeds')
      const data = await response.json()

      if (response.ok) {
        const allFeeds = data.feeds || []
        setFeeds(allFeeds)

        // Separate RSS and YouTube feeds
        const rss = allFeeds.filter((feed: Feed) => !feed.feed_url.includes('youtube.com') && !feed.feed_url.includes('youtu.be'))
        const yt = allFeeds.filter((feed: Feed) => feed.feed_url.includes('youtube.com') || feed.feed_url.includes('youtu.be'))

        setRssFeeds(rss)
        setYoutubeFeeds(yt)
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
    if (!newFeed.feed_url || !newFeed.title) {
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
        await fetchFeeds() // Refresh all feeds to update categorization
        setNewFeed({ feed_url: '', title: '' })
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
        await fetchFeeds() // Refresh all feeds to update categorization
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
        await fetchFeeds() // Refresh all feeds to update categorization
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

  const toggleFeedActive = async (id: number, active: boolean) => {
    await updateFeed(id, { active })
  }

  const checkFeed = async (id: number) => {
    setChecking(id)
    try {
      const response = await fetch(`/api/feeds/${id}/check`, {
        method: 'POST'
      })

      if (response.ok) {
        await fetchFeeds() // Refresh feeds to show updated last_checked time
        setMessage({ type: 'success', text: 'Feed checked successfully' })
        setTimeout(() => setMessage(null), 3000)
      } else {
        const data = await response.json()
        setMessage({ type: 'error', text: data.error || 'Failed to check feed' })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to check feed' })
    } finally {
      setChecking(null)
    }
  }

  const getHealthStatusColor = (consecutive_failures: number) => {
    if (consecutive_failures === 0) {
      return 'text-success-700 bg-success-50 border-success-200'
    } else if (consecutive_failures <= 2) {
      return 'text-warning-700 bg-warning-50 border-warning-200'
    } else {
      return 'text-error-700 bg-error-50 border-error-200'
    }
  }

  const getHealthStatusText = (consecutive_failures: number) => {
    if (consecutive_failures === 0) {
      return 'healthy'
    } else if (consecutive_failures <= 2) {
      return 'warning'
    } else {
      return 'error'
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
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">RSS Feeds</h1>
          <p className="mt-1 text-gray-600">Manage podcast RSS feeds and monitoring status</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="flex rounded-md shadow-sm">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-2 text-sm font-medium rounded-l-md border ${
                viewMode === 'table'
                  ? 'bg-primary-50 text-primary-700 border-primary-200'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              Table
            </button>
            <button
              onClick={() => setViewMode('cards')}
              className={`px-3 py-2 text-sm font-medium rounded-r-md border-t border-r border-b ${
                viewMode === 'cards'
                  ? 'bg-primary-50 text-primary-700 border-primary-200'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              Cards
            </button>
          </div>
          <button
            onClick={() => setShowAddForm(true)}
            className="btn-primary whitespace-nowrap"
            disabled={saving}
          >
            Add Feed
          </button>
        </div>
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

      {/* Add Feed Form - Flask-style horizontal layout */}
      <div className="card">
        <h3 className="font-semibold mb-3">Add New Feed</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Feed URL
            </label>
            <input
              type="url"
              className="input w-full"
              value={newFeed.feed_url}
              onChange={(e) => setNewFeed({ ...newFeed, feed_url: e.target.value })}
              placeholder="https://... or file:///"
              disabled={saving}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title (optional)
            </label>
            <input
              type="text"
              className="input w-full"
              value={newFeed.title}
              onChange={(e) => setNewFeed({ ...newFeed, title: e.target.value })}
              placeholder="Auto-filled if possible"
              disabled={saving}
            />
          </div>
          <div>
            <button
              onClick={addFeed}
              className="btn-secondary w-full"
              disabled={saving || !newFeed.feed_url}
            >
              {saving ? 'Adding...' : 'Add Feed'}
            </button>
          </div>
        </div>
      </div>

      {/* Edit Feed Modal */}
      {editingFeed && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Edit Feed</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  RSS Feed URL
                </label>
                <input
                  type="url"
                  className="input"
                  value={editingFeed.feed_url}
                  onChange={(e) => setEditingFeed({ ...editingFeed, feed_url: e.target.value })}
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
                  feed_url: editingFeed.feed_url,
                  title: editingFeed.title
                })}
                className="btn-primary"
                disabled={saving || !editingFeed.feed_url || !editingFeed.title}
              >
                {saving ? 'Updating...' : 'Update Feed'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RSS Feeds Section */}
      <div className="space-y-6">
        <div>
          <h3 className="font-semibold mb-4">RSS Feeds</h3>
          {viewMode === 'table' ? (
            <div className="overflow-x-auto">
              <table className="min-w-full border border-gray-300 rounded-lg">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="text-left p-3 border-b font-medium text-gray-700">Title</th>
                    <th className="text-left p-3 border-b font-medium text-gray-700 hidden sm:table-cell">URL</th>
                    <th className="text-left p-3 border-b font-medium text-gray-700 hidden lg:table-cell">Latest Episode</th>
                    <th className="text-left p-3 border-b font-medium text-gray-700 hidden lg:table-cell">Published</th>
                    <th className="text-left p-3 border-b font-medium text-gray-700">Active</th>
                    <th className="text-left p-3 border-b font-medium text-gray-700 hidden md:table-cell">Last Checked</th>
                    <th className="text-left p-3 border-b font-medium text-gray-700 hidden md:table-cell">Failures</th>
                    <th className="text-left p-3 border-b font-medium text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rssFeeds.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="p-6 text-center text-gray-500">No RSS feeds</td>
                    </tr>
                  ) : (
                    rssFeeds.map((feed) => (
                      <tr key={feed.id} className="border-t hover:bg-gray-50">
                        <td className="p-3 align-top">
                          <div>
                            <div className="font-medium text-gray-900">{feed.title}</div>
                            <div className="sm:hidden text-xs text-gray-500 mt-1 break-all">{feed.feed_url}</div>
                          </div>
                        </td>
                        <td className="p-3 align-top text-sm text-blue-700 break-all hidden sm:table-cell max-w-xs truncate">
                          {feed.feed_url}
                        </td>
                        <td className="p-3 align-top text-sm hidden lg:table-cell max-w-xs truncate">
                          {feed.latest_episode_title || '-'}
                        </td>
                        <td className="p-3 align-top text-sm hidden lg:table-cell">
                          {feed.last_episode_date ? new Date(feed.last_episode_date).toLocaleDateString() : '-'}
                        </td>
                        <td className="p-3 align-top">
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${
                            feed.active
                              ? 'text-success-700 bg-success-50 border-success-200'
                              : 'text-gray-700 bg-gray-50 border-gray-200'
                          }`}>
                            {feed.active ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="p-3 align-top text-sm hidden md:table-cell">
                          {feed.last_checked ? new Date(feed.last_checked).toLocaleString() : '-'}
                        </td>
                        <td className="p-3 align-top hidden md:table-cell">
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${getHealthStatusColor(feed.consecutive_failures)}`}>
                            {feed.consecutive_failures}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <div className="flex flex-wrap gap-1">
                            <button
                              onClick={() => toggleFeedActive(feed.id, !feed.active)}
                              className="px-2 py-1 text-xs rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300"
                              disabled={saving}
                            >
                              {feed.active ? 'Deactivate' : 'Activate'}
                            </button>
                            <button
                              onClick={() => checkFeed(feed.id)}
                              className="px-2 py-1 text-xs rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300"
                              disabled={checking === feed.id}
                            >
                              {checking === feed.id ? 'Checking...' : 'Check'}
                            </button>
                            <button
                              onClick={() => setEditingFeed(feed)}
                              className="px-2 py-1 text-xs rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300"
                              disabled={saving}
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteFeed(feed.id)}
                              className="px-2 py-1 text-xs rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300"
                              disabled={saving}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {rssFeeds.length === 0 ? (
                <div className="card text-center py-12">
                  <p className="text-gray-500 text-lg">No RSS feeds configured</p>
                  <p className="text-gray-400 text-sm mt-2">Add your first podcast RSS feed to get started</p>
                </div>
              ) : (
                rssFeeds.map((feed) => (
                  <div key={feed.id} className="card">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <h3 className="text-lg font-medium text-gray-900 truncate">
                            {feed.title}
                          </h3>
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${getHealthStatusColor(feed.consecutive_failures)}`}>
                            {getHealthStatusText(feed.consecutive_failures)}
                          </span>
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${
                            feed.active
                              ? 'text-success-700 bg-success-50 border-success-200'
                              : 'text-gray-700 bg-gray-50 border-gray-200'
                          }`}>
                            {feed.active ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mb-2 break-all">
                          {feed.feed_url}
                        </p>
                        {feed.latest_episode_title && (
                          <p className="text-sm text-gray-600 mb-1">
                            Latest: {feed.latest_episode_title}
                          </p>
                        )}
                        {feed.last_checked && (
                          <p className="text-xs text-gray-400">
                            Last checked: {new Date(feed.last_checked).toLocaleString()}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => toggleFeedActive(feed.id, !feed.active)}
                          className={`btn-sm ${
                            feed.active
                              ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                              : 'bg-success-100 text-success-700 hover:bg-success-200'
                          }`}
                          disabled={saving}
                        >
                          {feed.active ? 'Disable' : 'Enable'}
                        </button>
                        <button
                          onClick={() => checkFeed(feed.id)}
                          className="btn-sm bg-primary-100 text-primary-700 hover:bg-primary-200"
                          disabled={checking === feed.id}
                        >
                          {checking === feed.id ? 'Checking...' : 'Check'}
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
          )}
        </div>

        {/* YouTube Feeds Section */}
        {youtubeFeeds.length > 0 && (
          <div>
            <h3 className="font-semibold mb-4">YouTube Feeds</h3>
            {viewMode === 'table' ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-300 rounded-lg">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="text-left p-3 border-b font-medium text-gray-700">Title</th>
                      <th className="text-left p-3 border-b font-medium text-gray-700 hidden sm:table-cell">URL</th>
                      <th className="text-left p-3 border-b font-medium text-gray-700">Active</th>
                      <th className="text-left p-3 border-b font-medium text-gray-700 hidden md:table-cell">Last Checked</th>
                      <th className="text-left p-3 border-b font-medium text-gray-700 hidden md:table-cell">Failures</th>
                      <th className="text-left p-3 border-b font-medium text-gray-700">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {youtubeFeeds.map((feed) => (
                      <tr key={feed.id} className="border-t hover:bg-gray-50">
                        <td className="p-3 align-top">
                          <div>
                            <div className="font-medium text-gray-900">{feed.title}</div>
                            <div className="sm:hidden text-xs text-gray-500 mt-1 break-all">{feed.feed_url}</div>
                          </div>
                        </td>
                        <td className="p-3 align-top text-sm text-blue-700 break-all hidden sm:table-cell max-w-xs truncate">
                          {feed.feed_url}
                        </td>
                        <td className="p-3 align-top">
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${
                            feed.active
                              ? 'text-success-700 bg-success-50 border-success-200'
                              : 'text-gray-700 bg-gray-50 border-gray-200'
                          }`}>
                            {feed.active ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="p-3 align-top text-sm hidden md:table-cell">
                          {feed.last_checked ? new Date(feed.last_checked).toLocaleString() : '-'}
                        </td>
                        <td className="p-3 align-top hidden md:table-cell">
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${getHealthStatusColor(feed.consecutive_failures)}`}>
                            {feed.consecutive_failures}
                          </span>
                        </td>
                        <td className="p-3 align-top">
                          <div className="flex flex-wrap gap-1">
                            <button
                              onClick={() => toggleFeedActive(feed.id, !feed.active)}
                              className={`px-2 py-1 text-xs rounded ${
                                feed.active
                                  ? 'bg-yellow-600 text-white hover:bg-yellow-700'
                                  : 'bg-green-600 text-white hover:bg-green-700'
                              }`}
                              disabled={saving}
                            >
                              {feed.active ? 'Deactivate' : 'Activate'}
                            </button>
                            <button
                              onClick={() => checkFeed(feed.id)}
                              className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700"
                              disabled={checking === feed.id}
                            >
                              {checking === feed.id ? 'Checking...' : 'Check'}
                            </button>
                            <button
                              onClick={() => setEditingFeed(feed)}
                              className="px-2 py-1 text-xs rounded bg-gray-600 text-white hover:bg-gray-700"
                              disabled={saving}
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteFeed(feed.id)}
                              className="px-2 py-1 text-xs rounded bg-gray-600 text-white hover:bg-gray-700"
                              disabled={saving}
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {youtubeFeeds.map((feed) => (
                  <div key={feed.id} className="card">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-2">
                          <h3 className="text-lg font-medium text-gray-900 truncate">
                            {feed.title}
                          </h3>
                          <span className="px-2 py-1 text-xs font-medium rounded bg-red-100 text-red-700 border border-red-200">
                            YouTube
                          </span>
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${getHealthStatusColor(feed.consecutive_failures)}`}>
                            {getHealthStatusText(feed.consecutive_failures)}
                          </span>
                          <span className={`px-2 py-1 text-xs font-medium rounded border ${
                            feed.active
                              ? 'text-success-700 bg-success-50 border-success-200'
                              : 'text-gray-700 bg-gray-50 border-gray-200'
                          }`}>
                            {feed.active ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mb-2 break-all">
                          {feed.feed_url}
                        </p>
                        {feed.last_checked && (
                          <p className="text-xs text-gray-400">
                            Last checked: {new Date(feed.last_checked).toLocaleString()}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => toggleFeedActive(feed.id, !feed.active)}
                          className={`btn-sm ${
                            feed.active
                              ? 'bg-yellow-600 text-white hover:bg-yellow-700'
                              : 'bg-green-600 text-white hover:bg-green-700'
                          }`}
                          disabled={saving}
                        >
                          {feed.active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button
                          onClick={() => checkFeed(feed.id)}
                          className="btn-sm bg-blue-600 text-white hover:bg-blue-700"
                          disabled={checking === feed.id}
                        >
                          {checking === feed.id ? 'Checking...' : 'Check'}
                        </button>
                        <button
                          onClick={() => setEditingFeed(feed)}
                          className="btn-sm bg-gray-600 text-white hover:bg-gray-700"
                          disabled={saving}
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => deleteFeed(feed.id)}
                          className="btn-sm bg-gray-600 text-white hover:bg-gray-700"
                          disabled={saving}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
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