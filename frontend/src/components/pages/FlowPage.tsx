/** Inspect actual accepted graphs and causal deliveries; never render a fictional fixed execution pipeline. @module */
import {useState} from 'react'
import {useQuery,useQueryClient} from '@tanstack/react-query'
import {Link} from 'react-router-dom'
import {useProjectStore} from '../../stores/project'
import {projectWorkspace,type ProjectWorkspaceState} from '../../api/projectWorkspace'
import {executionState,type WorkDelivery} from '../../api/planExecution'
import {PlanExecution} from '../tasks/PlanExecution'
import '../../styles/tasks.css'
import '../../styles/flow.css'

/** Original accepted-plan locator supplied by the project projection, including historical contexts. */
type Plan=ProjectWorkspaceState['plans'][number]
/** Display node from the checked manifest, or an explicitly incomplete historical task identity. */
type Node={task_id:number;title:string;type:string;depends_on:number[]|null}
const statuses:Record<string,string>={pending:'Pendiente de despacho o dependencias',queued:'En cola',running:'En ejecución registrada',waiting_input:'Espera una respuesta',needs_review:'Resultado pendiente de revisión',accepted:'Resultado aceptado',cancelling:'Detención solicitada',reconciling:'Requiere comprobación',cancelled:'Cancelada',failed:'Intento fallido',superseded:'Contexto reemplazado'}

/** Reset the inspector on project changes while original owner-control packets stay in their own scope. */
export function FlowPage(){
 const projectId=useProjectStore(state=>state.activeProjectId)
 if(projectId==null)return <section className="task-workbench flow-workbench"><header className="flow-heading"><h1>Ejecución</h1><p>Selecciona un proyecto para consultar sus planes y entregas.</p><Link to="/projects">Abrir proyectos</Link></header></section>
 return <ProjectExecution key={projectId} projectId={projectId}/>
}

/** List all accepted plans, including paused/history entries that the active graph list omits. */
function ProjectExecution({projectId}:{projectId:number}){
 const state=useQuery({queryKey:['project-workspace',projectId],queryFn:()=>projectWorkspace(projectId),retry:false,refetchInterval:10000})
 const [selected,setSelected]=useState<string|null>(null)
 const data=state.data?.project_id===projectId?state.data:undefined
 const plans=data?.plans.filter(plan=>plan.accepted)??[],plan=plans.find(item=>item.run_id===selected)
 /** Focus the original plan after revealing its responsive detail. */
 function select(runId:string){setSelected(runId);requestAnimationFrame(()=>document.getElementById('flow-plan-title')?.focus())}
 /** Restore focus to the chosen plan when leaving its mobile detail. */
 function back(){const id=selected;setSelected(null);requestAnimationFrame(()=>document.getElementById(`flow-plan-${id}`)?.focus())}
 return <section className="task-workbench flow-workbench" data-selected={Boolean(plan)}>
  <header className="flow-heading"><p className="task-eyebrow">RECORRIDO DEL TRABAJO</p><h1>Ejecución</h1><p>Consulta dependencias, entregas guardadas y decisiones pendientes.</p><p className="flow-muted">El estado registrado no confirma actividad en este instante. Aceptar un plan y autorizar su ejecución son decisiones distintas.</p></header>
  {state.error&&<div role="alert" className="flow-notice"><p>No pudimos consultar el recorrido. {state.error.message}</p>{data&&<p>Se conserva la última consulta correcta; los controles quedan en lectura.</p>}<button onClick={()=>state.refetch()}>Volver a consultar</button></div>}
  <div className="flow-layout"><aside className="flow-plans" aria-label="Planes aceptados"><div className="flow-section-heading"><h2>Planes</h2><button disabled={state.isFetching} onClick={()=>state.refetch()}>Actualizar</button></div>
   {state.isPending&&<p role="status">Consultando planes…</p>}{state.isSuccess&&!plans.length&&<p>Todavía no hay planes aceptados en este proyecto.</p>}
   <ul>{plans.map(item=><li key={item.run_id}><button id={`flow-plan-${item.run_id}`} className="flow-plan-row" aria-pressed={selected===item.run_id} onClick={()=>select(item.run_id)}><strong>{item.title}</strong><span className="flow-muted">{item.context_current?'Aceptación registrada · consultar ejecución':'Contexto anterior · consultar historia'}</span></button></li>)}</ul>
   <Link to="/epics">Revisar planificación</Link>
   {!!data?.activity.length&&<section className="flow-activity"><h3>Actividad registrada</h3><ul>{data.activity.map(run=><li key={run.run_id}><Link to={`/tasks?project=${projectId}&task=${run.task_id}`}>Tarea {run.task_id}</Link><p className="flow-muted">{statuses[run.status]??run.status}</p></li>)}</ul><Link to="/agents">Identidades e intentos</Link></section>}
   {data?.legacy_registered&&<p className="flow-notice">El proyecto conserva actividad del sistema anterior. Consulta su cierre en Proyectos antes de autorizar trabajo nuevo.</p>}
  </aside><div className="flow-reading">{plan?<><button className="flow-back" onClick={back}>Volver a planes</button><PlanInspector key={plan.run_id} projectId={projectId} plan={plan} readOnly={!data?.runtime_available||state.isError}/></>:<div className="flow-intro"><h2>Qué puede avanzar y qué espera</h2><p>Selecciona un plan aceptado para consultar su recorrido real.</p><p>Por ejemplo, si «Corregir» depende de «Investigar», no basta con que termine una respuesta: el resultado previo necesita aceptación antes de entregar el siguiente trabajo.</p><p>Una tarea independiente puede aparecer en Actividad registrada sin pertenecer a un plan.</p></div>}</div></div>
 </section>
}

/** Show checked dependencies and current deliveries separately from historical attempts and owner authorization. */
function PlanInspector({projectId,plan,readOnly}:{projectId:number;plan:Plan;readOnly:boolean}){
 const query=useQuery({queryKey:['plan-execution',projectId,plan.run_id],queryFn:()=>executionState(projectId,plan.task_id,plan.run_id),retry:false,refetchInterval:5000})
 const [selected,setSelected]=useState<number|null>(null),[controls,setControls]=useState(false),[pending,setPending]=useState(false)
 const client=useQueryClient(),data=query.data,execution=data?.execution
 const deliveries=execution?.deliveries??[]
 const nodes:Node[]=data?.manifest?.tasks??Array.from(new Set(deliveries.map(d=>d.task_id))).map(task=>({task_id:task,title:`Tarea ${task}`,type:'',depends_on:null}))
 const node=nodes.find(item=>item.task_id===selected)
 const accepted=deliveries.filter(item=>item.current&&item.status==='accepted').length
 const total=deliveries.filter(item=>item.current).length
 /** Focus the requested task, including a dependency chosen from the current inspector. */
 function select(taskId:number){setSelected(taskId);requestAnimationFrame(()=>document.getElementById('flow-task-title')?.focus())}
 /** Restore the task row after leaving the narrow-screen evidence inspector. */
 function back(){const task=selected;setSelected(null);requestAnimationFrame(()=>document.getElementById(`flow-task-${task}`)?.focus())}
 /** Refresh project observations after the shared control acknowledges its original packet. */
 function resolved(){setPending(false);void client.invalidateQueries({queryKey:['project-workspace',projectId]})}
 return <article className="flow-detail" data-task-selected={Boolean(node)}>
  <p className="task-eyebrow">PLAN ACEPTADO · TAREA {plan.task_id}</p><h2 id="flow-plan-title" tabIndex={-1}>{plan.title}</h2>
  <Link to={`/tasks?project=${projectId}&task=${plan.task_id}&planRun=${encodeURIComponent(plan.run_id)}`}>Abrir plan y decisiones originales</Link>
  {query.isPending&&<p role="status">Comprobando el grafo guardado…</p>}
  {query.error&&<div role="alert"><p>No pudimos consultar este plan. {query.error.message}</p><button onClick={()=>query.refetch()}>Consultar este plan</button></div>}
  {data&&<>
   <p className="flow-state">{execution?execution.current?(execution.status==='active'?'Despacho autorizado para esta versión.':'Despacho pausado. Los intentos conservan su estado propio.'):'El contexto cambió. Se conserva la historia; la autorización anterior no permite trabajo nuevo.':data.eligible?'Plan aceptado, ejecución aún no autorizada.':'No hay ejecución autorizada verificable para este contexto.'}</p>
   {execution?.current&&<p className="flow-muted">{accepted} de {total} entregas actuales con resultado aceptado. Esto no declara terminado el proyecto.</p>}
   {!data.manifest&&<p className="flow-notice">Dependencias no verificables con el contexto actual. Los identificadores y entregas anteriores siguen disponibles como historia.</p>}
   <div className="flow-graph"><section className="flow-node-list" aria-label="Tareas y dependencias"><h3>Tareas del plan</h3><p className="flow-muted">El orden de esta lista no es una cronología. Las dependencias indican qué resultado espera cada tarea.</p><ul>{nodes.map(item=>{const delivery=deliveries.find(d=>d.task_id===item.task_id&&d.current);return <li key={item.task_id}><button id={`flow-task-${item.task_id}`} className="flow-node" aria-pressed={selected===item.task_id} onClick={()=>select(item.task_id)}><strong>{item.title}</strong><span>{delivery?statuses[delivery.status]??delivery.status:'Sin entrega registrada'}</span></button><p className="flow-muted">{item.depends_on===null?'Dependencias no verificables':item.depends_on.length?'Depende de: '+item.depends_on.map(id=>nodes.find(n=>n.task_id===id)?.title??`Tarea ${id}`).join(', '):'Sin prerrequisitos en este plan'}</p></li>})}</ul></section>
    <div className="flow-inspection">{node?<><button className="flow-task-back" onClick={back}>Volver a tareas</button><TaskInspection node={node} nodes={nodes} deliveries={deliveries.filter(d=>d.task_id===node.task_id)} projectId={projectId} onSelect={select}/></>:<div className="flow-intro"><h3>Inspeccionar una entrega</h3><p>Selecciona una tarea para ver su estado guardado, el resultado previo que recibió y el acceso a sus controles.</p></div>}</div>
   </div>
   <details className="flow-controls" onToggle={event=>setControls(event.currentTarget.open)}><summary>Controles del plan</summary>{controls&&<><h3 className="flow-control-heading">Decisiones sobre este recorrido</h3>{pending&&<p role="status">Se conserva una decisión original pendiente hasta comprobar su recibo.</p>}<PlanExecution projectId={projectId} taskId={plan.task_id} runId={plan.run_id} readOnly={readOnly||query.isError} onPending={()=>setPending(true)} onResolved={resolved}/></>}</details>
  </>}
 </article>
}

/** Explain actual handoff evidence and issues while retaining earlier deliveries as history rather than current progress. */
function TaskInspection({node,nodes,deliveries,projectId,onSelect}:{node:Node;nodes:Node[];deliveries:WorkDelivery[];projectId:number;onSelect:(task:number)=>void}){
 const current=deliveries.find(item=>item.current),history=deliveries.filter(item=>!item.current)
 return <section className="flow-task-detail" aria-label="Detalle de la tarea"><p className="task-eyebrow">TAREA {node.task_id} · INSPECCIÓN</p><h3 id="flow-task-title" tabIndex={-1}>{node.title}</h3><p className="flow-state">{current?statuses[current.status]??current.status:'Sin entrega registrada'}</p>
  {node.depends_on!==null&&<div className="flow-dependencies"><h4>Qué necesita antes</h4>{node.depends_on.length?<ul>{node.depends_on.map(id=><li key={id}><button onClick={()=>onSelect(id)}>{nodes.find(item=>item.task_id===id)?.title??`Tarea ${id}`}</button></li>)}</ul>:<p>Sin prerrequisitos en este plan.</p>}</div>}
  {current?.issue&&<div className="flow-issue"><h4>Necesita una comprobación</h4><p>El intento o su entrega encontró un impedimento. Abre la tarea original para revisar el estado y decidir cómo recuperar el trabajo.</p><p className="flow-muted">Código registrado: <code>{current.issue.code}</code></p></div>}
  <Link className="flow-primary" to={`/tasks?project=${projectId}&task=${node.task_id}`}>Abrir tarea y recuperación</Link>
  {current?.handoff&&<section className="flow-handoff"><h4>Evidencia recibida</h4>{current.handoff.prerequisites.length?<><p>Esta entrega recibió resultados aceptados de:</p><ul>{current.handoff.prerequisites.map(prerequisite=><li key={`${prerequisite.task_id}:${prerequisite.run_id}`}><Link to={`/tasks?project=${projectId}&task=${prerequisite.task_id}`}>{nodes.find(item=>item.task_id===prerequisite.task_id)?.title??`Tarea ${prerequisite.task_id}`}</Link><p className="flow-muted">Ejecución {prerequisite.run_id} · contexto {prerequisite.context_version}</p></li>)}</ul></>:<p>No recibió resultados previos como prerrequisitos.</p>}<p className="flow-muted">La entrega guardada no confirma que este intento haya terminado.</p></section>}
  {!!history.length&&<details className="flow-history"><summary>{history.length} entrega(s) anterior(es)</summary><ul>{history.map(item=><li key={item.delivery_id}><p>{statuses[item.status]??item.status} · entrega histórica</p><p className="flow-muted">{item.delivery_id}{item.run_id?` · ${item.run_id}`:''}</p></li>)}</ul><p>Se conservan como historia y no se cuentan como entregas actuales.</p></details>}
  {current&&<details className="flow-history"><summary>Identidad de la entrega</summary><p>{current.delivery_id}</p><p>Ejecución: {current.run_id??'Todavía no registrada'}</p>{current.predecessor_delivery_id&&<p>Entrega anterior: {current.predecessor_delivery_id}</p>}</details>}
 </section>
}
