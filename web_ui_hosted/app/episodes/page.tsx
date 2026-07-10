'use client';

import { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { X, RotateCcw, Undo2, Loader2 } from 'lucide-react';
import { EPISODE_STATUSES } from '@/lib/constants';
import { PageHeader } from '@/components/ui/PageHeader';
import { Pill, type PillTone } from '@/components/ui/Pill';

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

const STATUS_TONE: Record<string, PillTone> = {
  pending: 'neutral',
  processing: 'accent',
  transcribed: 'accent',
  scored: 'accent',
  digested: 'success',
  not_relevant: 'neutral',
  failed: 'danger',
};

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
    <div>
      <PageHeader title="Episodes" description="Source episodes moving through discovery, scoring, and digest inclusion." />

      <div className="card">
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

        {/* Filters */}
        <div className="mb-[var(--space-4)] grid grid-cols-1 items-end gap-[var(--space-3)] md:grid-cols-12">
          <div className="md:col-span-5">
            <label className="field-label">Search</label>
            <input
              type="text"
              value={filters.q}
              onChange={(e) => handleFilterChange('q', e.target.value)}
              placeholder="Search episode or feed title"
              className="input"
            />
          </div>

          <div className="md:col-span-2">
            <label className="field-label">Status</label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="select"
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
            <label className="field-label">Sort by</label>
            <select
              value={filters.sortBy}
              onChange={(e) => handleFilterChange('sortBy', e.target.value)}
              className="select"
            >
              {sortByOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-1">
            <label className="field-label">Dir</label>
            <select
              value={filters.sortDir}
              onChange={(e) => handleFilterChange('sortDir', e.target.value)}
              className="select"
            >
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </select>
          </div>

          <div className="flex gap-[var(--space-2)] md:col-span-2">
            <button onClick={applyFilters} className="btn btn-primary flex-1 justify-center">
              Apply
            </button>
            <button onClick={resetFilters} className="btn btn-secondary flex-1 justify-center">
              Reset
            </button>
          </div>
        </div>

        {/* Active Filter Chips */}
        {hasActiveFilters && (
          <div className="mb-[var(--space-4)] flex flex-wrap items-center gap-[var(--space-2)]">
            <span className="micro">Active filters:</span>
            {filters.q && (
              <button onClick={() => removeFilter('q')} className="pill pill-accent" aria-label="Remove search filter">
                Search: {filters.q} <X size={12} />
              </button>
            )}
            {filters.status && (
              <button onClick={() => removeFilter('status')} className="pill pill-success" aria-label="Remove status filter">
                Status: {filters.status} <X size={12} />
              </button>
            )}
            {filters.sortBy !== 'scored_at' && (
              <button onClick={() => removeFilter('sortBy')} className="pill" aria-label="Remove sort filter">
                Sort: {sortByOptions.find(o => o.value === filters.sortBy)?.label} <X size={12} />
              </button>
            )}
            {filters.sortDir !== 'desc' && (
              <button onClick={() => removeFilter('sortDir')} className="pill" aria-label="Remove direction filter">
                Direction: Asc <X size={12} />
              </button>
            )}
          </div>
        )}

        {/* Episodes Table */}
        <div className="table-shell overflow-x-auto">
          <table className="house-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Feed</th>
                <th>Published</th>
                <th>Status</th>
                <th>Scores</th>
                <th>Included in</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-[var(--space-6)] text-center text-ink-subtle">
                    <Loader2 size={16} className="mr-2 inline animate-spin" /> Loading episodes…
                  </td>
                </tr>
              ) : episodes.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-[var(--space-6)] text-center text-ink-subtle">
                    No episodes found
                  </td>
                </tr>
              ) : (
                episodes.map((episode) => (
                  <tr key={episode.id}>
                    <td className="max-w-[280px]">{episode.title}</td>
                    <td className="text-ink-muted">
                      <span className="font-mono text-xs">{episode.feed_title_display}</span>
                    </td>
                    <td className="text-ink-muted">
                      <span className="font-mono text-xs">{formatDate(episode.published_date)}</span>
                    </td>
                    <td>
                      <Pill tone={STATUS_TONE[episode.status] || 'neutral'}>{episode.status}</Pill>
                    </td>
                    <td className="text-ink-muted">
                      <span className="font-mono text-xs">{episode.score_labels}</span>
                    </td>
                    <td className="text-ink-muted">
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
                        <span className="text-xs text-ink-faint">—</span>
                      )}
                    </td>
                    <td>
                      <div className="flex flex-col items-start gap-[var(--space-2)]">
                        <button
                          onClick={() => handleEpisodeAction(episode.id, 'undigest')}
                          className="flex items-center gap-1 whitespace-nowrap text-xs hover:underline"
                          style={{ color: 'var(--accent)' }}
                          title="Reset to scored and restore transcript if archived"
                        >
                          <Undo2 size={12} /> Reset to Scored
                        </button>
                        <button
                          onClick={() => handleEpisodeAction(episode.id, 'reset_to_pending')}
                          className="flex items-center gap-1 whitespace-nowrap text-xs hover:underline"
                          style={{ color: 'var(--warm)' }}
                          title="Reset to pending status, clear scores, and remove from digests"
                        >
                          <RotateCcw size={12} /> Reset to Pending
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {!loading && episodes.length > 0 && (
          <div className="mt-[var(--space-4)] flex items-center justify-between">
            <div className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>
              Showing {currentPage * pageSize + 1} - {Math.min((currentPage + 1) * pageSize, totalCount)} of {totalCount} episodes
            </div>
            <div className="flex gap-[var(--space-2)]">
              <button
                onClick={() => {
                  const newPage = Math.max(0, currentPage - 1);
                  setCurrentPage(newPage);
                  updateUrl(filters, newPage);
                  loadEpisodesWithFilters({ ...filters, page: newPage });
                }}
                disabled={currentPage === 0}
                className="btn btn-secondary btn-sm"
              >
                Previous
              </button>
              <span className="flex items-center px-[var(--space-2)] text-ink-muted" style={{ font: 'var(--t-small)' }}>
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
                className="btn btn-secondary btn-sm"
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
      <div>
        <PageHeader title="Episodes" description="Source episodes moving through discovery, scoring, and digest inclusion." />
        <div className="card h-64 animate-pulse" />
      </div>
    }>
      <EpisodesContent />
    </Suspense>
  );
}
