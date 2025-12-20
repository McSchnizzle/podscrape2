'use client';

import { useState, useEffect, useRef } from 'react';

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
  // Track pending filter changes that haven't been applied yet
  // IMPORTANT: This must be declared with other useState hooks (React rules of hooks)
  const [pendingFilters, setPendingFilters] = useState({
    q: '',
    status: '',
    sortBy: 'scored_at',
    sortDir: 'desc'
  });
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize] = useState(25);  // Could be made configurable later
  const [totalPages, setTotalPages] = useState(0);
  const [totalCount, setTotalCount] = useState(0);

  // Track if this is the first render to avoid double-loading
  const isFirstRender = useRef(true);

  const loadEpisodes = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });

      // Add pagination parameters
      params.append('page', String(currentPage));
      params.append('pageSize', String(pageSize));

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
        setTotalCount(data.total || 0);
        setTotalPages(data.totalPages || 1);
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

  // Auto-apply filters when dropdown values change (skip search field for debouncing)
  useEffect(() => {
    // Skip the first render (initial load handles it)
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    console.log('[Episodes] Auto-applying filters due to change:', pendingFilters);
    setFilters(pendingFilters);
    setCurrentPage(0);  // Reset to first page on filter change
    loadEpisodesWithFilters({ ...pendingFilters, page: 0 });
  }, [pendingFilters.status, pendingFilters.sortBy, pendingFilters.sortDir]);

  const handleFilterChange = (key: string, value: string) => {
    console.log('[Episodes] handleFilterChange:', key, '=', value);
    setPendingFilters(prev => ({ ...prev, [key]: value }));
  };

  const loadEpisodesWithFilters = async (filterOverride?: typeof filters & { page?: number }) => {
    console.log('[Episodes] loadEpisodesWithFilters called, filterOverride:', filterOverride);
    const activeFilters = filterOverride || filters;
    const page = filterOverride?.page ?? currentPage;
    console.log('[Episodes] activeFilters:', activeFilters, 'page:', page);
    setLoading(true);
    try {
      const params = new URLSearchParams();
      Object.entries(activeFilters).forEach(([key, value]) => {
        if (key !== 'page' && value) params.append(key, String(value));
      });

      // Add pagination parameters
      params.append('page', String(page));
      params.append('pageSize', String(pageSize));

      // Add cache-busting timestamp to prevent stale data
      params.append('_t', Date.now().toString());

      console.log('[Episodes] loadEpisodesWithFilters: Making API request to:', `/api/episodes?${params}`);
      const response = await fetch(`/api/episodes?${params}`, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        }
      });
      console.log('[Episodes] loadEpisodesWithFilters: Response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        console.log('[Episodes] loadEpisodesWithFilters: Got', data.episodes?.length, 'episodes');
        setEpisodes(data.episodes || []);
        setTotalCount(data.total || 0);
        setTotalPages(data.totalPages || 1);
        setMessage(null);
      } else {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        console.error('[Episodes] loadEpisodesWithFilters: Failed to load episodes:', errorData);
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
        <div className="mb-4 grid grid-cols-1 md:grid-cols-10 gap-2 items-end">
          <div className="md:col-span-5">
            <label className="block text-xs text-gray-600 mb-1">Search (press Enter)</label>
            <input
              type="text"
              value={pendingFilters.q}
              onChange={(e) => handleFilterChange('q', e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  setCurrentPage(0);  // Reset to first page on search
                  setFilters(prev => ({ ...prev, q: pendingFilters.q }));
                  loadEpisodesWithFilters({ ...pendingFilters, page: 0 });
                }
              }}
              placeholder="Search episode title"
              className="border px-3 py-2 rounded w-full"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs text-gray-600 mb-1">Status</label>
            <select
              value={pendingFilters.status}
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
              value={pendingFilters.sortBy}
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
              value={pendingFilters.sortDir}
              onChange={(e) => handleFilterChange('sortDir', e.target.value)}
              className="border px-2 py-2 rounded w-full"
            >
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </select>
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

        {/* Pagination Controls */}
        {!loading && episodes.length > 0 && (
          <div className="mt-4 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              Showing {currentPage * pageSize + 1} - {Math.min((currentPage + 1) * pageSize, totalCount)} of {totalCount} episodes
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  const newPage = Math.max(0, currentPage - 1);
                  setCurrentPage(newPage);
                  loadEpisodesWithFilters({ ...filters, page: newPage });
                }}
                disabled={currentPage === 0}
                className="px-3 py-1 text-sm border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Previous
              </button>
              <span className="px-3 py-1 text-sm">
                Page {currentPage + 1} of {totalPages}
              </span>
              <button
                onClick={() => {
                  const newPage = Math.min(totalPages - 1, currentPage + 1);
                  setCurrentPage(newPage);
                  loadEpisodesWithFilters({ ...filters, page: newPage });
                }}
                disabled={currentPage >= totalPages - 1}
                className="px-3 py-1 text-sm border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}