/** Exact captured code observations and explicit durable owner acceptance. @module */
import { fetchApi } from './client.ts'
import { ownerActionStore } from './ownerActions.ts'

/** Canonical captured Git identity, independent of a moving branch or reviewer prose. */
export interface CodeCandidate {project_id:number;task_id:number;repository_id:number;run_id:string;attempt_id:string;context_version:number;fence:number;base_sha:string;head_sha:string;tree_sha:string;diff_sha256:string}
/** The server's actual independent attributed assertions and limitations. */
export interface CodeReviewProposal {verdict:'supported'|'needs_revision'|'inconclusive';rationale:string;checks:{criterion:string;outcome:string;explanation:string}[];references:{kind:string;path:string;sha256:string;start_line:number;quote:string}[];limitations:string[]}
/** Historical owner decision; currentness is reported separately. */
export interface CodeAcceptanceReceipt {project_id:number;task_id:number;run_id:string;operation_key:string;attempt_id:string;context_version:number;subject_sha256:string;review_sha256:string;accepted_at:number;note:string|null;task_accepted:true;publication_performed:false}
/** Scoped current evidence and blockers; unknown checks are never rendered as passing tests. */
export interface CodeResultState {
  project_id:number;task_id:number;run_id:string;candidate:CodeCandidate;candidate_current:boolean
  packet:{author_request:{text:string};checks:{id:string;state:string;spec:{argv:string[];framework:string};result:{status:string;reason:string}|null}[]}|null
  subject_sha256:string|null;review_sha256:string;review:{run_id:string;attempt_id:string;actor_id:string;state:string;proposal:CodeReviewProposal|null}|null
  eligible:boolean;blockers:{code:string;message:string}[];checks:{limitations:{code:string;message:string}[]};requires_acknowledgement:boolean
  review_issues?:{run_id:string;state:string;verdict:string;rationale:string;blocking:boolean;message:string}[]
  acceptance:CodeAcceptanceReceipt|null;acceptance_current:boolean;publication:{performed:false;eligibility:string;message:string}
}
/** One explicit captured diff window with identity and unread-tail information. */
export interface CodeDiffWindow {content:string;offset:number;next_offset:number|null;total_chars:number;bytes:number;sha256:string;complete_file:boolean}
/** Freeze every observed field once; no refreshed state may silently replace this body. */
export interface CodeAcceptanceBody {operation_key:string;attempt_id:string;context_version:number;subject_sha256:string;review_sha256:string;acknowledge_limits:boolean;note:string|null}
/** Namespace-specific durable retry packet, separate from report acceptance. */
export type CodeAcceptanceAction=Readonly<{schema:1;kind:'accept-code';projectId:number;taskId:number;runId:string;body:Readonly<CodeAcceptanceBody>}>

/** Strictly recover the code decision kind and complete body; never adopt arbitrary local JSON. */
function parseCodeAction(value:unknown):CodeAcceptanceAction {
  const action=value as CodeAcceptanceAction
  const body=action.body
  if(action.kind!=='accept-code' || typeof body.attempt_id!=='string' || !body.attempt_id || body.attempt_id.length>128 || !Number.isSafeInteger(body.context_version) || body.context_version<=0 || !/^[a-f0-9]{64}$/.test(body.subject_sha256) || !/^[a-f0-9]{64}$/.test(body.review_sha256) || typeof body.acknowledge_limits!=='boolean' || !(body.note===null || (typeof body.note==='string' && body.note.trim() && new TextEncoder().encode(body.note).length<=4000)) || Object.keys(body).sort().join(',')!=='acknowledge_limits,attempt_id,context_version,note,operation_key,review_sha256,subject_sha256') throw new Error('Invalid code acceptance packet')
  return action
}

/** Reuse the research decision lifecycle with an independent code namespace and validator. */
export const codeActions=ownerActionStore<CodeAcceptanceAction>('code',parseCodeAction)

/** Read current candidate, review and historical acceptance without starting any work. */
export function codeResultState(projectId:number,runId:string) {
  return fetchApi<CodeResultState>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/code-result`)
}
/** Refuse a diff response whose stored identity differs from the owner's selected candidate. */
export async function codeResultDiff(projectId:number,runId:string,expectedSha:string,offset=0) {
  const value=await fetchApi<CodeDiffWindow>(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/code-result/diff?offset=${offset}&max_chars=12000`)
  if(value.sha256!==expectedSha) throw new Error('Cambió la identidad del diff. Vuelve a consultar el candidato.')
  return value
}
/** Prepare a new explicit decision only after inspection; retry callers reuse this frozen value. */
export function prepareCodeAcceptance(projectId:number,taskId:number,runId:string,observed:{attemptId:string;contextVersion:number;subjectSha:string;reviewSha:string;acknowledgeLimits:boolean;note:string|null}):CodeAcceptanceAction {
  const action:CodeAcceptanceAction={schema:1,kind:'accept-code',projectId,taskId,runId,body:{operation_key:crypto.randomUUID(),attempt_id:observed.attemptId,context_version:observed.contextVersion,subject_sha256:observed.subjectSha,review_sha256:observed.reviewSha,acknowledge_limits:observed.acknowledgeLimits,note:observed.note}}
  parseCodeAction(action)
  return Object.freeze({...action,body:Object.freeze({...action.body})})
}
/** Send only the original saved body to the owner endpoint; there is no inference or publication call. */
export async function sendCodeAcceptance(action:CodeAcceptanceAction) {
  const receipt=await fetchApi<CodeAcceptanceReceipt>(`/api/projects/${action.projectId}/runs/${encodeURIComponent(action.runId)}/code-result/accept`,{method:'POST',body:JSON.stringify(action.body)})
  if(!matchesCodeReceipt(receipt,action)) throw new Error('El recibo no corresponde a esta aceptación. Conservamos la solicitud original para comprobarla.')
  return receipt
}

/** Confirm exact historical scope before resolving a lost response; a receipt is not a new current acceptance. */
export function matchesCodeReceipt(receipt:CodeAcceptanceReceipt,action:CodeAcceptanceAction) {
  return receipt.project_id===action.projectId && receipt.task_id===action.taskId && receipt.run_id===action.runId && receipt.operation_key===action.body.operation_key && receipt.attempt_id===action.body.attempt_id && receipt.context_version===action.body.context_version && receipt.subject_sha256===action.body.subject_sha256 && receipt.review_sha256===action.body.review_sha256 && receipt.task_accepted===true && receipt.publication_performed===false
}
