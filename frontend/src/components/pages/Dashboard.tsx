/** Project overview connects observed questions, plans and tasks to their original owner controls. @module */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { useProjectStore } from '../../stores/project'
import { useProject } from '../../hooks/useProjects'
import { useTasks } from '../../hooks/useTasks'
import { projectWorkspace } from '../../api/projectWorkspace'
import { QuestionInbox } from '../chat/QuestionInbox'
import '../../styles/tasks.css'
import '../../styles/overview.css'

const taskLabels: Record<string, string> = {
  backlog: 'Por organizar', pending: 'Pendiente', in_progress: 'En curso registrado',
  review_ready: 'Pendiente de revisión', rejected: 'Requiere cambios', done: 'Marcada como hecha', blocked: 'Bloqueada',
}
const activityLabels: Record<string, string> = {
  queued: 'En cola', running: 'En ejecución registrada', waiting_input: 'Esperando una respuesta',
  needs_review: 'Pendiente de revisión', cancelling: 'Detención solicitada', reconciling: 'Comprobando el cierre',
}

/** Reset project-specific observations when the owner changes the global selection. */
export function Dashboard() {
  const projectId = useProjectStore(state => state.activeProjectId)
  if (projectId == null) return <section className="task-workbench overview-workbench"><div className="overview-empty">
    <p className="task-eyebrow">RESUMEN</p><h1>Un lugar para retomar el trabajo</h1>
    <p>Elige un proyecto en la cabecera para ver sus preguntas, tareas y decisiones guardadas.</p>
    <Link className="overview-primary" to="/projects">Abrir proyectos</Link>
  </div></section>
  return <ProjectOverview key={projectId} projectId={projectId} />
}

/** Read independent sources without converting errors, task counts or saved labels into acceptance. */
function ProjectOverview({ projectId }: { projectId: number }) {
  const project = useProject(projectId), tasks = useTasks(projectId)
  const workspace = useQuery({queryKey:['project-workspace',projectId],queryFn:()=>projectWorkspace(projectId),retry:false,refetchInterval:15000})
  const client = useQueryClient(), navigate = useNavigate()
  const data = workspace.data, registered = tasks.data?.filter(task => task.project_id === projectId)
  const plans = data?.plans.filter(plan => plan.proposed && (!plan.accepted || !plan.context_current)) ?? []
  const planTasks = new Set(plans.map(plan => plan.task_id))
  const attention = registered?.filter(task => ['review_ready','rejected','blocked'].includes(task.status) && !planTasks.has(task.id)) ?? []
  const visible = registered?.slice(0,6) ?? []
  const done = registered?.filter(task => task.status === 'done').length ?? 0
  const description = data?.project.description ?? project.data?.description
  /** Refresh all independent observations; never create or retry work as a side effect. */
  function refresh() {
    void workspace.refetch(); void project.refetch(); void tasks.refetch()
    void client.invalidateQueries({queryKey:['question-inbox',projectId]})
  }
  /** Preserve the original project/task/question identity when opening an owner answer. */
  function openQuestion(taskId:number, requestId?:number) {
    navigate(`/chat?project=${projectId}&task=${taskId}${requestId == null ? '' : `&question=${requestId}`}`)
  }
  return <section className="task-workbench overview-workbench">
    <div className="overview-grid">
      <div className="overview-main">
        <header className="overview-heading">
          <p className="task-eyebrow">RESUMEN · CUADERNO DE SITUACIÓN</p>
          <h1>{data?.project.name ?? project.data?.name ?? 'Resumen del proyecto'}</h1>
          <p>{description || 'El alcance del proyecto todavía necesita una descripción.'}</p>
          <button onClick={refresh} disabled={workspace.isFetching || tasks.isFetching}>Actualizar resumen</button>
          {(workspace.isFetching || tasks.isFetching) && <p className="overview-muted" role="status">Consultando el estado guardado…</p>}
          {project.error && <p role="alert">No pudimos consultar los datos del proyecto.</p>}
          {workspace.error && <p role="alert">No pudimos consultar el contexto del proyecto.</p>}
          {workspace.error && data && <p>El contexto visible corresponde a la última consulta correcta.</p>}
        </header>
        <section className="overview-section" aria-labelledby="overview-attention">
          <h2 id="overview-attention">Necesita tu atención</h2>
          <p className="overview-muted">Abre el trabajo para leer su evidencia y decidir el siguiente paso.</p>
          {workspace.isPending && <p role="status">Consultando planes y decisiones…</p>}
          <ul className="overview-records">{plans.map(plan => <li key={plan.run_id}>
            <Link to={`/tasks?project=${projectId}&task=${plan.task_id}&planRun=${encodeURIComponent(plan.run_id)}`}>{plan.title}</Link>
            <span>{plan.context_current ? 'Propuesta guardada · revisar decisión' : 'El contexto cambió · revisar el plan original'}</span>
          </li>)}{attention.map(task => <li key={task.id}>
            <Link to={`/tasks?project=${projectId}&task=${task.id}`}>{task.title}</Link><span>{taskLabels[task.status] ?? task.status} · tarea {task.id}</span>
          </li>)}</ul>
          {(plans[0] || attention[0]) && <Link className="overview-primary" to={plans[0] ? `/tasks?project=${projectId}&task=${plans[0].task_id}&planRun=${encodeURIComponent(plans[0].run_id)}` : `/tasks?project=${projectId}&task=${attention[0].id}`}>Abrir tarea {plans[0]?.task_id ?? attention[0]?.id}</Link>}
          {workspace.isSuccess && tasks.isSuccess && !plans.length && !attention.length && <p>No hay planes ni tareas señalados para revisión en estas consultas.</p>}
          <QuestionInbox projectId={projectId} tasks={registered ?? []} onChoose={openQuestion} />
        </section>
        <section className="overview-section" aria-labelledby="overview-work">
          <div className="overview-section-heading"><h2 id="overview-work">Trabajo registrado</h2><Link to={`/tasks?project=${projectId}`}>Ver todas las tareas</Link></div>
          {tasks.isPending && <p role="status">Consultando tareas…</p>}
          {tasks.error && <p role="alert">No pudimos consultar las tareas. {registered ? 'Se conserva la última consulta correcta.' : 'Su cantidad es desconocida.'}</p>}
          {registered && <p className="overview-muted">{registered.length} tareas registradas · {done} marcadas como hechas.</p>}
          {registered?.length === 0 && <p>Todavía no hay tareas registradas.</p>}
          <ul className="overview-records">{visible.map(task => <li key={task.id} className="overview-task-row"><div><Link to={`/tasks?project=${projectId}&task=${task.id}`}>{task.title}</Link><span>Tarea {task.id}</span></div><span>{taskLabels[task.status] ?? task.status}</span></li>)}</ul>
          {registered && registered.length > visible.length && <p className="overview-muted">Se muestran {visible.length} de {registered.length} tareas. Abre la lista completa para consultar el resto.</p>}
          <p className="overview-note">Una tarea marcada como hecha puede conservar un resultado de una versión anterior. La aceptación y su vigencia se comprueban al abrir su evidencia.</p>
        </section>
      </div>
      <aside className="overview-context" aria-label="Contexto y decisiones del proyecto">
        <section><h2>Contexto del proyecto</h2><p>{description || 'Sin alcance disponible en esta consulta.'}</p><Link to="/projects">Ver proyecto</Link></section>
        <section><h2>Fuentes</h2>{!data ? <p>Fuentes pendientes de consulta.</p> : data.sources.length === 0 ? <p>No hay fuentes registradas.</p> : <ul className="overview-records">{data.sources.map(source => <li key={source.repository_id}><strong>{source.name}</strong><span>{source.availability === 'available' ? 'Carpeta disponible' : source.availability === 'unavailable' ? 'Carpeta no disponible' : 'Disponibilidad sin comprobar'}</span></li>)}</ul>}<Link to="/repositories">Consultar fuentes</Link></section>
        <section><h2>Actividad registrada</h2>{!data ? <p>Actividad pendiente de consulta.</p> : data.activity.length === 0 ? <p>Sin intentos activos registrados en esta consulta.</p> : <ul className="overview-records">{data.activity.map(run => <li key={run.run_id}><Link to={`/tasks?project=${projectId}&task=${run.task_id}`}>Tarea {run.task_id}</Link><span>{activityLabels[run.status] ?? run.status}</span></li>)}</ul>}<p className="overview-muted">Consulta el intento para comprobar su estado actual y su cierre.</p>{data?.legacy_registered && <p>Hay un controlador anterior registrado. Consulta su cierre en el proyecto.</p>}</section>
        <section><h2>Decisiones guardadas</h2>{!data ? <p>Decisiones pendientes de consulta.</p> : data.reports.length === 0 ? <p>No hay informes de cierre aceptados registrados.</p> : <><ul className="overview-records">{data.reports.map(report => <li key={report.operation_key}><Link to={`/tasks?project=${projectId}&task=${report.task_id}&planRun=${encodeURIComponent(report.plan_run_id)}`}>Informe de cierre · tarea {report.task_id}</Link></li>)}</ul><p className="overview-muted">Vigencia pendiente de comprobar. Abre el informe y su contexto original.</p></>}</section>
      </aside>
    </div>
  </section>
}
