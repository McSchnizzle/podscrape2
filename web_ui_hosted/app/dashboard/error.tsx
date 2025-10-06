'use client'

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Dashboard error:', error)
  }, [error])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-4 p-8">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900">Something went wrong!</h2>
          <p className="mt-2 text-sm text-gray-600">
            {error.message || 'An unexpected error occurred while loading the dashboard.'}
          </p>
        </div>
        <button
          onClick={() => reset()}
          className="w-full btn btn-primary"
        >
          Try again
        </button>
        <button
          onClick={() => window.location.href = '/'}
          className="w-full btn btn-secondary"
        >
          Go to home
        </button>
      </div>
    </div>
  )
}
