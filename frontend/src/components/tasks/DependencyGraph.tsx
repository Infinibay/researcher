import type { Task, TaskDependency } from '../../types/api'
import { STATUS_COLORS } from '../../utils/colors'

export function DependencyGraph({
  tasks,
  dependencies,
  selectedTaskId,
  onSelectTask,
}: {
  tasks: Task[]
  dependencies: TaskDependency[]
  selectedTaskId?: number
  onSelectTask?: (id: number) => void
}) {
  if (tasks.length === 0) {
    return <div className="py-4 text-center text-sm text-slate-500">No tasks to display</div>
  }

  const taskMap = new Map(tasks.map((t) => [t.id, t]))

  // Build adjacency: task_id depends_on depends_on_task_id
  const depEdges = dependencies.filter(
    (d) => taskMap.has(d.task_id) && taskMap.has(d.depends_on_task_id),
  )

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Dependency Map</div>
      <div className="space-y-1">
        {tasks.map((task) => {
          const deps = depEdges.filter((d) => d.task_id === task.id)
          const blockers = depEdges.filter((d) => d.depends_on_task_id === task.id)
          const isSelected = task.id === selectedTaskId

          return (
            <button
              key={task.id}
              onClick={() => onSelectTask?.(task.id)}
              className={`flex w-full items-start gap-3 rounded-md border p-2 text-left text-sm transition-colors ${
                isSelected
                  ? 'border-sky-500/50 bg-sky-500/10'
                  : 'border-surface-700 bg-surface-800 hover:border-surface-700/80'
              }`}
            >
              <span className="shrink-0 font-mono text-xs text-slate-500">#{task.id}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-slate-200">{task.title}</div>
                <div className="mt-0.5 flex flex-wrap gap-1">
                  <span className={`inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STATUS_COLORS[task.status] || ''}`}>
                    {task.status}
                  </span>
                  {deps.length > 0 && (
                    <span className="text-[10px] text-slate-500">
                      depends on: {deps.map((d) => `#${d.depends_on_task_id}`).join(', ')}
                    </span>
                  )}
                  {blockers.length > 0 && (
                    <span className="text-[10px] text-amber-500">
                      blocks: {blockers.map((d) => `#${d.task_id}`).join(', ')}
                    </span>
                  )}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
