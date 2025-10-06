'use client'

import { useEffect, useState } from 'react'

interface PerformanceData {
  avgProcessingTime: number
  bottleneckPhase: string
  bottleneckDuration: number
  successRate: number
  totalRuns: number
}

interface PhaseInfo {
  phase: string
  status: string
  duration: number
  logCount: number
}

interface LatestRunData {
  runId: string
  status: string
  phases: PhaseInfo[]
  startedAt: string
  completedAt: string
  totalDuration: number
}

export function PerformanceInsights() {
  const [performance, setPerformance] = useState<PerformanceData | null>(null)
  const [latestRun, setLatestRun] = useState<LatestRunData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const response = await fetch('/api/dashboard/analytics')
      if (response.ok) {
        const data = await response.json()
        setPerformance(data.performanceInsights)
        setLatestRun(data.latestRun)
      }
    } catch (error) {
      console.error('Failed to load performance insights:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`
    const minutes = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${minutes}m ${secs}s`
  }

  const getPhaseIcon = (phase: string) => {
    const icons: Record<string, string> = {
      discovery: '🔍',
      audio: '🎧',
      digest: '📝',
      tts: '🎙️',
      publishing: '📡',
      retention: '🧹'
    }
    return icons[phase] || '⚙️'
  }

  const getStatusColor = (status: string) => {
    if (status === 'completed') return 'bg-green-500'
    if (status === 'failed') return 'bg-red-500'
    return 'bg-yellow-500'
  }

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Performance Insights</h3>
        <div className="h-48 animate-pulse bg-gray-100 rounded-md" />
      </div>
    )
  }

  if (!performance || !latestRun) {
    return (
      <div className="card">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Performance Insights</h3>
        <div className="text-sm text-gray-500">No performance data available</div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Performance Insights</h3>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div>
          <p className="text-xs text-gray-500">Avg Processing Time</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatDuration(performance.avgProcessingTime)}
          </p>
        </div>

        <div>
          <p className="text-xs text-gray-500">Bottleneck Phase</p>
          <p className="text-lg font-semibold text-gray-900 capitalize">
            {getPhaseIcon(performance.bottleneckPhase)} {performance.bottleneckPhase}
          </p>
          <p className="text-xs text-gray-400">{formatDuration(performance.bottleneckDuration)}</p>
        </div>

        <div>
          <p className="text-xs text-gray-500">Success Rate</p>
          <p className={`text-lg font-semibold ${performance.successRate >= 90 ? 'text-green-600' : performance.successRate >= 70 ? 'text-yellow-600' : 'text-red-600'}`}>
            {performance.successRate}%
          </p>
          <p className="text-xs text-gray-400">{performance.totalRuns} runs</p>
        </div>

        <div>
          <p className="text-xs text-gray-500">Latest Run</p>
          <p className="text-sm font-medium text-gray-900 capitalize">{latestRun.status}</p>
          <p className="text-xs text-gray-400">{formatDuration(latestRun.totalDuration)}</p>
        </div>
      </div>

      {/* Latest Run Phase Breakdown */}
      <div className="mb-4">
        <p className="text-sm font-medium text-gray-700 mb-3">Latest Run: {latestRun.runId}</p>
        <div className="space-y-2">
          {latestRun.phases.map((phase) => {
            const percentage = (phase.duration / latestRun.totalDuration) * 100
            return (
              <div key={phase.phase}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-gray-700 capitalize">
                    {getPhaseIcon(phase.phase)} {phase.phase}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatDuration(phase.duration)} ({Math.round(percentage)}%)
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${getStatusColor(phase.status)}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Recommendations */}
      {performance.bottleneckDuration > 600 && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
          <p className="text-sm text-blue-800">
            💡 The {performance.bottleneckPhase} phase is taking {formatDuration(performance.bottleneckDuration)}. Consider optimizing this phase.
          </p>
        </div>
      )}
    </div>
  )
}
