/** Retained work is historical data: quarantine, verified archive, removal and new-copy recovery remain explicit owner choices. @module */
import { useEffect, useState } from 'react'
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '../../api/client'
import { clearRetentionAction, loadRetentionAction, readRetentionAction, saveRetentionAction, sendRetentionAction, type RetainedWork as Copy, type RetentionAction, type RetentionOperation } from '../../api/workspaceRetention'
import { reportTimestamp } from '../reports/presentation'
import '../../styles/retention.css'

const labels:Record<Copy['state'],string>={available:'Copia conservada',quarantined:'En cuarentena; archivo pendiente',retained:'Archivo de recuperación verificado',removing:'Borrado pendiente de comprobar',removed:'Copia original eliminada; archivo conservado'}
const actions:Record<RetentionOperation['kind'],string>={archive:'Archivo de recuperación',remove:'Borrado de la copia original',restore:'Recuperación en carpeta nueva'}

/** Explain effects and retain unresolved requests across reload; only owner clicks perform mutations. */
export function RetainedWork({projectId,onClose}:{projectId:number;onClose:()=>void}){
 const client=useQueryClient(),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
 const [saved,setSaved]=useState<{action:RetentionAction|null;error:string}>(()=>{try{return {action:loadRetentionAction(sessionStorage,projectId),error:''}}catch(e){return {action:null,error:e instanceof Error?e.message:'No se pudo leer la solicitud guardada.'}}})
 const copies=useInfiniteQuery({queryKey:['retained-work',projectId],initialPageParam:0,queryFn:({pageParam})=>fetchApi<Copy[]>(`/api/projects/${projectId}/retained-work?offset=${pageParam}&limit=100`),getNextPageParam:(last,all)=>last.length===100?all.length*100:undefined,retry:false})
 const history=useInfiniteQuery({queryKey:['retention-operations',projectId],initialPageParam:0,queryFn:({pageParam})=>fetchApi<RetentionOperation[]>(`/api/projects/${projectId}/retained-work/operations?offset=${pageParam}&limit=100`),getNextPageParam:(last,all)=>last.length===100?all.length*100:undefined,retry:false,refetchInterval:query=>query.state.data?.pages.flat().some(row=>row.state==='pending'&&!row.issue)?2000:false})
 const rows=copies.data?.pages.flat().filter(row=>row.project_id===projectId)??[],operations=history.data?.pages.flat().filter(row=>row.project_id===projectId)??[]
 useEffect(()=>{if(history.dataUpdatedAt)client.invalidateQueries({queryKey:['retained-work',projectId]})},[client,projectId,history.dataUpdatedAt])
 /** Refresh documentary state without replaying a pending mutation. */
 function refresh(){client.invalidateQueries({queryKey:['retained-work',projectId]});client.invalidateQueries({queryKey:['retention-operations',projectId]})}
 /** Preserve a failed response as uncertain, and clear storage only after an exact receipt is observed. */
 async function resolve(action:RetentionAction,readOnly=false){
  setBusy(true);setError('');setNotice('')
  try{const result=await(readOnly?readRetentionAction(action):sendRetentionAction(action));clearRetentionAction(sessionStorage,action);setSaved({action:null,error:''});setNotice(result.state==='completed'?'Resultado original comprobado.':'Solicitud registrada. Consulta su resultado en el historial.');refresh()}
  catch(e){setError(e instanceof Error?e.message:'No se pudo confirmar la operación.')}
  finally{setBusy(false)}
 }
 /** Save an original packet before sending it; unresolved prior intent must be checked first. */
 function act(copy:Copy,kind:RetentionOperation['kind'],days?:number){
  if(saved.action||saved.error)return
  const action:RetentionAction={projectId,attemptId:copy.attempt_id,kind,body:{operation_key:crypto.randomUUID(),...(kind==='archive'?{retention_days:days,acknowledge_unavailability:true as const}:{archive_sha256:copy.archive_sha256!})}}
  try{saveRetentionAction(sessionStorage,action);setSaved({action,error:''});void resolve(action)}catch(e){setError(e instanceof Error?e.message:'No se pudo conservar la solicitud; no se envió.')}
 }
 /** Continue only the explicitly selected historical operation; the backend retains its original archive and destination. */
 async function reconcile(operation:RetentionOperation){setBusy(true);setError('');try{const result=await fetchApi<RetentionOperation>(`/api/projects/${projectId}/retained-work/operations/${encodeURIComponent(operation.operation_key)}/reconcile`,{method:'POST'});if(result.project_id!==projectId||result.operation_key!==operation.operation_key||result.attempt_id!==operation.attempt_id)throw new Error('La respuesta no corresponde a la operación elegida.');refresh()}catch(e){setError(e instanceof Error?e.message:'No se pudo comprobar la operación.')}finally{setBusy(false)}}
 return <section className="retention-panel" aria-labelledby="retained-work-title">
  <header><div><p className="repo-muted">Conservación del proyecto</p><h2 id="retained-work-title">Copias de trabajo</h2></div><button onClick={onClose}>Volver a fuentes</button></header>
  <p>Archivar conserva los cambios, incluidos los archivos nuevos e ignorados por Git. La cuarentena impide reutilizar esta copia para trabajar o publicar. Restaurar crea una carpeta nueva, sin reactivar agentes ni aceptar código.</p>
  <p className="repo-muted">Por ejemplo: un intento dejó cambios útiles sin publicar. Puedes guardarlos, retirar después la copia original y recuperar los archivos cuando los necesites.</p>
  <button disabled={busy||copies.isFetching||history.isFetching} onClick={refresh}>Actualizar copias e historial</button>
  {saved.error&&<p role="alert">{saved.error}</p>}
  {saved.action&&<aside className="retention-uncertain"><h3>Solicitud sin confirmar</h3><p>Conservamos la decisión original. Comprueba su resultado antes de crear otra.</p><button disabled={busy} onClick={()=>void resolve(saved.action!,true)}>Consultar solicitud original</button><button disabled={busy} onClick={()=>void resolve(saved.action!)}>Reenviar la misma solicitud</button></aside>}
  {(copies.isError||history.isError)&&<p role="alert">No pudimos consultar la conservación. No deducimos que las copias estén vacías o eliminadas. {copies.error?.message??history.error?.message}</p>}
  {copies.isPending&&<p role="status">Consultando copias conservadas…</p>}
  {rows.length===0&&!copies.isPending&&!copies.isError&&<p>Todavía no hay copias privadas de intentos registradas.</p>}
  <ul className="retention-copies">{rows.map(copy=><RetainedCopy key={copy.attempt_id} copy={copy} disabled={busy||Boolean(saved.action)||Boolean(saved.error)} act={act}/>)}</ul>
  {copies.hasNextPage&&<button disabled={copies.isFetchingNextPage} onClick={()=>copies.fetchNextPage()}>Ver copias anteriores</button>}
  <h3>Historial de conservación</h3><p className="repo-muted">Un resultado es histórico. Un error conserva la intención para comprobarla; no significa que no haya ocurrido ningún efecto.</p>
  <ul className="retention-history">{operations.map(operation=><li key={operation.operation_key}><strong>{actions[operation.kind]}</strong><p className="repo-muted">{rows.find(copy=>copy.attempt_id===operation.attempt_id)?.title??"Copia de trabajo"} · intento {operation.attempt_id.slice(0,12)}</p><p>{operation.state==='completed'?'Resultado confirmado':operation.state==='superseded'?'Sustituido por otra decisión; restos conservados':'Pendiente de comprobar'} · {reportTimestamp(operation.created_at).label}</p>{operation.issue&&<p role="alert">{operation.issue}</p>}{operation.state==='pending'&&<button disabled={busy} onClick={()=>void reconcile(operation)}>Comprobar operación original</button>}{typeof operation.receipt?.restored_path==='string'&&<p>Recuperado como datos en <code>{operation.receipt.restored_path}</code>. Puedes registrar esa carpeta como una fuente nueva.</p>}</li>)}</ul>
  {history.hasNextPage&&<button disabled={history.isFetchingNextPage} onClick={()=>history.fetchNextPage()}>Ver operaciones anteriores</button>}
  {error&&<p role="alert">{error} Consulta el historial antes de cambiar la solicitud.</p>}{notice&&<p role="status">{notice}</p>}
 </section>
}

/** Keep the retention period and acknowledgement bound to one visible attempt, never a similarly named task. */
function RetainedCopy({copy,disabled,act}:{copy:Copy;disabled:boolean;act:(copy:Copy,kind:RetentionOperation['kind'],days?:number)=>void}){
 const [days,setDays]=useState(7),[ack,setAck]=useState(false),until=copy.retain_until?reportTimestamp(copy.retain_until).label:null
 return <li><h3>{copy.title}</h3><p>{labels[copy.state]}</p><p className="repo-muted">Intento {copy.attempt_id.slice(0,12)} · {copy.bytes===null?'Tamaño sin comprobar':`${new Intl.NumberFormat('es').format(copy.bytes)} bytes archivados`}</p>
  {copy.changes?.state==='observed'?<p>{copy.changes.tracked} entradas modificadas · {copy.changes.untracked} nuevas · {copy.changes.ignored} ignoradas.</p>:copy.changes&&<p>Git no pudo clasificar los cambios. El archivo conserva todas las entradas inventariadas.</p>}
  {['available','quarantined','retained'].includes(copy.state)&&<div className="retention-choice"><label>Conservar al menos <input aria-label={`Días de retención para ${copy.title}`} type="number" min="1" max="3650" value={days} onChange={event=>setDays(Number(event.target.value))}/> días antes de permitir el borrado.</label><label><input type="checkbox" checked={ack} onChange={event=>setAck(event.target.checked)}/> Entiendo que esta copia quedará fuera del trabajo y la publicación; su historia se conserva.</label><button disabled={disabled||!ack||!Number.isInteger(days)||days<1||days>3650} onClick={()=>act(copy,'archive',days)}>{copy.archive_sha256?'Crear otro archivo de la copia actual':'Poner en cuarentena y archivar'}</button></div>}
  {until&&<p>Conservar hasta: {until}. El borrado siempre requiere otra acción explícita.</p>}
  {copy.archive_sha256&&<div className="retention-actions"><button disabled={disabled} onClick={()=>act(copy,'restore')}>Recuperar en carpeta nueva</button>{copy.state==='retained'&&<button disabled={disabled||Boolean(copy.retain_until&&Date.now()<copy.retain_until*1000)} onClick={()=>act(copy,'remove')}>Eliminar la copia original</button>}</div>}
 </li>
}
