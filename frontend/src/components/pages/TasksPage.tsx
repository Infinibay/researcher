/** Project task selection and report-to-task navigation for the owner. @module */

import { useState, useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { scopedEntityId } from '../../utils/projectSelection'
import { useProjectStore } from '../../stores/project'
import { useTasks, useCreateTask, useDeleteTask } from '../../hooks/useTasks'
import { useEpics } from '../../hooks/useEpics'
import { useMilestones } from '../../hooks/useMilestones'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ConfirmDialog } from '../common/ConfirmDialog'
import { TaskInspector } from '../tasks/TaskInspector'
import { TaskQueue, taskStatusLabels } from '../tasks/TaskQueue'
import '../../styles/tasks.css'
import { DependencyGraph } from '../tasks/DependencyGraph'
import type { TaskDependency } from '../../types/api'

const statusOptions = ['', 'backlog', 'pending', 'in_progress', 'review_ready', 'rejected', 'done', 'blocked']
const typeOptions = ['code', 'research', 'investigation', 'review', 'test', 'design', 'integrate', 'documentation', 'bug_fix']
const complexityOptions = ['low', 'medium', 'high']

/** Open the selected project's task workbench without inferring a project from a URL. */
export function TasksPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  if (!projectId) return <div className="task-workbench"><section className="task-idle"><p className="task-eyebrow">TAREAS</p><h1>Elige un proyecto para trabajar</h1><p>Selecciona el proyecto en la cabecera. Aquí podrás consultar sus tareas, contrastar evidencia y corregir el contexto.</p></section></div>
  return <ProjectTaskWorkbench key={projectId} projectId={projectId} />
}

/** Keep task selection and return-to-report links scoped to the visibly active project. */
function ProjectTaskWorkbench({ projectId }: { projectId: number }) {
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
  const [params, setParams] = useSearchParams()
  const selectedTaskId = scopedEntityId(params, projectId, 'task')
  const returnArtifactId = scopedEntityId(params, projectId, 'fromArtifact')
  const foreignLink = params.has('task') && Number(params.get('project')) !== projectId
  const setSelectedTaskId = (id: number | null) => setParams(id == null ? {} : { project: String(projectId), task: String(id) })
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [showDepGraph, setShowDepGraph] = useState(false)
  const [allDeps, setAllDeps] = useState<TaskDependency[]>([])

  // Form state
  const [fTitle, setFTitle] = useState('')
  const [fDesc, setFDesc] = useState('')
  const [fType, setFType] = useState('research')
  const [fEpic, setFEpic] = useState<number | undefined>()
  const [fMilestone, setFMilestone] = useState<number | undefined>()
  const [fPriority, setFPriority] = useState(3)
  const [fComplexity, setFComplexity] = useState('medium')
  const [fDependsOn, setFDependsOn] = useState<number[]>([])

  const [search, setSearch] = useState('')
  const lastSelection = useRef<number | null>(null)
  useEffect(() => {
    if (selectedTaskId == null && lastSelection.current != null) document.getElementById(`task-select-${lastSelection.current}`)?.focus()
  }, [selectedTaskId])
  const visibleTasks = (tasks ?? []).filter(task => `${task.id} ${task.title}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  const selectTask = (id: number) => { lastSelection.current = id; setShowForm(false); setShowDepGraph(false); setSelectedTaskId(id) }

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
          setFType('research')
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
    <div className="task-workbench" data-has-selection={selectedTaskId != null}>
      {returnArtifactId && <nav className="task-report-return" aria-label="Regreso al informe"><Link to={`/reports?project=${projectId}&artifact=${returnArtifactId}`}>Volver al informe</Link></nav>}
      {foreignLink && <p className="task-error" role="status">Este enlace corresponde a otro proyecto. Elige ese proyecto o una tarea de la lista actual.</p>}
      {selectedTaskId != null && <h1 className="sr-only min-[701px]:hidden">Tareas</h1>}
      <div className="task-page-heading">
        <div><p className="task-eyebrow">ESPACIO DE TRABAJO</p><h1>Tareas</h1><p className="task-page-description">Selecciona una tarea para revisar la evidencia, corregir el contexto o iniciar trabajo.</p></div>
        <div className="flex gap-2">
          <button
            onClick={handleToggleDepGraph}
            className={`rounded-md px-4 py-2 text-sm font-medium ${
              showDepGraph
                ? 'bg-[var(--work-wash)] text-[var(--work-accent)]'
                : 'border border-[var(--work-line)] text-[var(--work-ink)] hover:bg-[var(--work-paper)]'
            }`}
          >
            Dependencias
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded-md bg-[var(--work-accent-fill)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--work-accent-strong)]"
          >
            {showForm ? 'Cerrar formulario' : 'Nueva tarea'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="task-filters" aria-label="Filtros de tareas">
        <label className="task-search">Buscar tarea<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Título o número" /></label>
        <select
          aria-label="Filtrar por estado"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-1.5 text-sm text-[var(--work-ink)]"
        >
          <option value="">Todos los estados</option>
          {statusOptions.filter(Boolean).map((s) => (
            <option key={s} value={s}>{taskStatusLabels[s] ?? s}</option>
          ))}
        </select>
        <select
          aria-label="Filtrar por épica"
          value={filterEpic ?? ''}
          onChange={(e) => setFilterEpic(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-1.5 text-sm text-[var(--work-ink)]"
        >
          <option value="">Todas las épicas</option>
          {(epics ?? []).map((ep) => (
            <option key={ep.id} value={ep.id}>{ep.title}</option>
          ))}
        </select>
        <select
          aria-label="Filtrar por hito"
          value={filterMilestone ?? ''}
          onChange={(e) => setFilterMilestone(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-1.5 text-sm text-[var(--work-ink)]"
        >
          <option value="">Todos los hitos</option>
          {(milestones ?? []).map((ms) => (
            <option key={ms.id} value={ms.id}>{ms.title}</option>
          ))}
        </select>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="rounded-lg border border-[var(--work-line)] bg-[var(--work-paper)] p-4 space-y-3">
          <label htmlFor="task-new-title" className="block text-sm">Título</label>
          <input
            type="text"
            value={fTitle}
            onChange={(e) => setFTitle(e.target.value)}
            id="task-new-title" placeholder="Qué necesitas comprobar o construir"
            className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-2 text-sm text-[var(--work-ink)] placeholder-slate-600 focus:border-sky-500/50 focus:outline-hidden"
            autoFocus
          />
          <label htmlFor="task-new-description" className="block text-sm">Descripción</label>
          <textarea
            value={fDesc}
            onChange={(e) => setFDesc(e.target.value)}
            id="task-new-description" placeholder="Contexto, ejemplo y resultado esperado"
            rows={3}
            className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-2 text-sm text-[var(--work-ink)] placeholder-slate-600 focus:border-sky-500/50 focus:outline-hidden"
          />
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div>
              <label htmlFor="task-new-type" className="mb-1 block text-xs text-[var(--work-muted)]">Tipo</label>
              <select id="task-new-type" value={fType} onChange={(e) => setFType(e.target.value)} className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-2 py-1.5 text-sm text-[var(--work-ink)]">
                {typeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="task-new-priority" className="mb-1 block text-xs text-[var(--work-muted)]">Prioridad</label>
              <select id="task-new-priority" value={fPriority} onChange={(e) => setFPriority(Number(e.target.value))} className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-2 py-1.5 text-sm text-[var(--work-ink)]">
                {[1, 2, 3, 4, 5].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="task-new-complexity" className="mb-1 block text-xs text-[var(--work-muted)]">Complejidad</label>
              <select id="task-new-complexity" value={fComplexity} onChange={(e) => setFComplexity(e.target.value)} className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-2 py-1.5 text-sm text-[var(--work-ink)]">
                {complexityOptions.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="task-new-epic" className="mb-1 block text-xs text-[var(--work-muted)]">Épica</label>
              <select id="task-new-epic" value={fEpic ?? ''} onChange={(e) => setFEpic(e.target.value ? Number(e.target.value) : undefined)} className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-2 py-1.5 text-sm text-[var(--work-ink)]">
                <option value="">Sin épica</option>
                {(epics ?? []).map((ep) => <option key={ep.id} value={ep.id}>{ep.title}</option>)}
              </select>
            </div>
          </div>
          {/* Depends on multi-select */}
          {(tasks ?? []).length > 0 && (
            <div>
              <label className="mb-1 block text-xs text-[var(--work-muted)]">Tareas que deben resolverse antes</label>
              <div className="flex flex-wrap gap-1.5 rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2 max-h-32 overflow-y-auto">
                {(tasks ?? []).map((t) => {
                  const selected = fDependsOn.includes(t.id)
                  return (
                    <button
                      key={t.id}
                      type="button" aria-pressed={selected}
                      onClick={() =>
                        setFDependsOn((prev) =>
                          selected ? prev.filter((id) => id !== t.id) : [...prev, t.id],
                        )
                      }
                      className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                        selected
                          ? 'bg-[var(--work-wash)] text-[var(--work-accent)]'
                          : 'bg-[var(--work-wash)] text-[var(--work-muted)] hover:bg-[var(--work-wash)]'
                      }`}
                    >
                      #{t.id} {t.title.length > 30 ? t.title.slice(0, 30) + '...' : t.title}
                    </button>
                  )
                })}
              </div>
              {fDependsOn.length > 0 && (
                <div className="mt-1 text-xs text-[var(--work-muted)]">
                  Seleccionadas: {fDependsOn.map((id) => `#${id}`).join(', ')}
                </div>
              )}
            </div>
          )}
          <button
            onClick={handleCreate}
            disabled={!fTitle.trim() || createTask.isPending}
            className="rounded-md bg-[var(--work-accent-fill)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--work-accent-strong)] disabled:opacity-50"
          >
            {createTask.isPending ? 'Creando…' : 'Crear tarea'}
          </button>
          {createTask.error && <p role="alert" className="task-error">No se confirmó la creación. {createTask.error.message}</p>}
        </div>
      )}

      {/* Dependency Graph */}
      {showDepGraph && tasks && tasks.length > 0 && (
        <div className="rounded-lg border border-[var(--work-line)] bg-[var(--work-paper)] p-4">
          <DependencyGraph
            tasks={tasks}
            dependencies={allDeps}
            selectedTaskId={selectedTaskId ?? undefined}
            onSelectTask={selectTask}
          />
        </div>
      )}

      <div className="task-split">
        <section className="task-index" aria-label="Elegir tarea">
          <div className="task-index-heading"><h2>Cola de trabajo</h2><span>{isLoading ? 'Consultando…' : error ? 'Sin confirmar' : `${visibleTasks.length} visibles`}</span></div>
          {!isLoading && !error && selectedTaskId != null && !visibleTasks.some(task => task.id === selectedTaskId) && <p className="task-empty">La tarea abierta queda fuera de estos filtros.</p>}
          {isLoading ? <div className="task-empty" role="status"><LoadingSpinner />Cargando la lista…</div> : error ? <div role="alert" className="task-error"><p>No se pudo consultar la lista. {error.message}</p><button className="task-secondary" onClick={() => refetch()}>Volver a consultar</button></div> : visibleTasks.length === 0 ? <p className="task-empty">{tasks?.length ? 'No hay tareas que coincidan con esta búsqueda.' : 'No hay tareas con estos filtros. Puedes crear una o cambiar los filtros.'}</p> : <TaskQueue tasks={visibleTasks} selectedTaskId={selectedTaskId} onSelect={selectTask} onDelete={setDeleteId} />}
          {deleteTask.error && <p role="alert" className="task-error">No se pudo eliminar la tarea. {deleteTask.error.message}</p>}
        </section>
        {selectedTaskId != null ? <TaskInspector key={selectedTaskId} taskId={selectedTaskId} onClose={() => setSelectedTaskId(null)} /> : <section id="task-detail" className="task-idle" aria-label="Trabajo de la tarea"><p className="task-eyebrow">EMPIEZA POR UNA PREGUNTA</p><h2>Elige una tarea para trabajar</h2><p>Aquí podrás leer la propuesta, contrastar las fuentes y corregir el contexto. Elegir una tarea no inicia una ejecución.</p></section>}
      </div>

      <ConfirmDialog
        open={deleteId != null}
        title="Eliminar tarea"
        message={deleteTask.error ? `No se pudo eliminar la tarea. ${deleteTask.error.message}` : 'Se eliminará esta tarea. Si tiene una ejecución pendiente de cierre, primero debe resolverse.'}
        confirmLabel="Eliminar"
        cancelLabel="Conservar tarea"
        danger
        onConfirm={() => {
          if (deleteId) deleteTask.mutate(deleteId, { onSuccess: () => { if (selectedTaskId === deleteId) setSelectedTaskId(null); setDeleteId(null) } })
        }}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  )
}
