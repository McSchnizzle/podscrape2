'use client'

import { useEffect, useState } from 'react'

type WatchTheme = {
  id: number
  name: string
  description: string
  active: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

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
    if (!confirm('Delete this theme? It will stop being scanned in future weekly digests.'))
      return
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
    <div style={{ maxWidth: 860, margin: '24px auto', padding: '0 16px' }}>
      <h1 style={{ fontSize: 28, marginBottom: 4 }}>Watch Themes</h1>
      <p style={{ color: '#666', marginBottom: 20, fontSize: 14 }}>
        Curated natural-language themes scanned every Sunday against the week&apos;s
        AI &amp; Technology transcripts. Each active theme produces a section in
        your personal weekly digest (emailed to brownpr0@gmail.com + displayed on
        Harold&apos;s brief dashboard).
      </p>

      {error && (
        <div style={{
          padding: 12, marginBottom: 16, background: '#fee', border: '1px solid #fcc',
          borderRadius: 4, color: '#900',
        }}>
          {error}
        </div>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : (
        <>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {themes.map(theme => (
              <li key={theme.id} style={{
                marginBottom: 16, padding: 16, background: '#fafafa',
                border: '1px solid #e5e5e5', borderRadius: 6,
              }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                  <strong style={{ fontSize: 16 }}>
                    {theme.active ? '' : '[inactive] '}{theme.name}
                  </strong>
                  <span style={{ color: '#888', fontSize: 12 }}>
                    sort {theme.sort_order}
                  </span>
                </div>
                <p style={{ margin: '8px 0', color: '#444', fontSize: 14, lineHeight: 1.5 }}>
                  {theme.description}
                </p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    disabled={saving}
                    onClick={() => setEditing(theme)}
                    style={btnStyle}
                  >
                    Edit
                  </button>
                  <button
                    disabled={saving}
                    onClick={() => save({ ...theme, active: !theme.active })}
                    style={btnStyle}
                  >
                    {theme.active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button
                    disabled={saving}
                    onClick={() => remove(theme.id)}
                    style={{ ...btnStyle, color: '#b00' }}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>

          {editing === null ? (
            <button
              onClick={() => setEditing({ name: '', description: '', active: true, sort_order: 100 })}
              style={{ ...btnStyle, marginTop: 12 }}
            >
              + Add new theme
            </button>
          ) : (
            <ThemeEditor
              theme={editing}
              onCancel={() => setEditing(null)}
              onSave={save}
              saving={saving}
            />
          )}
        </>
      )}
    </div>
  )
}

const btnStyle: React.CSSProperties = {
  padding: '6px 12px', background: '#fff', border: '1px solid #ccc',
  borderRadius: 4, cursor: 'pointer', fontSize: 13,
}

function ThemeEditor({
  theme, onCancel, onSave, saving,
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

  return (
    <div style={{
      marginTop: 16, padding: 16, background: '#fff',
      border: '1px solid #7c8aff', borderRadius: 6,
    }}>
      <h3 style={{ marginTop: 0 }}>
        {theme.id ? `Editing theme #${theme.id}` : 'New theme'}
      </h3>
      <label style={labelStyle}>Name</label>
      <input
        value={name}
        onChange={e => setName(e.target.value)}
        style={inputStyle}
        placeholder="Short descriptive title"
      />
      <label style={labelStyle}>Description (the scan prompt)</label>
      <textarea
        value={description}
        onChange={e => setDescription(e.target.value)}
        rows={5}
        style={{ ...inputStyle, fontFamily: 'inherit', resize: 'vertical' }}
        placeholder="Describe what transcripts should match this theme. The weekly scan uses this verbatim as part of the claude -p prompt."
      />
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 8 }}>
        <label style={{ ...labelStyle, display: 'inline-flex', marginBottom: 0 }}>
          <span style={{ marginRight: 6 }}>Sort order</span>
          <input
            type="number"
            value={sortOrder}
            onChange={e => setSortOrder(Number(e.target.value))}
            style={{ ...inputStyle, width: 80, display: 'inline-block' }}
          />
        </label>
        <label style={{ ...labelStyle, display: 'inline-flex', marginBottom: 0 }}>
          <input
            type="checkbox"
            checked={active}
            onChange={e => setActive(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          Active (scanned weekly)
        </label>
      </div>
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button
          disabled={saving || !name.trim() || !description.trim()}
          onClick={() => onSave({
            id: theme.id,
            name: name.trim(),
            description: description.trim(),
            sort_order: sortOrder,
            active,
          })}
          style={{ ...btnStyle, background: '#7c8aff', color: '#fff', borderColor: '#7c8aff' }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button onClick={onCancel} style={btnStyle} disabled={saving}>
          Cancel
        </button>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 13, color: '#555', marginTop: 12, marginBottom: 4,
}
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', fontSize: 14,
  border: '1px solid #ccc', borderRadius: 4, boxSizing: 'border-box',
}
