/** Review corrected graph premises before a distinct owner adoption, within the selected Tasks visual system. @module */
import {useEffect,useState} from 'react'
import {useMutation,useQuery} from '@tanstack/react-query'
import {ApiError} from '../../api/client'
import {graphActions,graphRevisionState,prepareGraphAction,sendGraphAction,type GraphAction} from '../../api/planReauthorizations'

const button='rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--work-accent)]'

/** Keep original plan, current metadata, known effects and owner adoption distinct; reloading never replaces an unresolved decision with a fresh graph. */
export function GraphReauthorization({projectId,taskId,runId,executionId,readOnly,onPending,onResolved}:{projectId:number;taskId:number;runId:string;executionId:string;readOnly:boolean;onPending:()=>void;onResolved:()=>void}){
 const [opened,setOpened]=useState(false),[ready,setReady]=useState(false),[saved,setSaved]=useState<GraphAction|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState('')
 useEffect(()=>{try{const a=graphActions.load(sessionStorage,projectId,taskId,runId);setSaved(a);if(a)setOpened(true);setReady(true)}catch(e){setError(e instanceof Error?e.message:'No se pudo recuperar la decisión original.')}},[projectId,taskId,runId])
 const preview=useQuery({queryKey:['graph-revision',projectId,executionId],queryFn:()=>graphRevisionState(projectId,runId,executionId),enabled:opened,retry:false})
 const mutation=useMutation({mutationFn:sendGraphAction,onSuccess:(r,a)=>{try{graphActions.clear(sessionStorage,a);setSaved(null);setOpened(false);onResolved();setNotice(`Revisión ${r.authorization_revision} adoptada. El despacho sigue pausado. Consulta la ejecución y decide después si reanudar esta revisión.`)}catch(e){setError(e instanceof Error?e.message:'No se pudo cerrar la solicitud local.')}}})
 /** Save exact observed graph and expected delivery identities before authorizing any replacement work. */
 function submit(){try{let a=saved;if(!a){if(!preview.data)throw new Error('Consulta primero los cambios del plan.');a=prepareGraphAction(projectId,taskId,runId,executionId,preview.data);graphActions.save(sessionStorage,a);setSaved(a);onPending()}mutation.mutate(a)}catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la decisión original.')}}
 const data=preview.data,snapshot=data?.snapshot,rejected=mutation.error instanceof ApiError&&[409,422].includes(mutation.error.status)
 /** Render prerequisite references as task names and ordinary values as literal attributed metadata. */
 function describe(value:unknown):string {if(value===null||value===undefined||value==='')return 'Sin contenido registrado';return Array.isArray(value)?value.map(id=>snapshot?.corrected_tasks.find(t=>t.task_id===id)?.task.title??String(id)).join(', '):String(value)}
 const fields:Record<string,string>={title:'Título',description:'Condiciones del trabajo',acceptance_criteria:'Resultado comprobable',depends_on:'Prerrequisitos',type:'Tipo de trabajo',priority:'Prioridad'}
 return <section aria-label="Revisión del grafo corregido" className="space-y-3 border-t border-[var(--work-line)] pt-3">
  <h5 className="font-medium">Revisar las condiciones actuales del plan</h5>
  <p className="text-[var(--work-muted)]">Un cambio de contexto necesita una decisión nueva. Por ejemplo, corregir el tamaño de una muestra puede cambiar qué debe investigar una tarea. Aquí puedes revisar el grafo actual y su historia antes de adoptarlo; el plan original se conserva.</p>
  <button className={button} disabled={!ready||readOnly||!!error||mutation.isPending||preview.isFetching} onClick={()=>{setOpened(true);if(opened)preview.refetch()}}>Revisar cambios del plan</button>
  {preview.isFetching&&<p role="status">Consultando condiciones y cierre de los intentos…</p>}
  {preview.error&&<p role="alert">No se pudo consultar la revisión. {preview.error.message}</p>}
  {opened&&snapshot&&<div className="space-y-3">
   <p>{snapshot.changes.length} cambio(s) frente a la decisión anterior. Se conservan {snapshot.retained_results.length} resultado(s) aceptado(s) y vigentes. Las otras {snapshot.corrected_tasks.length-snapshot.retained_results.length} tarea(s) necesitan una entrega nueva.</p>
   <p className="text-[var(--work-muted)]">Estos textos son registros actuales y correcciones atribuidas. Adoptarlos establece las condiciones del trabajo; no significa que el agente original los haya propuesto ni que sus supuestos estén demostrados.</p>
   <div role="group" className="space-y-3" aria-label="Diferencias de las condiciones del plan">{snapshot.changes.map((change,index)=><div key={index} className="space-y-2 rounded-md border border-[var(--work-line)] p-3"><p className="font-medium">{change.project?'Objetivo del proyecto':snapshot.corrected_tasks.find(t=>t.task_id===change.task_id)?.task.title??`Tarea ${change.task_id}`}</p>{change.project?<><p>Antes: {describe(change.project.before.description)}</p><p>Ahora: {describe(change.project.after.description)}</p>{change.project.before.name!==change.project.after.name&&<p>Nombre: {change.project.before.name} → {change.project.after.name}</p>}</>:Object.entries(change.changes??{}).filter(([key])=>key in fields).map(([key,value])=><div key={key} className="space-y-1"><p className="font-medium">{fields[key]}</p><p className="text-[var(--work-muted)]">Antes: {describe(value.before)}</p><p>Ahora: {describe(value.after)}</p></div>)}{!change.project&&!Object.keys(change.changes??{}).some(key=>key in fields)&&<p className="text-[var(--work-muted)]">Esta tarea necesita revisar su contexto por otra corrección del grafo; su texto no cambió.</p>}</div>)}</div>
   <ol className="space-y-2">{snapshot.corrected_tasks.map(t=><li key={t.task_id} className="space-y-1 rounded-md border border-[var(--work-line)] p-3"><p className="font-medium">{t.task.title}</p><p>{t.task.description}</p><p className="text-[var(--work-muted)]">Resultado comprobable: {t.task.acceptance_criteria}</p><p>{snapshot.retained_results.some(r=>r.task_id===t.task_id)?'Conserva su resultado aceptado vigente.':'Nueva entrega bajo esta revisión.'} {t.depends_on.length?'Espera resultados aceptados de: '+t.depends_on.map(id=>snapshot.corrected_tasks.find(item=>item.task_id===id)?.task.title??id).join(', '):'Sin prerrequisitos en este grafo.'}</p></li>)}</ol>
   <details><summary className="cursor-pointer">Ver el registro completo de atribuciones y efectos</summary><pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(snapshot,null,2)}</pre></details>
   <p className="text-[var(--work-muted)]">El consumo y los efectos anteriores permanecen registrados. Las propuestas que se sustituyan quedan como historia. Esta decisión no incorpora archivos privados de candidatos, no acepta resultados nuevos y mantiene el despacho pausado.</p>
  </div>}
  {opened&&data&&!data.eligible&&!saved&&<p>Antes de adoptar el grafo, pausa el despacho y comprueba el cierre y el contexto de los intentos anteriores. {data.blocked_reason}</p>}
  {((opened&&data?.eligible)||saved)&&<button className={button} disabled={!ready||readOnly||!!error||mutation.isPending||(!saved&&preview.isFetching)} onClick={submit}>{saved?'Reenviar la misma adopción del grafo':'Adoptar este grafo y mantenerlo pausado'}</button>}
  {mutation.error&&<p role="alert">{rejected?'La adopción fue rechazada; consulta las condiciones actuales.':'No se confirmó la adopción. Conservamos el grafo y la solicitud originales para recuperar su recibo sin duplicar entregas.'}</p>}
  {rejected&&saved&&<button className={button} onClick={()=>{try{graphActions.clear(sessionStorage,saved);setSaved(null);onResolved();mutation.reset();preview.refetch()}catch(e){setError(e instanceof Error?e.message:'No se pudo retirar la decisión rechazada.')}}}>Descartar adopción rechazada</button>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>
}
