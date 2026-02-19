import { useState } from 'react'
import { useProjects, useCreateProject, useDeleteProject, useStartProject, useStopProject } from '../../hooks/useProjects'
import { useProjectStore } from '../../stores/project'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ErrorMessage } from '../common/ErrorMessage'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { StatusDot } from '../common/StatusDot'
import { ConfirmDialog } from '../common/ConfirmDialog'
import { formatRelative } from '../../utils/date'

const statusVariant: Record<string, string> = {
  new: 'neutral',
  planning: 'info',
  executing: 'success',
  paused: 'warning',
  completed: 'info',
  failed: 'error',
}

export function ProjectsPage() {
  const { data, isLoading, error, refetch } = useProjects()
  const createProject = useCreateProject()
  const deleteProject = useDeleteProject()
  const startProject = useStartProject()
  const stopProject = useStopProject()
  const { activeProjectId, setActiveProject } = useProjectStore()

  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [deleteId, setDeleteId] = useState<number | null>(null)

  const handleCreate = () => {
    if (!name.trim()) return
    createProject.mutate(
      { name: name.trim(), description: description.trim() || undefined },
      {
        onSuccess: () => {
          setName('')
          setDescription('')
          setShowForm(false)
        },
      },
    )
  }

  const handleDelete = () => {
    if (deleteId == null) return
    deleteProject.mutate(deleteId, { onSettled: () => setDeleteId(null) })
  }

  if (isLoading) return <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
  if (error) return <ErrorMessage message={(error as Error).message} retry={() => refetch()} />

  const projects = data?.projects ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Projects</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
        >
          {showForm ? 'Cancel' : 'New Project'}
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-4 space-y-3">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            autoFocus
          />
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            rows={2}
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
          <button
            onClick={handleCreate}
            disabled={!name.trim() || createProject.isPending}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {createProject.isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
      )}

      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Create your first project to get started."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => {
            const isRunning = p.status === 'executing'
            return (
              <div
                key={p.id}
                className={`rounded-lg border p-4 ${
                  p.id === activeProjectId
                    ? 'border-sky-500/50 bg-sky-500/5'
                    : 'border-surface-700 bg-surface-800'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <StatusDot
                      status={isRunning ? 'active' : p.status === 'failed' ? 'error' : 'inactive'}
                      animated={isRunning}
                    />
                    <h3 className="font-semibold text-slate-200">{p.name}</h3>
                  </div>
                  <Badge variant={statusVariant[p.status] || 'neutral'}>{p.status}</Badge>
                </div>
                {p.description && (
                  <p className="mt-2 text-sm text-slate-400 line-clamp-2">{p.description}</p>
                )}
                <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                  {p.total_epics != null && <span>{p.total_epics} epics</span>}
                  {p.total_tasks != null && <span>{p.total_tasks} tasks</span>}
                  {p.updated_at && <span>{formatRelative(p.updated_at)}</span>}
                </div>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => setActiveProject(p.id)}
                    className="rounded px-2 py-1 text-xs font-medium text-sky-400 hover:bg-sky-500/10"
                  >
                    Select
                  </button>
                  {isRunning ? (
                    <button
                      onClick={() => stopProject.mutate(p.id)}
                      disabled={stopProject.isPending}
                      className="rounded px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                    >
                      Stop
                    </button>
                  ) : (
                    <button
                      onClick={() => startProject.mutate(p.id)}
                      disabled={startProject.isPending || p.status === 'completed'}
                      className="rounded px-2 py-1 text-xs font-medium text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-50"
                    >
                      Start
                    </button>
                  )}
                  <button
                    onClick={() => setDeleteId(p.id)}
                    className="rounded px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-500/10"
                  >
                    Delete
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <ConfirmDialog
        open={deleteId != null}
        title="Delete Project"
        message="This will permanently delete this project and all related data. This action cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  )
}
