import { useProjectStore } from '../../stores/project'
import { useProject } from '../../hooks/useProjects'
import { useEpics } from '../../hooks/useEpics'
import { useTasks } from '../../hooks/useTasks'
import { useProjectProgress } from '../../hooks/useProgress'
import { useChatMessages } from '../../hooks/useChat'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { formatRelative } from '../../utils/date'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const barColors: Record<string, string> = {
  backlog: '#64748b',
  pending: '#94a3b8',
  in_progress: '#f59e0b',
  review_ready: '#8b5cf6',
  rejected: '#ef4444',
  done: '#10b981',
  blocked: '#f97316',
}

export function Dashboard() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const { data: project } = useProject(projectId)
  const { data: epics } = useEpics(projectId)
  const { data: tasks } = useTasks(projectId)
  const { data: progress } = useProjectProgress(projectId)
  const { data: messages } = useChatMessages(projectId, 10)

  if (!projectId) {
    return (
      <EmptyState
        title="No project selected"
        description="Select a project from the header to see your dashboard."
      />
    )
  }

  // Use progress endpoint data when available, fall back to local calculation
  const total = progress?.total_tasks ?? tasks?.length ?? 0
  const done = progress?.done ?? (tasks ?? []).filter((t) => t.status === 'done').length
  const pct = progress?.completion_pct ?? (total > 0 ? Math.round((done / total) * 100) : 0)
  const inProgressCount = progress?.in_progress ?? 0
  const blockedCount = progress?.blocked ?? 0

  const chartData = progress?.by_status
    ? Object.entries(barColors).map(([status]) => ({
        name: status,
        count: progress.by_status[status] ?? 0,
      }))
    : Object.entries(barColors).map(([status]) => ({
        name: status,
        count: (tasks ?? []).filter((t) => t.status === status).length,
      }))

  // Use real blocked task details from the progress endpoint
  const blockedTasks = progress?.blocked_tasks ?? []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">{project?.name ?? 'Dashboard'}</h1>
        {project?.description && (
          <p className="mt-1 text-sm text-slate-400">{project.description}</p>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Task Progress */}
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold text-slate-200">Task Progress</h2>
            <span className="text-2xl font-bold text-sky-400">{pct}%</span>
          </div>
          {/* Progress bar */}
          <div className="mb-4 h-2 overflow-hidden rounded-full bg-surface-700">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="text-xs text-slate-500">{done} of {total} tasks completed</div>

          {total > 0 && (
            <div className="mt-4 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                    labelStyle={{ color: '#e2e8f0' }}
                    itemStyle={{ color: '#94a3b8' }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry) => (
                      <Cell key={entry.name} fill={barColors[entry.name] || '#64748b'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Epics Progress */}
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-5">
          <h2 className="mb-4 font-semibold text-slate-200">Epics</h2>
          {progress?.epic_progress && progress.epic_progress.length > 0 ? (
            <div className="space-y-3">
              {progress.epic_progress.map((ep) => (
                <div key={ep.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="truncate text-slate-300">{ep.title}</span>
                    <span className="ml-2 shrink-0 text-xs text-slate-500">{ep.done}/{ep.total}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-700">
                    <div
                      className="h-full rounded-full bg-sky-500 transition-all"
                      style={{ width: `${ep.pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : !epics || epics.length === 0 ? (
            <p className="text-sm text-slate-500">No epics yet</p>
          ) : (
            <div className="space-y-3">
              {epics.map((epic) => {
                const epicTotal = epic.task_count ?? 0
                const epicDone = epic.tasks_done ?? 0
                const epicPct = epicTotal > 0 ? Math.round((epicDone / epicTotal) * 100) : 0
                return (
                  <div key={epic.id}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="truncate text-slate-300">{epic.title}</span>
                      <span className="ml-2 shrink-0 text-xs text-slate-500">{epicDone}/{epicTotal}</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-700">
                      <div
                        className="h-full rounded-full bg-sky-500 transition-all"
                        style={{ width: `${epicPct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Blocked Tasks */}
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold text-slate-200">Blocked Tasks</h2>
            {blockedCount > 0 ? (
              <span className="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-red-500/20 px-2 text-xs font-medium text-red-400">
                {blockedCount}
              </span>
            ) : (
              <span className="inline-flex h-6 items-center text-xs text-emerald-400">None</span>
            )}
          </div>
          {blockedTasks.length === 0 ? (
            <p className="text-sm text-slate-500">No blocked tasks</p>
          ) : (
            <div className="space-y-2">
              {blockedTasks.map((task) => (
                <div key={task.id} className="rounded-md bg-surface-900 px-3 py-2">
                  <div className="flex items-center">
                    <span className="text-sm text-slate-300">#{task.id} {task.title}</span>
                    <span className="ml-2"><Badge variant="warning">{task.status}</Badge></span>
                  </div>
                  {task.blocked_by.length > 0 && (
                    <p className="mt-1 text-xs text-slate-500">
                      Blocked by: {task.blocked_by.map((b) => `#${b.id} ${b.title} (${b.status})`).join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Project Status */}
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-5">
          <h2 className="mb-4 font-semibold text-slate-200">Project Status</h2>
          <div className="flex items-center gap-3">
            <span
              className={`inline-block h-3 w-3 rounded-full ${
                inProgressCount > 0
                  ? 'bg-amber-400 animate-pulse'
                  : pct === 100
                    ? 'bg-emerald-400'
                    : 'bg-slate-500'
              }`}
            />
            <span className="text-sm text-slate-300">
              {inProgressCount > 0
                ? `Active — ${inProgressCount} task${inProgressCount !== 1 ? 's' : ''} in progress`
                : pct === 100
                  ? 'Complete — all tasks done'
                  : total === 0
                    ? 'No tasks created yet'
                    : 'Idle — no tasks in progress'}
            </span>
          </div>
          <div className="mt-4 text-3xl font-bold text-sky-400">{pct}%</div>
          <p className="text-xs text-slate-500">{done} of {total} tasks completed</p>

          {progress?.milestone_progress && progress.milestone_progress.length > 0 && (
            <div className="mt-4 border-t border-surface-700 pt-4">
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">Milestones</h3>
              <div className="space-y-2">
                {progress.milestone_progress.map((ms) => (
                  <div key={ms.id} className="flex items-center justify-between text-sm">
                    <span className="truncate text-slate-300">{ms.title}</span>
                    <span className="ml-2 shrink-0 text-xs text-slate-500">{ms.done}/{ms.total} ({ms.pct}%)</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="rounded-lg border border-surface-700 bg-surface-800 p-5 lg:col-span-2">
          <h2 className="mb-4 font-semibold text-slate-200">Recent Messages</h2>
          {!messages || messages.length === 0 ? (
            <p className="text-sm text-slate-500">No messages yet</p>
          ) : (
            <div className="space-y-2">
              {messages.map((msg) => (
                <div key={msg.id} className="flex items-start gap-3 rounded-md bg-surface-900 p-3">
                  <Badge variant="info">{msg.from_agent}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-300 line-clamp-2">{msg.message}</p>
                    {msg.created_at && (
                      <span className="text-xs text-slate-500">{formatRelative(msg.created_at)}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
