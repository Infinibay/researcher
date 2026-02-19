import { useState } from 'react'
import { useProjectStore } from '../../stores/project'
import { useTasks, useCreateTask, useDeleteTask } from '../../hooks/useTasks'
import { useEpics } from '../../hooks/useEpics'
import { useMilestones } from '../../hooks/useMilestones'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ErrorMessage } from '../common/ErrorMessage'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { ConfirmDialog } from '../common/ConfirmDialog'
import { TaskDetailModal } from '../tasks/TaskDetailModal'
import { DependencyGraph } from '../tasks/DependencyGraph'
import { PRIORITY_COLORS } from '../../utils/colors'
import type { TaskDependency } from '../../types/api'

const statusOptions = ['', 'backlog', 'pending', 'in_progress', 'review_ready', 'rejected', 'done']
const typeOptions = ['code', 'research', 'review', 'documentation']
const complexityOptions = ['low', 'medium', 'high']

const statusVariant: Record<string, string> = {
  backlog: 'neutral',
  pending: 'neutral',
  in_progress: 'warning',
  review_ready: 'violet',
  rejected: 'error',
  done: 'success',
}

const typeVariant: Record<string, string> = {
  code: 'info',
  research: 'warning',
  review: 'violet',
  documentation: 'neutral',
}

export function TasksPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterEpic, setFilterEpic] = useState<number | undefined>()
  const [filterMilestone, setFilterMilestone] = useState<number | undefined>()

  const { data: tasks, isLoading, error, refetch } = useTasks(projectId, {
    status: filterStatus || undefined,
    epic_id: filterEpic,
    milestone_id: filterMilestone,
  })
  const { data: epics } = useEpics(projectId)
  const { data: milestones } = useMilestones(projectId)
  const createTask = useCreateTask()
  const deleteTask = useDeleteTask()

  const [showForm, setShowForm] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [showDepGraph, setShowDepGraph] = useState(false)
  const [allDeps, setAllDeps] = useState<TaskDependency[]>([])

  // Form state
  const [fTitle, setFTitle] = useState('')
  const [fDesc, setFDesc] = useState('')
  const [fType, setFType] = useState('code')
  const [fEpic, setFEpic] = useState<number | undefined>()
  const [fMilestone, setFMilestone] = useState<number | undefined>()
  const [fPriority, setFPriority] = useState(3)
  const [fComplexity, setFComplexity] = useState('medium')
  const [fDependsOn, setFDependsOn] = useState<number[]>([])

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  if (isLoading) return <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
  if (error) return <ErrorMessage message={(error as Error).message} retry={() => refetch()} />

  const handleCreate = () => {
    if (!fTitle.trim()) return
    createTask.mutate(
      {
        project_id: projectId,
        type: fType,
        title: fTitle.trim(),
        description: fDesc.trim() || undefined,
        epic_id: fEpic,
        milestone_id: fMilestone,
        priority: fPriority,
        estimated_complexity: fComplexity,
        depends_on: fDependsOn.length > 0 ? fDependsOn : undefined,
      },
      {
        onSuccess: () => {
          setFTitle('')
          setFDesc('')
          setFType('code')
          setFEpic(undefined)
          setFMilestone(undefined)
          setFPriority(3)
          setFComplexity('medium')
          setFDependsOn([])
          setShowForm(false)
        },
      },
    )
  }

  // Fetch dependency data for the graph when toggled
  const handleToggleDepGraph = async () => {
    if (showDepGraph) {
      setShowDepGraph(false)
      return
    }
    // Fetch dependencies for all visible tasks
    const ids = (tasks ?? []).map((t) => t.id)
    try {
      const results = await Promise.all(
        ids.map((id) =>
          fetch(`/api/tasks/${id}/dependencies`)
            .then((r) => (r.ok ? r.json() : []))
            .catch(() => []),
        ),
      )
      setAllDeps(results.flat())
    } catch {
      setAllDeps([])
    }
    setShowDepGraph(true)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Tasks</h1>
        <div className="flex gap-2">
          <button
            onClick={handleToggleDepGraph}
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              showDepGraph
                ? 'bg-sky-500/20 text-sky-300'
                : 'border border-surface-700 text-slate-300 hover:bg-surface-800'
            }`}
          >
            Dependencies
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
          >
            {showForm ? 'Cancel' : 'New Task'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-md border border-surface-700 bg-surface-900 px-3 py-1.5 text-sm text-slate-300"
        >
          <option value="">All statuses</option>
          {statusOptions.filter(Boolean).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={filterEpic ?? ''}
          onChange={(e) => setFilterEpic(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded-md border border-surface-700 bg-surface-900 px-3 py-1.5 text-sm text-slate-300"
        >
          <option value="">All epics</option>
          {(epics ?? []).map((ep) => (
            <option key={ep.id} value={ep.id}>{ep.title}</option>
          ))}
        </select>
        <select
          value={filterMilestone ?? ''}
          onChange={(e) => setFilterMilestone(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded-md border border-surface-700 bg-surface-900 px-3 py-1.5 text-sm text-slate-300"
        >
          <option value="">All milestones</option>
          {(milestones ?? []).map((ms) => (
            <option key={ms.id} value={ms.id}>{ms.title}</option>
          ))}
        </select>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-4 space-y-3">
          <input
            type="text"
            value={fTitle}
            onChange={(e) => setFTitle(e.target.value)}
            placeholder="Task title"
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            autoFocus
          />
          <textarea
            value={fDesc}
            onChange={(e) => setFDesc(e.target.value)}
            placeholder="Description (optional)"
            rows={3}
            className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
          />
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs text-slate-500">Type</label>
              <select value={fType} onChange={(e) => setFType(e.target.value)} className="w-full rounded-md border border-surface-700 bg-surface-900 px-2 py-1.5 text-sm text-slate-300">
                {typeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">Priority</label>
              <select value={fPriority} onChange={(e) => setFPriority(Number(e.target.value))} className="w-full rounded-md border border-surface-700 bg-surface-900 px-2 py-1.5 text-sm text-slate-300">
                {[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">Complexity</label>
              <select value={fComplexity} onChange={(e) => setFComplexity(e.target.value)} className="w-full rounded-md border border-surface-700 bg-surface-900 px-2 py-1.5 text-sm text-slate-300">
                {complexityOptions.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-500">Epic</label>
              <select value={fEpic ?? ''} onChange={(e) => setFEpic(e.target.value ? Number(e.target.value) : undefined)} className="w-full rounded-md border border-surface-700 bg-surface-900 px-2 py-1.5 text-sm text-slate-300">
                <option value="">None</option>
                {(epics ?? []).map((ep) => <option key={ep.id} value={ep.id}>{ep.title}</option>)}
              </select>
            </div>
          </div>
          {/* Depends on multi-select */}
          {(tasks ?? []).length > 0 && (
            <div>
              <label className="mb-1 block text-xs text-slate-500">Depends on (select tasks this blocks on)</label>
              <div className="flex flex-wrap gap-1.5 rounded-md border border-surface-700 bg-surface-900 p-2 max-h-32 overflow-y-auto">
                {(tasks ?? []).map((t) => {
                  const selected = fDependsOn.includes(t.id)
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() =>
                        setFDependsOn((prev) =>
                          selected ? prev.filter((id) => id !== t.id) : [...prev, t.id],
                        )
                      }
                      className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                        selected
                          ? 'bg-sky-500/30 text-sky-300'
                          : 'bg-surface-700 text-slate-400 hover:bg-surface-700/80'
                      }`}
                    >
                      #{t.id} {t.title.length > 30 ? t.title.slice(0, 30) + '...' : t.title}
                    </button>
                  )
                })}
              </div>
              {fDependsOn.length > 0 && (
                <div className="mt-1 text-xs text-slate-500">
                  Selected: {fDependsOn.map((id) => `#${id}`).join(', ')}
                </div>
              )}
            </div>
          )}
          <button
            onClick={handleCreate}
            disabled={!fTitle.trim() || createTask.isPending}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {createTask.isPending ? 'Creating...' : 'Create Task'}
          </button>
        </div>
      )}

      {/* Dependency Graph */}
      {showDepGraph && tasks && tasks.length > 0 && (
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-4">
          <DependencyGraph
            tasks={tasks}
            dependencies={allDeps}
            selectedTaskId={selectedTaskId ?? undefined}
            onSelectTask={(id) => setSelectedTaskId(id)}
          />
        </div>
      )}

      {/* Task list */}
      {(!tasks || tasks.length === 0) ? (
        <EmptyState title="No tasks" description="Create a task or adjust your filters." />
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <button
              key={task.id}
              onClick={() => setSelectedTaskId(task.id)}
              className="flex w-full items-center gap-3 rounded-lg border border-surface-700 bg-surface-800 p-3 text-left transition-colors hover:border-surface-700/80 hover:bg-surface-700/50"
            >
              <span className="shrink-0 font-mono text-xs text-slate-500">#{task.id}</span>
              <Badge variant={statusVariant[task.status] || 'neutral'}>{task.status}</Badge>
              <Badge variant={typeVariant[task.type] || 'neutral'}>{task.type}</Badge>
              <span className="min-w-0 flex-1 truncate text-sm text-slate-200">{task.title}</span>
              {task.priority != null && (
                <span className={`text-xs font-medium ${PRIORITY_COLORS[task.priority] || ''}`}>P{task.priority}</span>
              )}
              {task.assigned_to && (
                <span className="text-xs text-slate-500">{task.assigned_to}</span>
              )}
              {['backlog', 'pending'].includes(task.status) && (
                <span
                  role="button"
                  onClick={(e) => { e.stopPropagation(); setDeleteId(task.id) }}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Del
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {selectedTaskId != null && (
        <TaskDetailModal taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} />
      )}

      <ConfirmDialog
        open={deleteId != null}
        title="Delete Task"
        message="Are you sure you want to delete this task?"
        confirmLabel="Delete"
        danger
        onConfirm={() => {
          if (deleteId) deleteTask.mutate(deleteId, { onSettled: () => setDeleteId(null) })
        }}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  )
}
