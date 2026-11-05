/** Exact owner adoption of current corrected graph premises, preserving the original decision across lost replies. @module */
import {fetchApi} from './client.ts'
import {ownerActionStore} from './ownerActions.ts'

/** Current metadata and attributed corrections are offered for a new owner decision, never presented as the original model's revised proposal. */
export interface CorrectedTask {task_id:number;context_version:number;task:{title:string;description:string;acceptance_criteria:string;type:string};depends_on:number[];corrections:{source_kind:string;statement:string}[]}
/** Side-by-side observed premises distinguish actual text changes from propagated context invalidation. */
export interface GraphChange {task_id?:number;changes?:Record<string,{before:unknown;after:unknown}>;project?:{before:{name:string;description:string|null};after:{name:string;description:string|null}}}
/** Readonly exact snapshot includes current accepted results and old execution/effect observations. */
export interface GraphRevisionState {
 project_id:number;execution_id:string;plan_run_id:string;eligible:boolean;snapshot_sha256:string|null;manifest_sha256:string|null;blocked_reason:string
 snapshot:{previous_revision:number;changes:GraphChange[];corrected_tasks:CorrectedTask[];retained_results:{task_id:number;run_id:string}[];history:{run:{run_id:string};attempts:{effects:unknown[];inference:{observed_tokens:number|null}|null}[]}[];limitations:string[]}|null
}
/** Persisted graph adoption records expected new delivery scope separately from its minimal server command. */
export interface GraphAction {readonly schema:1;readonly kind:'plan-reauthorization';readonly projectId:number;readonly taskId:number;readonly runId:string;readonly executionId:string;readonly manifestSha256:string;readonly authorizationRevision:number;readonly replacementTaskIds:readonly number[];readonly retainedRunIds:readonly string[];readonly body:Readonly<{operation_key:string;snapshot_sha256:string}>}
/** The receipt confirms exact owner adoption, while dispatch remains paused for a separate resume. */
export interface GraphReceipt {project_id:number;plan_run_id:string;execution_id:string;authorization_revision:number;manifest_sha256:string;operation_key:string;snapshot_sha256:string;status:'paused';inference_started:false;deliveries:Record<string,string>;retained_results:{task_id:number;run_id:string}[]}

/** Bounded references protect URL scope and receipt matching. */
function reference(value:unknown):value is string{return typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value)}
/** Reject damaged or expanded commands rather than silently adopting a new snapshot on reload. */
function parse(value:unknown):GraphAction {
 const a=value as GraphAction,b=a.body
 if(a.kind!=='plan-reauthorization'||![a.executionId,a.runId].every(reference)||!/^[a-f0-9]{64}$/.test(a.manifestSha256)||!/^[a-f0-9]{64}$/.test(b.snapshot_sha256)||!Number.isSafeInteger(a.authorizationRevision)||a.authorizationRevision<1||Object.keys(b).sort().join(',')!=='operation_key,snapshot_sha256'||!Array.isArray(a.replacementTaskIds)||!a.replacementTaskIds.every(v=>Number.isSafeInteger(v)&&v>0)||new Set(a.replacementTaskIds).size!==a.replacementTaskIds.length||!Array.isArray(a.retainedRunIds)||!a.retainedRunIds.every(reference)||new Set(a.retainedRunIds).size!==a.retainedRunIds.length)throw new Error('Invalid original graph adoption decision')
 return {...a,replacementTaskIds:Object.freeze([...a.replacementTaskIds]),retainedRunIds:Object.freeze([...a.retainedRunIds])}
}
/** A separate namespace keeps graph adoption distinct from result acceptance, execution controls and single-delivery continuation. */
export const graphActions=ownerActionStore<GraphAction>('plan-reauthorization',parse)
/** Freeze the inspected graph and exact expected result scope before the first POST. */
export function prepareGraphAction(projectId:number,taskId:number,runId:string,executionId:string,state:GraphRevisionState):GraphAction {
 if(state.project_id!==projectId||state.execution_id!==executionId||state.plan_run_id!==runId||!state.eligible||!state.snapshot||!state.snapshot_sha256||!state.manifest_sha256)throw new Error('Consulta el grafo actual antes de adoptarlo.')
 const retained=new Set(state.snapshot.retained_results.map(r=>r.task_id))
 const a:GraphAction={schema:1,kind:'plan-reauthorization',projectId,taskId,runId,executionId,manifestSha256:state.manifest_sha256,authorizationRevision:state.snapshot.previous_revision+1,replacementTaskIds:state.snapshot.corrected_tasks.filter(t=>!retained.has(t.task_id)).map(t=>t.task_id),retainedRunIds:state.snapshot.retained_results.map(r=>r.run_id),body:{operation_key:crypto.randomUUID(),snapshot_sha256:state.snapshot_sha256}}
 return Object.freeze({...parse(a),body:Object.freeze(a.body)})
}
/** Build the exact owner route from domain references rather than historical source text. */
function path(project:number,execution:string){return `/api/projects/${project}/plan-executions/${encodeURIComponent(execution)}/reauthorization`}
/** Validate actual preview scope before offering a corrected graph for adoption. */
export async function graphRevisionState(project:number,run:string,execution:string){const s=await fetchApi<GraphRevisionState>(path(project,execution));if(s.project_id!==project||s.plan_run_id!==run||s.execution_id!==execution)throw new Error('La revisión no corresponde a este plan.');return s}
/** Send only the saved decision and retain uncertainty on foreign, incomplete or differently scoped receipts. */
export async function sendGraphAction(a:GraphAction){
 parse(a)
 const r=await fetchApi<GraphReceipt>(path(a.projectId,a.executionId),{method:'POST',body:JSON.stringify(a.body)})
 if(r.project_id!==a.projectId||r.plan_run_id!==a.runId||r.execution_id!==a.executionId||r.authorization_revision!==a.authorizationRevision||r.manifest_sha256!==a.manifestSha256||r.operation_key!==a.body.operation_key||r.snapshot_sha256!==a.body.snapshot_sha256||r.status!=='paused'||r.inference_started!==false||!r.deliveries||Object.keys(r.deliveries).sort().join(',')!==a.replacementTaskIds.map(String).sort().join(',')||!Object.values(r.deliveries).every(reference)||new Set(Object.values(r.deliveries)).size!==Object.values(r.deliveries).length||!Array.isArray(r.retained_results)||r.retained_results.map(v=>v.run_id).sort().join(',')!==[...a.retainedRunIds].sort().join(','))throw new Error('El recibo no corresponde al grafo y revisión originales. Conservamos la solicitud.')
 return r
}
