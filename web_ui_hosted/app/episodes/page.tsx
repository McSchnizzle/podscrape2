'use client';

import { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { EPISODE_STATUSES } from '@/utils/supabase';

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

// Empty string for "All" filter, then valid statuses
const statusOptions = ['', ...EPISODE_STATUSES];
const sortByOptions = [
  { value: 'scored_at', label: 'Scored' },
  { value: 'published_date', label: 'Published' },
  { value: 'title', label: 'Title' },
  { value: 'status', label: 'Status' }
];

function EpisodesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);

  // Initialize filters from URL params on mount
  const [filters, setFilters] = useState({
    q: searchParams.get('q') || '',
    status: searchParams.get('status') || '',
    sortBy: searchParams.get('sortBy') || 'scored_at',
    sortDir: searchParams.get('sortDir') || 'desc'
  });

  // Use ref to track current filter values for synchronous access in applyFilters
  // This fixes the React state closure issue where async state updates may not be visible
  const filtersRef = useRef(filters);
  useEffect(() => {
    filtersRef.current = filters;
  }, [filters]);

  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Pagination state - initialize from URL
  const [currentPage, setCurrentPage] = useState(
    parseInt(searchParams.get('page') || '0')
  );
  const [pageSize] = useState(25);  // Could be made configurable later
  const [totalPages, setTotalPages] = useState(0);
  const [totalCount, setTotalCount] = useState(0);

  // Function to update URL with current filters
  const updateUrl = (newFilters: typeof filters, page: number) => {
    const params = new URLSearchParams();
    if (newFilters.q) params.set('q', newFilters.q);
    if (newFilters.status) params.set('status', newFilters.status);
    if (newFilters.sortBy !== 'scored_at') params.set('sortBy', newFilters.sortBy);
    if (newFilters.sortDir !== 'desc') params.set('sortDir', newFilters.sortDir);
    if (page > 0) params.set('page', String(page));

    const queryString = params.toString();
    router.push(queryString ? `/episodes?${queryString}` : '/episodes', { scroll: false });
  };

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

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  // Apply current filters - uses ref to ensure we read latest state values
  const applyFilters = () => {
    const currentFilters = filtersRef.current;
    setCurrentPage(0);
    updateUrl(currentFilters, 0);
    loadEpisodesWithFilters({ ...currentFilters, page: 0 });
  };

  // Reset all filters to defaults
  const resetFilters = () => {
    const defaultFilters = {
      q: '',
      status: '',
      sortBy: 'scored_at',
      sortDir: 'desc'
    };
    setFilters(defaultFilters);
    setCurrentPage(0);
    updateUrl(defaultFilters, 0);
    loadEpisodesWithFilters({ ...defaultFilters, page: 0 });
  };

  // Check if any filters are active (non-default)
  const hasActiveFilters = filters.q || filters.status ||
    filters.sortBy !== 'scored_at' || filters.sortDir !== 'desc';

  // Remove a specific filter and reset to default
  const removeFilter = (key: keyof typeof filters) => {
    const defaultValues: typeof filters = {
      q: '',
      status: '',
      sortBy: 'scored_at',
      sortDir: 'desc'
    };
    const newFilters = { ...filters, [key]: defaultValues[key] };
    setFilters(newFilters);
    setCurrentPage(0);
    updateUrl(newFilters, 0);
    loadEpisodesWithFilters({ ...newFilters, page: 0 });
  };

  const loadEpisodesWithFilters = async (filterOverride?: typeof filters & { page?: number }) => {
    const activeFilters = filterOverride || filters;
    const page = filterOverride?.page ?? currentPage;
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
        <div className="mb-4 grid grid-cols-1 md:grid-cols-12 gap-2 items-end">
          <div className="md:col-span-5">
            <label className="block text-xs text-gray-600 mb-1">Search</label>
            <input
              type="text"
              value={filters.q}
              onChange={(e) => handleFilterChange('q', e.target.value)}
              placeholder="Search episode or feed title"
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

          <div className="md:col-span-2 flex gap-2">
            <button
              onClick={applyFilters}
              className="flex-1 px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 text-sm font-medium"
            >
              Apply
            </button>
            <button
              onClick={resetFilters}
              className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 text-sm font-medium"
            >
              Reset
            </button>
          </div>
        </div>

        {/* Active Filter Chips */}
        {hasActiveFilters && (
          <div className="mb-4 flex flex-wrap gap-2 items-center">
            <span className="text-sm text-gray-500">Active filters:</span>
            {filters.q && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-800">
                Search: {filters.q}
                <button
                  onClick={() => removeFilter('q')}
                  className="ml-1 hover:text-primary-600"
                  aria-label="Remove search filter"
                >
                  <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </span>
            )}
            {filters.status && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                Status: {filters.status}
                <button
                  onClick={() => removeFilter('status')}
                  className="ml-1 hover:text-green-600"
                  aria-label="Remove status filter"
                >
                  <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </span>
            )}
            {filters.sortBy !== 'scored_at' && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                Sort: {sortByOptions.find(o => o.value === filters.sortBy)?.label}
                <button
                  onClick={() => removeFilter('sortBy')}
                  className="ml-1 hover:text-gray-600"
                  aria-label="Remove sort filter"
                >
                  <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </span>
            )}
            {filters.sortDir !== 'desc' && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                Direction: Asc
                <button
                  onClick={() => removeFilter('sortDir')}
                  className="ml-1 hover:text-gray-600"
                  aria-label="Remove direction filter"
                >
                  <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </span>
            )}
          </div>
        )}

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
                  updateUrl(filters, newPage);
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
                  updateUrl(filters, newPage);
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

export default function EpisodesPage() {
  return (
    <Suspense fallback={
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white shadow rounded p-6">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
            <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          </div>
        </div>
      </div>
    }>
      <EpisodesContent />
    </Suspense>
  );
}