'use client'

import { useEffect, useState } from 'react'

interface TranscriptData {
  avgChars: number
  avgTokens: number
  maxChars: number
  minChars: number
  totalEpisodes: number
  truncationRisk: number
  episodesPerDigest: number
  currentUtilization: number
}

export function TranscriptAnalytics() {
  const [data, setData] = useState<TranscriptData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const response = await fetch('/api/dashboard/analytics')
      if (response.ok) {
        const result = await response.json()
        setData(result.transcriptAnalytics)
      }
    } catch (error) {
      console.error('Failed to load transcript analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Transcript Analytics</h3>
        <div className="h-32 animate-pulse bg-gray-100 rounded-md" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Transcript Analytics</h3>
        <div className="text-sm text-gray-500">No transcript data available</div>
      </div>
    )
  }

  const getUtilizationColor = (utilization: number) => {
    if (utilization < 50) return 'text-green-600 bg-green-50'
    if (utilization < 75) return 'text-yellow-600 bg-yellow-50'
    if (utilization < 90) return 'text-orange-600 bg-orange-50'
    return 'text-red-600 bg-red-50'
  }

  const formatNumber = (num: number) => {
    return num.toLocaleString()
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">Transcript Analytics</h3>
        <span className="text-xs text-gray-500">Last {data.totalEpisodes} episodes</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div>
          <p className="text-xs text-gray-500">Avg Length</p>
          <p className="text-lg font-semibold text-gray-900">{formatNumber(data.avgChars)}</p>
          <p className="text-xs text-gray-400">~{formatNumber(data.avgTokens)} tokens</p>
        </div>

        <div>
          <p className="text-xs text-gray-500">Range</p>
          <p className="text-sm font-medium text-gray-900">
            {formatNumber(data.minChars)} - {formatNumber(data.maxChars)}
          </p>
          <p className="text-xs text-gray-400">chars</p>
        </div>

        <div>
          <p className="text-xs text-gray-500">Episodes/Digest</p>
          <p className="text-lg font-semibold text-gray-900">{data.episodesPerDigest}</p>
          <p className="text-xs text-gray-400">from settings</p>
        </div>

        <div>
          <p className="text-xs text-gray-500">Truncation Risk</p>
          <p className="text-lg font-semibold text-gray-900">{data.truncationRisk}</p>
          <p className="text-xs text-gray-400">episodes &gt;100K tokens</p>
        </div>
      </div>

      {/* Context Utilization Bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Estimated Context Usage</span>
          <span className={`text-sm font-semibold px-2 py-1 rounded ${getUtilizationColor(data.currentUtilization)}`}>
            {data.currentUtilization}%
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all ${
              data.currentUtilization < 50 ? 'bg-green-500' :
              data.currentUtilization < 75 ? 'bg-yellow-500' :
              data.currentUtilization < 90 ? 'bg-orange-500' :
              'bg-red-500'
            }`}
            style={{ width: `${Math.min(data.currentUtilization, 100)}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {formatNumber(data.avgTokens * data.episodesPerDigest)} tokens / 128K limit
        </p>
      </div>

      {/* Warnings */}
      {data.currentUtilization > 75 && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
          <p className="text-sm text-yellow-800">
            ⚠️ Context usage is high. Consider reducing episodes per digest or implementing transcript summarization.
          </p>
        </div>
      )}

      {data.truncationRisk > 0 && (
        <div className="p-3 bg-orange-50 border border-orange-200 rounded-md mt-2">
          <p className="text-sm text-orange-800">
            🔔 {data.truncationRisk} episode{data.truncationRisk > 1 ? 's' : ''} exceed 100K tokens and may need summarization.
          </p>
        </div>
      )}

      {data.currentUtilization < 50 && data.truncationRisk === 0 && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md">
          <p className="text-sm text-green-800">
            ✅ Transcript sizes are well within limits. No action needed.
          </p>
        </div>
      )}
    </div>
  )
}
