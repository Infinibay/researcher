import { useState, useEffect } from 'react'
import { useTask, useTaskComments, useAddTaskComment, useUpdateTask, useTaskDependencies, useSetTaskDependencies, useTasks } from '../../hooks/useTasks'
import { useProjectStore } from '../../stores/project'
import { Badge } from '../common/Badge'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { STATUS_COLORS, PRIORITY_COLORS } from '../../utils/colors'
import { formatRelative } from '../../utils/date'

const taskStatuses = ['backlog', 'pending', 'in_progress', 'review_ready', 'rejected', 'done']

export function TaskDetailModal({
  taskId,
  onClose,
}: {
  taskId: number
  onClose: () => void
}) {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const { data: task, isLoading } = useTask(taskId)
  const { data: comments } = useTaskComments(taskId)
  const { data: dependencies } = useTaskDependencies(taskId)
  const { data: allTasks } = useTasks(projectId)
  const addComment = useAddTaskComment()
  const updateTask = useUpdateTask()
  const setDependencies = useSetTaskDependencies()

  const [tab, setTab] = useState<'details' | 'comments' | 'dependencies'>('details')
  const [commentText, setCommentText] = useState('')
  const [commentType, setCommentType] = useState<string>('comment')
  const [editingDeps, setEditingDeps] = useState(false)
  const [selectedDeps, setSelectedDeps] = useState<number[]>([])
  const [editingTitle, setEditingTitle] = useState(false)
  const [editingDesc, setEditingDesc] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftDesc, setDraftDesc] = useState('')

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const handleAddComment = () => {
    if (!commentText.trim()) return
    addComment.mutate(
      { taskId, author: 'user', content: commentText, comment_type: commentType },
      { onSuccess: () => setCommentText('') },
    )
  }

  const handleStatusChange = (status: string) => {
    updateTask.mutate({ id: taskId, status })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/60" onClick={onClose} />
      <div className="relative z-10 flex max-h-[80vh] w-full max-w-2xl flex-col rounded-lg border border-surface-700 bg-surface-800 shadow-xl">
        {isLoading || !task ? (
          <div className="flex items-center justify-center p-12">
            <LoadingSpinner />
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-start justify-between border-b border-surface-700 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-500">#{task.id}</span>
                  <select
                    value={task.status}
                    onChange={(e) => handleStatusChange(e.target.value)}
                    disabled={updateTask.isPending}
                    className={`cursor-pointer rounded-full border-none px-2 py-0.5 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-sky-500 ${STATUS_COLORS[task.status] || 'bg-surface-700 text-slate-300'}`}
                  >
                    {taskStatuses.map((s) => (
                      <option key={s} value={s} className="bg-surface-800 text-slate-200">
                        {s}
                      </option>
                    ))}
                  </select>
                  <Badge variant="info">{task.type}</Badge>
                </div>
                {editingTitle ? (
                  <div className="mt-1 flex items-center gap-2">
                    <input
                      autoFocus
                      value={draftTitle}
                      onChange={(e) => setDraftTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          updateTask.mutate({ id: taskId, title: draftTitle })
                          setEditingTitle(false)
                        }
                        if (e.key === 'Escape') setEditingTitle(false)
                      }}
                      className="flex-1 rounded-md border border-surface-600 bg-surface-900 px-2 py-1 text-lg font-semibold text-slate-100 focus:border-sky-500/50 focus:outline-none"
                    />
                    <button
                      onClick={() => {
                        updateTask.mutate({ id: taskId, title: draftTitle })
                        setEditingTitle(false)
                      }}
                      className="rounded bg-sky-600 px-2 py-1 text-xs text-white hover:bg-sky-500"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingTitle(false)}
                      className="rounded bg-surface-700 px-2 py-1 text-xs text-slate-400 hover:bg-surface-600"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <h2
                    className="mt-1 cursor-pointer text-lg font-semibold text-slate-100 hover:text-sky-300"
                    onClick={() => {
                      setDraftTitle(task.title)
                      setEditingTitle(true)
                    }}
                    title="Click to edit title"
                  >
                    {task.title}
                  </h2>
                )}
              </div>
              <button onClick={onClose} className="ml-4 text-slate-500 hover:text-slate-300">
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-surface-700">
              {(['details', 'comments', 'dependencies'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium capitalize ${
                    tab === t
                      ? 'border-b-2 border-sky-400 text-sky-300'
                      : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {t}
                  {t === 'comments' && comments && ` (${comments.length})`}
                  {t === 'dependencies' && dependencies && ` (${dependencies.length})`}
                </button>
              ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {tab === 'details' && (
                <div className="space-y-4">
                  {editingDesc ? (
                    <div className="space-y-2">
                      <textarea
                        autoFocus
                        value={draftDesc}
                        onChange={(e) => setDraftDesc(e.target.value)}
                        rows={8}
                        className="w-full rounded-md border border-surface-600 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            updateTask.mutate({ id: taskId, description: draftDesc })
                            setEditingDesc(false)
                          }}
                          className="rounded bg-sky-600 px-3 py-1 text-xs font-medium text-white hover:bg-sky-500"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingDesc(false)}
                          className="rounded bg-surface-700 px-3 py-1 text-xs text-slate-400 hover:bg-surface-600"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : task.description ? (
                    <div
                      className="cursor-pointer rounded p-1 hover:bg-surface-700/50"
                      onClick={() => {
                        setDraftDesc(task.description || '')
                        setEditingDesc(true)
                      }}
                      title="Click to edit description"
                    >
                      <MarkdownRenderer content={task.description} />
                    </div>
                  ) : (
                    <button
                      onClick={() => {
                        setDraftDesc('')
                        setEditingDesc(true)
                      }}
                      className="text-sm text-slate-500 hover:text-sky-400"
                    >
                      + Add description
                    </button>
                  )}

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {task.priority != null && (
                      <div>
                        <span className="text-slate-500">Priority: </span>
                        <span className={PRIORITY_COLORS[task.priority] || 'text-slate-300'}>
                          {task.priority}
                        </span>
                      </div>
                    )}
                    {task.estimated_complexity && (
                      <div>
                        <span className="text-slate-500">Complexity: </span>
                        <span className="text-slate-300">{task.estimated_complexity}</span>
                      </div>
                    )}
                    {task.assigned_to && (
                      <div>
                        <span className="text-slate-500">Assigned to: </span>
                        <span className="text-slate-300">{task.assigned_to}</span>
                      </div>
                    )}
                    {task.reviewer && (
                      <div>
                        <span className="text-slate-500">Reviewer: </span>
                        <span className="text-slate-300">{task.reviewer}</span>
                      </div>
                    )}
                    {task.branch_name && (
                      <div className="col-span-2">
                        <span className="text-slate-500">Branch: </span>
                        <code className="text-sky-300">{task.branch_name}</code>
                      </div>
                    )}
                    {task.epic_id && (
                      <div>
                        <span className="text-slate-500">Epic: </span>
                        <span className="text-slate-300">#{task.epic_id}</span>
                      </div>
                    )}
                    {task.milestone_id && (
                      <div>
                        <span className="text-slate-500">Milestone: </span>
                        <span className="text-slate-300">#{task.milestone_id}</span>
                      </div>
                    )}
                    {(task.retry_count ?? 0) > 0 && (
                      <div>
                        <span className="text-slate-500">Retries: </span>
                        <span className="text-amber-300">{task.retry_count}</span>
                      </div>
                    )}
                  </div>

                  {/* Status changer */}
                  <div>
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Change status</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {taskStatuses.map((s) => (
                        <button
                          key={s}
                          disabled={s === task.status || updateTask.isPending}
                          onClick={() => handleStatusChange(s)}
                          className={`rounded-full px-2 py-0.5 text-xs font-medium disabled:opacity-30 ${STATUS_COLORS[s] || ''}`}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {tab === 'comments' && (
                <div className="space-y-4">
                  {/* Comments list */}
                  <div className="space-y-3">
                    {comments?.length === 0 && (
                      <p className="text-sm text-slate-500">No comments yet</p>
                    )}
                    {comments?.map((c) => (
                      <div key={c.id} className="rounded-md border border-surface-700 bg-surface-900 p-3">
                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <span className="font-medium text-slate-300">{c.author}</span>
                          <Badge variant={c.comment_type === 'approval' ? 'success' : c.comment_type === 'change_request' ? 'warning' : 'neutral'}>
                            {c.comment_type}
                          </Badge>
                          {c.created_at && <span>{formatRelative(c.created_at)}</span>}
                        </div>
                        <div className="mt-2 text-sm text-slate-300">
                          <MarkdownRenderer content={c.content} />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Add comment */}
                  <div className="space-y-2 border-t border-surface-700 pt-4">
                    <div className="flex gap-2">
                      <select
                        value={commentType}
                        onChange={(e) => setCommentType(e.target.value)}
                        className="rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-slate-300"
                      >
                        <option value="comment">Comment</option>
                        <option value="change_request">Change Request</option>
                        <option value="approval">Approval</option>
                      </select>
                    </div>
                    <textarea
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      placeholder="Add a comment..."
                      rows={3}
                      className="w-full rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
                    />
                    <button
                      onClick={handleAddComment}
                      disabled={!commentText.trim() || addComment.isPending}
                      className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
                    >
                      Add Comment
                    </button>
                  </div>
                </div>
              )}

              {tab === 'dependencies' && (
                <div className="space-y-4">
                  {/* Current dependencies */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                        This task depends on
                      </span>
                      <button
                        onClick={() => {
                          if (!editingDeps) {
                            setSelectedDeps(
                              (dependencies ?? [])
                                .filter((d) => d.task_id === taskId)
                                .map((d) => d.depends_on_task_id),
                            )
                          }
                          setEditingDeps(!editingDeps)
                        }}
                        className="text-xs text-sky-400 hover:text-sky-300"
                      >
                        {editingDeps ? 'Cancel' : 'Edit'}
                      </button>
                    </div>

                    {!editingDeps ? (
                      <div className="space-y-1">
                        {(dependencies ?? []).filter((d) => d.task_id === taskId).length === 0 ? (
                          <p className="text-sm text-slate-500">No dependencies</p>
                        ) : (
                          (dependencies ?? [])
                            .filter((d) => d.task_id === taskId)
                            .map((dep) => {
                              const depTask = (allTasks ?? []).find((t) => t.id === dep.depends_on_task_id)
                              return (
                                <div key={dep.depends_on_task_id} className="flex items-center gap-2 rounded bg-surface-900 px-3 py-2 text-sm">
                                  <span className="font-mono text-xs text-slate-500">#{dep.depends_on_task_id}</span>
                                  <span className="text-slate-300">
                                    {depTask?.title || 'Unknown task'}
                                  </span>
                                  {depTask && (
                                    <Badge variant={depTask.status === 'done' ? 'success' : 'neutral'}>
                                      {depTask.status}
                                    </Badge>
                                  )}
                                </div>
                              )
                            })
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-1.5 rounded-md border border-surface-700 bg-surface-900 p-2 max-h-48 overflow-y-auto">
                          {(allTasks ?? [])
                            .filter((t) => t.id !== taskId)
                            .map((t) => {
                              const isSelected = selectedDeps.includes(t.id)
                              return (
                                <button
                                  key={t.id}
                                  type="button"
                                  onClick={() =>
                                    setSelectedDeps((prev) =>
                                      isSelected ? prev.filter((id) => id !== t.id) : [...prev, t.id],
                                    )
                                  }
                                  className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                                    isSelected
                                      ? 'bg-sky-500/30 text-sky-300'
                                      : 'bg-surface-700 text-slate-400 hover:bg-surface-700/80'
                                  }`}
                                >
                                  #{t.id} {t.title.length > 25 ? t.title.slice(0, 25) + '...' : t.title}
                                </button>
                              )
                            })}
                        </div>
                        <button
                          onClick={() => {
                            setDependencies.mutate(
                              { taskId, depends_on: selectedDeps },
                              { onSuccess: () => setEditingDeps(false) },
                            )
                          }}
                          disabled={setDependencies.isPending}
                          className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
                        >
                          {setDependencies.isPending ? 'Saving...' : 'Save Dependencies'}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Tasks blocked by this one */}
                  <div>
                    <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Tasks blocked by this task
                    </span>
                    <div className="mt-2 space-y-1">
                      {(dependencies ?? []).filter((d) => d.depends_on_task_id === taskId).length === 0 ? (
                        <p className="text-sm text-slate-500">No tasks are blocked by this task</p>
                      ) : (
                        (dependencies ?? [])
                          .filter((d) => d.depends_on_task_id === taskId)
                          .map((dep) => {
                            const blockedTask = (allTasks ?? []).find((t) => t.id === dep.task_id)
                            return (
                              <div key={dep.task_id} className="flex items-center gap-2 rounded bg-surface-900 px-3 py-2 text-sm">
                                <span className="font-mono text-xs text-slate-500">#{dep.task_id}</span>
                                <span className="text-slate-300">
                                  {blockedTask?.title || 'Unknown task'}
                                </span>
                                {blockedTask && (
                                  <Badge variant={blockedTask.status === 'done' ? 'success' : 'neutral'}>
                                    {blockedTask.status}
                                  </Badge>
                                )}
                              </div>
                            )
                          })
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
