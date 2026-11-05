/** Distinct owner execution decisions and typed causal work deliveries, with exact packets retained after uncertain replies. @module */
import {fetchApi} from './client.ts'
import {ownerActionStore} from './ownerActions.ts'

/** Original causal data is evidence, not an agent command extracted from chat. */
export interface WorkDelivery {delivery_id:string;predecessor_delivery_id:string|null;current:boolean;task_id:number;run_id:string|null;status:string;issue:{code:string;next_action:string}|null;handoff:{kind:'work.request';cause:{plan_run_id:string};prerequisites:{task_id:number;run_id:string;kind:string;context_version:number}[]}|null}
/** A current graph context and its original execution remain distinct from plan acceptance. */
export interface ExecutionState {project_id:number;task_id:number;plan_run_id:string;manifest_sha256:string|null;manifest:{tasks:{task_id:number;title:string;type:string;depends_on:number[]}[]}|null;eligible:boolean;blocked_reason:string;execution:{execution_id:string;operation_key:string;manifest_sha256:string;status:'active'|'paused';current:boolean;deliveries:WorkDelivery[]}|null}
/** One immutable execute/pause/resume request; controls identify their original execution. */
export interface ExecutionAction {readonly schema:1;readonly kind:'plan-execution';readonly projectId:number;readonly taskId:number;readonly runId:string;readonly executionId:string|null;readonly body:Readonly<{operation_key:string;manifest_sha256:string;status?:'active'|'paused'}>}
/** The receipt acknowledges original intent, while current physical state is read separately. */
export interface ExecutionReceipt {project_id:number;task_id:number;plan_run_id:string;execution_id:string;operation_key:string;manifest_sha256:string;status:'active'|'paused'}

/** Reject damaged/extra fields rather than rebuilding a different intent on reload. */
function parse(value:unknown):ExecutionAction {const a=value as ExecutionAction,b=a.body,control=a.executionId!==null;if(a.kind!=='plan-execution'||!/^[a-f0-9]{64}$/.test(b.manifest_sha256)||!(a.executionId===null||(typeof a.executionId==='string'&&a.executionId.length>0&&a.executionId.length<=128))||Object.keys(b).sort().join(',')!==(control?'manifest_sha256,operation_key,status':'manifest_sha256,operation_key')||(control&&!['active','paused'].includes(b.status??'')))throw new Error('Invalid original execution decision');return a}
/** Execution packets cannot overwrite pending plan-acceptance or result decisions. */
export const executionActions=ownerActionStore<ExecutionAction>('plan-execution',parse)
/** Freeze observed graph context before releasing the first owner execution/control request. */
export function prepareExecutionAction(projectId:number,taskId:number,runId:string,manifest:string,status:'execute'|'active'|'paused',executionId?:string):ExecutionAction{const action:ExecutionAction={schema:1,kind:'plan-execution',projectId,taskId,runId,executionId:status==='execute'?null:executionId??null,body:{operation_key:crypto.randomUUID(),manifest_sha256:manifest,...(status==='execute'?{}:{status})}};if(status!=='execute'&&!executionId)throw new Error('A control requires its original execution');parse(action);return Object.freeze({...action,body:Object.freeze(action.body)})}
/** Check exact scope and operation identity; a foreign receipt must remain unresolved locally. */
export function matchesExecutionReceipt(r:ExecutionReceipt,a:ExecutionAction){return r.project_id===a.projectId&&r.task_id===a.taskId&&r.plan_run_id===a.runId&&typeof r.execution_id==='string'&&r.execution_id.length>0&&(a.executionId===null||r.execution_id===a.executionId)&&r.operation_key===a.body.operation_key&&r.manifest_sha256===a.body.manifest_sha256&&r.status===(a.body.status??'active')}
/** Inspect the original graph and delivery states without activating inference. */
export async function executionState(project:number,task:number,run:string){const data=await fetchApi<ExecutionState>(`/api/projects/${project}/runs/${encodeURIComponent(run)}/project-plan/execution`);if(data.project_id!==project||data.task_id!==task||data.plan_run_id!==run)throw new Error('La ejecución no corresponde a este plan.');return data}
/** Send only the persisted intent; an uncertain reply is retried using this same packet. */
export async function sendExecutionAction(a:ExecutionAction){parse(a);const url=a.executionId===null?`/api/projects/${a.projectId}/runs/${encodeURIComponent(a.runId)}/project-plan/execution`:`/api/projects/${a.projectId}/plan-executions/${encodeURIComponent(a.executionId)}/control`;const receipt=await fetchApi<ExecutionReceipt>(url,{method:'POST',body:JSON.stringify(a.body)});if(!matchesExecutionReceipt(receipt,a))throw new Error('El recibo no corresponde a la decisión original de ejecución. Conservamos la solicitud.');return receipt}
