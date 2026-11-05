/** Owner-readable closed-attempt history and explicit successor permission within the Tasks design. @module */
import {useEffect,useState} from 'react'
import {useMutation,useQuery} from '@tanstack/react-query'
import {ApiError} from '../../api/client'
import {continuationActions,continuationState,prepareContinuationAction,sendContinuationAction,type ContinuationAction} from '../../api/planContinuations'
import type {WorkDelivery} from '../../api/planExecution'

const button='rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--work-accent)]'

/** Require inspection and a separate saved owner decision; reloading or losing a reply never creates another successor. */
export function DeliveryContinuation({projectId,taskId,runId,executionId,deliveries,readOnly,onPending,onResolved}:{projectId:number;taskId:number;runId:string;executionId:string;deliveries:WorkDelivery[];readOnly:boolean;onPending:()=>void;onResolved:()=>void}){
 const [saved,setSaved]=useState<ContinuationAction|null>(null),[selected,setSelected]=useState(''),[ready,setReady]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
 useEffect(()=>{try{const a=continuationActions.load(sessionStorage,projectId,taskId,runId);setSaved(a);if(a)setSelected(a.deliveryId);setReady(true)}catch(e){setError(e instanceof Error?e.message:'No se pudo recuperar la decisión original.')}},[projectId,taskId,runId])
 const preview=useQuery({queryKey:['plan-continuation',projectId,executionId,selected],queryFn:()=>continuationState(projectId,executionId,selected),enabled:!!selected,retry:false})
 const mutation=useMutation({mutationFn:sendContinuationAction,onSuccess:(_receipt,action)=>{try{continuationActions.clear(sessionStorage,action);setSaved(null);setSelected('');onResolved();setNotice('Sucesora autorizada. Conservamos el intento anterior. Cada resultado sigue necesitando revisión y aceptación; el plan pausado sigue pausado.')}catch(e){setError(e instanceof Error?e.message:'No se pudo cerrar la solicitud local.')}}})
 /** Persist the exact evidence offered for inspection; a retry always uses the existing packet. */
 function submit(){try{let a=saved;if(!a){const p=preview.data;if(!p?.eligible||!p.snapshot||!p.snapshot_sha256||p.delivery_id!==selected)throw new Error('Consulta primero el cierre y los efectos del intento.');a=prepareContinuationAction(projectId,taskId,runId,executionId,selected,p.snapshot.previous_run.run_id,p.snapshot_sha256);continuationActions.save(sessionStorage,a);setSaved(a);onPending()}mutation.mutate(a)}catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la decisión.')}}
 const candidates=deliveries.filter(d=>d.current&&d.run_id&&['failed','cancelled','superseded'].includes(d.status)),data=preview.data,snapshot=data?.snapshot,rejected=mutation.error instanceof ApiError&&[409,422].includes(mutation.error.status)
 if(!candidates.length&&!saved&&!notice&&!error)return null
 return <section aria-label="Continuar una entrega interrumpida" className="space-y-3 border-t border-[var(--work-line)] pt-3">
  <h5 className="font-medium">Continuar una entrega interrumpida</h5>
  <p className="text-[var(--work-muted)]">Una sucesora es un turno nuevo con tu permiso. Por ejemplo, si una investigación se detuvo después de guardar una fuente, esa fuente permanece: detener el trabajo no deshace lo que ya guardó.</p>
  {!saved&&<div className="flex flex-wrap gap-2">{candidates.map(d=><button key={d.delivery_id} className={button} disabled={!ready||readOnly||!!error||mutation.isPending} onClick={()=>{setSelected(d.delivery_id);mutation.reset()}}>Consultar continuación de tarea {d.task_id}</button>)}</div>}
  {preview.isFetching&&<p role="status">Consultando el intento original…</p>}
  {preview.error&&<p role="alert">No se pudo consultar la entrega. {preview.error.message}</p>}
  {snapshot&&<div className="space-y-2 rounded-md border border-[var(--work-line)] p-3">
   <p>El intento anterior está cerrado ({snapshot.previous_run.status}). Conservamos {snapshot.attempts.reduce((n,a)=>n+a.effects.length,0)} efecto(s) registrado(s) y {snapshot.attempts.reduce((n,a)=>n+a.jobs.length,0)} ejecución(es) de comandos.</p>
   {snapshot.attempts.map(a=><p key={a.attempt_id} className="text-[var(--work-muted)]">Consumo anterior: {a.inference?(a.inference.observed_tokens===null?'sin confirmar; la reserva sigue contabilizada':`${a.inference.observed_tokens} tokens registrados`):'sin despacho de inferencia registrado'}. No se reinicia el presupuesto.</p>)}
   {snapshot.candidate&&<p>Existe un candidato parcial ({snapshot.candidate.state}). Sus archivos privados se conservan como historia; esta decisión no los incorpora a la nueva ejecución.</p>}
   <p className="text-[var(--work-muted)]">Los resultados parciales no están aceptados. Un comando sin resultado confirmado sigue siendo incierto; su cierre no permite asumir que no tuvo efectos. {data?.dispatch_status==='paused'?'El despacho está pausado y seguirá pausado.':'El despacho está activo: la sucesora podrá iniciarse al quedar disponible la capacidad.'}</p>
   <details><summary className="cursor-pointer">Ver evidencia original y limitaciones</summary><pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(snapshot,null,2)}</pre></details>
  </div>}
  {data&&!data.eligible&&!saved&&<p>Esta entrega todavía no admite una sucesora. Consulta el cierre, el contexto del plan y cualquier entrega posterior. {data.blocked_reason}</p>}
  {(data?.eligible||saved)&&<button className={button} disabled={!ready||readOnly||!!error||mutation.isPending} onClick={submit}>{saved?'Reenviar la misma autorización de sucesora':'Autorizar un turno sucesor con esta evidencia'}</button>}
  {mutation.error&&<p role="alert">{rejected?'La decisión fue rechazada; consulta la evidencia actual.':'No se confirmó la decisión. Conservamos la misma solicitud para recuperar su recibo sin crear otra sucesora.'}</p>}
  {rejected&&saved&&<button className={button} onClick={()=>{try{continuationActions.clear(sessionStorage,saved);setSaved(null);onResolved();mutation.reset();preview.refetch()}catch(e){setError(e instanceof Error?e.message:'No se pudo retirar la decisión rechazada.')}}}>Descartar autorización rechazada</button>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>
}
