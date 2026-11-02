/** Version-bound owner result inspection and durable local retry packets. @module */
import { fetchApi } from './client.ts'
import { ownerActionStore } from './ownerActions.ts'

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
/** Validate domain fields while the shared store preserves the existing research scope/keys. */
function parseResultAction(value:unknown):ResultAction {
 const action=value as ResultAction
 const positive=(v:unknown)=>typeof v==='number' && Number.isSafeInteger(v) && v>0
 const sha=(v:unknown)=>typeof v==='string' && /^[a-f0-9]{64}$/.test(v)
 if(action.kind==='accept') {
  const body=action.body
  if(!positive(body.candidate_id) || !positive(body.context_version) || !sha(body.candidate_sha256) || !sha(body.review_sha256) || typeof body.acknowledge_limits!=='boolean' || !(body.note===null || (typeof body.note==='string' && body.note.length<=4000))) throw new Error('acceptance')
 } else if(action.kind==='change') {
  const body=action.body
  if(!positive(body.expected_version) || body.source_kind!=='user_message' || typeof body.statement!=='string' || !body.statement.trim() || body.statement.length>12000) throw new Error('correction')
 } else throw new Error('kind')
 return action
}
/** Existing research packets keep their namespace and body contract during extraction. */
const resultActions=ownerActionStore<ResultAction>('result',parseResultAction)
/** Locate the original pending research run, including runs outside the recent list. */
export const pendingResultRun=resultActions.pendingRun
/** Persist the complete original research decision before sending. */
export const saveResultAction=resultActions.save
/** Recover exact scoped research history without refreshing its fingerprints. */
export const loadResultAction=resultActions.load
/** Clear only the resolved original research decision. */
export const clearResultAction=resultActions.clear
/** Explicitly retry the saved command; callers never substitute refreshed hashes or context. */
export function sendResultAction(action:ResultAction) {
 const path=action.kind==='accept'?`/api/projects/${action.projectId}/runs/${encodeURIComponent(action.runId)}/result/accept`:`/api/projects/${action.projectId}/tasks/${action.taskId}/context-corrections`
 return fetchApi<AcceptanceReceipt|{context_version:number;inference_started:false}>(path,{method:'POST',body:JSON.stringify(action.body)})
}
