'use client'

import { useEffect, useState } from 'react'
import { Eye, EyeOff, Pencil, Trash2, Plus, Loader2, AlertTriangle } from 'lucide-react'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'

type Scope = 'weekly' | 'daily' | 'both'

type WatchTheme = {
  id: number
  name: string
  description: string
  active: boolean
  sort_order: number
  scope: Scope
  created_at: string
  updated_at: string
}

const SCOPE_LABEL: Record<Scope, string> = { weekly: 'Weekly', daily: 'Daily', both: 'Weekly + Daily' }

export default function WatchThemesPage() {
  const [themes, setThemes] = useState<WatchTheme[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<Partial<WatchTheme> | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/watch-themes', { cache: 'no-store' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const data = await r.json()
      setThemes(data.themes || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function save(theme: Partial<WatchTheme>) {
    setSaving(true)
    setError(null)
    try {
      const r = await fetch('/api/watch-themes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(theme),
      })
      if (!r.ok) {
        const msg = await r.json().catch(() => ({}))
        throw new Error(msg.error || `HTTP ${r.status}`)
      }
      setEditing(null)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function remove(id: number) {
    if (!confirm('Delete this theme? It will stop being scanned in future digests.')) return
    setSaving(true)
    try {
      const r = await fetch(`/api/watch-themes?id=${id}`, { method: 'DELETE' })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Watch Themes"
        description="Curated natural-language themes scanned against AI & Technology transcripts. Each active theme produces a section in your personal digest (emailed to brownpr0@gmail.com and shown on Harold's brief dashboard). Scope controls whether a theme is scanned in the weekly digest, the daily digest, or both."
        actions={
          editing === null && (
            <button
              onClick={() => setEditing({ name: '', description: '', active: true, sort_order: 100, scope: 'weekly' })}
              className="btn btn-primary"
            >
              <Plus size={14} /> Add theme
            </button>
          )
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

      {editing !== null && (
        <div className="mb-[var(--space-6)]">
          <ThemeEditor theme={editing} onCancel={() => setEditing(null)} onSave={save} saving={saving} />
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-[var(--space-2)] text-ink-subtle">
          <Loader2 size={16} className="animate-spin" /> Loading themes…
        </div>
      ) : (
        <div className="flex flex-col gap-[var(--space-4)]">
          {themes.length === 0 && <p className="text-ink-subtle">No watch themes yet.</p>}
          {themes.map((theme) => (
            <div key={theme.id} className="card card-hover">
              <div className="flex flex-wrap items-start justify-between gap-[var(--space-3)]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-[var(--space-2)]">
                    <h3 style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>{theme.name}</h3>
                    <Pill tone={theme.active ? 'success' : 'neutral'}>{theme.active ? 'Active' : 'Inactive'}</Pill>
                    <Pill tone="accent">{SCOPE_LABEL[theme.scope] || theme.scope}</Pill>
                    <span className="micro">sort {theme.sort_order}</span>
                  </div>
                  <p className="mt-[var(--space-3)] text-ink-muted" style={{ font: 'var(--t-body)' }}>
                    {theme.description}
                  </p>
                </div>
                <div className="flex shrink-0 gap-[var(--space-2)]">
                  <button disabled={saving} onClick={() => setEditing(theme)} className="btn btn-secondary btn-sm">
                    <Pencil size={13} /> Edit
                  </button>
                  <button
                    disabled={saving}
                    onClick={() => save({ ...theme, active: !theme.active })}
                    className="btn btn-secondary btn-sm"
                  >
                    {theme.active ? <EyeOff size={13} /> : <Eye size={13} />}
                    {theme.active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button disabled={saving} onClick={() => remove(theme.id)} className="btn btn-secondary btn-sm hover:text-danger">
                    <Trash2 size={13} /> Delete
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

function ThemeEditor({
  theme,
  onCancel,
  onSave,
  saving,
}: {
  theme: Partial<WatchTheme>
  onCancel: () => void
  onSave: (t: Partial<WatchTheme>) => void
  saving: boolean
}) {
  const [name, setName] = useState(theme.name || '')
  const [description, setDescription] = useState(theme.description || '')
  const [sortOrder, setSortOrder] = useState(theme.sort_order ?? 100)
  const [active, setActive] = useState(theme.active ?? true)
  const [scope, setScope] = useState<Scope>(theme.scope ?? 'weekly')

  return (
    <div className="card" style={{ borderColor: 'var(--accent)' }}>
      <h3 className="mb-[var(--space-4)]" style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>
        {theme.id ? `Editing theme #${theme.id}` : 'New theme'}
      </h3>

      <label className="field-label" htmlFor="theme-name">
        Name
      </label>
      <input
        id="theme-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="input"
        placeholder="Short descriptive title"
      />

      <label className="field-label mt-[var(--space-4)]" htmlFor="theme-description">
        Description (the scan prompt)
      </label>
      <textarea
        id="theme-description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={5}
        className="textarea"
        placeholder="Describe what transcripts should match this theme. The scan uses this verbatim as part of the claude -p prompt."
      />

      <div className="mt-[var(--space-4)] grid grid-cols-1 gap-[var(--space-4)] sm:grid-cols-3">
        <div>
          <label className="field-label" htmlFor="theme-scope">
            Scope
          </label>
          <select
            id="theme-scope"
            value={scope}
            onChange={(e) => setScope(e.target.value as Scope)}
            className="select"
          >
            <option value="weekly">Weekly digest</option>
            <option value="daily">Daily digest</option>
            <option value="both">Weekly + daily</option>
          </select>
          <p className="field-hint">Which digest run scans this theme.</p>
        </div>

        <div>
          <label className="field-label" htmlFor="theme-sort">
            Sort order
          </label>
          <input
            id="theme-sort"
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(Number(e.target.value))}
            className="input"
          />
        </div>

        <div className="flex items-end pb-[10px]">
          <label className="flex items-center gap-[var(--space-2)] text-ink" style={{ font: 'var(--t-small)' }}>
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              className="h-4 w-4 accent-[var(--accent)]"
            />
            Active
          </label>
        </div>
      </div>

      <div className="mt-[var(--space-5)] flex gap-[var(--space-3)]">
        <button
          disabled={saving || !name.trim() || !description.trim()}
          onClick={() =>
            onSave({
              id: theme.id,
              name: name.trim(),
              description: description.trim(),
              sort_order: sortOrder,
              active,
              scope,
            })
          }
          className="btn btn-primary"
        >
          {saving ? (
            <>
              <Loader2 size={14} className="animate-spin" /> Saving…
            </>
          ) : (
            'Save'
          )}
        </button>
        <button onClick={onCancel} disabled={saving} className="btn btn-secondary">
          Cancel
        </button>
      </div>
    </div>
  )
}
