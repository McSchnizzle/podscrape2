import { DatabaseClient } from '@/lib/supabase'

async function getSystemHealth() {
  const db = new DatabaseClient()
  const health = await db.getSystemHealth()

  return {
    database: health.database === 'connected' ? 'healthy' : 'error',
    environment: process.env.NODE_ENV || 'unknown',
    timestamp: new Date().toISOString()
  }
}

export async function SystemHealth() {
  const health = await getSystemHealth()

  const statusColors = {
    healthy: 'status-success',
    warning: 'status-warning',
    error: 'status-error'
  }

  return (
    <div className="card">
      <h3 className="text-lg font-medium text-gray-900 mb-4">System Health</h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="text-center">
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusColors[health.database as keyof typeof statusColors]}`}>
            Database: {health.database}
          </div>
        </div>

        <div className="text-center">
          <div className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium status-success">
            Environment: {health.environment}
          </div>
        </div>

        <div className="text-center">
          <div className="text-sm text-gray-500">
            Last check: {new Date(health.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  )
}