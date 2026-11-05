/** Owner inspection of uncertain local publication, retaining its original attempt and recovery key. @module */
import {useEffect,useState} from 'react'
import {useMutation,useQueryClient} from '@tanstack/react-query'
import {ApiError} from '../../api/client'
import type {CodeResultState} from '../../api/codeResults'
import {preparePublicationRecovery,publicationRecoveryActions,sendPublicationRecovery,type PublicationRecoveryAction} from '../../api/publicationRecovery'

/** Explain uncertainty and request readonly evidence without offering another publication effect. */
export function CodePublicationRecovery({data,readOnly,onPending}:{data:CodeResultState;readOnly:boolean;onPending?:(run:string|null)=>void}) {
 const client=useQueryClient(),[saved,setSaved]=useState<PublicationRecoveryAction|null>(null),[ready,setReady]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
 useEffect(()=>{try {setSaved(publicationRecoveryActions.load(sessionStorage,data.project_id,data.task_id,data.run_id));setReady(true)}catch(e){setError(e instanceof Error?e.message:'No se pudo recuperar la consulta original.')}},[data.project_id,data.task_id,data.run_id])
 const send=useMutation({mutationFn:sendPublicationRecovery,onSuccess:(result,action)=>{
  try {publicationRecoveryActions.clear(sessionStorage,action);setSaved(null);onPending?.(null);setNotice(result.observed.state==='published'?'Se comprobó la publicación original.'+(result.observed.target_current?'':' La rama cambió después.'):result.observed.state==='not_applied'?'Se comprobó que la publicación original no se aplicó.':'La evidencia todavía no permite confirmar el resultado. Puedes volver a consultarlo.')}catch(e){setError(e instanceof Error?e.message:'No se pudo cerrar la consulta local.')}
  client.invalidateQueries({queryKey:['code-result',data.project_id,data.run_id]});client.invalidateQueries({queryKey:['task-workspace',data.project_id,data.task_id]})
 }})
 const pub=data.publication,canObserve=!pub.result && ['reconciling','cancelling','superseded','cancelled'].includes(pub.status??'') && !!pub.attempt_id && !!pub.run_id && !!pub.fence
 if(!canObserve && !saved && !error && !notice)return null
 /** Persist the original fenced attempt before any request; retry only that saved command. */
 function submit(){try {let action=saved;if(!action){if(!canObserve)throw new Error('Consulta el intento incierto antes de comprobarlo.');action=preparePublicationRecovery(data.project_id,data.task_id,data.run_id,pub.run_id!,pub.attempt_id!,pub.fence!);publicationRecoveryActions.save(sessionStorage,action);setSaved(action);onPending?.(data.run_id)}send.mutate(action)}catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la consulta.')}}
 const rejected=send.error instanceof ApiError && [409,422].includes(send.error.status)
 return <section className="space-y-3 border-t border-[var(--work-line)] pt-3 text-sm" aria-label="Comprobar publicación original">
  <p className="text-[var(--work-muted)]">No sabemos todavía si se aplicó la publicación. Por ejemplo, Git pudo crear la rama antes de perderse la respuesta. Esta consulta comprueba el recibo original; no vuelve a publicar.</p>
  {(canObserve||saved)&&<button className="rounded-md border border-[var(--work-line)] px-3 py-2 disabled:opacity-50" disabled={!ready||readOnly||send.isPending||!!error} onClick={submit}>{send.isPending?'Comprobando…':saved?'Reenviar la misma consulta':'Comprobar qué ocurrió'}</button>}
  {send.error&&<p role="alert">{rejected?'El intento cambió o no puede comprobarse ahora. Consulta su estado antes de preparar otra consulta.':'No se confirmó la consulta. Conservamos el intento y la solicitud originales para reenviarlos.'}</p>}
  {rejected&&saved&&<button className="rounded-md border border-[var(--work-line)] px-3 py-2" onClick={()=>{try{publicationRecoveryActions.clear(sessionStorage,saved);setSaved(null);onPending?.(null);send.reset();client.invalidateQueries({queryKey:['code-result',data.project_id,data.run_id]})}catch(e){setError(e instanceof Error?e.message:'No se pudo cerrar la solicitud rechazada.')}}}>Descartar esta consulta rechazada</button>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>
}
