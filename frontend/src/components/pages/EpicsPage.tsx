import { useState } from 'react'
import { useProjectStore } from '../../stores/project'
import { useEpics, useCreateEpic, useDeleteEpic } from '../../hooks/useEpics'
import { useMilestones, useCreateMilestone } from '../../hooks/useMilestones'
import { useTasks } from '../../hooks/useTasks'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ErrorMessage } from '../common/ErrorMessage'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { ConfirmDialog } from '../common/ConfirmDialog'
import { STATUS_COLORS } from '../../utils/colors'
import { MarkdownRenderer } from '../common/MarkdownRenderer'

const statusVariant: Record<string, string> = {
  open: 'neutral',
  in_progress: 'warning',
  completed: 'success',
  cancelled: 'error',
}

export function EpicsPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const { data: epics, isLoading, error, refetch } = useEpics(projectId)
  const { data: milestones } = useMilestones(projectId)
  const { data: tasks } = useTasks(projectId)
  const createEpic = useCreateEpic()
  const deleteEpic = useDeleteEpic()
  const createMilestone = useCreateMilestone()

  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState(3)
  const [expandedEpic, setExpandedEpic] = useState<number | null>(null)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [msTitle, setMsTitle] = useState('')
  const [msEpicId, setMsEpicId] = useState<number | null>(null)

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  if (isLoading) return <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
  if (error) return <ErrorMessage message={(error as Error).message} retry={() => refetch()} />

  const handleCreate = () => {
    if (!title.trim()) return
    createEpic.mutate(
      { project_id: projectId, title: title.trim(), description: description.trim() || undefined, priority },
      {
        onSuccess: () => {
          setTitle('')
          setDescription('')
          setPriority(3)
          setShowForm(false)
        },
      },
    )
  }

  const handleAddMilestone = (epicId: number) => {
    if (!msTitle.trim()) return
    createMilestone.mutate(
      { epic_id: epicId, title: msTitle.trim() },
      { onSuccess: () => { setMsTitle(''); setMsEpicId(null) } },
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Epics</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
        >
          {showForm ? 'Cancel' : 'New Epic'}
        </button>
      </div>

      {showForm && (
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-4 space-y-3">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Epic title"
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
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-400">Priority:</label>
            <select
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
              className="rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-slate-300"
            >
              {[1, 2, 3, 4, 5].map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleCreate}
            disabled={!title.trim() || createEpic.isPending}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {createEpic.isPending ? 'Creating...' : 'Create'}
          </button>
        </div>
      )}

      {(!epics || epics.length === 0) ? (
        <EmptyState title="No epics yet" description="Create your first epic to organize tasks." />
      ) : (
        <div className="space-y-3">
          {epics.map((epic) => {
            const isExpanded = expandedEpic === epic.id
            const epicMilestones = (milestones ?? []).filter((m) => m.epic_id === epic.id)
            const epicTasks = (tasks ?? []).filter((t) => t.epic_id === epic.id)
            const total = epic.task_count ?? 0
            const done = epic.tasks_done ?? 0
            const pct = total > 0 ? Math.round((done / total) * 100) : 0

            return (
              <div key={epic.id} className="rounded-lg border border-surface-700 bg-surface-800 overflow-hidden">
                <button
                  onClick={() => setExpandedEpic(isExpanded ? null : epic.id)}
                  className="flex w-full items-center gap-3 p-4 text-left hover:bg-surface-700/50"
                >
                  <svg
                    className={`h-4 w-4 shrink-0 text-slate-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path d="M6 6l8 4-8 4V6z" />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-200">{epic.title}</span>
                      <Badge variant={statusVariant[epic.status] || 'neutral'}>{epic.status}</Badge>
                    </div>
                    {epic.description && (
                      <p className="mt-0.5 text-sm text-slate-400 line-clamp-1">{epic.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-sm text-slate-500">
                    <span>{done}/{total} tasks</span>
                    <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-700">
                      <div className="h-full rounded-full bg-sky-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-surface-700 p-4 space-y-4">
                    {/* Description */}
                    {epic.description && (
                      <div>
                        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Description</h4>
                        <div className="text-sm text-slate-300">
                          <MarkdownRenderer content={epic.description} />
                        </div>
                      </div>
                    )}

                    {/* Milestones */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Milestones</h4>
                        <button
                          onClick={() => setMsEpicId(msEpicId === epic.id ? null : epic.id)}
                          className="text-xs text-sky-400 hover:text-sky-300"
                        >
                          + Add
                        </button>
                      </div>
                      {msEpicId === epic.id && (
                        <div className="flex gap-2 mb-2">
                          <input
                            type="text"
                            value={msTitle}
                            onChange={(e) => setMsTitle(e.target.value)}
                            placeholder="Milestone title"
                            className="flex-1 rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
                            autoFocus
                          />
                          <button
                            onClick={() => handleAddMilestone(epic.id)}
                            disabled={!msTitle.trim()}
                            className="rounded-md bg-sky-600 px-3 py-1 text-xs text-white hover:bg-sky-500 disabled:opacity-50"
                          >
                            Add
                          </button>
                        </div>
                      )}
                      {epicMilestones.length === 0 ? (
                        <p className="text-xs text-slate-500">No milestones</p>
                      ) : (
                        <div className="space-y-1">
                          {epicMilestones.map((ms) => (
                            <div key={ms.id} className="flex items-center gap-2 rounded bg-surface-900 px-3 py-2 text-sm">
                              <Badge variant={statusVariant[ms.status] || 'neutral'}>{ms.status}</Badge>
                              <span className="text-slate-300">{ms.title}</span>
                              <span className="ml-auto text-xs text-slate-500">
                                {ms.tasks_done ?? 0}/{ms.task_count ?? 0}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Tasks */}
                    <div>
                      <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Tasks</h4>
                      {epicTasks.length === 0 ? (
                        <p className="text-xs text-slate-500">No tasks</p>
                      ) : (
                        <div className="space-y-1">
                          {epicTasks.map((task) => (
                            <div key={task.id} className="flex items-center gap-2 rounded bg-surface-900 px-3 py-2 text-sm">
                              <span className="font-mono text-xs text-slate-500">#{task.id}</span>
                              <span className={`inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STATUS_COLORS[task.status] || ''}`}>
                                {task.status}
                              </span>
                              <span className="truncate text-slate-300">{task.title}</span>
                              {task.assigned_to && (
                                <span className="ml-auto text-xs text-slate-500">{task.assigned_to}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setDeleteId(epic.id)}
                        className="rounded px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-500/10"
                      >
                        Delete Epic
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <ConfirmDialog
        open={deleteId != null}
        title="Delete Epic"
        message="This will delete this epic and all its milestones. Tasks will be unlinked but not deleted."
        confirmLabel="Delete"
        danger
        onConfirm={() => {
          if (deleteId) deleteEpic.mutate(deleteId, { onSettled: () => setDeleteId(null) })
        }}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  )
}
