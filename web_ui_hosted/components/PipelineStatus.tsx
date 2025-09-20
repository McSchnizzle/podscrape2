export function PipelineStatus() {
  return (
    <div className="card">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Pipeline Status</h3>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Last Run</span>
          <span className="text-sm text-gray-500">2 hours ago</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Status</span>
          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium status-success">
            Success
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Episodes Processed</span>
          <span className="text-sm text-gray-500">12</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Next Scheduled</span>
          <span className="text-sm text-gray-500">5:00 AM UTC</span>
        </div>
      </div>

      <div className="mt-6 pt-4 border-t border-gray-200">
        <button className="w-full btn btn-primary">
          Run Pipeline Now
        </button>
      </div>
    </div>
  )
}