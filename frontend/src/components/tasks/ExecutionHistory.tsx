/** Lazy paginated owner history, separate from controls for current work. @module */
import {useState} from 'react'
import {useInfiniteQuery} from '@tanstack/react-query'
import {measuredTokens,runAttempts,taskRunHistory} from '../../api/history'
import {presentRun} from '../../api/runtime'
import {RunCommands} from './RunCommands'
import {RunInputRecord} from './RunInputRecord'

const panel='space-y-2 rounded-md border border-[var(--work-line)] p-3'
const button='min-h-11 text-[var(--work-accent)] underline disabled:opacity-50'

/** Reset disclosure state on subject changes while preserving project-scoped query caches. */
export function RunAttempts({projectId,runId}:{projectId:number;runId:string}){
 return <AttemptPages key={`${projectId}:${runId}`} projectId={projectId} runId={runId}/>
}

/** Page original attempts on demand; an HTTP failure is never rendered as missing history. */
function AttemptPages({projectId,runId}:{projectId:number;runId:string}){
 const [open,setOpen]=useState(false)
 const query=useInfiniteQuery({queryKey:['run-attempts',projectId,runId],initialPageParam:null as string|null,queryFn:({pageParam})=>runAttempts(projectId,runId,pageParam),getNextPageParam:page=>page.next_before_seq??undefined,enabled:open,retry:false,refetchInterval:open?10000:false})
 const pages=query.data?.pages.filter(page=>page.project_id===projectId&&page.run_id===runId)??[]
 const items=Array.from(new Map(pages.flatMap(page=>page.items).map(item=>[item.attempt_id,item])).values())
 return <details className={panel} onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary className="min-h-11 cursor-pointer">Intentos guardados</summary>
  <p>Un intento conserva su modelo y resultado propios. Consultarlo no reanuda trabajo.</p>
  {open&&query.isPending&&<p role="status">Consultando los intentos…</p>}
  {query.error&&<div role="alert"><p>No se pudieron consultar los intentos. {items.length>0?'Se conserva la última consulta correcta.':''}</p><button className={button} onClick={()=>query.refetch()}>Volver a consultar intentos</button></div>}
  {query.isSuccess&&items.length===0&&<p>Sin intentos registrados.</p>}
  {pages[0]&&<p>{items.length} de {pages[0].total} intentos guardados.</p>}
  <ol className="space-y-3">{items.map(item=><li key={item.attempt_id} className="border-t border-[var(--work-line)] pt-2">
   <p><strong>Intento {item.seq}</strong> · {item.is_current?'actual':'anterior'} · {item.status==='finished'?'finalizado':item.status==='reconciling'?'requiere comprobación':'en ejecución registrada'}</p>
   <dl><div><dt>Modelo para el envío</dt><dd>{item.model??'Sin envío registrado'}</dd></div><div><dt>Esfuerzo seleccionado</dt><dd>{item.model_selection?.reasoning_effort??'No disponible'}</dd></div></dl>
   {item.preparation_token_ceiling!=null&&item.dispatch_status===null&&<p>Preparación reservada: {measuredTokens(item.preparation_token_ceiling)} tokens de capacidad. No hay envío registrado; la reserva se conserva y no equivale a consumo medido.</p>}
   <p>Tokens observados: {measuredTokens(item.observed_tokens)}</p>
   <p className="text-[var(--work-muted)]">{item.dispatch_status==='settled'?'Máximo acumulado conservado al cerrar el recibo; puede ser una medición incompleta.':'La medición puede estar incompleta; la reserva se consulta en el presupuesto del proyecto.'}</p>
   {item.result?.summary&&<p className="whitespace-pre-wrap break-words">{item.result.summary}</p>}
  </li>)}</ol>
  {query.hasNextPage&&<button className={button} disabled={query.isFetching} onClick={()=>query.fetchNextPage()}>Cargar intentos anteriores</button>}
 </details>
}

/** Keep task history selection independent from the current workspace's execution controls. */
export function TaskRunHistory({projectId,taskId}:{projectId:number;taskId:number}){
 return <TaskHistoryPages key={`${projectId}:${taskId}`} projectId={projectId} taskId={taskId}/>
}

/** Read all task runs through stable pages rather than silently stopping at the workspace preview. */
function TaskHistoryPages({projectId,taskId}:{projectId:number;taskId:number}){
 const [open,setOpen]=useState(false)
 const query=useInfiniteQuery({queryKey:['task-run-history',projectId,taskId],initialPageParam:null as string|null,queryFn:({pageParam})=>taskRunHistory(projectId,taskId,pageParam),getNextPageParam:page=>page.next_before_seq??undefined,enabled:open,retry:false,refetchInterval:open?10000:false})
 const pages=query.data?.pages.filter(page=>page.project_id===projectId&&page.task_id===taskId)??[]
 const items=Array.from(new Map(pages.flatMap(page=>page.items.filter(run=>run.project_id===projectId&&run.task_id===taskId)).map(run=>[run.run_id,run])).values())
 return <details className={panel} onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary className="min-h-11 cursor-pointer font-medium">Historial de ejecuciones</summary>
  {open&&query.isPending&&<p role="status">Consultando el historial…</p>}
  {query.error&&<div role="alert"><p>No se pudo consultar el historial. {items.length>0?'Se conserva la última consulta correcta.':''}</p><button className={button} onClick={()=>query.refetch()}>Volver a consultar historial</button></div>}
  {query.isSuccess&&items.length===0&&<p>Sin ejecuciones registradas.</p>}
  {pages[0]&&<p>{items.length} de {pages[0].total} ejecuciones guardadas. Los controles de trabajo siguen vinculados a la ejecución actual.</p>}
  <ul className="space-y-3">{items.map(run=><li key={run.run_id} className="space-y-2 border-t border-[var(--work-line)] pt-2">
   <p>{presentRun(run.status).title} · contexto {run.context_version}</p>
   <p className="whitespace-pre-wrap break-words">{run.prompt}</p>
   <RunAttempts projectId={projectId} runId={run.run_id}/>
   <RunInputRecord projectId={projectId} runId={run.run_id}/>
   <RunCommands projectId={projectId} runId={run.run_id}/>
  </li>)}</ul>
  {query.hasNextPage&&<button className={button} disabled={query.isFetching} onClick={()=>query.fetchNextPage()}>Cargar ejecuciones anteriores</button>}
 </details>
}
