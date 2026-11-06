/** Planning register separates saved native proposals from existing work groups and milestones. @module */
import {useEffect,useRef,useState,type FormEvent} from 'react'
import {useQuery,useQueryClient} from '@tanstack/react-query'
import {Link} from 'react-router-dom'
import {useProjectStore} from '../../stores/project'
import {useEpics,useCreateEpic,useDeleteEpic} from '../../hooks/useEpics'
import {useMilestones,useCreateMilestone} from '../../hooks/useMilestones'
import {useTasks,useTaskDependencies} from '../../hooks/useTasks'
import {projectWorkspace} from '../../api/projectWorkspace'
import {projectPlanState} from '../../api/projectPlans'
import type {Epic,Task} from '../../types/api'
import '../../styles/tasks.css'
import '../../styles/planning.css'

/** One explicit selection belongs to the currently mounted project only. */
type Selection={kind:'group';id:number}|{kind:'proposal';runId:string;taskId:number}|{kind:'create'}|null
const statusLabels:Record<string,string>={open:'Abierto',in_progress:'En curso registrado',completed:'Marcado como completado',cancelled:'Cancelado',pending:'Pendiente',backlog:'Por organizar',review_ready:'Pendiente de revisión',done:'Marcada como hecha',rejected:'Requiere cambios',blocked:'Bloqueada'}

/** Dispose selection and form state on project changes so delayed responses cannot target another project. */
export function EpicsPage(){
 const projectId=useProjectStore(state=>state.activeProjectId)
 if(projectId==null)return <section className="task-workbench planning-workbench"><div className="planning-empty"><h1>Planificación</h1><p>Elige un proyecto para consultar propuestas, grupos e hitos.</p><Link to="/projects">Abrir proyectos</Link></div></section>
 return <PlanningRegister key={projectId} projectId={projectId}/>
}

/** Keep proposals and created groups independently observable; selection never accepts or starts a plan. */
function PlanningRegister({projectId}:{projectId:number}){
 const epics=useEpics(projectId),client=useQueryClient()
 const workspace=useQuery({queryKey:['project-workspace',projectId],queryFn:()=>projectWorkspace(projectId),retry:false})
 const [selection,setSelection]=useState<Selection>(null)
 const lastIndex=useRef<string|null>(null)
 const groups=epics.data?.filter(epic=>epic.project_id===projectId)??[]
 const selected=selection?.kind==='group'?groups.find(group=>group.id===selection.id):undefined
 /** Move focus to the chosen reading pane after React has committed its content. */
 function choose(next:Selection,indexId?:string){lastIndex.current=indexId??lastIndex.current;setSelection(next);requestAnimationFrame(()=>document.getElementById('planning-reading')?.focus())}
 /** Restore the index control after leaving the mobile reading view. */
 function back(){setSelection(null);requestAnimationFrame(()=>document.getElementById(lastIndex.current??'planning-new')?.focus())}
 /** Refresh saved observations without creating a planning request or issuing any work. */
 function refresh(){void epics.refetch();void workspace.refetch();void client.invalidateQueries({queryKey:['milestones',projectId]});void client.invalidateQueries({queryKey:['tasks',projectId]})}
 return <section className="task-workbench planning-workbench" data-selected={selection!==null}>
  <header className="planning-heading"><div><h1>Planificación</h1><p>Organiza el trabajo y revisa qué se está proponiendo.</p></div><button id="planning-new" className="planning-primary" onClick={()=>choose({kind:'create'},'planning-new')}>Nuevo grupo</button></header>
  <div className="planning-layout">
   <aside className="planning-index" aria-label="Índice de propuestas y grupos"><button className="planning-link" disabled={epics.isFetching||workspace.isFetching} onClick={refresh}>Actualizar planificación</button>
    <section><h2>Propuestas</h2>{workspace.isPending&&<p role="status">Consultando propuestas…</p>}{workspace.error&&<p role="alert">No pudimos consultar las propuestas. La lista visible conserva la última consulta correcta.</p>}{workspace.isSuccess&&!workspace.data.plans.length&&<p>No hay planes nativos guardados.</p>}<ul>{workspace.data?.plans.map(plan=><li key={plan.run_id}><button id={`planning-plan-${plan.run_id}`} aria-pressed={selection?.kind==='proposal'&&selection.runId===plan.run_id} onClick={()=>choose({kind:'proposal',runId:plan.run_id,taskId:plan.task_id},`planning-plan-${plan.run_id}`)}><strong>{plan.title}</strong><span>{!plan.context_current?'Contexto original cambió':plan.accepted?'Aceptación guardada':plan.proposed?'Propuesta guardada':'Propuesta aún no guardada'}</span></button></li>)}</ul><Link to="/projects">Preparar un plan desde el proyecto</Link></section>
    <section><h2>Grupos de trabajo</h2><p>Una épica agrupa tareas de un mismo objetivo.</p>{epics.isPending&&<p role="status">Consultando grupos…</p>}{epics.error&&<p role="alert">No pudimos consultar los grupos.</p>}{epics.isSuccess&&!groups.length&&<p>Todavía no hay grupos en este proyecto.</p>}<ul>{groups.map(group=><li key={group.id}><button id={`planning-group-${group.id}`} aria-pressed={selected?.id===group.id} onClick={()=>choose({kind:'group',id:group.id},`planning-group-${group.id}`)}><strong>{group.title}</strong><span>{group.task_count??'Sin recuento de'} tareas · prioridad {group.priority}</span></button></li>)}</ul></section>
   </aside>
   <div id="planning-reading" tabIndex={-1} className="planning-reading">
    {selection&&<button className="planning-link planning-back" onClick={back}>Volver al índice</button>}
    {selection?.kind==='create'?<GroupForm projectId={projectId} onCreated={id=>choose({kind:'group',id},`planning-group-${id}`)} onCancel={back}/>:selected?<GroupDetail key={selected.id} projectId={projectId} group={selected} onDeleted={back}/>:selection?.kind==='proposal'?<PlanPreview key={selection.runId} projectId={projectId} taskId={selection.taskId} runId={selection.runId}/>:<section className="planning-empty"><h2>{selection?'Grupo no disponible en esta consulta':'Del objetivo al trabajo concreto'}</h2><p>Elige un grupo para ver sus hitos, tareas y dependencias, o una propuesta para revisar sus bases.</p><p>Un plan propone trabajo. Aceptarlo crea tareas pendientes; ejecutarlas y aceptar sus resultados son decisiones posteriores.</p></section>}
   </div>
  </div>
 </section>
}

/** Create one manual work group from the captured project; preserve its draft after a rejected response. */
function GroupForm({projectId,onCreated,onCancel}:{projectId:number;onCreated:(id:number)=>void;onCancel:()=>void}){
 const mutation=useCreateEpic(),[title,setTitle]=useState(''),[description,setDescription]=useState(''),[priority,setPriority]=useState(2)
 /** Submit only the entered metadata; creating a group grants no execution permission. */
 function submit(event:FormEvent){event.preventDefault();mutation.mutate({project_id:projectId,title:title.trim(),description,priority},{onSuccess:group=>onCreated(group.id)})}
 return <form className="planning-form" onSubmit={submit}><h2>Nuevo grupo de trabajo</h2><p>Organiza un objetivo en una épica. Las tareas y su ejecución se deciden por separado.</p><label>Nombre del grupo<input autoFocus required maxLength={255} value={title} onChange={event=>setTitle(event.target.value)}/></label><label>Descripción<textarea rows={4} value={description} onChange={event=>setDescription(event.target.value)}/></label><label>Prioridad<select value={priority} onChange={event=>setPriority(Number(event.target.value))}>{[1,2,3,4,5].map(value=><option key={value} value={value}>{value}{value===1?' · más urgente':''}</option>)}</select></label><div className="planning-actions"><button className="planning-primary" disabled={!title.trim()||mutation.isPending}>Crear grupo</button><button type="button" onClick={onCancel}>Cancelar</button></div>{mutation.error&&<p role="alert">No se confirmó la creación. {mutation.error.message} El borrador se conserva; si se perdió la conexión, consulta el índice antes de repetir.</p>}</form>
}

/** Show actual group members, independently loaded milestones and original task dependencies. */
function GroupDetail({projectId,group,onDeleted}:{projectId:number;group:Epic;onDeleted:()=>void}){
 const tasks=useTasks(projectId),milestones=useMilestones(projectId,group.id),create=useCreateMilestone(),remove=useDeleteEpic(),client=useQueryClient()
 const [adding,setAdding]=useState(false),[title,setTitle]=useState(''),[deleting,setDeleting]=useState(false),[dependencyTask,setDependencyTask]=useState<number|null>(null)
 const members=tasks.data?.filter(task=>task.project_id===projectId&&task.epic_id===group.id)??[]
 const stages=milestones.data?.filter(m=>m.project_id===projectId&&m.epic_id===group.id)??[]
 /** Bind the submitted milestone to this exact mounted group; a project switch cannot retarget it. */
 function addMilestone(event:FormEvent){event.preventDefault();create.mutate({epic_id:group.id,title:title.trim()},{onSuccess:()=>{setAdding(false);setTitle('')}})}
 /** Remove only the explicitly named group and refresh every affected list after confirmation. */
 function deleteGroup(){remove.mutate(group.id,{onSuccess:()=>{void client.invalidateQueries({queryKey:['milestones',projectId]});void client.invalidateQueries({queryKey:['tasks',projectId]});setDeleting(false);onDeleted()}})}
 return <article className="planning-detail"><h2>{group.title}</h2><p className="planning-description">{group.description||'Sin descripción registrada.'}</p><p className="planning-muted">{group.tasks_done??'—'} de {group.task_count??'—'} tareas marcadas como hechas · {statusLabels[group.status]??group.status}.</p>
  <section><div className="planning-section-heading"><h3>Hitos</h3><button className="planning-link" onClick={()=>setAdding(!adding)}>Añadir hito</button></div>{milestones.isPending&&<p role="status">Consultando hitos…</p>}{milestones.error&&<div role="alert"><p>No pudimos consultar los hitos.</p><button onClick={()=>milestones.refetch()}>Volver a consultar hitos</button></div>}{milestones.isSuccess&&!stages.length&&<p>Este grupo no tiene hitos registrados.</p>}<ul className="planning-records">{stages.map(stage=><li key={stage.id}><strong>{stage.title}</strong><p className="planning-muted">{statusLabels[stage.status]??stage.status} · {stage.tasks_done??'—'} de {stage.task_count??'—'} tareas marcadas como hechas{stage.due_date?` · fecha registrada: ${stage.due_date}`:''}</p></li>)}</ul>
   {adding&&<form className="planning-form" onSubmit={addMilestone}><label>Nombre del hito<input autoFocus required maxLength={255} value={title} onChange={event=>setTitle(event.target.value)}/></label><div className="planning-actions"><button className="planning-primary" disabled={!title.trim()||create.isPending}>Guardar hito</button><button type="button" onClick={()=>setAdding(false)}>Cancelar hito</button></div>{create.error&&<p role="alert">No se confirmó el hito. {create.error.message} Conservamos el texto; consulta la lista antes de repetir si se perdió la conexión.</p>}</form>}
  </section>
  <section><h3>Tareas y dependencias</h3>{tasks.isPending&&<p role="status">Consultando tareas…</p>}{tasks.error&&<p role="alert">No pudimos consultar las tareas del grupo.</p>}{tasks.isSuccess&&!members.length&&<p>No hay tareas asociadas a este grupo.</p>}<ul className="planning-records">{members.map(task=><li key={task.id}><div className="planning-task-heading"><Link to={`/tasks?project=${projectId}&task=${task.id}`}>{task.title}</Link><span className="planning-muted">{statusLabels[task.status]??task.status}</span></div>{task.milestone_id&&<p className="planning-muted">Hito: {stages.find(stage=>stage.id===task.milestone_id)?.title??`#${task.milestone_id} · pendiente de consulta`}</p>}<button className="planning-link" aria-expanded={dependencyTask===task.id} aria-controls={`planning-dependencies-${task.id}`} onClick={()=>setDependencyTask(dependencyTask===task.id?null:task.id)}>Ver dependencias: {task.title}</button>{dependencyTask===task.id&&<TaskDependencies projectId={projectId} task={task} tasks={tasks.data??[]}/>}</li>)}</ul><p className="planning-muted planning-explanation">Las dependencias describen el orden del trabajo. La aceptación y su vigencia se comprueban en la tarea original.</p></section>
  <footer><button className="planning-link planning-danger" onClick={()=>setDeleting(true)}>Eliminar grupo</button><p className="planning-muted">Eliminar retira el grupo y sus hitos; las tareas se desvinculan. El servidor puede rechazarlo si hay trabajo activo o historia protegida.</p></footer>
  {deleting&&<GroupDeleteDialog name={group.title} working={remove.isPending} error={remove.error?.message} onCancel={()=>setDeleting(false)} onConfirm={deleteGroup}/>}
 </article>
}

/** Load dependencies only for the expanded known task; absent referenced tasks remain explicitly unresolved. */
function TaskDependencies({projectId,task,tasks}:{projectId:number;task:Task;tasks:Task[]}){
 const query=useTaskDependencies(task.id)
 return <section id={`planning-dependencies-${task.id}`} className="planning-dependencies" role="region" aria-label={`Dependencias de ${task.title}`}>
  {query.isPending&&<p role="status">Consultando dependencias…</p>}{query.error&&<p role="alert">No pudimos consultar las dependencias.</p>}{query.isSuccess&&!query.data.length&&<p>Sin dependencias registradas para esta tarea.</p>}<ul>{query.data?.map(dep=>{const source=tasks.find(item=>item.project_id===projectId&&item.id===dep.depends_on_task_id);return <li key={`${dep.depends_on_task_id}:${dep.dependency_type}`}>Depende de: {source?<Link to={`/tasks?project=${projectId}&task=${source.id}`}>{source.title}</Link>:`Tarea ${dep.depends_on_task_id} · no disponible en esta consulta`}<span className="planning-muted"> · relación registrada: {dep.dependency_type}</span></li>})}</ul>
 </section>
}

/** Read one exact native plan, preserving attribution and proposed identifiers until its original acceptance flow. */
function PlanPreview({projectId,taskId,runId}:{projectId:number;taskId:number;runId:string}){
 const state=useQuery({queryKey:['project-plan',projectId,runId],queryFn:()=>projectPlanState(projectId,taskId,runId),retry:false})
 const data=state.data,draft=data?.proposal?.draft
 const originLabels:Record<string,string>={owner_request:data?.snapshot.instruction_origin==='owner_message'?'Mensaje del propietario':'Directiva del host para planificar',project_name:'Nombre registrado del proyecto',project_description:'Descripción registrada del proyecto',task_description:'Descripción registrada de la tarea',acceptance_criteria:'Criterios registrados'}
 return <article className="planning-detail"><p className="planning-eyebrow">PROPUESTA GUARDADA · TAREA {taskId}</p><h2>{draft?.title??'Plan original'}</h2><button className="planning-link" disabled={state.isFetching} onClick={()=>state.refetch()}>Actualizar propuesta</button>{state.isPending&&<p role="status">Consultando el plan original…</p>}{state.error&&<p role="alert">No pudimos consultar la propuesta. {state.error.message}</p>}{data&&!draft&&<p>Todavía no hay una propuesta estructurada guardada.</p>}
  {draft&&<><p className="planning-description">{draft.rationale}</p><section><h3>En qué se apoya</h3>{draft.basis.map((basis,index)=><blockquote key={index}><p className="planning-muted">{originLabels[basis.source]??`Referencia registrada: ${basis.source}`}</p><p>{basis.quote}</p></blockquote>)}</section><section><h3>Lo que se está suponiendo</h3>{draft.assumptions.length?<ul className="planning-bullets">{draft.assumptions.map((assumption,index)=><li key={index}>{assumption}</li>)}</ul>:<p>No se declararon suposiciones. Esto no demuestra que todas las premisas estén comprobadas.</p>}</section><section><h3>Trabajo propuesto</h3>{draft.epics.map(epic=><section className="planning-proposed-group" key={epic.key}><h4>{epic.title}</h4><p>{epic.description}</p><ol className="planning-records">{draft.tasks.filter(task=>task.epic_key===epic.key).map(task=><li key={task.key}><strong>{task.title}</strong><p>{task.description}</p><p className="planning-muted">Resultado comprobable: {task.acceptance_criteria}</p><p className="planning-muted">{task.depends_on.length?`Depende de: ${task.depends_on.map(key=>draft.tasks.find(item=>item.key===key)?.title??key).join(', ')}`:'Sin prerrequisitos en esta propuesta'}</p></li>)}</ol></section>)}</section></>}
  {data?.acceptance&&<p className="planning-notice">{data.acceptance_current?'La aceptación está registrada para este contexto. Consulta la ejecución y los resultados por separado.':'Aceptación histórica: el contexto cambió. Consulta la versión original antes de actuar.'}</p>}
  <section><p>Si una base o suposición es incorrecta, registra una corrección en la tarea. Aceptar un plan crea tareas pendientes; ejecutarlo requiere otra decisión.</p><Link className="planning-primary" to={`/tasks?project=${projectId}&task=${taskId}&planRun=${encodeURIComponent(runId)}`}>Revisar y decidir en la tarea original</Link></section>
 </article>
}

/** Native modal preserves focus and names the exact destructive target; failed deletion stays visible. */
function GroupDeleteDialog({name,working,error,onCancel,onConfirm}:{name:string;working:boolean;error?:string;onCancel:()=>void;onConfirm:()=>void}){
 const ref=useRef<HTMLDialogElement>(null)
 useEffect(()=>{const dialog=ref.current;dialog?.showModal();return()=>dialog?.close()},[])
 return <dialog ref={ref} className="planning-delete" aria-labelledby="planning-delete-title" onCancel={event=>{event.preventDefault();if(!working)onCancel()}}><h2 id="planning-delete-title">Eliminar «{name}»</h2><p>Se eliminarán este grupo y sus hitos. Las tareas se conservan sin estas asociaciones. Revisa su historia antes de confirmar.</p><div className="planning-actions"><button autoFocus disabled={working} onClick={onCancel}>Conservar grupo</button><button disabled={working} onClick={onConfirm}>Eliminar este grupo</button></div>{error&&<p role="alert">No se confirmó la eliminación. {error}</p>}</dialog>
}
