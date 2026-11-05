/** Explicit remote decisions, readonly destination evidence and original recovery receipts. @module */
import {fetchApi} from './client.ts'
import {ownerActionStore} from './ownerActions.ts'
import type {RuntimeRun} from './runtime.ts'

/** Canonical server identity observed by the host; this contains no credential. */
export interface RemoteRepository {api_base:string;repository_id:number;full_name:string;clone_url:string}
/** Each write needs its own owner decision; acceptance and PR creation never imply merge permission. */
export type RemoteChoice={stage:'push';remote:RemoteRepository;target_ref:string;expected_target_sha:string|null}|{stage:'pull';base_ref:string;base_sha:string;title:string;body:string}|{stage:'merge'}
/** Complete original action, rooted in a local publication but addressed to its exact preceding stage. */
export type RemoteAction=Readonly<{schema:1;kind:'publish-remote';projectId:number;taskId:number;runId:string;originRunId:string;contextVersion:number;headSha:string;body:Readonly<RemoteChoice&{operation_key:string}>}>
/** Observation fields distinguish original effect history from current branch/PR eligibility. */
export interface RemoteObservation {state:string;target_current?:boolean;candidate_current?:boolean;number?:number|null;merge_sha?:string|null;observed_target_sha?:string|null}
/** Fixed protocol fields are shown as destinations, never interpreted as client-side authority. */
export interface RemoteProtocol {remote?:RemoteRepository;target_ref?:string;base_ref?:string;head_ref?:string;head_sha?:string;base_sha?:string;number?:number;push?:RemoteProtocol;pull?:RemoteProtocol}
/** Saved server request plus original effect facts; unknown stages must use readonly recovery. */
export interface RemoteRequest {run_id:string;stage:RemoteChoice['stage'];origin_run_id:string;local_publication_run_id:string;intent:Record<string,unknown>;protocol:RemoteProtocol;effects:{effect_name:string;state:string;outcome:RemoteObservation|null}[];result:{effects:Record<string,RemoteObservation>;observations?:Record<string,RemoteObservation>;completed_after_withdrawal:boolean}|null}
/** One actual runtime action paired with the immutable request it admitted. */
export interface RemoteEntry {run:RuntimeRun;request:RemoteRequest}
/** Bounded saved history; truncation is explicit and never treated as proof of absence. */
export interface RemoteHistory {project_id:number;task_id:number;local_publication_run_id:string;context_version:number;head_sha:string;base_sha:string;acceptance_current:boolean;actions:RemoteEntry[];truncated:boolean}
/** Readonly host observation used to prepare a new explicit action, not to retry an unknown effect. */
export interface RemotePreview {project_id:number;task_id:number;local_publication_run_id:string;context_version:number;head_sha:string;base_sha:string;remote:RemoteRepository;target_ref:string;target_sha:string|null;base_ref:string;observed_base_sha:string|null;push_allowed:boolean;pull_allowed:boolean;observed_at:number}
/** Recovery has its own original fenced command and never shares a publication key. */
export type RemoteRecoveryAction=Readonly<{schema:1;kind:'observe-remote';projectId:number;taskId:number;runId:string;remoteRunId:string;body:Readonly<{operation_key:string;attempt_id:string;expected_fence:number}>}>
/** Immutable observer receipt, including uncertainty and completion after a human withdrawal. */
export interface RemoteRecoveryReceipt {run_id:string;source_attempt_id:string;recovery_operation_key:string;effects_confirmed:boolean;completed_after_withdrawal:boolean;observations:Record<string,RemoteObservation>}
const sha=/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/
/** Validate branch syntax before persistence; the server performs the authoritative Git checks. */
function ref(value:unknown):boolean{return typeof value==='string' && value.length<=240 && /^refs\/heads\/[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(value) && !value.includes('..') && !value.endsWith('/') && !value.endsWith('.') && !value.split('/').some(part=>part.startsWith('.')||part.endsWith('.lock'))}
/** Compare only JSON fields with stable object ordering, including nested remote identity. */
function same(left:unknown,right:unknown):boolean {if(left===right)return true;if(!left||!right||typeof left!=='object'||typeof right!=='object')return false;const a=Object.entries(left).sort(),b=Object.entries(right).sort();return a.length===b.length&&a.every(([key,value],i)=>key===b[i][0]&&same(value,b[i][1]))}
/** Reject damaged or expanded local intents instead of refreshing destinations on reload. */
function parseRemote(value:unknown):RemoteAction {
 const action=value as RemoteAction,b=action.body
 if(action.kind!=='publish-remote'||!action.originRunId||action.originRunId.length>128||!Number.isSafeInteger(action.contextVersion)||action.contextVersion<1||!sha.test(action.headSha))throw new Error('Invalid original remote scope')
 let keys:string[]=['operation_key','stage']
 if(b.stage==='push') {keys.push('remote','target_ref','expected_target_sha');const r=b.remote;if(!r||!Number.isSafeInteger(r.repository_id)||r.repository_id<=0||!/^https:\/\//.test(r.api_base)||!r.api_base.endsWith('/api/v1')||!/^[-A-Za-z0-9_.]+\/[-A-Za-z0-9_.]+$/.test(r.full_name)||r.clone_url!==r.api_base.slice(0,-7)+'/'+r.full_name+'.git'||Object.keys(r).sort().join(',')!=='api_base,clone_url,full_name,repository_id'||!ref(b.target_ref)||(b.expected_target_sha!==null&&!sha.test(b.expected_target_sha)))throw new Error('Invalid original push destination');Object.freeze(r)}
 else if(b.stage==='pull'){keys.push('base_ref','base_sha','title','body');if(!ref(b.base_ref)||!sha.test(b.base_sha)||typeof b.title!=='string'||!b.title.trim()||b.title.length>256||typeof b.body!=='string'||!b.body.trim()||b.body.length>12000)throw new Error('Invalid original PR decision')}
 else if(b.stage!=='merge')throw new Error('Unknown remote stage')
 if(Object.keys(b).sort().join(',')!==keys.sort().join(','))throw new Error('Expanded remote request')
 return action
}
/** Publication and recovery pointers remain independently scoped to the original local root. */
export const remoteActions=ownerActionStore<RemoteAction>('remote-publication',parseRemote)
/** Reject mismatched recovery attempts before retaining or sending a local command. */
function parseRecovery(value:unknown):RemoteRecoveryAction {const a=value as RemoteRecoveryAction,b=a.body;if(a.kind!=='observe-remote'||!a.remoteRunId||a.remoteRunId.length>128||typeof b.attempt_id!=='string'||!b.attempt_id||b.attempt_id.length>128||!Number.isSafeInteger(b.expected_fence)||b.expected_fence<1||Object.keys(b).sort().join(',')!=='attempt_id,expected_fence,operation_key')throw new Error('Invalid original remote observation');return a}
/** Recovery persistence never grants or reconstructs a writer intent. */
export const remoteRecoveryActions=ownerActionStore<RemoteRecoveryAction>('remote-recovery',parseRecovery)
/** Freeze a new explicit stage after its original destination/accepted version was observed. */
export function prepareRemoteAction(projectId:number,taskId:number,runId:string,originRunId:string,observed:{contextVersion:number;headSha:string},choice:RemoteChoice):RemoteAction {
 const body=JSON.parse(JSON.stringify({...choice,operation_key:crypto.randomUUID()})) as RemoteAction['body']
 const action:RemoteAction={schema:1,kind:'publish-remote',projectId,taskId,runId,originRunId,...observed,body};parseRemote(action);return Object.freeze({...action,body:Object.freeze(body)})
}
/** Resolve an admission only when every original field, prerequisite and accepted version match. */
export function matchesRemoteReceipt(entry:RemoteEntry,action:RemoteAction):boolean {return entry.run.project_id===action.projectId&&entry.run.task_id===action.taskId&&entry.run.context_version===action.contextVersion&&entry.run.operation_key===action.body.operation_key&&entry.run.execution_kind==='remote_publication'&&entry.request.origin_run_id===action.originRunId&&entry.request.local_publication_run_id===action.runId&&entry.request.stage===action.body.stage&&(entry.request.protocol.head_sha??entry.request.protocol.push?.head_sha)===action.headSha&&Object.entries(action.body).every(([key,value])=>same(entry.request.intent[key],value))}
/** Retry only the saved owner request; the host returns its original run rather than dispatching the effect again. */
export async function sendRemoteAction(action:RemoteAction){const entry=await fetchApi<RemoteEntry>(`/api/projects/${action.projectId}/runs/${encodeURIComponent(action.originRunId)}/remote-publications`,{method:'POST',body:JSON.stringify(action.body)});if(!matchesRemoteReceipt(entry,action))throw new Error('El recibo no corresponde a la solicitud original. Conservamos su versión y destino.');return entry}
/** Read saved bounded history without connecting to the remote server. */
export async function remoteHistory(project:number,task:number,local:string){const data=await fetchApi<RemoteHistory>(`/api/projects/${project}/code-publications/${encodeURIComponent(local)}/remote-publications`);if(data.project_id!==project||data.task_id!==task||data.local_publication_run_id!==local)throw new Error('El historial no corresponde a esta publicación.');return data}
/** Observe the registered server only on explicit owner request; branch edits require another observation. */
export async function previewRemote(project:number,task:number,local:string,target:string,base:string){const data=await fetchApi<RemotePreview>(`/api/projects/${project}/code-publications/${encodeURIComponent(local)}/remote-preview`,{method:'POST',body:JSON.stringify({target_ref:target,base_ref:base})});if(data.project_id!==project||data.task_id!==task||data.local_publication_run_id!==local||data.target_ref!==target||data.base_ref!==base)throw new Error('La observación no corresponde al destino solicitado.');return data}
/** Preserve the exact uncertain attempt and fence before its first readonly recovery request. */
export function prepareRemoteRecovery(projectId:number,taskId:number,runId:string,remoteRunId:string,attempt:string,fence:number):RemoteRecoveryAction{const a:RemoteRecoveryAction={schema:1,kind:'observe-remote',projectId,taskId,runId,remoteRunId,body:{operation_key:crypto.randomUUID(),attempt_id:attempt,expected_fence:fence}};parseRecovery(a);return Object.freeze({...a,body:Object.freeze(a.body)})}
/** Verify the original observer receipt after a lost reply; uncertainty never becomes a publication retry. */
export async function sendRemoteRecovery(action:RemoteRecoveryAction){const result=await fetchApi<RemoteRecoveryReceipt>(`/api/projects/${action.projectId}/remote-publications/${encodeURIComponent(action.remoteRunId)}/recovery`,{method:'POST',body:JSON.stringify(action.body)});if(result.run_id!==action.remoteRunId||result.source_attempt_id!==action.body.attempt_id||result.recovery_operation_key!==action.body.operation_key||typeof result.effects_confirmed!=='boolean')throw new Error('El recibo no corresponde a la consulta original. Conservamos su intento.');return result}
