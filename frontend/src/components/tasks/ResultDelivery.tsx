/** Owner inspection and distinct acceptance of explicitly delivered research reports. @module */
import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clearResultAction, deliveredReport, loadResultAction, prepareAcceptance, prepareResultChange, pendingResultRun, resultState, saveResultAction, sendResultAction } from '../../api/results'
import type { DeliveredCandidate, DeliveredReport, ResultAction } from '../../api/results'
import type { RuntimeRun } from '../../api/runtime'
import { MarkdownRenderer } from '../common/MarkdownRenderer'

const buttonClass='rounded-md border border-[var(--work-line)] px-3 py-2 text-sm hover:bg-[var(--work-wash)] disabled:opacity-50'
const inputClass='w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] px-3 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-[var(--work-accent)]'

/** Page the original selected report; never show a current draft as the delivered version. */
function FrozenReport({projectId,runId,candidate,report}:{projectId:number;runId:string;candidate:DeliveredCandidate;report:DeliveredReport}) {
 const [open,setOpen]=useState(false)
 const [offset,setOffset]=useState(0)
 const query=useQuery({queryKey:['delivered-report',projectId,runId,candidate.candidate_id,report.artifact_id,offset],queryFn:()=>deliveredReport(projectId,runId,candidate,report,offset),enabled:open,retry:false})
 return <details className="rounded-md border border-[var(--work-line)] p-3" onToggle={event=>setOpen(event.currentTarget.open)}>
  <summary className="cursor-pointer font-medium">{report.title} <span className="font-normal text-[var(--work-muted)]">· versión entregada</span></summary>
  {open && query.isPending && <p role="status">Recuperando informe…</p>}
  {query.error && <div role="alert"><p>No se pudo recuperar el informe entregado. {query.error.message}</p><button className={buttonClass} onClick={()=>query.refetch()}>Volver a consultar informe</button></div>}
  {query.data && <div className="mt-3 space-y-3"><MarkdownRenderer content={query.data.content} headingBase={5}/><p className="text-xs text-[var(--work-muted)]">Caracteres {Math.min(offset+1,query.data.total_chars)}–{Math.min(offset+query.data.content.length,query.data.total_chars)} de {query.data.total_chars}.</p><div className="flex flex-wrap gap-2">{offset>0 && <button className={buttonClass} onClick={()=>setOffset(Math.max(0,offset-12000))}>Parte anterior</button>}{query.data.next_offset!==null && <button className={buttonClass} onClick={()=>setOffset(query.data!.next_offset!)}>Parte siguiente</button>}</div></div>}
 </details>
}

/** Explain actual currentness/review facts and preserve uncertain owner commands across reloads. */
export function ResultDelivery({projectId,taskId,runId,contextVersion,readOnly=false}:{projectId:number;taskId:number;runId:string;contextVersion:number;readOnly?:boolean}) {
 const qc=useQueryClient()
 const query=useQuery({queryKey:['run-result',projectId,runId],queryFn:()=>resultState(projectId,runId),retry:false,refetchInterval:3000})
 const [pending,setPending]=useState<ResultAction|null>(null)
 const [storageChecked,setStorageChecked]=useState(()=>typeof window==='undefined')
 const [localError,setLocalError]=useState('')
 const [ackFor,setAckFor]=useState<string|null>(null)
 const [note,setNote]=useState('')
 const [statement,setStatement]=useState('')
 const [notice,setNotice]=useState('')
 // Restored controls are loaded before permitting any new owner action.
 useEffect(()=>{
  try {setPending(loadResultAction(window.sessionStorage,projectId,taskId,runId))}
  catch(error) {setLocalError(error instanceof Error?error.message:'No se pudo recuperar la decisión guardada.')}
  setStorageChecked(true)
 },[projectId,taskId,runId])
 const action=useMutation({mutationFn:sendResultAction,retry:false,onSuccess:(_,intent)=>{
  try {clearResultAction(window.sessionStorage,intent);setPending(null);setLocalError('')}
  catch {setLocalError('La acción quedó registrada, pero no se pudo limpiar su consulta local. Puedes consultar el mismo recibo.')}
  setNotice(intent.kind==='accept'?'Aceptación registrada para esta entrega.':'Cambios registrados. La próxima ejecución usará el nuevo contexto; todavía no comenzó.')
 },onSettled:(_,__,intent)=>{
  qc.invalidateQueries({queryKey:['run-result',intent.projectId,intent.runId]})
  qc.invalidateQueries({queryKey:['task-workspace',intent.projectId,intent.taskId]})
  qc.invalidateQueries({queryKey:['task',intent.taskId]})
  qc.invalidateQueries({queryKey:['tasks',intent.projectId]})
 }})
 /** Persist the full original scope before any mutation can reach the server. */
 const submit=(intent:ResultAction)=>{
  try {saveResultAction(window.sessionStorage,intent);setPending(intent);setLocalError('');action.mutate(intent)}
  catch {setLocalError('No se pudo guardar la decisión en esta pestaña. No se envió; comprueba el almacenamiento antes de intentarlo de nuevo.')}
 }
 const data=query.data
 const scoped=data?.project_id===projectId && data.task_id===taskId && data.run_id===runId
 const candidate=scoped?data.candidate:null
 const observedReview=candidate && data?`${candidate.candidate_sha256}:${data.review_sha256}`:null
 const ack=observedReview!==null && ackFor===observedReview
 return <section className="space-y-4 rounded-md border border-[var(--work-line)] p-4" aria-label="Resultado entregado">
  <div><h4 className="font-semibold">Resultado entregado</h4><p className="mt-1 text-[var(--work-muted)]">El agente selecciona sus informes finales. Tú puedes revisar esa versión y decidir si resuelve la tarea.</p></div>
  {query.isPending && <p role="status">Consultando la entrega…</p>}
  {(query.error || (data && !scoped)) && <div role="alert"><p>No se pudo comprobar la entrega de esta tarea. {query.error?.message}</p><button className={buttonClass} onClick={()=>query.refetch()}>Volver a consultar entrega</button></div>}
  {localError && <p role="alert" className="text-[var(--work-error)]">{localError}</p>}
  {notice && <p role="status" className="text-[var(--work-accent)]">{notice}</p>}
  {pending && <div className="space-y-2 rounded-md border border-[var(--work-line)] p-3"><p>Hay una {pending.kind==='accept'?'aceptación':'petición de cambios'} guardada bajo contexto {pending.kind==='accept'?pending.body.context_version:pending.body.expected_version}. Conserva su contenido y su identidad aunque la tarea cambie.</p><button className={buttonClass} disabled={action.isPending} onClick={()=>action.mutate(pending)}>{action.isPending?'Consultando…':'Consultar la misma decisión'}</button>{action.error && <p role="alert" className="text-[var(--work-error)]">No quedó confirmada. {action.error.message}</p>}{action.error && <button className={buttonClass} disabled={action.isPending} onClick={()=>{try{clearResultAction(window.sessionStorage,pending);setPending(null);action.reset();setNotice('Consulta el historial antes de preparar otra decisión: la anterior puede haber quedado registrada.')}catch{setLocalError('No se pudo actualizar la decisión guardada.')}}}>Revisar la decisión</button>}</div>}
  {scoped && !candidate && <p className="text-[var(--work-muted)]">El agente todavía no seleccionó una entrega. Terminar un turno o guardar borradores no permite aceptar la tarea.</p>}
  {candidate && data && <>
   <div className="space-y-2"><p className="text-xs text-[var(--work-muted)]">Declaración del agente · contexto {candidate.scope.context_version}</p><MarkdownRenderer content={candidate.summary} headingBase={5}/></div>
   {candidate.reports.map(report=><FrozenReport key={`${candidate.candidate_id}:${report.artifact_id}`} projectId={projectId} runId={runId} candidate={candidate} report={report}/>)}
   <div><h5 className="font-medium">Límites declarados por el agente</h5><ul className="mt-1 list-disc space-y-1 pl-5">{candidate.limitations.map((limit,index)=><li key={index} className="whitespace-pre-wrap">{limit}</li>)}</ul></div>
   <div className="space-y-2"><h5 className="font-medium">Revisión independiente</h5><p className="text-[var(--work-muted)]">La revisión comprueba hallazgos y fuentes; no certifica el informe completo. Aceptar esta entrega no publica el informe ni valida científicamente sus conclusiones.</p>
    {data.review_issues.map((issue,index)=><p key={index} className="text-[var(--work-caution)]">Hallazgo {issue.finding_id}: {issue.reason==='no_independent_review'?'Sin revisión independiente registrada':issue.reason==='review_without_decision'?'Revisión sin decisión registrada':issue.reason==='review_outdated_or_unverifiable'?'Revisión anterior o sin vigencia comprobada':'La revisión informa límites o cambios necesarios'}.</p>)}
    {data.reviews?.items.filter(item=>item.decision_id!==null).map(item=><div key={item.finding_id} className="border-l-2 border-[var(--work-line)] pl-3"><p>Hallazgo {item.finding_id}: {item.verdict==='supported'?'El revisor declara que tiene respaldo':item.verdict==='needs_revision'?'El revisor pide cambios':'Revisión no concluyente'}{item.subject_current!==true?' · vigencia no confirmada':''}.</p>{item.rationale_preview && <p className="whitespace-pre-wrap text-[var(--work-muted)]">Extracto de la revisión: {item.rationale_preview}</p>}</div>)}
    <a className="text-[var(--work-accent)] underline" href={`/findings?project=${projectId}`}>Consultar hallazgos y revisiones</a>
   </div>
   {data.candidate_current===false && <p role="status" className="text-[var(--work-caution)]">La tarea, el informe o alguna dependencia cambió desde la entrega. Conservamos esta versión para consultarla; hace falta otra entrega para aceptarla.</p>}
   {data.candidate_current===null && <p role="status" className="text-[var(--work-caution)]">No se pudo comprobar que esta entrega siga vigente. Su versión guardada permanece disponible.</p>}
   {data.acceptance && <div className="space-y-1 border-t border-[var(--work-line)] pt-3"><h5 className="font-medium">Aceptación registrada</h5><p className="text-[var(--work-muted)]">{data.acceptance_current?'La decisión corresponde a la versión vigente.':'Es una decisión histórica; no confirma la aceptación de los requisitos actuales.'}</p>{data.acceptance.owner_note && <p className="whitespace-pre-wrap">{data.acceptance.owner_note}</p>}</div>}
   {storageChecked && !readOnly && !pending && !localError && data.eligible && data.candidate_current===true && data.review_sha256 && <form className="space-y-3 border-t border-[var(--work-line)] pt-3" onSubmit={event=>{event.preventDefault();submit(prepareAcceptance(projectId,taskId,runId,{candidateId:candidate.candidate_id,candidateSha:candidate.candidate_sha256,contextVersion:candidate.scope.context_version,reviewSha:data.review_sha256!,acknowledgeLimits:ack,note:note.trim()||null}))}}>
    <label className="block space-y-1">Nota para esta decisión <span className="text-[var(--work-muted)]">(opcional)</span><textarea className={inputClass} rows={2} maxLength={4000} value={note} onChange={event=>setNote(event.target.value)}/></label>
    {data.requires_acknowledgement && <label className="flex items-start gap-2"><input type="checkbox" checked={ack} onChange={event=>setAckFor(event.target.checked?observedReview:null)}/>Acepto el resultado teniendo en cuenta la ausencia o los límites de revisión indicados.</label>}
    <button className={buttonClass} disabled={query.isFetching || action.isPending || (data.requires_acknowledgement && !ack)}>Aceptar esta entrega</button>
   </form>}
   {!data.eligible && !data.acceptance && data.candidate_current===true && <p className="text-[var(--work-muted)]">{data.reason==='other_work_unreconciled'?'Hay otra ejecución cuyo cierre falta comprobar.':'La entrega todavía no está lista para aceptar. Consulta el estado de la ejecución.'}</p>}
   {storageChecked && !readOnly && !pending && !localError && <form className="space-y-2 border-t border-[var(--work-line)] pt-3" onSubmit={event=>{event.preventDefault();submit(prepareResultChange(projectId,taskId,runId,contextVersion,statement.trim()))}}><label className="block space-y-1">Qué debe cambiar<textarea className={inputClass} rows={3} maxLength={12000} placeholder="Por ejemplo: compara la cifra con otra fuente y explica si usan la misma unidad." value={statement} onChange={event=>setStatement(event.target.value)}/></label><p className="text-[var(--work-muted)]">Se guardará tu corrección para el siguiente trabajo. Si aceptaste antes, la tarea se reabrirá y conservará la decisión anterior.</p><button className={buttonClass} disabled={!statement.trim() || query.isFetching || action.isPending}>Pedir cambios</button></form>}
  </>}
 </section>
}


/** Prefer a saved unresolved decision and let the owner inspect older author deliveries explicitly. */
export function TaskResults({projectId,taskId,runs,contextVersion}:{projectId:number;taskId:number;runs:RuntimeRun[];contextVersion:number}) {
 const authors=runs.filter(run=>run.execution_kind==='research')
 const [selection,setSelection]=useState<string|null>(null)
 const [error,setError]=useState('')
 const [ready,setReady]=useState(()=>typeof window==='undefined')
 useEffect(()=>{
  try {setSelection(pendingResultRun(window.sessionStorage,projectId,taskId))}
  catch(issue) {setError(issue instanceof Error?issue.message:'No se pudo recuperar la decisión pendiente.')}
  setReady(true)
 },[projectId,taskId])
 const chosen=selection??authors[0]?.run_id
 if(!chosen) return null
 return <div className="space-y-2">
  {error && <p role="alert" className="text-[var(--work-error)]">{error}</p>}
  {authors.length>1 && <label className="block space-y-1">Entrega de una ejecución<select className={inputClass} value={chosen} onChange={event=>setSelection(event.target.value)}>{!authors.some(run=>run.run_id===chosen) && <option value={chosen}>Decisión pendiente de una ejecución anterior</option>}{authors.map(run=><option key={run.run_id} value={run.run_id}>Contexto {run.context_version} · {run.status==='accepted'?'aceptación registrada':run.status==='needs_review'?'terminada para revisar':run.status==='superseded'?'contexto anterior':'ejecución conservada'}</option>)}</select></label>}
  <ResultDelivery key={`${projectId}:${taskId}:${chosen}`} projectId={projectId} taskId={taskId} runId={chosen} contextVersion={contextVersion} readOnly={!ready || !!error}/>
 </div>
}
