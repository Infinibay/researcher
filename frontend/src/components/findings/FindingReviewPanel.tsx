/** Independent review controls, retained decisions and exact-source inspection for one finding. @module */
import {useEffect,useRef,useState} from 'react'
import {useQuery} from '@tanstack/react-query'
import {Link} from 'react-router-dom'
import type {ReviewEvidence,ReviewIntent} from '../../api/reviews'
import {sourceWindow} from '../../api/runtime'
import {useCloseReview,useRequestReview,useReviewDetail,useReviewHistory,useReviewState,useReviewWorkspace} from '../../hooks/useReviews'
import {loadReviewIntent,reviewReason,reviewRunStatus,reviewVerdict,saveReviewIntent,scopedReview} from './reviewPresentation'

/** Require an explicit owner action against an observed version; never start work from a read. */
export function FindingReviewPanel({projectId,findingId,taskId,legacy=false,knownRequestId=null}:{projectId:number;findingId:number;taskId:number|null;legacy?:boolean;knownRequestId?:number|null}) {
 const stateQuery=useReviewState(projectId,findingId)
 const state=scopedReview(stateQuery.data,projectId,findingId,taskId)
 const workspaceQuery=useReviewWorkspace(projectId,taskId)
 const workspace=workspaceQuery.data?.project_id===projectId&&workspaceQuery.data.task_id===taskId?workspaceQuery.data:undefined
 const request=useRequestReview(),close=useCloseReview(projectId,findingId)
 const [repository,setRepository]=useState(''),[selected,setSelected]=useState<number|null>(null)
 const [intent,setIntent]=useState<ReviewIntent|null>(()=>loadReviewIntent(projectId,findingId,taskId))
 const [acknowledged,setAcknowledged]=useState(false),[foreignReceipt,setForeignReceipt]=useState(false)
 const submissionLock=useRef(false)
 const requestId=selected??state?.latest_review?.request_id??state?.reviews.items[state.reviews.items.length-1]?.request_id??knownRequestId
 const detailQuery=useReviewDetail(projectId,findingId,requestId)
 const candidate=scopedReview(detailQuery.data,projectId,findingId,taskId)
 const detail=candidate?.request_id===requestId?candidate:undefined
 const history=useReviewHistory(projectId,findingId,state?.reviews.next_after_id??null)
 const historyValid=history.data?.pages.every(page=>!!scopedReview(page,projectId,findingId,taskId))
 const items=[...(state?.reviews.items??[]),...(historyValid?history.data!.pages.flatMap(page=>page.reviews.items):[])]
 const repositories=workspace?.repositories??[]
 const repositoryId=repository?Number(repository):repositories.length===1?repositories[0].id:null
 const active=state?.active_review
 const acknowledgedIntent=!!intent&&(state?.latest_review?.operation_key===intent.operation_key||active?.operation_key===intent.operation_key)
 const ready=!!state&&!stateQuery.isError&&state.reviewable&&!active&&!!workspace&&!workspaceQuery.isError
  &&workspace.runtime.configured&&workspace.context.context_version===state.context_version
  &&repositories.some(repo=>repo.id===repositoryId)&&!request.isPending&&!intent
 useEffect(()=>{
  if(acknowledgedIntent){saveReviewIntent(projectId,findingId,null);setIntent(null);setAcknowledged(true);setForeignReceipt(false)}
 },[acknowledgedIntent,projectId,findingId])

 /** Reuse the exact packet after an unknown HTTP outcome; a new nonce would risk duplicate work. */
 async function submit(packet:ReviewIntent) {
  if(submissionLock.current)return
  submissionLock.current=true
  setIntent(packet);saveReviewIntent(projectId,findingId,packet);setForeignReceipt(false)
  try {
   const run=await request.mutateAsync(packet)
   if(run.project_id!==projectId||run.task_id!==taskId||run.operation_key!==packet.operation_key){setForeignReceipt(true);return}
   saveReviewIntent(projectId,findingId,null);setIntent(null);setAcknowledged(true)
  } catch { /* Preserve the original nonce and version; the owner chooses whether to retry. */ }
  finally{submissionLock.current=false}
 }

 /** Capture the visible subject version and repository only on the owner's explicit click. */
 function start() {
  if(!ready||!state||taskId==null||repositoryId==null)return
  void submit({projectId,taskId,findingId,context_version:state.context_version,subject_sha256:state.subject_sha256,
   repository_id:repositoryId,operation_key:`review-${crypto.randomUUID()}`})
 }

 return <section className="findings-review findings-assessment" aria-label="Revisión independiente">
  <header><h2>Revisión independiente</h2><p>Otro intento contrasta esta versión y sus fuentes. Sus comprobaciones quedan atribuidas; no aceptan la tarea ni publican el informe.</p></header>
  {stateQuery.isPending?<p role="status">Consultando la revisión…</p>:!state||stateQuery.isError?<div className="findings-error" role="alert"><p>No se pudo consultar la revisión. No se conoce su estado actual.</p><button onClick={()=>stateQuery.refetch()}>Volver a consultar la revisión</button></div>:<>
   {!state.latest_review&&!state.reviews.items.length&&<p><strong>{legacy?'Revisión independiente no acreditada':'Sin revisión independiente registrada'}</strong></p>}
   {stateQuery.isFetching&&<p role="status">Actualizando el estado…</p>}
   {active&&<div className="findings-review-status"><p><strong>{reviewRunStatus(active.status).title}</strong></p><p>{active.finding_id!==findingId?'Hay una revisión activa de otro hallazgo de esta tarea. Primero debe cerrarse ese intento.':reviewRunStatus(active.status).description}</p>
    <Link to={`/tasks?project=${projectId}&task=${taskId}`}>Ver tarea, preguntas y controles</Link>
    {active.finding_id===findingId&&<button disabled={close.isPending||['cancelling','reconciling'].includes(active.status)} onClick={()=>close.mutate(active.run_id)}>{active.status==='needs_review'?'Cerrar intento':'Detener revisión'}</button>}
    <p className="findings-muted">Las decisiones ya guardadas se conservan después del cierre.</p>
   </div>}
   {close.isError&&<p role="alert" className="findings-error">No se pudo confirmar el cierre. Consulta el estado antes de pedir otra revisión.</p>}
   {!active&&<div className="findings-review-start">
    {!state.reviewable?<p>{reviewReason(state.reason)}</p>:workspaceQuery.isPending?<p role="status">Consultando dónde ejecutar la revisión…</p>:!workspace||workspaceQuery.isError?<p role="alert">No se pudo consultar el entorno de la tarea. <button onClick={()=>workspaceQuery.refetch()}>Volver a consultar el entorno</button></p>:<>
     {!workspace.runtime.configured?<p>El motor de ejecución todavía no está configurado. Configúralo antes de solicitar la revisión.</p>:workspace.context.context_version!==state.context_version?<p>El contexto cambió. <button onClick={()=>{stateQuery.refetch();workspaceQuery.refetch()}}>Consultar la versión actual</button></p>:repositories.length===0?<p>Registra un repositorio en el proyecto para disponer de un entorno de revisión.</p>:repositories.length===1?<p>Entorno: <strong>{repositories[0].name}</strong>.</p>:<label htmlFor={`review-repository-${findingId}`}>Entorno de revisión<select id={`review-repository-${findingId}`} value={repository} onChange={event=>setRepository(event.target.value)}><option value="">Elige un repositorio</option>{repositories.map(repo=><option key={repo.id} value={repo.id}>{repo.name}</option>)}</select></label>}
    </>}
    <button className="findings-primary" disabled={!ready} onClick={start}>{request.isPending?'Registrando solicitud…':'Solicitar revisión independiente'}</button>
    <p className="findings-muted">Se iniciará un agente con el modelo configurado. Puede preguntarte si falta contexto.</p>
   </div>}
  </>}
  {acknowledged&&<p role="status">Solicitud registrada. El estado de arriba muestra el avance del intento.</p>}
  {(intent&&!request.isPending||foreignReceipt)&&<div className="findings-error" role="alert"><p>No se pudo confirmar la recepción de esta solicitud. Puede haberse registrado; consultar el estado permite comprobarlo.</p>
   {request.error instanceof Error&&<p>{request.error.message}</p>}
   <button onClick={()=>stateQuery.refetch()}>Consultar recepción</button>
   {intent&&!acknowledgedIntent&&<button disabled={request.isPending} onClick={()=>void submit(intent)}>Reenviar la misma solicitud</button>}
   <p className="findings-muted">El reenvío conserva la misma versión y clave: el servidor recupera el intento existente si ya lo admitió.</p>
  </div>}
  {items.length>0&&<label className="findings-review-history" htmlFor={`review-history-${findingId}`}>Intentos guardados<select id={`review-history-${findingId}`} value={requestId??''} onChange={event=>setSelected(Number(event.target.value))}>
   {requestId!=null&&!items.some(item=>item.request_id===requestId)&&<option value={requestId}>Revisión {requestId}</option>}
   {items.map(item=><option key={item.request_id} value={item.request_id}>Revisión {item.request_id} · {item.verdict?reviewVerdict(item.verdict):reviewRunStatus(item.status).title}</option>)}
  </select></label>}
  {state?.reviews.next_after_id!=null&&(!history.data||history.hasNextPage)&&<button disabled={history.isFetching} onClick={()=>history.fetchNextPage()}>Mostrar más intentos</button>}
  {history.isError||history.data&&!historyValid?<p className="findings-error" role="alert">No se pudo consultar el resto del historial.</p>:null}
  {requestId!=null&&(detail?<ReviewDecision key={requestId} projectId={projectId} detail={detail}/>:detailQuery.isError||detailQuery.data?<div className="findings-error" role="alert"><p>No se pudo consultar la decisión seleccionada.</p><button onClick={()=>detailQuery.refetch()}>Volver a consultar la decisión</button></div>:<p role="status">Consultando la decisión…</p>)}
  <p>Confianza científica: sin evaluar.</p>
 </section>
}

/** Display the reviewer's actual statements with old, unknown and current version labels kept distinct. */
function ReviewDecision({projectId,detail}:{projectId:number;detail:NonNullable<ReturnType<typeof useReviewDetail>['data']>}) {
 const [source,setSource]=useState<ReviewEvidence|null>(null)
 const trigger=useRef<string|null>(null)
 const outcomes:Record<string,string>={supported:'Respaldado',concern:'Objeción',not_checked:'Sin comprobar',not_applicable:'No aplicable'}
 if(source)return <ReviewSource key={`${source.source_id}:${source.source_sha256}`} projectId={projectId} evidence={source} close={()=>{setSource(null);setTimeout(()=>{if(trigger.current)document.getElementById(trigger.current)?.focus()},0)}}/>
 return <section className="findings-review-decision" aria-label="Decisión guardada">
  {detail.subject_current===false?<p className="findings-review-warning">Esta revisión corresponde a una versión anterior o a un contexto anterior. Alguna dependencia cambió; no evalúa la versión actual.</p>:detail.subject_current==null?<p className="findings-review-warning">No se pudo comprobar si esta revisión sigue correspondiendo a la versión actual. La decisión guardada se conserva para inspección.</p>:<p className="findings-muted">La versión y las fuentes coinciden con las revisadas. Esto no demuestra la validez científica de la conclusión.</p>}
  {detail.decision?<>
   <h3>{reviewVerdict(detail.decision.verdict)}</h3><p>{detail.decision.rationale}</p>
   <h3>Qué declaró haber comprobado</h3><ul className="findings-review-checks">{detail.decision.checks.map((check,index)=><li key={index}><strong>{outcomes[check.outcome]??'Resultado no reconocido'}</strong><p>{check.explanation}</p></li>)}</ul>
   <h3>Qué queda sin comprobar</h3>{detail.decision.limitations.length?<ul>{detail.decision.limitations.map((limitation,index)=><li key={index}>{limitation}</li>)}</ul>:<p>El revisor no declaró limitaciones. Eso no demuestra que no existan.</p>}
   {detail.decision.verified_evidence.length>0&&<><h3>Citas usadas por el revisor</h3>{detail.decision.verified_evidence.map((item,index)=><div className="findings-citation" key={`${item.source_id}:${index}`}><h4>{item.source?.title??`Fuente ${item.source_id}`}</h4><blockquote>{item.quote}</blockquote><button id={`review-${detail.request_id}-cite-${index}`} onClick={event=>{trigger.current=event.currentTarget.id;setSource(item)}}>Abrir captura de la revisión</button></div>)}</>}
  </>:<p>Este intento todavía no tiene una decisión guardada. Estado: {reviewRunStatus(detail.status).title}.</p>}
  <details><summary>Procedencia de esta revisión</summary><dl><dt>Solicitud</dt><dd>{detail.request_id}</dd><dt>Revisor</dt><dd>{detail.reviewer_actor_id}</dd><dt>Intento revisor</dt><dd>{detail.reviewer_attempt_id??'Todavía no asignado'}</dd><dt>Intento autor</dt><dd>{detail.author_attempt_id}</dd><dt>Versión del contexto</dt><dd>{detail.context_version}</dd><dt>Huella de la versión revisada</dt><dd><code>{detail.subject_sha256}</code></dd></dl></details>
 </section>
}

/** Open literal saved evidence only when project, source and reviewed body hash all match. */
function ReviewSource({projectId,evidence,close}:{projectId:number;evidence:ReviewEvidence;close:()=>void}) {
 const [offset,setOffset]=useState(Math.max(0,(evidence.quote_offset??0)-300))
 const heading=useRef<HTMLHeadingElement>(null)
 const query=useQuery({queryKey:['review-source',projectId,evidence.source_id,evidence.source_sha256,offset],
  queryFn:()=>sourceWindow(projectId,evidence.source_id,offset,evidence.source_sha256),retry:false})
 const value=query.data
 const data=value?.project_id===projectId&&value.source_id===evidence.source_id&&value.sha256===evidence.source_sha256?value:undefined
 useEffect(()=>{if(data)heading.current?.focus()},[data?.source_id,data?.offset])
 const position=data?.content.indexOf(evidence.quote)??-1
 return <section className="findings-source" aria-label="Captura usada en la revisión"><button onClick={close}>‹ Volver a la revisión</button><h3 ref={heading} tabIndex={-1}>{evidence.source?.title??'Captura citada'}</h3><p className="findings-muted">{evidence.source?.locator}</p>
  {data?<><p>Texto guardado de la versión citada por el revisor.</p><pre className="findings-source-text">{position>=0?<>{data.content.slice(0,position)}<mark>{evidence.quote}</mark>{data.content.slice(position+evidence.quote.length)}</>:data.content}</pre><p>Caracteres {data.content.length?data.offset+1:0}–{data.offset+Array.from(data.content).length} de {data.total_chars}.</p><div className="findings-window-nav">{offset>0&&<button onClick={()=>setOffset(Math.max(0,offset-12000))}>Fragmento anterior de la captura</button>}{data.next_offset!=null&&<button onClick={()=>setOffset(data.next_offset!)}>Siguiente fragmento de la captura</button>}</div></>:query.isError||query.data?<div className="findings-error" role="alert"><p>No se pudo recuperar la captura con la versión citada. La cita guardada no se atribuye a un texto diferente.</p><button onClick={()=>query.refetch()}>Volver a consultar la captura</button></div>:<p role="status">Consultando la captura…</p>}
 </section>
}
