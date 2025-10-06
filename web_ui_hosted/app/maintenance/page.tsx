'use client'

import { useEffect, useState } from 'react'

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
  { value: 'open', label: 'Open', color: 'bg-blue-100 text-blue-800' },
  { value: 'in_progress', label: 'In Progress', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'on_hold', label: 'On Hold', color: 'bg-gray-100 text-gray-800' },
  { value: 'completed', label: 'Completed', color: 'bg-green-100 text-green-800' },
  { value: 'skipped', label: 'Skipped', color: 'bg-purple-100 text-purple-800' }
]

const PRIORITY_OPTIONS = [
  { value: 'P0', label: 'P0 (Critical)', color: 'text-red-600 font-bold' },
  { value: 'P1', label: 'P1 (High)', color: 'text-orange-600 font-semibold' },
  { value: 'P2', label: 'P2 (Medium)', color: 'text-yellow-600' },
  { value: 'P3', label: 'P3 (Low)', color: 'text-gray-600' }
]

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
      alert('Failed to update task')
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
      alert('Failed to delete task')
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
      alert('Failed to create task')
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

  const getStatusBadge = (status: string) => {
    const option = STATUS_OPTIONS.find(o => o.value === status)
    return (
      <span className={`px-2 py-1 text-xs rounded-full ${option?.color || 'bg-gray-100 text-gray-800'}`}>
        {option?.label || status}
      </span>
    )
  }

  const getPriorityClass = (priority: string) => {
    const option = PRIORITY_OPTIONS.find(o => o.value === priority)
    return option?.color || 'text-gray-600'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Task Management</h1>
        <p className="mt-1 text-sm text-gray-500">
          Track features, bugs, and improvements for the podcast digest system
        </p>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatsCard label="Total Tasks" value={stats.total} />
          <StatsCard label="Open" value={stats.byStatus.open} color="text-blue-600" />
          <StatsCard label="In Progress" value={stats.byStatus.in_progress} color="text-yellow-600" />
          <StatsCard label="Completed" value={stats.byStatus.completed} color="text-green-600" />
        </div>
      )}

      {/* Filters and Search */}
      <div className="card space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search tasks..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Add Task Button */}
          <button
            onClick={() => setShowAddModal(true)}
            className="btn btn-primary whitespace-nowrap"
          >
            + Add Task
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {/* Status Filters */}
          <div className="flex flex-wrap gap-2">
            <span className="text-sm font-medium text-gray-700">Status:</span>
            {STATUS_OPTIONS.map(option => (
              <button
                key={option.value}
                onClick={() => toggleStatusFilter(option.value)}
                className={`px-3 py-1 text-xs rounded-full ${
                  statusFilters.includes(option.value)
                    ? option.color
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          {/* Priority Filters */}
          <div className="flex flex-wrap gap-2 ml-4">
            <span className="text-sm font-medium text-gray-700">Priority:</span>
            {PRIORITY_OPTIONS.map(option => (
              <button
                key={option.value}
                onClick={() => togglePriorityFilter(option.value)}
                className={`px-3 py-1 text-xs rounded-full ${
                  priorityFilters.includes(option.value)
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
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
              className="ml-auto text-sm text-gray-600 hover:text-gray-900"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Task List */}
      <div className="card">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading tasks...</div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-8 text-gray-500">No tasks found</div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Priority</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Title</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Category</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Updated</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-700 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {tasks.map(task => (
                  <tr key={task.id} className="hover:bg-gray-50">
                    <td className={`px-4 py-3 text-sm font-medium ${getPriorityClass(task.priority)}`}>
                      {task.priority}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-gray-900 line-clamp-2">{task.title}</div>
                      {task.tags && task.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {task.tags.slice(0, 3).map(tag => (
                            <span key={tag} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">{getStatusBadge(task.status)}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{task.category}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {new Date(task.last_update_date).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => {
                          setSelectedTask(task)
                          setShowModal(true)
                        }}
                        className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
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

function StatsCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="card">
      <div className="text-sm text-gray-600">{label}</div>
      <div className={`text-2xl font-bold ${color || 'text-gray-900'}`}>{value}</div>
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <div className="p-6 space-y-4">
            <h2 className="text-xl font-bold text-gray-900">
              {task ? 'Edit Task' : 'Add New Task'}
            </h2>

            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Title *
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                required
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                rows={4}
              />
            </div>

            {/* Status and Priority */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Status *
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  {STATUS_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Priority *
                </label>
                <select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  {PRIORITY_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Category */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Category
              </label>
              <input
                type="text"
                value={formData.category || ''}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>

            {/* Tags */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tags (comma-separated)
              </label>
              <input
                type="text"
                value={formData.tags?.join(', ') || ''}
                onChange={(e) => setFormData({
                  ...formData,
                  tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="e.g. database, performance, security"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="border-t border-gray-200 px-6 py-4 flex justify-between">
            <div>
              {task && onDelete && (
                <button
                  type="button"
                  onClick={onDelete}
                  className="btn text-red-600 hover:text-red-800"
                >
                  Delete
                </button>
              )}
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={onClose}
                className="btn btn-secondary"
              >
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
