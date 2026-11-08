/** Project-scoped task details, context correction and execution controls. @module */

import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { taskWorkspace } from '../../api/runtime'
import type { TaskWorkspace } from '../../api/runtime'
import { useTask, useUpdateTask } from '../../hooks/useTasks'
import { useProjectStore } from '../../stores/project'
import { taskStatusLabels } from './TaskQueue'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import {TaskCommentsPanel} from './TaskCommentsPanel'
import {TaskDependenciesPanel} from './TaskDependenciesPanel'
import { TaskRunWorkspace } from './TaskRunWorkspace'

const taskStatuses = ['backlog', 'pending', 'in_progress', 'review_ready', 'rejected', 'done', 'blocked']

/** Show task controls only after the fetched task matches the current project. */
export function TaskInspector({
  taskId,
  onClose,
}: {
  taskId: number
  onClose: () => void
}) {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const { data: task, isLoading, error, refetch } = useTask(taskId, projectId)
  // Subscribe to the workbench's scoped read without creating a second polling request.
  const workspace = useQuery<TaskWorkspace>({queryKey:['task-workspace',projectId,taskId],queryFn:()=>{if(projectId==null) throw new Error('Selecciona un proyecto antes de consultar la tarea.');return taskWorkspace(projectId,taskId)},enabled:false})
  const scopedWorkspace = workspace.data?.project_id === projectId && workspace.data?.task_id === taskId
  const nativeOwned = !!scopedWorkspace && (!!workspace.data?.runs.length || !!workspace.data?.runtime.owner_controlled_task_types?.includes(workspace.data.context.task.type))
  const lifecycleEditable = !!scopedWorkspace && !workspace.isError && !nativeOwned

  const updateTask = useUpdateTask()

  const [tab, setTab] = useState<'details' | 'execution' | 'comments' | 'dependencies'>('execution')
  const heading = useRef<HTMLHeadingElement>(null)
  const panel = useRef<HTMLElement>(null)
  const [editingTitle, setEditingTitle] = useState(false)
  const [editingDesc, setEditingDesc] = useState(false)
  const [draftTitle, setDraftTitle] = useState('')
  const [draftDesc, setDraftDesc] = useState('')

  useEffect(() => { (heading.current ?? panel.current)?.focus({ preventScroll: true }) }, [taskId, task?.id])

  const handleStatusChange = (status: string) => {
    if (lifecycleEditable) updateTask.mutate({ id: taskId, status })
  }

  const saveTitle = () => {
    if (draftTitle.trim()) updateTask.mutate({ id: taskId, title: draftTitle.trim() }, { onSuccess: () => setEditingTitle(false) })
  }

  return (
    <section id="task-detail" ref={panel} tabIndex={-1} role="region" aria-labelledby={`task-title-${taskId}`} className="task-inspector">
      <div className="task-inspector-inner">
        {task && projectId != null && task.project_id !== projectId ? <div className="task-inspector-content" role="alert"><h2 id={`task-title-${taskId}`}>Esta tarea no pertenece al proyecto seleccionado</h2><button className="task-back" onClick={onClose}>Volver a tareas</button></div> : error && !task ? <div className="task-inspector-content" role="alert">
          <h2 id={`task-title-${taskId}`}>No se pudo cargar la tarea</h2>
          <p>{error.message}</p>
          <button className="task-secondary" onClick={() => refetch()}>Volver a consultar</button>{' · '}
          <button className="task-back" onClick={onClose}>Volver a tareas</button>
        </div> : isLoading || !task ? (
          <div className="task-inspector-content">
            <p id={`task-title-${taskId}`} role="status">Cargando la tarea…</p><LoadingSpinner />
            <button className="task-back" onClick={onClose}>Volver a tareas</button>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="task-inspector-heading">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-[var(--work-muted)]">#{task.id}</span>
                  <select
                    aria-label="Estado de la tarea"
                    value={task.status}
                    onChange={(e) => handleStatusChange(e.target.value)}
                    disabled={!lifecycleEditable || updateTask.isPending}
                    className={`cursor-pointer rounded-full border-none px-2 py-0.5 text-xs font-medium focus:outline-hidden focus:ring-1 focus:ring-[var(--work-accent)] task-status`}
                  >
                    {taskStatuses.map((s) => (
                      <option key={s} value={s} className="bg-[var(--work-paper)] text-[var(--work-ink)]">
                        {taskStatusLabels[s] ?? s}
                      </option>
                    ))}
                  </select>
                  <span className="task-status">{task.type === 'research' ? 'Investigación' : task.type}</span>
                </div>
                {nativeOwned && <p className="mt-2 text-xs text-[var(--work-muted)]">El estado se controla desde la pestaña Trabajo.</p>}
                {editingTitle ? (
                  <div className="mt-1 flex items-center gap-2">
                    <h2 id={`task-title-${taskId}`} className="sr-only">Editar tarea: {task.title}</h2>
                    <input
                      autoFocus
                      aria-label="Título de la tarea"
                      value={draftTitle}
                      onChange={(e) => setDraftTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          saveTitle()
                        }
                        if (e.key === 'Escape') setEditingTitle(false)
                      }}
                      className="flex-1 rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-2 py-1 text-lg font-semibold text-[var(--work-ink)] focus:border-sky-500/50 focus:outline-hidden"
                    />
                    <button
                      onClick={saveTitle} disabled={!draftTitle.trim() || updateTask.isPending}
                      className="rounded bg-[var(--work-accent-fill)] px-2 py-1 text-xs text-white hover:bg-[var(--work-accent-strong)]"
                    >
                      Guardar
                    </button>
                    <button
                      onClick={() => setEditingTitle(false)}
                      className="rounded bg-[var(--work-wash)] px-2 py-1 text-xs text-[var(--work-muted)] hover:bg-[var(--work-wash)]"
                    >
                      Cancelar
                    </button>
                  </div>
                ) : (
                  <h2
                    id={`task-title-${taskId}`} ref={heading} tabIndex={-1}
                    className="task-inspector-title"
                  >
                    {task.title}
                  </h2>
                )}
              </div>
              <button type="button" onClick={onClose} className="task-back">Volver a tareas</button>
            </div>

            {/* Tabs */}
            <div className="task-tabs" aria-label="Secciones de la tarea">
              {(['details', 'execution', 'comments', 'dependencies'] as const).map((t) => (
                <button
                  key={t}
                  type="button" aria-label={t==='dependencies'?'Dependencias de esta tarea':undefined} aria-pressed={tab === t} aria-controls={`task-section-${taskId}`}
                  onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-medium capitalize ${
                    tab === t
                      ? 'border-b-2 border-sky-400 text-[var(--work-accent)]'
                      : 'text-[var(--work-muted)] hover:text-[var(--work-ink)]'
                  }`}
                >
                  {{ execution: 'Trabajo', details: 'Detalles', comments: 'Comentarios', dependencies: 'Dependencias' }[t]}
                </button>
              ))}
            </div>

            {/* Content */}
            <div id={`task-section-${taskId}`} className="task-inspector-content">
              {updateTask.error && <p role="alert" className="task-error">No se confirmó el cambio. {updateTask.error.message}</p>}
              {tab === 'execution' && <TaskRunWorkspace key={`${task.project_id}:${task.id}`} projectId={task.project_id} taskId={task.id} />}
              {tab === 'details' && (
                <div className="space-y-4">
                  <button type="button" className="task-secondary" onClick={() => { setDraftTitle(task.title); setEditingTitle(true) }}>Editar título</button>
                  {editingDesc ? (
                    <div className="space-y-2">
                      <textarea
                        autoFocus
                        aria-label="Descripción de la tarea"
                        value={draftDesc}
                        onChange={(e) => setDraftDesc(e.target.value)}
                        rows={8}
                        className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-2 text-sm text-[var(--work-ink)] placeholder-slate-600 focus:border-sky-500/50 focus:outline-hidden"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            updateTask.mutate({ id: taskId, description: draftDesc }, { onSuccess: () => setEditingDesc(false) })
                          }}
                          className="rounded bg-[var(--work-accent-fill)] px-3 py-1 text-xs font-medium text-white hover:bg-[var(--work-accent-strong)]"
                        >
                          Guardar
                        </button>
                        <button
                          onClick={() => setEditingDesc(false)}
                          className="rounded bg-[var(--work-wash)] px-3 py-1 text-xs text-[var(--work-muted)] hover:bg-[var(--work-wash)]"
                        >
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : task.description ? (
                    <div>
                      <MarkdownRenderer content={task.description} />
                      <button type="button" className="task-secondary" onClick={() => { setDraftDesc(task.description || ''); setEditingDesc(true) }}>Editar descripción</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => {
                        setDraftDesc('')
                        setEditingDesc(true)
                      }}
                      className="text-sm text-[var(--work-muted)] hover:text-[var(--work-accent)]"
                    >
                      Añadir descripción
                    </button>
                  )}

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    {task.priority != null && (
                      <div>
                        <span className="text-[var(--work-muted)]">Prioridad: </span>
                        <span className="font-medium text-[var(--work-ink)]">
                          {task.priority}
                        </span>
                      </div>
                    )}
                    {task.estimated_complexity && (
                      <div>
                        <span className="text-[var(--work-muted)]">Complejidad: </span>
                        <span className="text-[var(--work-ink)]">{task.estimated_complexity}</span>
                      </div>
                    )}
                    {task.assigned_to && (
                      <div>
                        <span className="text-[var(--work-muted)]">Responsable: </span>
                        <span className="text-[var(--work-ink)]">{task.assigned_to}</span>
                      </div>
                    )}
                    {task.reviewer && (
                      <div>
                        <span className="text-[var(--work-muted)]">Revisor: </span>
                        <span className="text-[var(--work-ink)]">{task.reviewer}</span>
                      </div>
                    )}
                    {task.branch_name && (
                      <div className="col-span-2">
                        <span className="text-[var(--work-muted)]">Rama: </span>
                        <code className="text-[var(--work-accent)]">{task.branch_name}</code>
                      </div>
                    )}
                    {task.epic_id && (
                      <div>
                        <span className="text-[var(--work-muted)]">Épica: </span>
                        <span className="text-[var(--work-ink)]">#{task.epic_id}</span>
                      </div>
                    )}
                    {task.milestone_id && (
                      <div>
                        <span className="text-[var(--work-muted)]">Hito: </span>
                        <span className="text-[var(--work-ink)]">#{task.milestone_id}</span>
                      </div>
                    )}
                    {(task.retry_count ?? 0) > 0 && (
                      <div>
                        <span className="text-[var(--work-muted)]">Reintentos: </span>
                        <span className="text-[var(--work-caution)]">{task.retry_count}</span>
                      </div>
                    )}
                  </div>

                  {/* Status changer */}
                  <div>
                    <span className="text-xs font-medium text-[var(--work-muted)] uppercase tracking-wider">Cambiar estado</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {taskStatuses.map((s) => (
                        <button
                          key={s}
                          disabled={!lifecycleEditable || s === task.status || updateTask.isPending}
                          onClick={() => handleStatusChange(s)}
                          className={`rounded-full px-2 py-0.5 text-xs font-medium disabled:opacity-30 task-status`}
                        >
                          {taskStatusLabels[s] ?? s}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {tab==='comments'&&<TaskCommentsPanel key={`${task.project_id}:${taskId}`} projectId={task.project_id} taskId={taskId}/>}
              {tab==='dependencies'&&projectId!=null&&<TaskDependenciesPanel key={`${projectId}:${taskId}`} projectId={projectId} taskId={taskId}/>}

            </div>
          </>
        )}
      </div>
    </section>
  )
}
