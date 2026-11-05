/** Native project starts and explicit exact-plan owner decisions, separate from task execution. @module */
import {fetchApi} from './client.ts'
import {ownerActionStore,type OwnerActionStorage} from './ownerActions.ts'
import type {RuntimeRun} from './runtime.ts'

/** Local graph references are proposal data, never server identities or agent permissions. */
export interface ProposedTask {key:string;epic_key:string;type:'research'|'code'|'bug_fix';title:string;description:string;acceptance_criteria:string;priority:number;depends_on:string[]}
/** A justified append-only graph separates observed basis from assumptions the owner can correct. */
export interface ProjectPlanDraft {title:string;rationale:string;assumptions:string[];basis:{source:string;quote:string}[];epics:{key:string;title:string;description:string}[];tasks:ProposedTask[]}
/** Original material, proposal and distinct acceptance remain readable after withdrawal. */
export interface ProjectPlanState {project_id:number;task_id:number;run_id:string;context_version:number;snapshot:{project:{name:string;description:string|null};owner_request:string;instruction_origin:'owner_message'|'host_default';source_origins?:Record<string,string>;sources:Record<string,string>};proposal:{proposal_sha256:string;draft:ProjectPlanDraft}|null;acceptance:PlanAcceptanceReceipt|null;acceptance_current:boolean;eligible:boolean;blocked_reason:string}
/** Owner expansion returns original created IDs and explicitly does not start child work. */
export interface PlanAcceptanceReceipt {project_id:number;task_id:number;run_id:string;operation_key:string;proposal_sha256:string;context_version:number;epics:Record<string,number>;tasks:Record<string,number>;execution_started:false}
/** Persist one exact observed proposal/version before releasing the first acceptance POST. */
export type PlanAcceptanceAction=Readonly<{schema:1;kind:'accept-plan';projectId:number;taskId:number;runId:string;body:Readonly<{operation_key:string;proposal_sha256:string;context_version:number}>}>

/** Reject a damaged local decision instead of refreshing the proposal on reload. */
function parse(value:unknown):PlanAcceptanceAction {const a=value as PlanAcceptanceAction,b=a.body;if(a.kind!=='accept-plan'||!/^[a-f0-9]{64}$/.test(b.proposal_sha256)||!Number.isSafeInteger(b.context_version)||b.context_version<1||Object.keys(b).sort().join(',')!=='context_version,operation_key,proposal_sha256')throw new Error('Invalid original plan decision');return a}
/** Keep plan packets separate from research-result and code acceptance. */
export const planActions=ownerActionStore<PlanAcceptanceAction>('project-plan',parse)
/** Freeze the exact proposal, context and original request key; retries reuse this packet. */
export function preparePlanAcceptance(projectId:number,taskId:number,runId:string,proposalSha:string,contextVersion:number):PlanAcceptanceAction{const a:PlanAcceptanceAction={schema:1,kind:'accept-plan',projectId,taskId,runId,body:{operation_key:crypto.randomUUID(),proposal_sha256:proposalSha,context_version:contextVersion}};parse(a);return Object.freeze({...a,body:Object.freeze(a.body)})}
/** Validate both original identity and the explicit absence of execution permission. */
export function matchesPlanReceipt(r:PlanAcceptanceReceipt,a:PlanAcceptanceAction){return r.project_id===a.projectId&&r.task_id===a.taskId&&r.run_id===a.runId&&r.operation_key===a.body.operation_key&&r.proposal_sha256===a.body.proposal_sha256&&r.context_version===a.body.context_version&&r.execution_started===false&&r.tasks&&Object.keys(r.tasks).length>0&&Object.values(r.tasks).every(id=>Number.isSafeInteger(id)&&id>0)}
/** Read a saved proposal without invoking a planner or creating work. */
export async function projectPlanState(project:number,task:number,run:string){const data=await fetchApi<ProjectPlanState>(`/api/projects/${project}/runs/${encodeURIComponent(run)}/project-plan`);if(data.project_id!==project||data.task_id!==task||data.run_id!==run)throw new Error('La propuesta no corresponde a esta tarea.');return data}
/** Accept only the original observed version and retain the packet after an uncertain response. */
export async function sendPlanAcceptance(action:PlanAcceptanceAction){const receipt=await fetchApi<PlanAcceptanceReceipt>(`/api/projects/${action.projectId}/runs/${encodeURIComponent(action.runId)}/project-plan/accept`,{method:'POST',body:JSON.stringify(action.body)});if(!matchesPlanReceipt(receipt,action))throw new Error('El recibo no corresponde a esta aceptación de plan. Conservamos la solicitud original.');return receipt}

/** A project start exists before its planning task ID is known. */
interface PlanningStart {schema:1;projectId:number;body:{operation_key:string;prompt:null;repository_id:null}}
/** Actual native start receipt includes the saved original request and selected planning task. */
export interface PlanningStartReceipt {request:PlanningStart['body'];planning_task_id:number;run:RuntimeRun&{actor_id:string}}
/** Save before starting; a reload or edited project description cannot turn a lost reply into another native turn. */
export async function startProjectPlanning(storage:OwnerActionStorage,projectId:number){
 const key=`researcher:project-plan-start:v1:${projectId}`
 let action:PlanningStart
 const raw=storage.getItem(key)
 if(raw!==null){try{action=JSON.parse(raw);if(action.schema!==1||action.projectId!==projectId||!action.body||!/^[A-Za-z0-9_.:-]{1,128}$/.test(action.body.operation_key)||action.body.prompt!==null||action.body.repository_id!==null||Object.keys(action.body).sort().join(',')!=='operation_key,prompt,repository_id')throw new Error('scope')}catch{throw new Error('No se pudo recuperar el inicio original. Consulta el historial del proyecto antes de preparar otro.')}}
 else{action={schema:1,projectId,body:{operation_key:crypto.randomUUID(),prompt:null,repository_id:null}};storage.setItem(key,JSON.stringify(action))}
 const receipt=await fetchApi<PlanningStartReceipt>(`/api/projects/${projectId}/start`,{method:'POST',body:JSON.stringify(action.body)})
 if(receipt.run.project_id!==projectId||receipt.run.task_id!==receipt.planning_task_id||!Number.isSafeInteger(receipt.planning_task_id)||receipt.planning_task_id<=0||receipt.run.actor_id!=='native-project-planner'||receipt.run.execution_kind!=='research'||!receipt.request||receipt.request.operation_key!==action.body.operation_key||receipt.request.prompt!==action.body.prompt||receipt.request.repository_id!==action.body.repository_id)throw new Error('El recibo no corresponde al inicio original. Conservamos la solicitud.')
 if(storage.getItem(key)===JSON.stringify(action))storage.removeItem(key)
 return receipt
}
