/** Explicit independent code review over an owner-observed candidate; retries never adopt refreshed evidence. @module */
import { fetchApi } from './client.ts'
import { ownerActionStore } from './ownerActions.ts'
import type { RuntimeRun } from './runtime.ts'

/** Complete original review request; actor, capabilities and source paths belong to the host. */
export interface CodeReviewBody {operation_key:string;attempt_id:string;context_version:number;subject_sha256:string;request:string}
/** Discover the original author even if a newer run appears while a response is lost. */
export type CodeReviewAction=Readonly<{schema:1;kind:'review-code';projectId:number;taskId:number;runId:string;body:Readonly<CodeReviewBody>}>

/** Validate the full persisted body rather than treating damaged storage as permission for a new request. */
function parseCodeReview(value:unknown):CodeReviewAction {
  const action=value as CodeReviewAction
  const body=action.body
  if(action.kind!=='review-code' || typeof body.attempt_id!=='string' || !body.attempt_id.trim() || body.attempt_id.length>128 || !Number.isSafeInteger(body.context_version) || body.context_version<1 || !/^[a-f0-9]{64}$/.test(body.subject_sha256) || typeof body.request!=='string' || !body.request.trim() || new TextEncoder().encode(body.request).length>12000 || Object.keys(body).sort().join(',')!=='attempt_id,context_version,operation_key,request,subject_sha256') throw new Error('Invalid independent review request')
  return action
}

/** Separate review and acceptance intents while reusing the same durable packet lifecycle. */
export const codeReviewActions=ownerActionStore<CodeReviewAction>('code-review',parseCodeReview)

/** Freeze exactly the observed candidate and human request before the first send. */
export function prepareCodeReview(projectId:number,taskId:number,runId:string,observed:{attemptId:string;contextVersion:number;subjectSha:string;request:string}):CodeReviewAction {
  const action:CodeReviewAction={schema:1,kind:'review-code',projectId,taskId,runId,body:{operation_key:crypto.randomUUID(),attempt_id:observed.attemptId,context_version:observed.contextVersion,subject_sha256:observed.subjectSha,request:observed.request}}
  parseCodeReview(action)
  return Object.freeze({...action,body:Object.freeze({...action.body})})
}

/** Repeat the same admission receipt after uncertainty; successful admission never implies review, acceptance or publication. */
export async function sendCodeReview(action:CodeReviewAction) {
  const receipt=await fetchApi<RuntimeRun>(`/api/projects/${action.projectId}/tasks/${action.taskId}/code-reviews`,{method:'POST',body:JSON.stringify(action.body)})
  if(receipt.project_id!==action.projectId || receipt.task_id!==action.taskId || receipt.operation_key!==action.body.operation_key || receipt.context_version!==action.body.context_version || receipt.prompt!==action.body.request || receipt.execution_kind!=='code_review' || typeof receipt.run_id!=='string' || !receipt.run_id) throw new Error('El recibo no corresponde a esta revisión. Conservamos la solicitud original para comprobarla.')
  return receipt
}
