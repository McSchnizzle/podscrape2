export function RecentActivity() {
  // This will be populated with real data from Supabase
  const activities = [
    { id: 1, type: 'digest', message: 'Generated tech digest', time: '2 hours ago' },
    { id: 2, type: 'pipeline', message: 'Pipeline run completed', time: '2 hours ago' },
    { id: 3, type: 'episode', message: '12 episodes processed', time: '2 hours ago' },
    { id: 4, type: 'feed', message: 'Feed health check passed', time: '3 hours ago' },
  ]

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'digest': return '📄'
      case 'pipeline': return '⚙️'
      case 'episode': return '🎧'
      case 'feed': return '📡'
      default: return '📋'
    }
  }

  return (
    <div className="card">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>

      <div className="space-y-3">
        {activities.map((activity) => (
          <div key={activity.id} className="flex items-center space-x-3">
            <span className="text-lg">{getActivityIcon(activity.type)}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {activity.message}
              </p>
              <p className="text-sm text-gray-500">
                {activity.time}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-gray-200">
        <button className="text-sm text-primary-600 hover:text-primary-800">
          View all activity →
        </button>
      </div>
    </div>
  )
}