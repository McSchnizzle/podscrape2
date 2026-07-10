'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import {
  Flame,
  Trash2,
  ChevronDown,
  GitMerge,
  X,
  Loader2,
  Layers,
  Activity,
  TrendingUp,
  Megaphone,
  CheckCircle2,
  Plus,
  Pencil,
} from 'lucide-react'
import { toast } from '@/components/Toast'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill, type PillTone } from '@/components/ui/Pill'
import { StatCard } from '@/components/ui/StatCard'

interface StoryArcEvent {
  id: number
  event_date: string
  event_summary: string
  key_points: string[]
  source_name: string | null
  perspective: string | null
  relevance_score: number | null
  extracted_at: string
}

interface StoryArc {
  id: number
  arc_name: string
  arc_slug: string
  functional_category: string
  digest_topic: string
  summary: string | null
  started_at: string
  last_updated_at: string
  event_count: number
  source_count: number
  saturation_score: number | null
  is_hot: boolean
  hot_briefing: string | null
  retain_until: string | null
  included_in_digest_id: number | null
  included_at: string | null
  created_at: string
  events?: StoryArcEvent[]
}

interface CommonAd {
  id: number
  advertiser_name: string
  pattern_keywords: string[]
  confidence_threshold: number
  is_active: boolean
  detection_count: number
  created_at: string
  updated_at: string
}

interface Stats {
  total_arcs: number
  total_events: number
  arcs_by_category: Record<string, number>
  arcs_by_digest: Record<string, number>
  avg_events_per_arc: number
  total_ads: number
  active_ads: number
}

const CATEGORY_TYPES = [
  { value: 'model_release', label: 'Model Release' },
  { value: 'company_strategy', label: 'Company Strategy' },
  { value: 'research', label: 'Research' },
  { value: 'regulation', label: 'Regulation' },
  { value: 'product_launch', label: 'Product Launch' },
  { value: 'partnership', label: 'Partnership' },
  { value: 'controversy', label: 'Controversy' },
  { value: 'industry_trend', label: 'Industry Trend' },
  { value: 'technique', label: 'Technique' },
  { value: 'use_case', label: 'Use Case' },
  { value: 'other', label: 'Other' },
]

const CATEGORY_TONE: Record<string, PillTone> = {
  model_release: 'accent',
  company_strategy: 'neutral',
  research: 'accent',
  regulation: 'danger',
  product_launch: 'success',
  partnership: 'success',
  controversy: 'danger',
  industry_trend: 'accent',
  technique: 'accent',
  use_case: 'accent',
  other: 'neutral',
}

const PERSPECTIVE_TONE: Record<string, PillTone> = {
  positive: 'success',
  negative: 'danger',
  neutral: 'neutral',
  analytical: 'accent',
}

export default function StoryArcsPage() {
  const [arcs, setArcs] = useState<StoryArc[]>([])
  const [ads, setAds] = useState<CommonAd[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'arcs' | 'ads'>('arcs')

  // Arc filters
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [digestFilter, setDigestFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')

  // Modal states
  const [expandedArcId, setExpandedArcId] = useState<number | null>(null)
  const [showAdModal, setShowAdModal] = useState(false)
  const [editingAd, setEditingAd] = useState<CommonAd | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ type: 'arc' | 'ad', id: number } | null>(null)
  const [saving, setSaving] = useState(false)

  // Inline editing states
  const [editingNameId, setEditingNameId] = useState<number | null>(null)
  const [editingNameValue, setEditingNameValue] = useState('')
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null)
  const [editingSummaryId, setEditingSummaryId] = useState<number | null>(null)
  const [editingSummaryValue, setEditingSummaryValue] = useState('')
  const [editingBriefingId, setEditingBriefingId] = useState<number | null>(null)
  const [editingBriefingValue, setEditingBriefingValue] = useState('')

  // Merge selection states
  const [selectedArcIds, setSelectedArcIds] = useState<number[]>([])
  const [showMergeModal, setShowMergeModal] = useState(false)
  const [mergePrimaryId, setMergePrimaryId] = useState<number | null>(null)
  const [merging, setMerging] = useState(false)

  // Refs for inline editing
  const nameInputRef = useRef<HTMLInputElement>(null)
  const summaryTextareaRef = useRef<HTMLTextAreaElement>(null)
  const briefingTextareaRef = useRef<HTMLTextAreaElement>(null)

  // Form states
  const [adForm, setAdForm] = useState({
    advertiser_name: '',
    pattern_keywords: [''],
    confidence_threshold: 0.8,
    is_active: true
  })

  useEffect(() => {
    loadData()
  }, [categoryFilter, digestFilter, searchQuery])

  // Focus input when editing starts
  useEffect(() => {
    if (editingNameId !== null && nameInputRef.current) {
      nameInputRef.current.focus()
      nameInputRef.current.select()
    }
  }, [editingNameId])

  useEffect(() => {
    if (editingSummaryId !== null && summaryTextareaRef.current) {
      summaryTextareaRef.current.focus()
    }
  }, [editingSummaryId])

  useEffect(() => {
    if (editingBriefingId !== null && briefingTextareaRef.current) {
      briefingTextareaRef.current.focus()
    }
  }, [editingBriefingId])

  const loadData = async () => {
    try {
      setLoading(true)

      // Build query params
      const params = new URLSearchParams()
      if (categoryFilter) params.set('category', categoryFilter)
      if (digestFilter) params.set('digest', digestFilter)
      if (searchQuery) params.set('search', searchQuery)
      params.set('limit', '100')

      const [arcsRes, adsRes, statsRes] = await Promise.all([
        fetch(`/api/story-arcs/arcs?${params.toString()}`),
        fetch('/api/story-arcs/ads'),
        fetch('/api/story-arcs/stats')
      ])

      if (arcsRes.ok) {
        const data = await arcsRes.json()
        setArcs(data.arcs || [])
      }

      if (adsRes.ok) {
        const data = await adsRes.json()
        setAds(data.ads || [])
      }

      if (statsRes.ok) {
        const data = await statsRes.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getCategoryTone = (category: string): PillTone => {
    return CATEGORY_TONE[category] || 'neutral'
  }

  const getCategoryLabel = (category: string) => {
    return CATEGORY_TYPES.find(c => c.value === category)?.label || category.replace('_', ' ')
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    })
  }

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Sort arcs: hot arcs first, then by last_updated_at descending
  const sortedArcs = [...arcs].sort((a, b) => {
    if (a.is_hot && !b.is_hot) return -1
    if (!a.is_hot && b.is_hot) return 1
    return new Date(b.last_updated_at).getTime() - new Date(a.last_updated_at).getTime()
  })

  // Arc update helper
  const updateArc = useCallback(async (id: number, updates: Record<string, unknown>) => {
    try {
      const res = await fetch(`/api/story-arcs/arcs/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })
      if (res.ok) {
        const data = await res.json()
        setArcs(prev => prev.map(a => a.id === id ? { ...a, ...data.arc } : a))
        return true
      } else {
        const error = await res.json()
        toast.error('Failed to update arc', {
          description: error.error || 'Unknown error',
          duration: 5000
        })
        return false
      }
    } catch (error) {
      console.error('Failed to update arc:', error)
      toast.error('Failed to update arc', {
        description: 'Network error or server unavailable',
        duration: 5000
      })
      return false
    }
  }, [])

  // Hot toggle handler
  const handleToggleHot = useCallback(async (arc: StoryArc) => {
    const newValue = !arc.is_hot
    // Optimistic update
    setArcs(prev => prev.map(a => a.id === arc.id ? { ...a, is_hot: newValue } : a))
    const success = await updateArc(arc.id, { is_hot: newValue })
    if (!success) {
      // Revert on failure
      setArcs(prev => prev.map(a => a.id === arc.id ? { ...a, is_hot: arc.is_hot } : a))
    }
  }, [updateArc])

  // Inline name editing
  const startEditingName = (arc: StoryArc) => {
    setEditingNameId(arc.id)
    setEditingNameValue(arc.arc_name)
  }

  const saveNameEdit = async (id: number) => {
    const trimmed = editingNameValue.trim()
    if (!trimmed) {
      setEditingNameId(null)
      return
    }
    const arc = arcs.find(a => a.id === id)
    if (arc && trimmed !== arc.arc_name) {
      await updateArc(id, { arc_name: trimmed })
    }
    setEditingNameId(null)
  }

  const cancelNameEdit = () => {
    setEditingNameId(null)
    setEditingNameValue('')
  }

  // Inline category editing
  const handleCategoryChange = async (id: number, newCategory: string) => {
    await updateArc(id, { functional_category: newCategory })
    setEditingCategoryId(null)
  }

  // Inline summary editing
  const startEditingSummary = (arc: StoryArc) => {
    setEditingSummaryId(arc.id)
    setEditingSummaryValue(arc.summary || '')
  }

  const saveSummaryEdit = async (id: number) => {
    const arc = arcs.find(a => a.id === id)
    if (arc && editingSummaryValue !== (arc.summary || '')) {
      await updateArc(id, { summary: editingSummaryValue || null })
    }
    setEditingSummaryId(null)
  }

  // Hot briefing editing
  const startEditingBriefing = (arc: StoryArc) => {
    setEditingBriefingId(arc.id)
    setEditingBriefingValue(arc.hot_briefing || '')
  }

  const saveBriefingEdit = async (id: number) => {
    const arc = arcs.find(a => a.id === id)
    if (arc && editingBriefingValue !== (arc.hot_briefing || '')) {
      await updateArc(id, { hot_briefing: editingBriefingValue || null })
    }
    setEditingBriefingId(null)
  }

  // Merge selection handlers
  const toggleArcSelection = (id: number) => {
    setSelectedArcIds(prev => {
      if (prev.includes(id)) {
        return prev.filter(x => x !== id)
      }
      return [...prev, id]
    })
  }

  const openMergeModal = () => {
    if (selectedArcIds.length < 2) return
    setMergePrimaryId(selectedArcIds[0])
    setShowMergeModal(true)
  }

  const handleMerge = async () => {
    if (!mergePrimaryId || selectedArcIds.length < 2) return
    setMerging(true)
    try {
      const duplicateIds = selectedArcIds.filter(id => id !== mergePrimaryId)
      const res = await fetch('/api/story-arcs/arcs/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ primary_id: mergePrimaryId, duplicate_ids: duplicateIds })
      })

      if (res.ok) {
        const data = await res.json()
        toast.success('Arcs merged successfully', {
          description: `Merged ${data.duplicates_merged} arc(s), moved ${data.events_moved} event(s)`,
          duration: 5000
        })
        setShowMergeModal(false)
        setSelectedArcIds([])
        setMergePrimaryId(null)
        loadData()
      } else {
        const error = await res.json()
        toast.error('Failed to merge arcs', {
          description: error.error || 'Unknown error',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to merge arcs:', error)
      toast.error('Failed to merge arcs', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
    } finally {
      setMerging(false)
    }
  }

  // Arc handlers
  const handleDeleteArc = async (id: number) => {
    try {
      const res = await fetch(`/api/story-arcs/arcs/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setDeleteConfirm(null)
        loadData()
      } else {
        const error = await res.json()
        toast.error('Failed to delete story arc', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to delete arc:', error)
      toast.error('Failed to delete story arc', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
    }
  }

  // Ad CRUD handlers
  const handleEditAd = (ad: CommonAd) => {
    setEditingAd(ad)
    setAdForm({
      advertiser_name: ad.advertiser_name,
      pattern_keywords: ad.pattern_keywords.length > 0 ? ad.pattern_keywords : [''],
      confidence_threshold: ad.confidence_threshold,
      is_active: ad.is_active
    })
    setShowAdModal(true)
  }

  const handleSaveAd = async () => {
    setSaving(true)
    try {
      const payload = {
        ...adForm,
        pattern_keywords: adForm.pattern_keywords.filter(kw => kw.trim() !== '')
      }

      if (payload.pattern_keywords.length === 0) {
        toast.error('Validation Error', {
          description: 'At least one keyword is required',
          duration: 5000
        })
        setSaving(false)
        return
      }

      const url = editingAd
        ? `/api/story-arcs/ads/${editingAd.id}`
        : '/api/story-arcs/ads'
      const method = editingAd ? 'PUT' : 'POST'

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (res.ok) {
        setShowAdModal(false)
        setEditingAd(null)
        setAdForm({
          advertiser_name: '',
          pattern_keywords: [''],
          confidence_threshold: 0.8,
          is_active: true
        })
        loadData()
      } else {
        const error = await res.json()
        toast.error('Failed to save ad', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to save ad:', error)
      toast.error('Failed to save ad', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteAd = async (id: number) => {
    try {
      const res = await fetch(`/api/story-arcs/ads/${id}`, { method: 'DELETE' })
      if (res.ok) {
        setDeleteConfirm(null)
        loadData()
      } else {
        const error = await res.json()
        toast.error('Failed to delete ad', {
          description: error.error || 'Unknown error occurred',
          duration: 8000
        })
      }
    } catch (error) {
      console.error('Failed to delete ad:', error)
      toast.error('Failed to delete ad', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
    }
  }

  const handleToggleAdActive = async (ad: CommonAd) => {
    try {
      const res = await fetch(`/api/story-arcs/ads/${ad.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !ad.is_active })
      })
      if (res.ok) {
        loadData()
      }
    } catch (error) {
      console.error('Failed to toggle ad:', error)
    }
  }

  // Saturation bar color -- returns a token reference, never a raw hex value
  const getSaturationColor = (score: number) => {
    if (score < 0.3) return 'var(--success)'
    if (score <= 0.6) return 'var(--warning)'
    return 'var(--danger)'
  }

  const getSaturationLabel = (score: number) => {
    if (score < 0.3) return 'Low'
    if (score <= 0.6) return 'Medium'
    return 'High'
  }

  return (
    <div>
      <PageHeader
        title="Story Arcs & Ads"
        description="Track evolving news narratives and common ad patterns across episodes."
        actions={
          activeTab === 'ads' ? (
            <button
              onClick={() => {
                setEditingAd(null)
                setAdForm({
                  advertiser_name: '',
                  pattern_keywords: [''],
                  confidence_threshold: 0.8,
                  is_active: true
                })
                setShowAdModal(true)
              }}
              className="btn btn-primary"
            >
              <Plus size={14} /> Add ad pattern
            </button>
          ) : undefined
        }
      />

      {/* Stats */}
      {stats && (
        <div className="mb-[var(--space-6)] grid grid-cols-1 gap-[var(--space-4)] sm:grid-cols-2 lg:grid-cols-5">
          <StatCard label="Story arcs" value={stats.total_arcs} icon={<Layers size={16} />} />
          <StatCard label="Total events" value={stats.total_events} icon={<Activity size={16} />} />
          <StatCard label="Avg events / arc" value={stats.avg_events_per_arc.toFixed(1)} icon={<TrendingUp size={16} />} />
          <StatCard label="Total ads" value={stats.total_ads} icon={<Megaphone size={16} />} />
          <StatCard label="Active ads" value={stats.active_ads} tone="success" icon={<CheckCircle2 size={16} />} />
        </div>
      )}

      {/* Tabs */}
      <div className="mb-[var(--space-6)] flex gap-[var(--space-6)] border-b border-border">
        <button
          onClick={() => setActiveTab('arcs')}
          className={`border-b-2 pb-[var(--space-3)] transition-colors ${
            activeTab === 'arcs'
              ? 'border-accent text-accent'
              : 'border-transparent text-ink-subtle hover:border-border hover:text-ink-muted'
          }`}
          style={{ font: 'var(--t-small)', fontWeight: 600 }}
        >
          Story Arcs ({arcs.length})
        </button>
        <button
          onClick={() => setActiveTab('ads')}
          className={`border-b-2 pb-[var(--space-3)] transition-colors ${
            activeTab === 'ads'
              ? 'border-accent text-accent'
              : 'border-transparent text-ink-subtle hover:border-border hover:text-ink-muted'
          }`}
          style={{ font: 'var(--t-small)', fontWeight: 600 }}
        >
          Common Ads ({ads.length})
        </button>
      </div>

      {/* Story Arcs Tab */}
      {activeTab === 'arcs' && (
        <div className="flex flex-col gap-[var(--space-5)]">
          {/* Filters */}
          <div className="card">
            <div className="grid grid-cols-1 gap-[var(--space-4)] md:grid-cols-3">
              <div>
                <label className="field-label">Search</label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search story arcs..."
                  className="input"
                />
              </div>
              <div>
                <label className="field-label">Category</label>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="select"
                >
                  <option value="">All categories</option>
                  {CATEGORY_TYPES.map(cat => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="field-label">Digest topic</label>
                <input
                  type="text"
                  value={digestFilter}
                  onChange={(e) => setDigestFilter(e.target.value)}
                  placeholder="e.g., AI and Technology"
                  className="input"
                />
              </div>
            </div>
          </div>

          {/* Story Arcs List */}
          {loading ? (
            <div className="card flex flex-col items-center gap-[var(--space-3)] py-[var(--space-8)] text-center text-ink-subtle">
              <Loader2 size={20} className="animate-spin" />
              Loading story arcs…
            </div>
          ) : arcs.length === 0 ? (
            <div className="card py-[var(--space-8)] text-center text-ink-subtle">
              <p>No story arcs found</p>
              <p className="mt-[var(--space-2)] text-ink-faint" style={{ font: 'var(--t-small)' }}>
                Story arcs are automatically created when episodes are processed
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-[var(--space-4)]">
              {sortedArcs.map((arc) => (
                <div
                  key={arc.id}
                  className={`card !p-0 overflow-hidden transition-colors ${
                    selectedArcIds.includes(arc.id) ? 'ring-2 ring-accent' : ''
                  }`}
                  style={arc.is_hot ? { borderColor: 'var(--warm)', boxShadow: '0 0 0 1px var(--warm)' } : undefined}
                >
                  {/* Arc Header */}
                  <div className="p-[var(--space-5)]">
                    <div className="flex items-start gap-[var(--space-3)]">
                      {/* Merge checkbox */}
                      <input
                        type="checkbox"
                        checked={selectedArcIds.includes(arc.id)}
                        onChange={() => toggleArcSelection(arc.id)}
                        className="mt-[6px] h-4 w-4 shrink-0 cursor-pointer accent-[var(--accent)]"
                        title="Select for merge"
                      />

                      {/* Main content - clickable for expand */}
                      <div
                        className="min-w-0 flex-1 cursor-pointer"
                        onClick={() => setExpandedArcId(expandedArcId === arc.id ? null : arc.id)}
                      >
                        <div className="flex flex-wrap items-center gap-[var(--space-2)]">
                          {/* Inline editable name */}
                          {editingNameId === arc.id ? (
                            <input
                              ref={nameInputRef}
                              type="text"
                              value={editingNameValue}
                              onChange={(e) => setEditingNameValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.preventDefault()
                                  saveNameEdit(arc.id)
                                } else if (e.key === 'Escape') {
                                  cancelNameEdit()
                                }
                              }}
                              onBlur={() => saveNameEdit(arc.id)}
                              onClick={(e) => e.stopPropagation()}
                              className="input max-w-sm"
                              style={{ font: 'var(--t-h3)' }}
                            />
                          ) : (
                            <h3
                              className="cursor-text truncate hover:text-accent"
                              style={{ font: 'var(--t-h3)', color: 'var(--text)' }}
                              onClick={(e) => {
                                e.stopPropagation()
                                startEditingName(arc)
                              }}
                              title="Click to edit name"
                            >
                              {arc.is_hot && (
                                <Flame
                                  size={16}
                                  className="mr-1 inline align-[-3px]"
                                  style={{ color: 'var(--warm)' }}
                                  fill="var(--warm)"
                                />
                              )}
                              {arc.arc_name}
                            </h3>
                          )}

                          {/* Category badge - inline editable */}
                          {editingCategoryId === arc.id ? (
                            <select
                              value={arc.functional_category}
                              onChange={(e) => {
                                e.stopPropagation()
                                handleCategoryChange(arc.id, e.target.value)
                              }}
                              onBlur={() => setEditingCategoryId(null)}
                              onClick={(e) => e.stopPropagation()}
                              autoFocus
                              className="select w-auto"
                              style={{ font: 'var(--t-micro)' }}
                            >
                              {CATEGORY_TYPES.map(cat => (
                                <option key={cat.value} value={cat.value}>{cat.label}</option>
                              ))}
                            </select>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                setEditingCategoryId(arc.id)
                              }}
                              title="Click to change category"
                            >
                              <Pill tone={getCategoryTone(arc.functional_category)}>
                                {getCategoryLabel(arc.functional_category)}
                              </Pill>
                            </button>
                          )}

                          {arc.included_in_digest_id && <Pill tone="success">In digest</Pill>}
                        </div>

                        <div
                          className="mt-[var(--space-2)] flex flex-wrap items-center gap-x-[var(--space-4)] gap-y-[var(--space-1)] text-ink-subtle"
                          style={{ font: 'var(--t-small)' }}
                        >
                          <span>{arc.event_count} event{arc.event_count !== 1 ? 's' : ''}</span>
                          <span>{arc.source_count} source{arc.source_count !== 1 ? 's' : ''}</span>
                          <span>Started {formatDate(arc.started_at)}</span>
                          <span>Updated {formatDate(arc.last_updated_at)}</span>
                          {arc.saturation_score != null && arc.saturation_score > 0 && (
                            <span className="flex items-center gap-[4px]">
                              Sat:
                              <span style={{ color: getSaturationColor(arc.saturation_score), fontWeight: 600 }}>
                                {(arc.saturation_score * 100).toFixed(0)}%
                              </span>
                            </span>
                          )}
                        </div>
                        {arc.digest_topic && (
                          <div className="mt-[var(--space-1)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                            Topic: {arc.digest_topic}
                          </div>
                        )}
                      </div>

                      {/* Action buttons */}
                      <div className="flex shrink-0 items-center gap-[var(--space-1)]">
                        {/* Hot toggle button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleToggleHot(arc)
                          }}
                          className="btn btn-ghost btn-sm"
                          style={arc.is_hot ? { background: 'var(--warm-soft)', color: 'var(--warm)' } : undefined}
                          title={arc.is_hot ? 'Remove hot flag' : 'Mark as hot'}
                        >
                          <Flame size={14} fill={arc.is_hot ? 'currentColor' : 'none'} />
                        </button>

                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setDeleteConfirm({ type: 'arc', id: arc.id })
                          }}
                          className="btn btn-ghost btn-sm hover:text-danger"
                          title="Delete arc"
                        >
                          <Trash2 size={14} />
                        </button>
                        <button
                          onClick={() => setExpandedArcId(expandedArcId === arc.id ? null : arc.id)}
                          className="btn btn-ghost btn-sm"
                          title={expandedArcId === arc.id ? 'Collapse' : 'Expand'}
                        >
                          <ChevronDown
                            size={16}
                            className={`transition-transform ${expandedArcId === arc.id ? 'rotate-180' : ''}`}
                          />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Detail Panel */}
                  {expandedArcId === arc.id && (
                    <div className="border-t border-border p-[var(--space-5)]" style={{ background: 'var(--surface-2)' }}>
                      {/* Summary + Saturation + Hot Briefing Section */}
                      <div className="flex flex-col gap-[var(--space-4)]">
                        {/* Summary */}
                        <div>
                          <label className="field-label">Summary</label>
                          {editingSummaryId === arc.id ? (
                            <textarea
                              ref={summaryTextareaRef}
                              value={editingSummaryValue}
                              onChange={(e) => setEditingSummaryValue(e.target.value)}
                              onBlur={() => saveSummaryEdit(arc.id)}
                              onKeyDown={(e) => {
                                if (e.key === 'Escape') {
                                  setEditingSummaryId(null)
                                }
                              }}
                              rows={3}
                              className="textarea"
                              placeholder="Add a summary for this arc..."
                            />
                          ) : (
                            <div
                              className="min-h-[3rem] cursor-text rounded-sm border border-border p-[var(--space-3)] text-ink-muted transition-colors hover:border-border-strong"
                              style={{ background: 'var(--surface-1)', font: 'var(--t-small)' }}
                              onClick={() => startEditingSummary(arc)}
                              title="Click to edit summary"
                            >
                              {arc.summary || <span className="italic text-ink-faint">Click to add summary…</span>}
                            </div>
                          )}
                        </div>

                        {/* Saturation Score */}
                        <div>
                          <label className="field-label">Saturation score</label>
                          <div className="flex items-center gap-[var(--space-3)]">
                            <div className="h-3 flex-1 overflow-hidden rounded-full" style={{ background: 'var(--surface-3)' }}>
                              <div
                                className="h-full rounded-full transition-all"
                                style={{
                                  width: `${Math.min(100, (arc.saturation_score || 0) * 100)}%`,
                                  background: getSaturationColor(arc.saturation_score || 0),
                                }}
                              />
                            </div>
                            <span
                              className="min-w-[6rem] text-right"
                              style={{ font: 'var(--t-small)', fontWeight: 600, color: getSaturationColor(arc.saturation_score || 0) }}
                            >
                              {((arc.saturation_score || 0) * 100).toFixed(0)}% ({getSaturationLabel(arc.saturation_score || 0)})
                            </span>
                          </div>
                        </div>

                        {/* Hot Briefing - only visible when is_hot */}
                        {arc.is_hot && (
                          <div>
                            <label className="field-label flex items-center gap-[6px]" style={{ color: 'var(--warm)' }}>
                              <Flame size={12} /> Hot briefing
                            </label>
                            {editingBriefingId === arc.id ? (
                              <textarea
                                ref={briefingTextareaRef}
                                value={editingBriefingValue}
                                onChange={(e) => setEditingBriefingValue(e.target.value)}
                                onBlur={() => saveBriefingEdit(arc.id)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Escape') {
                                    setEditingBriefingId(null)
                                  }
                                }}
                                rows={6}
                                className="textarea font-mono"
                                style={{ borderColor: 'var(--warm)' }}
                                placeholder="Add hot briefing notes (supports markdown)..."
                              />
                            ) : (
                              <div
                                className="min-h-[4rem] cursor-text whitespace-pre-wrap rounded-sm border p-[var(--space-3)] font-mono text-ink-muted transition-colors"
                                style={{ background: 'var(--warm-soft)', borderColor: 'var(--warm)', font: 'var(--t-small)' }}
                                onClick={() => startEditingBriefing(arc)}
                                title="Click to edit hot briefing"
                              >
                                {arc.hot_briefing || (
                                  <span className="italic" style={{ color: 'var(--warm)' }}>Click to add hot briefing…</span>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Retain Until */}
                        {arc.retain_until && (
                          <div className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                            <span style={{ fontWeight: 600 }}>Retain until:</span> {formatDateTime(arc.retain_until)}
                          </div>
                        )}
                      </div>

                      {/* Events Timeline */}
                      {arc.events && arc.events.length > 0 && (
                        <div className="mt-[var(--space-5)] border-t border-border pt-[var(--space-5)]">
                          <h4 className="mb-[var(--space-4)]" style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
                            Timeline ({arc.events.length} event{arc.events.length !== 1 ? 's' : ''})
                          </h4>
                          <div className="relative">
                            <div className="absolute bottom-0 left-[7px] top-0 w-px" style={{ background: 'var(--border)' }} />
                            <div className="flex flex-col gap-[var(--space-4)]">
                              {arc.events.map((event) => (
                                <div key={event.id} className="relative pl-[var(--space-7)]">
                                  <div
                                    className="absolute left-[3px] top-[6px] h-3 w-3 rounded-full border-2"
                                    style={{ background: 'var(--accent)', borderColor: 'var(--surface-1)' }}
                                  />
                                  <div className="card">
                                    <div className="flex flex-wrap items-center gap-[var(--space-2)]">
                                      <span style={{ font: 'var(--t-small)', fontWeight: 600, color: 'var(--text)' }}>
                                        {formatDate(event.event_date)}
                                      </span>
                                      {event.perspective && (
                                        <Pill tone={PERSPECTIVE_TONE[event.perspective] || 'neutral'}>{event.perspective}</Pill>
                                      )}
                                      {event.relevance_score != null && (
                                        <span className="micro">rel: {(event.relevance_score * 100).toFixed(0)}%</span>
                                      )}
                                    </div>
                                    <p className="mt-[var(--space-2)] text-ink-muted" style={{ font: 'var(--t-small)' }}>
                                      {event.event_summary}
                                    </p>
                                    {event.key_points && event.key_points.length > 0 && (
                                      <ul
                                        className="mt-[var(--space-2)] list-inside list-disc text-ink-subtle"
                                        style={{ font: 'var(--t-small)' }}
                                      >
                                        {event.key_points.map((point, i) => (
                                          <li key={i}>{point}</li>
                                        ))}
                                      </ul>
                                    )}
                                    {event.source_name && (
                                      <div className="mt-[var(--space-2)] text-ink-faint" style={{ font: 'var(--t-small)' }}>
                                        Source: {event.source_name}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* No events message */}
                      {(!arc.events || arc.events.length === 0) && (
                        <div className="mt-[var(--space-5)] border-t border-border pt-[var(--space-5)]">
                          <p className="italic text-ink-faint" style={{ font: 'var(--t-small)' }}>
                            No events recorded for this arc.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Floating Merge Action Bar */}
      {selectedArcIds.length >= 2 && activeTab === 'arcs' && (
        <div className="fixed bottom-[var(--space-6)] left-1/2 z-40 -translate-x-1/2">
          <div className="card shadow-lg flex items-center gap-[var(--space-4)]">
            <span className="text-ink" style={{ font: 'var(--t-small)' }}>
              {selectedArcIds.length} arcs selected
            </span>
            <button onClick={openMergeModal} className="btn btn-primary btn-sm">
              <GitMerge size={14} /> Merge selected
            </button>
            <button onClick={() => setSelectedArcIds([])} className="btn btn-secondary btn-sm">
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Ads Tab */}
      {activeTab === 'ads' && (
        <div className="flex flex-col gap-[var(--space-4)]">
          {loading ? (
            <div className="card flex flex-col items-center gap-[var(--space-3)] py-[var(--space-8)] text-center text-ink-subtle">
              <Loader2 size={20} className="animate-spin" />
              Loading ads…
            </div>
          ) : ads.length === 0 ? (
            <div className="card py-[var(--space-8)] text-center text-ink-subtle">
              <p>No ads found</p>
              <button onClick={() => setShowAdModal(true)} className="btn btn-primary mt-[var(--space-4)]">
                <Plus size={14} /> Add first ad pattern
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-[var(--space-4)] md:grid-cols-2">
              {ads.map((ad) => (
                <div key={ad.id} className="card">
                  <div className="flex items-start justify-between gap-[var(--space-3)]">
                    <div className="min-w-0">
                      <h3 className="truncate" style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
                        {ad.advertiser_name}
                      </h3>
                      <div className="mt-[var(--space-2)] flex flex-wrap items-center gap-[var(--space-2)]">
                        <button
                          onClick={() => handleToggleAdActive(ad)}
                          className={ad.is_active ? 'pill pill-success' : 'pill'}
                        >
                          {ad.is_active ? 'Active' : 'Inactive'}
                        </button>
                        <span className="text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                          Detected {ad.detection_count} time{ad.detection_count === 1 ? '' : 's'}
                        </span>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-[var(--space-1)]">
                      <button onClick={() => handleEditAd(ad)} className="btn btn-ghost btn-sm" title="Edit">
                        <Pencil size={13} />
                      </button>
                      <button
                        onClick={() => setDeleteConfirm({ type: 'ad', id: ad.id })}
                        className="btn btn-ghost btn-sm hover:text-danger"
                        title="Delete"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>

                  <div
                    className="mt-[var(--space-4)] flex items-baseline justify-between gap-[var(--space-3)] rounded-sm p-[var(--space-3)]"
                    style={{ background: 'var(--surface-2)' }}
                  >
                    <span className="micro">Confidence threshold</span>
                    <span style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
                      {(ad.confidence_threshold * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="mt-[var(--space-4)]">
                    <div className="field-label">Keywords</div>
                    <div className="flex flex-wrap gap-[var(--space-2)]">
                      {ad.pattern_keywords.map((keyword, idx) => (
                        <span key={idx} className="pill">{keyword}</span>
                      ))}
                    </div>
                  </div>

                  <div
                    className="mt-[var(--space-4)] flex flex-wrap gap-x-[var(--space-4)] border-t border-border pt-[var(--space-3)] text-ink-faint"
                    style={{ font: 'var(--t-micro)' }}
                  >
                    <span>Created {formatDateTime(ad.created_at)}</span>
                    <span>Updated {formatDateTime(ad.updated_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Merge Modal */}
      {showMergeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]" style={{ background: 'var(--scrim)' }}>
          <div className="card !p-0 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="border-b border-border px-[var(--space-5)] py-[var(--space-4)]">
              <h2 style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>Merge story arcs</h2>
              <p className="mt-[var(--space-2)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                Select the primary arc. All events from duplicate arcs will be moved into it, and the duplicates will be deleted.
              </p>
            </div>
            <div className="flex flex-col gap-[var(--space-3)] px-[var(--space-5)] py-[var(--space-4)]">
              <label className="field-label">Primary arc (keep this one)</label>
              {selectedArcIds.map(id => {
                const arc = arcs.find(a => a.id === id)
                if (!arc) return null
                const isPrimary = mergePrimaryId === id
                return (
                  <div
                    key={id}
                    onClick={() => setMergePrimaryId(id)}
                    className="cursor-pointer rounded-sm border p-[var(--space-3)] transition-colors"
                    style={{
                      borderColor: isPrimary ? 'var(--accent)' : 'var(--border)',
                      background: isPrimary ? 'var(--accent-soft)' : 'var(--surface-1)',
                    }}
                  >
                    <div className="flex items-center gap-[var(--space-3)]">
                      <div
                        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2"
                        style={{ borderColor: isPrimary ? 'var(--accent)' : 'var(--border-strong)' }}
                      >
                        {isPrimary && <div className="h-2 w-2 rounded-full" style={{ background: 'var(--accent)' }} />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <span style={{ font: 'var(--t-small)', fontWeight: 600, color: 'var(--text)' }}>{arc.arc_name}</span>{' '}
                        <Pill tone={getCategoryTone(arc.functional_category)}>{getCategoryLabel(arc.functional_category)}</Pill>
                      </div>
                      <span className="micro">{arc.event_count} events</span>
                    </div>
                    {isPrimary && (
                      <div className="ml-[28px] mt-[var(--space-1)]" style={{ font: 'var(--t-micro)', color: 'var(--accent)' }}>
                        Primary — will be kept
                      </div>
                    )}
                    {!isPrimary && mergePrimaryId !== null && (
                      <div className="ml-[28px] mt-[var(--space-1)]" style={{ font: 'var(--t-micro)', color: 'var(--danger)' }}>
                        Duplicate — will be merged and deleted
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
            <div className="flex justify-end gap-[var(--space-3)] border-t border-border px-[var(--space-5)] py-[var(--space-4)]">
              <button
                onClick={() => {
                  setShowMergeModal(false)
                  setMergePrimaryId(null)
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button onClick={handleMerge} disabled={merging || !mergePrimaryId} className="btn btn-primary">
                {merging ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Merging…
                  </>
                ) : (
                  `Merge ${selectedArcIds.length} Arcs`
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ad Modal */}
      {showAdModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]" style={{ background: 'var(--scrim)' }}>
          <div className="card !p-0 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="border-b border-border px-[var(--space-5)] py-[var(--space-4)]">
              <h2 style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>
                {editingAd ? 'Edit ad pattern' : 'Create ad pattern'}
              </h2>
            </div>
            <div className="flex flex-col gap-[var(--space-4)] px-[var(--space-5)] py-[var(--space-4)]">
              <div>
                <label className="field-label">Advertiser name *</label>
                <input
                  type="text"
                  value={adForm.advertiser_name}
                  onChange={(e) => setAdForm({ ...adForm, advertiser_name: e.target.value })}
                  className="input"
                />
              </div>
              <div>
                <label className="field-label">Pattern keywords *</label>
                <div className="flex flex-col gap-[var(--space-2)]">
                  {adForm.pattern_keywords.map((kw, idx) => (
                    <div key={idx} className="flex gap-[var(--space-2)]">
                      <input
                        type="text"
                        value={kw}
                        onChange={(e) => {
                          const newKws = [...adForm.pattern_keywords]
                          newKws[idx] = e.target.value
                          setAdForm({ ...adForm, pattern_keywords: newKws })
                        }}
                        placeholder="Enter keyword..."
                        className="input flex-1"
                      />
                      <button
                        onClick={() => {
                          const newKws = adForm.pattern_keywords.filter((_, i) => i !== idx)
                          setAdForm({ ...adForm, pattern_keywords: newKws.length > 0 ? newKws : [''] })
                        }}
                        className="btn btn-ghost btn-sm hover:text-danger"
                        title="Remove keyword"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => setAdForm({ ...adForm, pattern_keywords: [...adForm.pattern_keywords, ''] })}
                  className="mt-[var(--space-2)] inline-flex items-center gap-[4px]"
                  style={{ font: 'var(--t-small)', color: 'var(--accent)' }}
                >
                  <Plus size={12} /> Add keyword
                </button>
              </div>
              <div>
                <label className="field-label">Confidence threshold</label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={adForm.confidence_threshold}
                  onChange={(e) => setAdForm({ ...adForm, confidence_threshold: parseFloat(e.target.value) })}
                  className="input"
                />
                <p className="field-hint">
                  Minimum confidence required to identify this ad pattern (0.0 - 1.0)
                </p>
              </div>
              <label className="flex items-center gap-[var(--space-2)] text-ink" style={{ font: 'var(--t-small)' }}>
                <input
                  type="checkbox"
                  checked={adForm.is_active}
                  onChange={(e) => setAdForm({ ...adForm, is_active: e.target.checked })}
                  className="h-4 w-4 accent-[var(--accent)]"
                />
                Active (actively filtering this ad pattern)
              </label>
            </div>
            <div className="flex justify-end gap-[var(--space-3)] border-t border-border px-[var(--space-5)] py-[var(--space-4)]">
              <button
                onClick={() => {
                  setShowAdModal(false)
                  setEditingAd(null)
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button onClick={handleSaveAd} disabled={saving || !adForm.advertiser_name} className="btn btn-primary">
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]" style={{ background: 'var(--scrim)' }}>
          <div className="card w-full max-w-md">
            <h2 className="mb-[var(--space-3)]" style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>
              Confirm delete
            </h2>
            <p className="text-ink-muted" style={{ font: 'var(--t-body)' }}>
              Are you sure you want to delete this {deleteConfirm.type === 'arc' ? 'story arc' : 'ad'}?
              {deleteConfirm.type === 'arc' && ' All associated events will also be deleted.'}
              {' '}This action cannot be undone.
            </p>
            <div className="mt-[var(--space-5)] flex justify-end gap-[var(--space-3)]">
              <button onClick={() => setDeleteConfirm(null)} className="btn btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => {
                  if (deleteConfirm.type === 'arc') {
                    handleDeleteArc(deleteConfirm.id)
                  } else {
                    handleDeleteAd(deleteConfirm.id)
                  }
                }}
                className="btn btn-danger"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
