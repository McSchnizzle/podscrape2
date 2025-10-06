export default function Loading() {
  return (
    <div className="space-y-6">
      <div>
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-64 bg-gray-100 rounded mt-2 animate-pulse" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card animate-pulse h-64 bg-gray-100" />
        <div className="card animate-pulse h-64 bg-gray-100" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card animate-pulse h-64 bg-gray-100" />
        <div className="card animate-pulse h-64 bg-gray-100" />
      </div>

      <div className="card animate-pulse h-32 bg-gray-100" />
    </div>
  )
}
