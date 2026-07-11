'use client'

import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, X } from 'lucide-react'
import { toast } from '@/components/Toast'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill, type PillTone } from '@/components/ui/Pill'
import { StatCard } from '@/components/ui/StatCard'

interface Task {
  id: number
  title: string
  description: string
  status: string
  priority: string
  category: string
  submission_date: string
  last_update_date: string
  version_introduced: string | null
  version_completed: string | null
  files_affected: string[] | null
  completion_notes: string | null
  estimated_effort: string | null
  session_number: number | null
  tags: string[] | null
  created_by: string | null
  assigned_to: string | null
}

interface TaskStats {
  total: number
  byStatus: {
    open: number
    in_progress: number
    on_hold: number
    completed: number
    skipped: number
  }
  byPriority: {
    P0: number
    P1: number
    P2: number
    P3: number
  }
}

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'on_hold', label: 'On Hold' },
  { value: 'completed', label: 'Completed' },
  { value: 'skipped', label: 'Skipped' },
]

const STATUS_TONE: Record<string, PillTone> = {
  open: 'neutral',
  in_progress: 'accent',
  on_hold: 'warning',
  completed: 'success',
  skipped: 'danger',
}

const PRIORITY_OPTIONS = [
  { value: 'P0', label: 'P0 (Critical)' },
  { value: 'P1', label: 'P1 (High)' },
  { value: 'P2', label: 'P2 (Medium)' },
  { value: 'P3', label: 'P3 (Low)' },
]

const PRIORITY_TONE: Record<string, PillTone> = {
  P0: 'danger',
  P1: 'warning',
  P2: 'accent',
  P3: 'neutral',
}

export default function MaintenancePage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)

  // Filters
  const [statusFilters, setStatusFilters] = useState<string[]>([])
  const [priorityFilters, setPriorityFilters] = useState<string[]>([])
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadData()
  }, [statusFilters, priorityFilters, searchQuery])

  const loadData = async () => {
    try {
      // Build query params
      const params = new URLSearchParams()
      statusFilters.forEach(s => params.append('status', s))
      priorityFilters.forEach(p => params.append('priority', p))
      if (searchQuery) params.set('search', searchQuery)

      const [tasksRes, statsRes] = await Promise.all([
        fetch(`/api/tasks?${params.toString()}`),
        fetch('/api/tasks/stats')
      ])

      if (tasksRes.ok) {
        const data = await tasksRes.json()
        setTasks(data.tasks || [])
      }

      if (statsRes.ok) {
        const data = await statsRes.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Failed to load tasks:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateTask = async (id: number, updates: Partial<Task>) => {
    try {
      const res = await fetch(`/api/tasks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      })

      if (res.ok) {
        loadData()
        setShowModal(false)
        setSelectedTask(null)
      }
    } catch (error) {
      console.error('Failed to update task:', error)
      toast.error('Failed to update task', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
    }
  }

  const handleDeleteTask = async (id: number) => {
    if (!confirm('Are you sure you want to delete this task?')) return

    try {
      const res = await fetch(`/api/tasks/${id}`, { method: 'DELETE' })
      if (res.ok) {
        loadData()
        setShowModal(false)
        setSelectedTask(null)
      }
    } catch (error) {
      console.error('Failed to delete task:', error)
      toast.error('Failed to delete task', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
    }
  }

  const handleCreateTask = async (task: Partial<Task>) => {
    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(task)
      })

      if (res.ok) {
        loadData()
        setShowAddModal(false)
      }
    } catch (error) {
      console.error('Failed to create task:', error)
      toast.error('Failed to create task', {
        description: 'Network error or server unavailable',
        duration: 8000
      })
    }
  }

  const toggleStatusFilter = (status: string) => {
    setStatusFilters(prev =>
      prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]
    )
  }

  const togglePriorityFilter = (priority: string) => {
    setPriorityFilters(prev =>
      prev.includes(priority) ? prev.filter(p => p !== priority) : [...prev, priority]
    )
  }

  return (
    <div>
      <PageHeader
        title="Task Management"
        description="Track features, bugs, and improvements for the podcast digest system."
        actions={
          <button onClick={() => setShowAddModal(true)} className="btn btn-primary">
            <Plus size={14} /> Add Task
          </button>
        }
      />

      <div className="flex flex-col gap-[var(--space-6)]">
        {/* Stats Overview */}
        {stats && (
          <div className="grid grid-cols-2 gap-[var(--space-4)] md:grid-cols-4">
            <StatCard label="Total Tasks" value={stats.total} />
            <StatCard label="Open" value={stats.byStatus.open} tone="neutral" />
            <StatCard label="In Progress" value={stats.byStatus.in_progress} tone="warning" />
            <StatCard label="Completed" value={stats.byStatus.completed} tone="success" />
          </div>
        )}

        {/* Filters and Search */}
        <div className="card flex flex-col gap-[var(--space-4)]">
          <div className="flex flex-col gap-[var(--space-3)] md:flex-row">
            {/* Search */}
            <div className="flex-1">
              <input
                type="text"
                placeholder="Search tasks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-[var(--space-4)]">
            {/* Status Filters */}
            <div className="flex flex-wrap items-center gap-[var(--space-2)]">
              <span className="micro">Status:</span>
              {STATUS_OPTIONS.map(option => (
                <button
                  key={option.value}
                  onClick={() => toggleStatusFilter(option.value)}
                  className={
                    statusFilters.includes(option.value)
                      ? `pill pill-${STATUS_TONE[option.value]}`
                      : 'pill'
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>

            {/* Priority Filters */}
            <div className="flex flex-wrap items-center gap-[var(--space-2)]">
              <span className="micro">Priority:</span>
              {PRIORITY_OPTIONS.map(option => (
                <button
                  key={option.value}
                  onClick={() => togglePriorityFilter(option.value)}
                  className={
                    priorityFilters.includes(option.value)
                      ? `pill pill-${PRIORITY_TONE[option.value]}`
                      : 'pill'
                  }
                >
                  {option.label}
                </button>
              ))}
            </div>

            {/* Clear Filters */}
            {(statusFilters.length > 0 || priorityFilters.length > 0 || searchQuery) && (
              <button
                onClick={() => {
                  setStatusFilters([])
                  setPriorityFilters([])
                  setSearchQuery('')
                }}
                className="btn btn-ghost btn-sm ml-auto"
              >
                <X size={12} /> Clear filters
              </button>
            )}
          </div>
        </div>

        {/* Task List */}
        {loading ? (
          <div className="card py-[var(--space-6)] text-center text-ink-subtle">Loading tasks...</div>
        ) : tasks.length === 0 ? (
          <div className="card py-[var(--space-6)] text-center text-ink-subtle">No tasks found</div>
        ) : (
          <div className="table-shell overflow-x-auto">
            <table className="house-table">
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Category</th>
                  <th>Updated</th>
                  <th style={{ textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map(task => (
                  <tr key={task.id}>
                    <td>
                      <Pill tone={PRIORITY_TONE[task.priority] || 'neutral'}>{task.priority}</Pill>
                    </td>
                    <td>
                      <div className="line-clamp-2 font-medium text-ink" style={{ font: 'var(--t-small)' }}>
                        {task.title}
                      </div>
                      {task.tags && task.tags.length > 0 && (
                        <div className="mt-[var(--space-1)] flex flex-wrap gap-[var(--space-1)]">
                          {task.tags.slice(0, 3).map(tag => (
                            <span
                              key={tag}
                              className="rounded-sm bg-surface-2 px-[6px] py-[1px] font-mono text-ink-subtle"
                              style={{ font: 'var(--t-micro)' }}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      <Pill tone={STATUS_TONE[task.status] || 'neutral'}>
                        {STATUS_OPTIONS.find(o => o.value === task.status)?.label || task.status}
                      </Pill>
                    </td>
                    <td className="text-ink-muted">{task.category}</td>
                    <td className="text-ink-muted">
                      <span className="font-mono text-xs">{new Date(task.last_update_date).toLocaleDateString()}</span>
                    </td>
                    <td className="text-center">
                      <button
                        onClick={() => {
                          setSelectedTask(task)
                          setShowModal(true)
                        }}
                        className="btn btn-ghost btn-sm"
                      >
                        <Pencil size={12} /> Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit Task Modal */}
      {showModal && selectedTask && (
        <TaskModal
          task={selectedTask}
          onClose={() => {
            setShowModal(false)
            setSelectedTask(null)
          }}
          onSave={(updates) => handleUpdateTask(selectedTask.id, updates)}
          onDelete={() => handleDeleteTask(selectedTask.id)}
        />
      )}

      {/* Add Task Modal */}
      {showAddModal && (
        <TaskModal
          task={null}
          onClose={() => setShowAddModal(false)}
          onSave={handleCreateTask}
        />
      )}
    </div>
  )
}

function TaskModal({
  task,
  onClose,
  onSave,
  onDelete
}: {
  task: Task | null
  onClose: () => void
  onSave: (updates: Partial<Task>) => void
  onDelete?: () => void
}) {
  const [formData, setFormData] = useState<Partial<Task>>(
    task || {
      title: '',
      description: '',
      status: 'open',
      priority: 'P3',
      category: '',
      tags: []
    }
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(formData)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-[var(--space-4)]"
      style={{ background: 'var(--scrim)' }}
    >
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-surface-1 shadow-lg">
        <form onSubmit={handleSubmit}>
          <div className="flex flex-col gap-[var(--space-4)] p-[var(--space-6)]">
            <h2 style={{ font: 'var(--t-h2)', color: 'var(--text)' }}>
              {task ? 'Edit Task' : 'Add New Task'}
            </h2>

            {/* Title */}
            <div>
              <label className="field-label">Title *</label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="input"
                required
              />
            </div>

            {/* Description */}
            <div>
              <label className="field-label">Description</label>
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="textarea"
                rows={4}
              />
            </div>

            {/* Status and Priority */}
            <div className="grid grid-cols-2 gap-[var(--space-4)]">
              <div>
                <label className="field-label">Status *</label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="select"
                >
                  {STATUS_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="field-label">Priority *</label>
                <select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  className="select"
                >
                  {PRIORITY_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Category */}
            <div>
              <label className="field-label">Category</label>
              <input
                type="text"
                value={formData.category || ''}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="input"
              />
            </div>

            {/* Tags */}
            <div>
              <label className="field-label">Tags (comma-separated)</label>
              <input
                type="text"
                value={formData.tags?.join(', ') || ''}
                onChange={(e) => setFormData({
                  ...formData,
                  tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                })}
                className="input"
                placeholder="e.g. database, performance, security"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-between border-t border-border px-[var(--space-6)] py-[var(--space-4)]">
            <div>
              {task && onDelete && (
                <button type="button" onClick={onDelete} className="btn btn-danger">
                  <Trash2 size={14} /> Delete
                </button>
              )}
            </div>
            <div className="flex gap-[var(--space-3)]">
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" className="btn btn-primary">
                {task ? 'Save Changes' : 'Create Task'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
