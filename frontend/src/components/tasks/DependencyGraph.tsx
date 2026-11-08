/** Read only the confirmed dependency snapshot; visible filters may omit other tasks. @module */
import type { Task, TaskDependency } from '../../types/api'
import {taskStatusLabels} from './TaskQueue'

/** Present confirmed prerequisite edges with keyboard task navigation and the workbench's readable palette. */
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
    return <div className="py-4 text-center text-sm text-[var(--work-muted)]">No hay tareas visibles con estos filtros.</div>
  }

  const taskMap = new Map(tasks.map((t) => [t.id, t]))

  // Build adjacency: task_id depends_on depends_on_task_id
  const depEdges = dependencies.filter(
    (d) => taskMap.has(d.task_id) && taskMap.has(d.depends_on_task_id),
  )

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-[var(--work-ink)]">Mapa de prerrequisitos</h2>
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
                  ? 'border-[var(--work-accent)] bg-[var(--work-wash)]'
                  : 'border-[var(--work-line)] bg-[var(--work-paper)] hover:bg-[var(--work-wash)]'
              }`}
            >
              <span className="shrink-0 font-mono text-xs text-[var(--work-muted)]">#{task.id}</span>
              <div className="min-w-0 flex-1">
                <div className="break-words text-[var(--work-ink)]">{task.title}</div>
                <div className="mt-0.5 flex flex-wrap gap-1">
                  <span className="task-status" data-status={task.status}>
                    {taskStatusLabels[task.status]??task.status}
                  </span>
                  {deps.length > 0 && (
                    <span className="text-xs text-[var(--work-muted)]">
                      Necesita antes: {deps.map((d) => `#${d.depends_on_task_id}`).join(', ')}
                    </span>
                  )}
                  {blockers.length > 0 && (
                    <span className="text-xs text-[var(--work-caution)]">
                      Prerrequisito de: {blockers.map((d) => `#${d.task_id}`).join(', ')}
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
