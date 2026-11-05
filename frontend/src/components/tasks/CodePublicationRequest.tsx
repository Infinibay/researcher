/** Owner publication of an accepted exact version to an explicit new local branch. @module */
import { useEffect,useState } from 'react'
import { useMutation,useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { codePublicationActions,prepareCodePublication,sendCodePublication,type CodePublicationAction } from '../../api/codePublications'
import type { CodeResultState } from '../../api/codeResults'

const buttonClass='rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--work-accent)]'

/** Save once before effects; an uncertain response keeps the same accepted candidate, destination and request key. */
export function CodePublicationRequest({data,available,readOnly,onPending}:{data:CodeResultState;available:boolean;readOnly:boolean;onPending?:(run:string|null)=>void}) {
  const client=useQueryClient()
  const [ready,setReady]=useState(typeof window==='undefined')
  const [saved,setSaved]=useState<CodePublicationAction|null>(null)
  const [branch,setBranch]=useState(`researcher/task-${data.task_id}-${data.candidate.head_sha.slice(0,8)}`)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  useEffect(()=>{try {setSaved(codePublicationActions.load(window.sessionStorage,data.project_id,data.task_id,data.run_id));setReady(true)} catch(issue) {setError(issue instanceof Error?issue.message:'No se pudo recuperar la publicación pendiente.')}},[data.project_id,data.task_id,data.run_id])
  const send=useMutation({mutationFn:sendCodePublication,onSuccess:(_receipt,action)=>{
    try {codePublicationActions.clear(window.sessionStorage,action);setSaved(null);onPending?.(null);setNotice('Publicación registrada. Consulta el estado para ver su resultado.')}
    catch(issue) {setError(issue instanceof Error?issue.message:'No se pudo cerrar la solicitud local.')}
    client.invalidateQueries({queryKey:['task-workspace',data.project_id,data.task_id]})
    client.invalidateQueries({queryKey:['code-result',data.project_id,data.run_id]})
  }})
  const canPublish=available && data.acceptance_current && !!data.acceptance && !data.publication.run_id && !notice
  if(!canPublish && !saved && !error && !notice) return null
  /** Persist the exact accepted observation before the first network call; retries never refresh it silently. */
  function submit() {
    try {
      let action=saved
      if(!action) {
        if(!canPublish || !data.acceptance || !data.subject_sha256) throw new Error('Consulta una aceptación vigente antes de publicar.')
        action=prepareCodePublication(data.project_id,data.task_id,data.run_id,{acceptanceKey:data.acceptance.operation_key,attemptId:data.candidate.attempt_id,contextVersion:data.candidate.context_version,subjectSha:data.subject_sha256,reviewSha:data.review_sha256,targetRef:'refs/heads/'+branch.trim()})
        codePublicationActions.save(window.sessionStorage,action);setSaved(action);onPending?.(action.runId)
      }
      send.mutate(action)
    } catch(issue) {setError(issue instanceof Error?issue.message:'No se pudo guardar la solicitud de publicación.')}
  }
  const rejected=send.error instanceof ApiError && [409,422].includes(send.error.status)
  return <section className="space-y-3 border-t border-[var(--work-line)] pt-3 text-sm" aria-label="Publicar versión aceptada">
    <p className="text-[var(--work-muted)]">Crea una rama local con esta versión aceptada. Los archivos de la rama abierta siguen en su versión actual; push y PR son pasos posteriores.</p>
    {(canPublish || saved) && <form className="space-y-3" onSubmit={event=>{event.preventDefault();submit()}}>
      <label className="block space-y-1 text-[var(--work-ink)]"><span>Nombre de la rama nueva</span><input className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" maxLength={220} value={saved?saved.body.target_ref.slice('refs/heads/'.length):branch} readOnly={!!saved || send.isPending || readOnly} onChange={event=>{setBranch(event.target.value);setError('')}}/></label>
      <p className="text-[var(--work-muted)]">Se creará si aún no existe. El sistema comprobará la versión y el destino antes de publicar.</p>
      {saved && <p className="text-[var(--work-muted)]">Hay un envío pendiente de confirmar. Reenviarlo conserva la versión y la rama originales.</p>}
      <button className={buttonClass} disabled={!ready || readOnly || send.isPending || !!error || (!saved && (!canPublish || !branch.trim()))}>{send.isPending?'Registrando publicación…':saved?'Reenviar la misma publicación':'Publicar en una rama nueva'}</button>
    </form>}
    {send.error && <p role="alert" className="text-[var(--work-error)]">{rejected?'El servidor rechazó la solicitud. Consulta el estado antes de preparar otra.':'No se confirmó el envío. Conservamos la solicitud original; reenviarla consulta su recibo sin publicar otra vez.'}</p>}
    {rejected && saved && <button className={buttonClass} onClick={()=>{try {codePublicationActions.clear(window.sessionStorage,saved);setSaved(null);onPending?.(null);send.reset()} catch(issue) {setError(issue instanceof Error?issue.message:'No se pudo cerrar la solicitud rechazada.')}}}>Descartar esta solicitud rechazada</button>}
    {error && <p role="alert" className="text-[var(--work-error)]">{error}</p>}
    {notice && <p role="status" className="text-[var(--work-muted)]">{notice}</p>}
  </section>
}
