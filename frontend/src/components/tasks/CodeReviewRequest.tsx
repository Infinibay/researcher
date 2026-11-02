/** Human-controlled independent review with durable original scope and explicit recovery after uncertain delivery. @module */
import { useEffect,useId,useState } from 'react'
import { useMutation,useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { codeReviewActions,prepareCodeReview,sendCodeReview,type CodeReviewAction } from '../../api/codeReviews'
import type { CodeResultState } from '../../api/codeResults'

const buttonClass='rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--work-accent)]'

/** Never replace a saved observation with a refreshed candidate, even after context correction or a completed review. */
export function CodeReviewRequest({data,available,readOnly,onPending}:{data:CodeResultState;available:boolean;readOnly:boolean;onPending?:(run:string|null)=>void}) {
  const client=useQueryClient()
  const [saved,setSaved]=useState<CodeReviewAction|null>(null)
  const [ready,setReady]=useState(typeof window==='undefined')
  const [request,setRequest]=useState('Revisa esta versión contra la petición original y sus requisitos. Comprueba el código y los resultados registrados, cita evidencia concreta y explica qué sigue sin comprobarse.')
  const [storageError,setStorageError]=useState('')
  const [notice,setNotice]=useState('')
  const [rejected,setRejected]=useState(false)
  const labelId=useId()
  useEffect(()=>{
    try {setSaved(codeReviewActions.load(window.sessionStorage,data.project_id,data.task_id,data.run_id));setReady(true)}
    catch(error) {setStorageError(error instanceof Error?error.message:'No se pudo recuperar la revisión pendiente.')}
  },[data.project_id,data.task_id,data.run_id])
  const send=useMutation({mutationFn:sendCodeReview,onSuccess:(_receipt,action)=>{
    try {codeReviewActions.clear(window.sessionStorage,action);setSaved(null);onPending?.(null);setNotice('Revisión solicitada. Consulta el estado para ver su resultado; la solicitud no acredita una revisión completada.')}
    catch(error) {setStorageError(error instanceof Error?error.message:'No se pudo cerrar la solicitud local.')}
    client.invalidateQueries({queryKey:['task-workspace',data.project_id,data.task_id]})
    client.invalidateQueries({queryKey:['code-result',data.project_id,data.run_id]})
  },onError:error=>{if(error instanceof ApiError && [409,422].includes(error.status)) setRejected(true)}})
  const canRequest=available && data.candidate_current && !!data.packet && !!data.subject_sha256 && !data.review && !data.acceptance && !notice
  if(!canRequest && !saved && !storageError && !notice) return null

  /** Save the complete body before network effects; all recovery sends preserve its exact nonce and evidence. */
  function submit() {
    try {
      let action=saved
      if(!action) {
        if(!canRequest || !data.subject_sha256) throw new Error('Consulta un candidato actual antes de solicitar la revisión.')
        action=prepareCodeReview(data.project_id,data.task_id,data.run_id,{attemptId:data.candidate.attempt_id,contextVersion:data.candidate.context_version,subjectSha:data.subject_sha256,request:request.trim()})
        codeReviewActions.save(window.sessionStorage,action)
        setSaved(action)
        onPending?.(action.runId)
      }
      send.mutate(action)
    } catch(error) {setStorageError(error instanceof Error?error.message:'No se pudo guardar la solicitud original.')}
  }
  const tooLong=!saved && new TextEncoder().encode(request.trim()).length>12000
  return <div className="space-y-3 border-l-2 border-[var(--work-line)] pl-3 text-sm">
    <p className="text-[var(--work-muted)]">La revisión encarga a otro agente comprobar esta versión contra tu petición original. Solicitarla no acepta ni publica el código.</p>
    {(canRequest || saved) && <form className="space-y-3" onSubmit={event=>{event.preventDefault();submit()}}>
      <label className="block space-y-1 text-[var(--work-ink)]"><span>Qué debe comprobar el revisor</span><textarea className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" rows={3} maxLength={12000} value={saved?saved.body.request:request} readOnly={!!saved || send.isPending || readOnly} aria-invalid={tooLong||undefined} aria-describedby={tooLong?labelId:undefined} onChange={event=>setRequest(event.target.value)}/></label>
      {tooLong && <p id={labelId} role="alert" className="text-[var(--work-error)]">Acorta la petición antes de solicitar la revisión.</p>}
      {saved && <p className="text-[var(--work-muted)]">Envío pendiente de confirmar para el contexto {saved.body.context_version}. Reenviarlo conserva la versión y la petición originales.</p>}
      <button className={buttonClass} disabled={!ready || readOnly || send.isPending || !!storageError || tooLong || (!saved && (!canRequest || !request.trim()))}>{send.isPending?'Solicitando revisión…':saved?'Reenviar la misma revisión':'Solicitar revisión independiente'}</button>
    </form>}
    {send.error && <p role="alert" className="text-[var(--work-error)]">{rejected?'El servidor rechazó la solicitud. Consulta el estado antes de preparar otra.':'No se confirmó el envío. Conservamos la solicitud original para reenviarla y consultar su recibo.'}</p>}
    {rejected && saved && <button className={buttonClass} onClick={()=>{try {codeReviewActions.clear(window.sessionStorage,saved);setSaved(null);onPending?.(null);setRejected(false);send.reset()} catch(error) {setStorageError(error instanceof Error?error.message:'No se pudo cerrar la solicitud rechazada.')}}}>Descartar esta revisión rechazada</button>}
    {storageError && <p role="alert" className="text-[var(--work-error)]">{storageError}</p>}
    {notice && <p role="status" className="text-[var(--work-muted)]">{notice}</p>}
  </div>
}
