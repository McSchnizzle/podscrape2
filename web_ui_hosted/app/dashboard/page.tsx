import { Suspense } from 'react'
import { SystemHealth } from '@/components/SystemHealth'
import { PipelineStatus } from '@/components/PipelineStatus'
import { RecentActivity } from '@/components/RecentActivity'

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of your podcast digest system
        </p>
      </div>

      {/* System Health */}
      <Suspense fallback={<div className="card animate-pulse h-32" />}>
        <SystemHealth />
      </Suspense>

      {/* Pipeline Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Suspense fallback={<div className="card animate-pulse h-64" />}>
          <PipelineStatus />
        </Suspense>

        <Suspense fallback={<div className="card animate-pulse h-64" />}>
          <RecentActivity />
        </Suspense>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <button className="btn btn-primary">
            Run Full Pipeline
          </button>
          <button className="btn btn-secondary">
            Publishing Only
          </button>
          <button className="btn btn-secondary">
            View Logs
          </button>
          <a href="/feeds" className="btn btn-secondary">
            Manage Feeds
          </a>
          <a href="/settings" className="btn btn-secondary">
            Settings
          </a>
        </div>
      </div>
    </div>
  )
}