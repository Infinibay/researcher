/** Version-bound owner result inspection and durable local retry packets. @module */
import { fetchApi } from './client.ts'

/** Exact selected report metadata; full text is read from its frozen candidate. */
export interface DeliveredReport {
 artifact_id:number; title:string; report_type:string; content_sha256:string; finding_ids:number[]
}
/** Explicit author declaration, distinct from completion, review and owner acceptance. */
export interface DeliveredCandidate {
 candidate_id:number; candidate_sha256:string; kind:'research_reports'; scope:{context_version:number};
 summary:string; limitations:string[]; reports:DeliveredReport[]; finding_ids:number[]; scientific_confidence:null
}
/** Historical owner action; currentness is provided separately by the state response. */
export interface AcceptanceReceipt {
 acceptance_id:number; task_accepted:true; accepted_at:number; owner_note:string|null; acknowledged_limits:boolean
}
/** Actual independent finding assessment; it does not review the whole report. */
export interface DeliveredReview {
 finding_id:number; request_id:number|null; decision_id:number|null; verdict?:string|null;
 subject_current?:boolean|null; rationale_preview?:string|null
}
/** Read-only version, authority and review facts used before preparing an owner decision. */
export interface ResultState {
 project_id:number; task_id:number; run_id:string; candidate:DeliveredCandidate|null;
 candidate_current:boolean|null; eligible:boolean; reason:string|null; acceptance:AcceptanceReceipt|null;
 acceptance_current:boolean; reviews:{scope:string;items:DeliveredReview[]}|null;
 review_sha256:string|null; review_issues:{finding_id:number;reason:string}[];
 requires_acknowledgement:boolean; active_work:{id:string;status:string}[]
}
/** Frozen report window identity remains tied to its original delivery. */
export interface DeliveredWindow {
 candidate_sha256:string; content_sha256:string; title:string; content:string; offset:number; total_chars:number; next_offset:number|null
}
/** Preserve exactly the observed decision and acknowledgement, including the original nonce. */
export interface AcceptanceBody {
 operation_key:string; candidate_id:number; candidate_sha256:string; context_version:number;
 review_sha256:string; acknowledge_limits:boolean; note:string|null
}
/** Owner corrections state new requirements; saving one never starts inference. */
export interface ResultChangeBody {
 operation_key:string; expected_version:number; statement:string; source_kind:'user_message'
}
/** A tab-local immutable retry packet survives navigation, project switching and reload. */
export type ResultAction = Readonly<{schema:1;projectId:number;taskId:number;runId:string} & (
 {kind:'accept';body:Readonly<AcceptanceBody>} | {kind:'change';body:Readonly<ResultChangeBody>}
)>
/** Narrow browser storage contract makes persistence failures explicit and testable. */
export type ActionStorage = Pick<Storage,'getItem'|'setItem'|'removeItem'>

/** Inspect the actual root's delivered result; no inferred final artifact selection. */
export function resultState(projectId:number,runId:string) {
 return fetchApi<ResultState>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/result`)
}
/** Page the selected immutable candidate and verify the response's observed identity. */
export async function deliveredReport(projectId:number,runId:string,candidate:DeliveredCandidate,report:DeliveredReport,offset=0) {
 const value=await fetchApi<DeliveredWindow>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/result/candidates/${candidate.candidate_id}/reports/${report.artifact_id}?offset=${offset}&max_chars=12000`)
 if(value.candidate_sha256!==candidate.candidate_sha256 || value.content_sha256!==report.content_sha256) throw new Error('Cambió la identidad de la entrega consultada. Vuelve a consultar su estado.')
 return value
}
/** Freeze the exact displayed version before the first owner acceptance attempt. */
export function prepareAcceptance(projectId:number,taskId:number,runId:string,observed:{candidateId:number;candidateSha:string;contextVersion:number;reviewSha:string;acknowledgeLimits:boolean;note:string|null}):ResultAction & {kind:'accept'} {
 return Object.freeze({schema:1,kind:'accept',projectId,taskId,runId,body:Object.freeze({operation_key:crypto.randomUUID(),candidate_id:observed.candidateId,candidate_sha256:observed.candidateSha,context_version:observed.contextVersion,review_sha256:observed.reviewSha,acknowledge_limits:observed.acknowledgeLimits,note:observed.note})})
}
/** Bind a correction to the currently observed task context without sending a new request. */
export function prepareResultChange(projectId:number,taskId:number,runId:string,contextVersion:number,statement:string):ResultAction & {kind:'change'} {
 return Object.freeze({schema:1,kind:'change',projectId,taskId,runId,body:Object.freeze({operation_key:crypto.randomUUID(),expected_version:contextVersion,statement,source_kind:'user_message'})})
}
/** Keep local receipts isolated by project, task and original author run. */
function storageKey(projectId:number,taskId:number,runId:string) {return `researcher:result-action:v1:${projectId}:${taskId}:${encodeURIComponent(runId)}`}
/** Locate a pending task decision even when its author has left the recent run list. */
export function pendingResultRun(storage:Pick<Storage,'getItem'>,projectId:number,taskId:number):string|null {
 const raw=storage.getItem(`researcher:result-pending:v1:${projectId}:${taskId}`)
 if(raw===null) return null
 try {
  const pointer=JSON.parse(raw)
  if(typeof pointer.runId!=='string' || !pointer.runId || pointer.runId.length>128) throw new Error('scope')
  const action=loadResultAction(storage,projectId,taskId,pointer.runId)
  if(!action || action.body.operation_key!==pointer.operationKey) throw new Error('packet')
  return pointer.runId
 } catch {throw new Error('No se pudo recuperar la decisión pendiente de esta tarea. Consulta su historial antes de preparar otra.')}
}
/** Persist before sending; storage failure must not produce an unrecorded owner mutation. */
export function saveResultAction(storage:ActionStorage,action:ResultAction) {
 const previous=pendingResultRun(storage,action.projectId,action.taskId)
 if(previous!==null) {
  const old=loadResultAction(storage,action.projectId,action.taskId,previous)
  if(old?.body.operation_key!==action.body.operation_key) throw new Error('Hay una decisión pendiente de esta tarea. Consulta su recibo antes de preparar otra.')
 }
 storage.setItem(storageKey(action.projectId,action.taskId,action.runId),JSON.stringify(action))
 storage.setItem(`researcher:result-pending:v1:${action.projectId}:${action.taskId}`,JSON.stringify({runId:action.runId,operationKey:action.body.operation_key}))
}
/** Recover a strict scoped packet; corrupt state cannot silently turn into a new action. */
export function loadResultAction(storage:Pick<Storage,'getItem'>,projectId:number,taskId:number,runId:string):ResultAction|null {
 const value=storage.getItem(storageKey(projectId,taskId,runId))
 if(value===null) return null
 try {
  if(value.length>64000) throw new Error('oversized')
  const action=JSON.parse(value)
  const body=action.body
  const positive=(v:unknown)=>typeof v==='number' && Number.isSafeInteger(v) && v>0
  const sha=(v:unknown)=>typeof v==='string' && /^[a-f0-9]{64}$/.test(v)
  if(action.schema!==1 || action.projectId!==projectId || action.taskId!==taskId || action.runId!==runId || !body || typeof body.operation_key!=='string' || !/^[A-Za-z0-9_.:-]{1,128}$/.test(body.operation_key)) throw new Error('scope')
  if(action.kind==='accept') {
   if(!positive(body.candidate_id) || !positive(body.context_version) || !sha(body.candidate_sha256) || !sha(body.review_sha256) || typeof body.acknowledge_limits!=='boolean' || !(body.note===null || (typeof body.note==='string' && body.note.length<=4000))) throw new Error('acceptance')
  } else if(action.kind==='change') {
   if(!positive(body.expected_version) || body.source_kind!=='user_message' || typeof body.statement!=='string' || !body.statement.trim() || body.statement.length>12000) throw new Error('correction')
  } else throw new Error('kind')
  return Object.freeze({...action,body:Object.freeze({...body})}) as ResultAction
 } catch {throw new Error('No se pudo recuperar la decisión guardada. Consulta el resultado antes de preparar otra.')}
}
/** Clear only the exact resolved packet, never a newer decision stored in the same scope. */
export function clearResultAction(storage:ActionStorage,action:ResultAction) {
 const current=loadResultAction(storage,action.projectId,action.taskId,action.runId)
 if(current?.body.operation_key===action.body.operation_key) {
  const pointer=storage.getItem(`researcher:result-pending:v1:${action.projectId}:${action.taskId}`)
  if(pointer!==null && JSON.parse(pointer).operationKey===action.body.operation_key) storage.removeItem(`researcher:result-pending:v1:${action.projectId}:${action.taskId}`)
  storage.removeItem(storageKey(action.projectId,action.taskId,action.runId))
 }
}
/** Explicitly retry the saved command; callers never substitute refreshed hashes or context. */
export function sendResultAction(action:ResultAction) {
 const path=action.kind==='accept'?`/api/projects/${action.projectId}/runs/${encodeURIComponent(action.runId)}/result/accept`:`/api/projects/${action.projectId}/tasks/${action.taskId}/context-corrections`
 return fetchApi<AcceptanceReceipt|{context_version:number;inference_started:false}>(path,{method:'POST',body:JSON.stringify(action.body)})
}
