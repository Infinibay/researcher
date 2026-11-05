/** Exact owner permission for a successor, with original evidence retained across reload and lost replies. @module */
import {fetchApi} from './client.ts'
import {ownerActionStore} from './ownerActions.ts'

/** Historical inference, effects and jobs are evidence; none is an instruction to replay an action. */
export interface ContinuationSnapshot {
 previous_run:{run_id:string;attempt_id:string|null;status:string;issue:unknown}
 attempts:{attempt_id:string;inference:{status:string;observed_tokens:number|null;token_ceiling:number}|null;effects:{operation_key:string;kind:string;receipt:unknown}[];jobs:{id:string;status:string;exit_code:number|null}[]}[]
 candidate:{state:string;head_sha:string|null;diff_sha256:string|null}|null
 limitations:string[]
}
/** Readonly exact closure preview; a paused graph stays paused after successor authorization. */
export interface ContinuationState {project_id:number;execution_id:string;delivery_id:string;eligible:boolean;snapshot:ContinuationSnapshot|null;snapshot_sha256:string|null;blocked_reason:string;dispatch_status:'active'|'paused'}
/** Saved owner decision identifies the exact predecessor and observed evidence. */
export interface ContinuationAction {
 readonly schema:1;readonly kind:'plan-continuation';readonly projectId:number;readonly taskId:number;readonly runId:string
 readonly executionId:string;readonly deliveryId:string;readonly previousRunId:string
 readonly body:Readonly<{operation_key:string;snapshot_sha256:string}>
}
/** Authorization receipt describes the new delivery; physical inference and result acceptance remain separate. */
export interface ContinuationReceipt {project_id:number;plan_run_id:string;execution_id:string;predecessor_delivery_id:string;previous_run_id:string;delivery_id:string;operation_key:string;snapshot_sha256:string;inference_started:false}

/** Accept bounded domain references before constructing paths or matching a successor receipt. */
function reference(value:unknown):value is string {return typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value)}
/** Reject injected fields or damaged evidence instead of silently preparing new permission. */
function parse(value:unknown):ContinuationAction {
 const a=value as ContinuationAction,b=a.body
 if(a.kind!=='plan-continuation'||![a.executionId,a.deliveryId,a.previousRunId,a.runId].every(reference)||!/^[a-f0-9]{64}$/.test(b.snapshot_sha256)||Object.keys(b).sort().join(',')!=='operation_key,snapshot_sha256')throw new Error('Invalid original continuation decision')
 return a
}
/** Separate namespace preserves unrelated owner decisions and the original pending plan selection. */
export const continuationActions=ownerActionStore<ContinuationAction>('plan-continuation',parse)
/** Freeze observed predecessor evidence before the first POST. */
export function prepareContinuationAction(projectId:number,taskId:number,runId:string,executionId:string,deliveryId:string,previousRunId:string,snapshot:string):ContinuationAction {
 const a:ContinuationAction={schema:1,kind:'plan-continuation',projectId,taskId,runId,executionId,deliveryId,previousRunId,body:{operation_key:crypto.randomUUID(),snapshot_sha256:snapshot}}
 parse(a);return Object.freeze({...a,body:Object.freeze(a.body)})
}
/** Build one scoped owner route; paths never come from historical effect text. */
function path(project:number,execution:string,delivery:string){return `/api/projects/${project}/plan-executions/${encodeURIComponent(execution)}/deliveries/${encodeURIComponent(delivery)}/continuation`}
/** Validate actual project/execution/delivery scope before showing permission controls. */
export async function continuationState(project:number,execution:string,delivery:string){
 const state=await fetchApi<ContinuationState>(path(project,execution,delivery))
 if(state.project_id!==project||state.execution_id!==execution||state.delivery_id!==delivery)throw new Error('La observación no corresponde a esta entrega.')
 return state
}
/** Recover only the original decision; an unrelated receipt remains uncertain in local storage. */
export async function sendContinuationAction(a:ContinuationAction){
 parse(a)
 const r=await fetchApi<ContinuationReceipt>(path(a.projectId,a.executionId,a.deliveryId),{method:'POST',body:JSON.stringify(a.body)})
 if(r.project_id!==a.projectId||r.plan_run_id!==a.runId||r.execution_id!==a.executionId||r.predecessor_delivery_id!==a.deliveryId||r.previous_run_id!==a.previousRunId||!reference(r.delivery_id)||r.delivery_id===a.deliveryId||r.operation_key!==a.body.operation_key||r.snapshot_sha256!==a.body.snapshot_sha256||r.inference_started!==false)throw new Error('El recibo no corresponde a la sucesora original. Conservamos la solicitud.')
 return r
}
