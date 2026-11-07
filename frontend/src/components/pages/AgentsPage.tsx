/** Observe native agents through original runs instead of reconstructing activity from legacy rosters. @module */
import {useState} from 'react'
import {useInfiniteQuery,useMutation,useQueryClient} from '@tanstack/react-query'
import {Link} from 'react-router-dom'
import {useProjectStore} from '../../stores/project'
import {agentRuns,type AgentRun} from '../../api/agentRuns'
import {stopRun} from '../../api/runtime'
import {RunAttempts} from '../tasks/ExecutionHistory'
import {WorkBudget} from '../tasks/WorkBudget'
import '../../styles/tasks.css'
import '../../styles/agents.css'

const states:Record<string,string>={queued:'En cola',running:'En ejecución registrada',waiting_input:'Espera una respuesta',needs_review:'Pendiente de revisión',cancelling:'Parada solicitada',reconciling:'Requiere comprobación',cancelled:'Cancelada',failed:'Fallida',superseded:'Contexto reemplazado',accepted:'Resultado aceptado'}
const kinds:Record<string,string>={research:'Investigación',investigation:'Investigación',plan:'Planificación',development:'Desarrollo',code:'Desarrollo',code_review:'Revisión de código',finding_review:'Revisión documental',code_publication:'Publicación local',remote_publication:'Publicación remota'}
/** Format reported usage without changing missing observations into zero. */
function tokens(value:number|null){return value==null?'No disponible':new Intl.NumberFormat('es-AR').format(value)}
/** Reset selection and control results when the owner changes project. */
export function AgentsPage(){
 const projectId=useProjectStore(state=>state.activeProjectId)
 if(projectId==null)return <section className="task-workbench agents-workbench"><div className="agents-heading"><p className="task-eyebrow">AGENTES</p><h1>Quién se ocupa del trabajo</h1><p>Selecciona un proyecto en la cabecera para consultar sus ejecuciones.</p><Link to="/projects">Abrir proyectos</Link></div></section>
 return <AgentLedger key={projectId} projectId={projectId}/>
}
/** Page saved runs; a failed read never becomes an empty roster or proof of inactivity. */
function AgentLedger({projectId}:{projectId:number}){
 const query=useInfiniteQuery({queryKey:['agent-runs',projectId],initialPageParam:null as string|null,queryFn:({pageParam})=>agentRuns(projectId,pageParam),getNextPageParam:page=>page.next_before_seq??undefined,retry:false,refetchInterval:10000})
 const [selected,setSelected]=useState<string|null>(null)
 const pages=query.data?.pages.filter(page=>page.project_id===projectId)??[]
 const records=Array.from(new Map(pages.flatMap(page=>page.items.filter(run=>run.project_id===projectId)).map(run=>[run.run_id,run])).values())
 const run=records.find(item=>item.run_id===selected)
 /** Select the original run and focus its heading after the mobile panel opens. */
 function select(id:string){setSelected(id);requestAnimationFrame(()=>document.getElementById('agent-detail-title')?.focus())}
 /** Return focus to the original row after revealing the mobile index. */
 function back(){const id=selected;setSelected(null);requestAnimationFrame(()=>document.getElementById(`agent-run-${id}`)?.focus())}
 return <section className="task-workbench agents-workbench" data-selected={Boolean(run)}>
  <header className="agents-heading"><p className="task-eyebrow">EQUIPO · REGISTRO NATIVO</p><h1>Agentes</h1><p>Responsabilidad y ejecución observada.</p><p className="agents-muted">Cada fila conserva una ejecución y su agente. El estado guardado no confirma actividad en este instante.</p></header>
  <WorkBudget projectId={projectId}/>
  {query.error&&<div className="agents-notice" role="alert"><p>No pudimos consultar las ejecuciones. {query.error.message}</p>{records.length>0&&<p>Se conserva la última consulta correcta.</p>}<button onClick={()=>query.refetch()}>Volver a consultar</button></div>}
  <div className="agents-layout"><aside className="agents-index" aria-label="Ejecuciones por agente">
   <div className="agents-index-heading"><h2>Ejecuciones</h2><button onClick={()=>query.refetch()} disabled={query.isFetching}>Actualizar</button></div>
   {pages[0]&&<p className="agents-muted">{records.length} de {pages[0].total_runs} guardadas · {pages[0].total_actors} identidades</p>}
   {query.isPending&&<p role="status">Consultando el registro…</p>}
   {query.isSuccess&&records.length===0&&<p>Todavía no hay ejecuciones nativas en este proyecto.</p>}
   <ul>{records.map(item=><li key={item.run_id}><button id={`agent-run-${item.run_id}`} className="agents-row" aria-pressed={selected===item.run_id} onClick={()=>select(item.run_id)}><strong>{item.actor_id}</strong><span>{item.task_title}</span><span className="agents-muted">{states[item.status]??item.status}</span><span className="agents-muted">Tokens del intento: {tokens(item.observed_tokens)}</span></button></li>)}</ul>
   {query.hasNextPage&&<button className="agents-load" disabled={query.isFetching} onClick={()=>query.fetchNextPage()}>Cargar ejecuciones anteriores</button>}
  </aside><div className="agents-reading">{run?<><button className="agents-back" onClick={back}>Volver a ejecuciones</button><AgentDetail key={run.run_id} run={run} configured={pages[0]?.runtime_configured===true}/></>:<div className="agents-intro"><h2>Una responsabilidad, con su contexto</h2><p>Selecciona una ejecución para ver quién recibió la tarea, su intento y los datos que dejó registrados.</p><p>Por ejemplo: «1.240 tokens observados» puede ser una medición parcial. No indica cuánto queda de tu suscripción.</p><Link to="/tasks">Abrir tareas</Link></div>}</div></div>
 </section>
}
/** Explain one original run and reuse owner Stop without treating its HTTP receipt as physical closure. */
function AgentDetail({run,configured}:{run:AgentRun;configured:boolean}){
 const client=useQueryClient()
 const stop=useMutation({mutationFn:()=>stopRun(run.project_id,run.run_id),retry:false,onSettled:()=>{
  void client.invalidateQueries({queryKey:['agent-runs',run.project_id]})
  void client.invalidateQueries({queryKey:['task-workspace',run.project_id,run.task_id]})
 }})
 const stoppable=['queued','running','waiting_input','needs_review','reconciling','cancelling'].includes(run.status)
 return <article className="agents-detail"><p className="task-eyebrow">{kinds[run.task_type]??run.task_type} · TAREA {run.task_id}</p><h2 id="agent-detail-title" tabIndex={-1}>{run.task_title}</h2><p className="agents-byline">Agente: <strong>{run.actor_id}</strong></p><Link to={`/tasks?project=${run.project_id}&task=${run.task_id}`}>Abrir tarea e historial</Link>
  <section><h3>Ejecución y consumo</h3><dl className="agents-facts">
   <div><dt>Estado guardado</dt><dd>{states[run.status]??run.status}</dd></div><div><dt>Trabajo</dt><dd>{kinds[run.execution_kind]??run.execution_kind}</dd></div>
   <div><dt>Intento actual</dt><dd>{run.attempt_id?'Registrado':'Sin intento registrado'}{run.attempt_id&&` · ${run.attempt_count} en esta ejecución`}</dd></div>
   <div><dt>Modelo para el envío</dt><dd>{run.model??'Sin envío registrado'}</dd></div><div><dt>Esfuerzo seleccionado</dt><dd>{run.model_selection?.reasoning_effort??'No disponible'}</dd></div>
   <div><dt>Tokens observados</dt><dd>{tokens(run.observed_tokens)}</dd></div>
  </dl><p className="agents-muted">{run.observed_tokens==null?'No hay una medición de consumo disponible para este intento.':run.dispatch_status==='settled'?'Máximo acumulado informado, conservado en el recibo final.':'Máximo acumulado informado hasta ahora; la medición puede estar incompleta.'} Cuota restante y coste de la suscripción: no disponibles.</p></section>
  <section className="agents-control"><h3>Control de esta ejecución</h3><p>{run.cancel_requested?'Parada solicitada. Consulta el cierre y la recuperación en la tarea original.':'Detener solicita el cese de esta ejecución. El resultado se consulta por separado de la aceptación de la tarea.'}</p>
   {stoppable&&<button className="agents-primary" disabled={!configured||stop.isPending||run.cancel_requested||run.status==='cancelling'} onClick={()=>stop.mutate()}>{stop.isPending?'Solicitando parada…':'Detener esta ejecución'}</button>}
   {!configured&&stoppable&&<p>El runtime no está configurado; sólo se puede consultar la historia guardada.</p>}
   {stop.error&&<p role="alert">No se confirmó la parada. {stop.error.message} Conservamos la identidad original; consulta su estado antes de repetir.</p>}
   {stop.isSuccess&&<p role="status">Solicitud recibida. El estado guardado y los recibos de cierre se comprueban por separado.</p>}
  </section>
  <RunAttempts projectId={run.project_id} runId={run.run_id}/>
  <details className="agents-identities"><summary>Identidad y comprobaciones del intento</summary><dl className="agents-facts"><div><dt>Ejecución</dt><dd>{run.run_id}</dd></div><div><dt>Intento</dt><dd>{run.attempt_id??'No registrado'}</dd></div><div><dt>Versión de contexto</dt><dd>{run.context_version}</dd></div><div><dt>Procesos registrados</dt><dd>{run.peer_count===0?'Sin recibos':`${run.peer_count} · ${run.unclosed_peer_count} sin recibo de cierre`}</dd></div></dl><p className="agents-muted">Estos datos describen recibos guardados. Abrir la página no comprueba procesos ni inicia trabajo.</p></details>
 </article>
}
