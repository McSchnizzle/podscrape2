'use client';

import { useState, useEffect } from 'react';

interface Episode {
  id: number;
  title: string;
  status: string;
  published_date?: string;
  scored_at?: string;
  feed_title_display: string;
  score_labels: string;
  included: Array<{ topic: string; date: string }>;
  scores: Record<string, number>;
}

const statusOptions = ['', 'pending', 'transcribed', 'scored', 'digested', 'published', 'not_relevant', 'failed'];
const sortByOptions = [
  { value: 'scored_at', label: 'Scored' },
  { value: 'published_date', label: 'Published' },
  { value: 'title', label: 'Title' },
  { value: 'status', label: 'Status' }
];

export default function EpisodesPage() {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    q: '',
    status: '',
    sortBy: 'scored_at',
    sortDir: 'desc'
  });
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadEpisodes = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });

      // Add cache-busting timestamp to prevent stale data
      params.append('_t', Date.now().toString());

      const response = await fetch(`/api/episodes?${params}`, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setEpisodes(data.episodes || []);
        setMessage(null); // Clear any previous error messages
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        console.error('Failed to load episodes:', errorData);
        setMessage({
          type: 'error',
          text: `Failed to load episodes: ${errorData.error || 'Unknown error'}`
        });
      }
    } catch (error) {
      console.error('Error loading episodes:', error);
      setMessage({
        type: 'error',
        text: `Network error loading episodes: ${error instanceof Error ? error.message : 'Unknown error'}`
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEpisodes();
  }, []);

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleApplyFilters = () => {
    loadEpisodes();
  };

  const handleEpisodeAction = async (episodeId: number, action: string) => {
    if (action === 'reset_to_pending' && !confirm('This will reset to pending status, clear all scores, and remove from any digests. Are you sure?')) {
      return;
    }

    try {
      const response = await fetch(`/api/episodes/${episodeId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ action }),
      });

      if (response.ok) {
        const data = await response.json();
        setMessage({ type: 'success', text: data.message });
        loadEpisodes(); // Reload episodes
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.error || 'Action failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to process action' });
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    return dateString.split('T')[0]; // Show just the date part
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="bg-white shadow rounded p-6">
        <h2 className="text-xl font-medium mb-4">Episodes</h2>

        {/* Message Display */}
        {message && (
          <div className={`px-4 py-3 rounded mb-4 ${
            message.type === 'success'
              ? 'bg-green-100 border border-green-400 text-green-700'
              : 'bg-red-100 border border-red-400 text-red-700'
          }`}>
            {message.text}
          </div>
        )}

        {/* Filters */}
        <div className="mb-4 grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
          <div className="md:col-span-5">
            <label className="block text-xs text-gray-600 mb-1">Search</label>
            <input
              type="text"
              value={filters.q}
              onChange={(e) => handleFilterChange('q', e.target.value)}
              placeholder="Search title or feed"
              className="border px-3 py-2 rounded w-full"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs text-gray-600 mb-1">Status</label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="border px-2 py-2 rounded w-full"
            >
              <option value="">Any</option>
              {statusOptions.slice(1).map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs text-gray-600 mb-1">Sort By</label>
            <select
              value={filters.sortBy}
              onChange={(e) => handleFilterChange('sortBy', e.target.value)}
              className="border px-2 py-2 rounded w-full"
            >
              {sortByOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-1">
            <label className="block text-xs text-gray-600 mb-1">Dir</label>
            <select
              value={filters.sortDir}
              onChange={(e) => handleFilterChange('sortDir', e.target.value)}
              className="border px-2 py-2 rounded w-full"
            >
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </select>
          </div>

          <div className="md:col-span-2">
            <button
              onClick={handleApplyFilters}
              disabled={loading}
              className="px-4 py-2 rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300 w-full disabled:opacity-50"
            >
              Apply
            </button>
          </div>
        </div>

        {/* Episodes Table */}
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2 pr-4">Title</th>
                <th className="py-2 pr-4">Feed</th>
                <th className="py-2 pr-4">Published</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Scores</th>
                <th className="py-2 pr-4">Included In</th>
                <th className="py-2 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-4 text-center text-gray-500">
                    Loading episodes...
                  </td>
                </tr>
              ) : episodes.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-4 text-center text-gray-500">
                    No episodes found
                  </td>
                </tr>
              ) : (
                episodes.map((episode) => (
                  <tr key={episode.id} className="border-b align-top">
                    <td className="py-2 pr-4">{episode.title}</td>
                    <td className="py-2 pr-4 text-gray-600">
                      <span className="font-mono text-xs">{episode.feed_title_display}</span>
                    </td>
                    <td className="py-2 pr-4 text-gray-600">
                      <span className="font-mono text-xs">{formatDate(episode.published_date)}</span>
                    </td>
                    <td className="py-2 pr-4">
                      <span className="font-mono text-xs">{episode.status}</span>
                    </td>
                    <td className="py-2 pr-4 text-gray-700">
                      <span className="font-mono text-xs">{episode.score_labels}</span>
                    </td>
                    <td className="py-2 pr-4 text-gray-700">
                      {episode.included.length > 0 ? (
                        <span className="font-mono text-xs">
                          {/* Show most recent digest for multi-digest episodes */}
                          {(() => {
                            const sortedInclusions = [...episode.included].sort((a, b) =>
                              new Date(b.date).getTime() - new Date(a.date).getTime()
                            )
                            const mostRecent = sortedInclusions[0]
                            return `${mostRecent.topic} — ${mostRecent.date}`
                          })()}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-500">—</span>
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      <button
                        onClick={() => handleEpisodeAction(episode.id, 'undigest')}
                        className="text-blue-700 text-xs hover:underline"
                        title="Reset to scored and restore transcript if archived"
                      >
                        Reset to Scored
                      </button>
                      <span className="text-gray-400 text-xs mx-1">|</span>
                      <button
                        onClick={() => handleEpisodeAction(episode.id, 'reset_to_pending')}
                        className="text-orange-700 text-xs hover:underline"
                        title="Reset to pending status, clear scores, and remove from digests"
                      >
                        Reset to Pending
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}