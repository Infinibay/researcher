/** Owner workbench for exact captured code, review evidence and explicit acceptance. @module */
import { useEffect,useId,useState } from 'react'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../../api/client'
import { codeActions,codeResultDiff,codeResultState,matchesCodeReceipt,prepareCodeAcceptance,sendCodeAcceptance,type CodeAcceptanceAction } from '../../api/codeResults'
import type { RuntimeRun } from '../../api/runtime'
import { codeReviewActions } from '../../api/codeReviews'
import { CodeReviewRequest } from './CodeReviewRequest'

const buttonClass='rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--work-accent)]'
const verdicts:Record<string,string>={supported:'Respaldado por el revisor',needs_revision:'Requiere cambios',inconclusive:'Sin evidencia suficiente'}
const outcomes:Record<string,string>={passed:'Comprobación satisfactoria',failed:'Comprobación fallida',no_tests:'No se ejecutaron pruebas',skipped:'Comprobación omitida',infrastructure_error:'Falló la infraestructura',invalidated:'Resultado invalidado'}

/** Page the captured historical diff, checking identity and explicitly showing unread ranges. */
function CodeDiff({projectId,runId,sha}:{projectId:number;runId:string;sha:string}) {
  const [offset,setOffset]=useState(0)
  const query=useQuery({queryKey:['code-diff',projectId,runId,sha,offset],queryFn:()=>codeResultDiff(projectId,runId,sha,offset),retry:false})
  return <div className="mt-3 space-y-3">
    {query.isPending && <p role="status">Cargando el diff capturado…</p>}
    {query.error && <p role="alert">No se pudo recuperar este diff. {query.error.message}</p>}
    {query.data && <>
      <p className="text-xs text-[var(--work-muted)]">Captura guardada · caracteres {query.data.total_chars?offset+1:0}–{offset+query.data.content.length} de {query.data.total_chars}{query.data.next_offset!==null?' · queda contenido por leer':''}</p>
      <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md bg-[var(--work-soft)] p-3 text-xs text-[var(--work-ink)]">{query.data.content || 'No hay cambios en el diff capturado.'}</pre>
      <div className="flex flex-wrap gap-2"><button className={buttonClass} disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-12000))}>Anterior</button><button className={buttonClass} disabled={query.data.next_offset===null} onClick={()=>setOffset(query.data!.next_offset!)}>Siguiente</button></div>
    </>}
  </div>
}

/** Keep retries tied to the saved owner observation even when newer evidence arrives. */
export function CodeDelivery({projectId,taskId,runId,contextVersion,readOnly=false,reviewAvailable=false,onPending}:{projectId:number;taskId:number;runId:string;contextVersion:number;readOnly?:boolean;reviewAvailable?:boolean;onPending?:(run:string|null)=>void}) {
  const client=useQueryClient()
  const state=useQuery({queryKey:['code-result',projectId,runId,contextVersion],queryFn:()=>codeResultState(projectId,runId),retry:false})
  const [ready,setReady]=useState(typeof window==='undefined')
  const [saved,setSaved]=useState<CodeAcceptanceAction|null>(null)
  const [storageError,setStorageError]=useState('')
  const [notice,setNotice]=useState('')
  const [acknowledged,setAcknowledged]=useState(false)
  const [note,setNote]=useState('')
  const [showDiff,setShowDiff]=useState(false)
  const [rejected,setRejected]=useState(false)
  const noteErrorId=useId()
  const noteTooLong=!saved && new TextEncoder().encode(note.trim()).length>4000

  useEffect(()=>{
    try {setSaved(codeActions.load(window.sessionStorage,projectId,taskId,runId));setReady(true)}
    catch(error) {setStorageError(error instanceof Error?error.message:'No se pudo recuperar la decisión guardada.')}
  },[projectId,taskId,runId])
  useEffect(()=>{if(!saved) setAcknowledged(false)},[state.data?.subject_sha256,state.data?.review_sha256,saved])

  /** Clear only confirmed local history; an unavailable storage service cannot create another intent. */
  function resolved(action:CodeAcceptanceAction) {
    try {codeActions.clear(window.sessionStorage,action);setSaved(null);onPending?.(null);setNotice('Aceptación registrada. No se publicó código.');setRejected(false)}
    catch(error) {setStorageError(error instanceof Error?error.message:'La aceptación está guardada, pero no se pudo limpiar la solicitud local.')}
    client.invalidateQueries({queryKey:['task-workspace',projectId,taskId]})
    state.refetch()
  }
  const accept=useMutation({mutationFn:sendCodeAcceptance,onSuccess:(_receipt,action)=>resolved(action),onError:error=>{
    if(error instanceof ApiError && [409,422].includes(error.status)) {setRejected(true);state.refetch()}
  }})
  useEffect(()=>{
    const receipt=state.data?.acceptance
    if(saved && receipt && matchesCodeReceipt(receipt,saved)) resolved(saved)
  },[state.data?.acceptance,saved])

  /** Save before the first mutation; subsequent sends reuse the exact original packet. */
  function submit() {
    try {
      let action=saved
      if(!action) {
        const data=state.data
        if(!data?.eligible || !data.subject_sha256) throw new Error('Consulta un candidato actual y elegible antes de aceptarlo.')
        action=prepareCodeAcceptance(projectId,taskId,runId,{attemptId:data.candidate.attempt_id,contextVersion:data.candidate.context_version,subjectSha:data.subject_sha256,reviewSha:data.review_sha256,acknowledgeLimits:acknowledged,note:note.trim()||null})
        codeActions.save(window.sessionStorage,action)
        setSaved(action);onPending?.(runId)
      }
      accept.mutate(action)
    } catch(error) {setStorageError(error instanceof Error?error.message:'No se pudo guardar esta decisión antes de enviarla.')}
  }
  const data=state.data
  return <section className="min-w-0 space-y-4 rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-4" aria-label="Código entregado">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-medium text-[var(--work-ink)]">Código entregado</h3><p className="mt-1 text-sm text-[var(--work-muted)]">Revisar el código → aceptar una versión → publicar por separado.</p></div><button className={buttonClass} disabled={state.isFetching} onClick={()=>state.refetch()}>Consultar estado</button></div>
    {state.isPending && <p role="status">Recuperando candidato y revisión…</p>}
    {state.error && (state.error instanceof ApiError && state.error.status===404?<p className="text-sm text-[var(--work-muted)]">Esta ejecución todavía no tiene un candidato de código capturado.</p>:<p role="alert">No se pudo comprobar la entrega. {state.error.message}</p>)}
    {storageError && <p role="alert" className="text-sm text-[var(--work-error)]">{storageError}</p>}
    {data && <>
      <p className="text-sm text-[var(--work-ink)]">Versión <code>{data.candidate.head_sha.slice(0,12)}</code> · contexto {data.candidate.context_version}</p>
      <p className="text-sm text-[var(--work-muted)]">{data.publication.message}</p>
      {data.packet && <details><summary className="cursor-pointer text-sm text-[var(--work-ink)]">Petición original del propietario</summary><p className="mt-2 whitespace-pre-wrap text-sm text-[var(--work-muted)]">{data.packet.author_request.text}</p></details>}
      <details onToggle={event=>setShowDiff(event.currentTarget.open)}><summary className="cursor-pointer text-sm text-[var(--work-ink)]">Ver diff capturado</summary>{showDiff && <CodeDiff key={data.candidate.diff_sha256} projectId={projectId} runId={runId} sha={data.candidate.diff_sha256}/>}</details>
      <section className="space-y-2" aria-label="Comprobaciones del candidato"><h4 className="text-sm font-medium text-[var(--work-ink)]">Comprobaciones</h4>
        {data.packet?.checks.map(check=><div key={check.id} className="text-sm text-[var(--work-muted)]"><p>{check.result?.status==='passed' && check.spec.framework==='command'?'Comando terminado con éxito; no acredita por sí solo que se ejecutaran pruebas':check.result?outcomes[check.result.status]??'Resultado sin clasificar':'Resultado pendiente o desconocido'}</p><details><summary className="cursor-pointer">Qué se comprobó</summary><code className="mt-1 block break-all">{check.spec.argv.join(' ')}</code></details></div>)}
        {data.checks.limitations.map((item,index)=><p key={`${item.code}:${index}`} className="text-sm text-[var(--work-muted)]">{item.message}</p>)}
      </section>
      <section className="space-y-2" aria-label="Revisión independiente"><h4 className="text-sm font-medium text-[var(--work-ink)]">Revisión independiente</h4>
        <CodeReviewRequest data={data} available={reviewAvailable} readOnly={readOnly || !!saved} onPending={onPending}/>
        <p className="text-sm text-[var(--work-ink)]">{data.review?.proposal?verdicts[data.review.proposal.verdict]:'Sin decisión confirmada'}</p>
        {data.review?.proposal && data.review.state!=='confirmed' && <p className="text-sm text-[var(--work-muted)]">Propuesta sin confirmar; no acredita una revisión completada.</p>}
        {data.review && (!data.candidate_current || data.blockers.some(item=>item.code==='review_not_current')) && <p className="text-sm text-[var(--work-muted)]">Revisión histórica; no acredita el contexto actual.</p>}
        {data.review?.proposal && <><p className="whitespace-pre-wrap text-sm text-[var(--work-muted)]">{data.review.proposal.rationale}</p><details><summary className="cursor-pointer text-sm text-[var(--work-ink)]">Citas y límites del revisor</summary><div className="mt-3 space-y-3">{data.review.proposal.references.map((reference,index)=><div key={index}><p className="break-all text-xs text-[var(--work-muted)]">{reference.kind==='diff'?'Diff capturado':reference.path} · línea {reference.start_line}</p><pre className="mt-1 overflow-auto whitespace-pre-wrap break-words text-xs text-[var(--work-ink)]">{reference.quote}</pre></div>)}<ul className="list-disc space-y-1 pl-5 text-sm text-[var(--work-muted)]">{data.review.proposal.limitations.map((item,index)=><li key={index}>{item}</li>)}</ul></div></details></>}
      </section>
      {!!data.review_issues?.length && <section className="space-y-2 text-sm" aria-label="Revisiones anteriores del mismo candidato"><h4 className="font-medium text-[var(--work-ink)]">Revisiones anteriores del mismo candidato</h4>{data.review_issues.map(issue=><details key={issue.run_id}><summary className="cursor-pointer text-[var(--work-ink)]">{issue.blocking?'Objeción confirmada sin resolver':issue.state==='confirmed'?'Revisión anterior con límites':'Propuesta anterior sin confirmar'}</summary><p className="mt-2 text-[var(--work-muted)]">{issue.message}</p><p className="mt-1 whitespace-pre-wrap text-[var(--work-ink)]">{issue.rationale}</p><p className="mt-1 break-all font-mono text-xs text-[var(--work-muted)]">{issue.run_id}</p></details>)}</section>}
      {data.blockers.length>0 && <div className="space-y-2 border-l-2 border-[var(--work-line)] pl-3 text-sm text-[var(--work-ink)]"><p>No se puede aceptar esta versión todavía.</p><ul className="list-disc space-y-1 pl-5">{data.blockers.map((item,index)=><li key={`${item.code}:${index}`}>{item.message}</li>)}</ul></div>}
      {data.acceptance && <div role="status" className="space-y-1 text-sm text-[var(--work-ink)]"><p>{data.acceptance_current?'Aceptación registrada':'Aceptación histórica; ya no acredita el contexto actual'}</p>{data.acceptance.note && <p className="whitespace-pre-wrap text-[var(--work-muted)]">{data.acceptance.note}</p>}</div>}
      {saved && <p className="text-sm text-[var(--work-muted)]">Hay una aceptación pendiente de confirmar. Reenviarla conserva la versión y el contexto {saved.body.context_version} originales.</p>}
      {(data.eligible || saved) && !data.acceptance && <form className="space-y-3" onSubmit={event=>{event.preventDefault();submit()}}>
        <fieldset className="space-y-3" disabled={!!saved || accept.isPending || !ready || readOnly || !!storageError}>
          {data.requires_acknowledgement && <label className="flex items-start gap-2 text-sm text-[var(--work-ink)]"><input type="checkbox" checked={saved?saved.body.acknowledge_limits:acknowledged} onChange={event=>setAcknowledged(event.target.checked)}/><span>He revisado los límites indicados, incluida la ausencia o la omisión de pruebas. Aceptarlos no significa que esas pruebas hayan pasado.</span></label>}
          <label className="block space-y-1 text-sm text-[var(--work-ink)]"><span>Nota de aceptación (opcional)</span><textarea className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" rows={2} maxLength={4000} value={saved?(saved.body.note??''):note} aria-invalid={noteTooLong||undefined} aria-describedby={noteTooLong?noteErrorId:undefined} onChange={event=>setNote(event.target.value)}/></label>
          {noteTooLong && <p id={noteErrorId} role="alert" className="text-sm text-[var(--work-error)]">La nota es demasiado larga. Acórtala para poder guardar la aceptación.</p>}
        </fieldset>
        <button className={buttonClass} disabled={accept.isPending || !ready || readOnly || !!storageError || noteTooLong || (!saved && (!data.eligible || (data.requires_acknowledgement && !acknowledged)))}>{accept.isPending?'Guardando aceptación…':saved?'Reenviar la misma aceptación':'Aceptar esta versión'}</button>
      </form>}
      {accept.error && <p role="alert" className="text-sm text-[var(--work-error)]">{rejected?'El servidor rechazó la solicitud; no se aceptó otra versión. Consulta el estado actualizado.':'No se confirmó la aceptación. Conservamos la misma solicitud para consultar su recibo o reenviarla.'}</p>}
      {rejected && saved && <button className={buttonClass} onClick={()=>{try {codeActions.clear(window.sessionStorage,saved);setSaved(null);onPending?.(null);setRejected(false);accept.reset();state.refetch()} catch(error) {setStorageError(error instanceof Error?error.message:'No se pudo cerrar la solicitud rechazada.')}}}>Descartar esta solicitud rechazada</button>}
      {notice && <p role="status" className="text-sm text-[var(--work-ink)]">{notice}</p>}
      <details className="text-xs text-[var(--work-muted)]"><summary className="cursor-pointer">Identidad de la versión observada</summary><dl className="mt-2 space-y-2"><div><dt>Commit</dt><dd className="break-all font-mono">{data.candidate.head_sha}</dd></div><div><dt>Diff</dt><dd className="break-all font-mono">{data.candidate.diff_sha256}</dd></div><div><dt>Objeto revisado</dt><dd className="break-all font-mono">{data.subject_sha256??'No se pudo comprobar su vigencia.'}</dd></div></dl></details>
    </>}
  </section>
}

/** Keep pending code decisions discoverable even when their run leaves the recent author list. */
export function TaskCodeResults({projectId,taskId,runs,contextVersion,reviewAvailable=false}:{projectId:number;taskId:number;runs:RuntimeRun[];contextVersion:number;reviewAvailable?:boolean}) {
  const authors=runs.filter(run=>run.execution_kind==='development')
  const [selection,setSelection]=useState<string|null>(null)
  const [pending,setPending]=useState<string|null>(null)
  const [error,setError]=useState('')
  const [ready,setReady]=useState(typeof window==='undefined')
  useEffect(()=>{try {const acceptance=codeActions.pendingRun(window.sessionStorage,projectId,taskId);const review=codeReviewActions.pendingRun(window.sessionStorage,projectId,taskId);if(acceptance && review && acceptance!==review) throw new Error('Hay solicitudes pendientes para dos versiones. Consulta sus recibos antes de continuar.');const run=acceptance??review;setPending(run);setSelection(run);setReady(true)} catch(issue) {setError(issue instanceof Error?issue.message:'No se pudo recuperar la decisión pendiente.')}},[projectId,taskId])
  const chosen=pending??selection??authors[0]?.run_id
  if(!chosen) return error?<p role="alert">{error}</p>:null
  return <div className="space-y-2">
    {error && <p role="alert">{error}</p>}
    {authors.length>1 && <label className="block space-y-1 text-sm text-[var(--work-ink)]"><span>Código de una ejecución</span><select className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" disabled={!!pending} value={chosen} onChange={event=>setSelection(event.target.value)}>{!authors.some(run=>run.run_id===chosen) && <option value={chosen}>Aceptación pendiente de una ejecución anterior</option>}{authors.map(run=><option key={run.run_id} value={run.run_id}>Contexto {run.context_version} · {run.status==='accepted'?'aceptación registrada':'candidato conservado'}</option>)}</select></label>}
    <CodeDelivery key={`${projectId}:${taskId}:${chosen}`} projectId={projectId} taskId={taskId} runId={chosen} contextVersion={contextVersion} readOnly={!ready || !!error} reviewAvailable={reviewAvailable} onPending={setPending}/>
  </div>
}
