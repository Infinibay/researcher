/** Explicit local-branch publication, preserving the original acceptance and destination over lost responses. @module */
import { fetchApi } from './client.ts'
import { ownerActionStore } from './ownerActions.ts'
import type { RuntimeRun } from './runtime.ts'

/** Complete original owner observation; paths, actor, process ownership and credentials are selected by the host. */
export interface CodePublicationBody {operation_key:string;acceptance_operation_key:string;author_attempt_id:string;context_version:number;subject_sha256:string;review_sha256:string;target_ref:string;expected_target_sha:string|null}
/** Durable original intent, separate from acceptance and independent review packets. */
export type CodePublicationAction=Readonly<{schema:1;kind:'publish-code';projectId:number;taskId:number;runId:string;body:Readonly<CodePublicationBody>}>

/** Refuse damaged local data instead of replacing its original publication intent. */
function parseCodePublication(value:unknown):CodePublicationAction {
  const action=value as CodePublicationAction
  const body=action.body
  if(action.kind!=='publish-code' || typeof body.acceptance_operation_key!=='string' || !/^[A-Za-z0-9_.:-]{1,128}$/.test(body.acceptance_operation_key) || typeof body.author_attempt_id!=='string' || !body.author_attempt_id || body.author_attempt_id.length>128 || !Number.isSafeInteger(body.context_version) || body.context_version<1 || !/^[a-f0-9]{64}$/.test(body.subject_sha256) || !/^[a-f0-9]{64}$/.test(body.review_sha256) || typeof body.target_ref!=='string' || !/^refs\/heads\/[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(body.target_ref) || body.target_ref.includes('..') || body.target_ref.length>240 || !(body.expected_target_sha===null || /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(body.expected_target_sha)) || Object.keys(body).sort().join(',')!=='acceptance_operation_key,author_attempt_id,context_version,expected_target_sha,operation_key,review_sha256,subject_sha256,target_ref') throw new Error('Invalid publication request packet')
  return action
}

/** Share the established saved-packet lifecycle with a separate publication namespace. */
export const codePublicationActions=ownerActionStore<CodePublicationAction>('code-publication',parseCodePublication)

/** Freeze one explicit request to create a new branch; retries reuse the returned object. */
export function prepareCodePublication(projectId:number,taskId:number,runId:string,observed:{acceptanceKey:string;attemptId:string;contextVersion:number;subjectSha:string;reviewSha:string;targetRef:string}):CodePublicationAction {
  const action:CodePublicationAction={schema:1,kind:'publish-code',projectId,taskId,runId,body:{operation_key:crypto.randomUUID(),acceptance_operation_key:observed.acceptanceKey,author_attempt_id:observed.attemptId,context_version:observed.contextVersion,subject_sha256:observed.subjectSha,review_sha256:observed.reviewSha,target_ref:observed.targetRef,expected_target_sha:null}}
  parseCodePublication(action)
  return Object.freeze({...action,body:Object.freeze({...action.body})})
}

/** Resolve only an admission receipt that retains every original body field and scope; a response lost after admission never creates another effect. */
export async function sendCodePublication(action:CodePublicationAction) {
  const receipt=await fetchApi<{run:RuntimeRun;request:{intent:CodePublicationBody}}>(`/api/projects/${action.projectId}/runs/${encodeURIComponent(action.runId)}/code-publications`,{method:'POST',body:JSON.stringify(action.body)})
  if(receipt.run.project_id!==action.projectId || receipt.run.task_id!==action.taskId || receipt.run.context_version!==action.body.context_version || receipt.run.operation_key!==action.body.operation_key || receipt.run.execution_kind!=='code_publication' || !Object.entries(action.body).every(([key,value])=>receipt.request.intent[key as keyof CodePublicationBody]===value)) throw new Error('El recibo no corresponde a esta publicación. Conservamos la solicitud original para comprobarla.')
  return receipt
}
