'use client'

import { useState, useEffect } from 'react'

interface WorkflowRun {
  id: number
  name: string
  status: string
  conclusion: string
  createdAt: string
  updatedAt: string
  htmlUrl: string
  headBranch: string
  event: string
}

interface Job {
  jobId: number
  jobName: string
  status: string
  conclusion: string
  startedAt: string
  completedAt: string
  steps: Array<{
    name: string
    status: string
    conclusion: string
    number: number
    startedAt: string
    completedAt: string
  }>
}

export default function LogsPage() {
  const [workflows, setWorkflows] = useState<WorkflowRun[]>([])
  const [selectedRun, setSelectedRun] = useState<number | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [jobsLoading, setJobsLoading] = useState(false)

  useEffect(() => {
    fetchWorkflows()

    // Auto-refresh every 10 seconds to show new runs
    const interval = setInterval(fetchWorkflows, 10000)

    return () => clearInterval(interval)
  }, [])

  const fetchWorkflows = async () => {
    try {
      const response = await fetch('/api/github/workflows')
      if (response.ok) {
        const data = await response.json()
        setWorkflows(data.workflows || [])
      }
    } catch (error) {
      console.error('Failed to fetch workflows:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchJobsForRun = async (runId: number) => {
    setJobsLoading(true)
    try {
      const response = await fetch(`/api/logs/stream?runId=${runId}`)
      if (response.ok) {
        const data = await response.json()
        setJobs(data.jobs || [])
        setSelectedRun(runId)
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error)
    } finally {
      setJobsLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const getStatusBadge = (status: string, conclusion: string) => {
    if (status === 'in_progress') {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">Running</span>
    } else if (status === 'completed') {
      if (conclusion === 'success') {
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">Success</span>
      } else if (conclusion === 'failure') {
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">Failed</span>
      } else {
        return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{conclusion}</span>
      }
    } else {
      return <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{status}</span>
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflow Logs</h1>
          <p className="mt-1 text-sm text-gray-500">
            View recent workflow runs and their status
          </p>
        </div>
        <div className="card">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Workflow Logs</h1>
        <p className="mt-1 text-sm text-gray-500">
          View recent workflow runs and their status
        </p>
      </div>

      {/* Workflow Runs List */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Recent Workflow Runs</h3>
          <button
            onClick={fetchWorkflows}
            disabled={loading}
            className="px-3 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        <div className="space-y-3">
          {workflows.length > 0 ? (
            workflows.map((workflow) => (
              <div
                key={workflow.id}
                className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                  selectedRun === workflow.id
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => fetchJobsForRun(workflow.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-gray-900">{workflow.name}</h4>
                    <p className="text-sm text-gray-500">
                      {formatDate(workflow.createdAt)} • Branch: {workflow.headBranch}
                    </p>
                  </div>
                  <div className="flex items-center space-x-3">
                    {getStatusBadge(workflow.status, workflow.conclusion)}
                    <a
                      href={workflow.htmlUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-primary-600 hover:text-primary-800"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View on GitHub
                    </a>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="text-sm text-gray-500 text-center py-8">
              No workflow runs found
            </div>
          )}
        </div>
      </div>

      {/* Job Details */}
      {selectedRun && (
        <div className="card">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            Job Details {jobsLoading && <span className="text-sm text-gray-500">(Loading...)</span>}
          </h3>

          {jobsLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-4 bg-gray-200 rounded"></div>
              <div className="h-4 bg-gray-200 rounded"></div>
              <div className="h-4 bg-gray-200 rounded"></div>
            </div>
          ) : jobs.length > 0 ? (
            <div className="space-y-6">
              {jobs.map((job) => (
                <div key={job.jobId} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-sm font-medium text-gray-900">{job.jobName}</h4>
                    {getStatusBadge(job.status, job.conclusion)}
                  </div>

                  <div className="space-y-2">
                    {job.steps.map((step) => (
                      <div key={step.number} className="flex items-center justify-between text-sm">
                        <div className="flex items-center space-x-2">
                          <span className="w-6 text-gray-400">#{step.number}</span>
                          <span className="text-gray-900">{step.name}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          {step.startedAt && (
                            <span className="text-gray-500">
                              {formatDate(step.startedAt)}
                            </span>
                          )}
                          {getStatusBadge(step.status, step.conclusion)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-500 text-center py-4">
              No job details available for this run
            </div>
          )}
        </div>
      )}
    </div>
  )
}