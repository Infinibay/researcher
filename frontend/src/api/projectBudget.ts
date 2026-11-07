/** Exact project-budget decisions and receipt recovery; never start or resume work. @module */
import {fetchApi} from './client.ts'
import type {OwnerActionStorage} from './ownerActions.ts'

/** Freeze the original project, version and total limits before a network write. */
export interface BudgetAction {readonly schema:1;readonly projectId:number;readonly body:Readonly<{operation_key:string;expected_revision:number;turn_limit:number;token_limit:number;reason:string;auxiliary_operation_limit?:number;auxiliary_cpu_ms_limit?:number}>}
/** A committed policy revision confirms only changed capacity, never execution. */
export type BudgetReceipt = BudgetAction['body'] & {project_id:number;revision:number;inference_started:false}
/** Use a project key because budget policy has no task/run identity. */
const key=(projectId:number)=>`researcher:project-budget:v1:${projectId}`
/** Reject ambiguous scope, lossy integers and corrupted packets instead of inventing a new decision. */
function parse(value:unknown,projectId:number):BudgetAction {
 const a=value as BudgetAction,b=a?.body
 const fields=b?Object.keys(b).sort().join(','):''
 const base='expected_revision,operation_key,reason,token_limit,turn_limit',extended='auxiliary_cpu_ms_limit,auxiliary_operation_limit,'+base
 const localValid=fields===base||(fields===extended&&[b.auxiliary_operation_limit,b.auxiliary_cpu_ms_limit].every(v=>typeof v==='number'&&Number.isSafeInteger(v)&&v>0))
 if(!Number.isSafeInteger(projectId)||projectId<1||a?.schema!==1||a.projectId!==projectId||!b||!localValid||typeof b.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key)||!Number.isSafeInteger(b.expected_revision)||b.expected_revision<0||![b.turn_limit,b.token_limit].every(v=>Number.isSafeInteger(v)&&v>0)||typeof b.reason!=='string'||new TextEncoder().encode(b.reason).length>2000)throw new Error('No se pudo validar la decisión original de presupuesto. Conserva su identidad antes de continuar.')
 return Object.freeze({...a,body:Object.freeze({...b})})
}
/** Create a version-bound decision; this alone neither persists nor sends it. */
export function prepareBudgetChange(projectId:number,revision:number,turns:number,tokens:number,reason:string,local?:{operations:number;cpuMs:number}):BudgetAction{return parse({schema:1,projectId,body:{operation_key:crypto.randomUUID(),expected_revision:revision,turn_limit:turns,token_limit:tokens,reason,...(local?{auxiliary_operation_limit:local.operations,auxiliary_cpu_ms_limit:local.cpuMs}:{})}},projectId)}
/** Recover the exact pending decision after reload, keeping other projects separate. */
export function loadBudgetAction(storage:Pick<Storage,'getItem'>,projectId:number):BudgetAction|null {const raw=storage.getItem(key(projectId));if(raw===null)return null;if(raw.length>10000)throw new Error('La decisión guardada supera el tamaño permitido.');return parse(JSON.parse(raw),projectId)}
/** Persist before sending, refusing to replace another unresolved original packet. */
export function saveBudgetAction(storage:OwnerActionStorage,action:BudgetAction){const checked=parse(action,action.projectId),old=loadBudgetAction(storage,action.projectId);if(old&&JSON.stringify(old)!==JSON.stringify(checked))throw new Error('Hay una decisión pendiente para este proyecto. Consulta su recibo.');storage.setItem(key(action.projectId),JSON.stringify(checked))}
/** Clear only this resolved/rejected packet; a newer original decision remains intact. */
export function clearBudgetAction(storage:OwnerActionStorage,action:BudgetAction){if(JSON.stringify(loadBudgetAction(storage,action.projectId))===JSON.stringify(action))storage.removeItem(key(action.projectId))}
/** Check original scope, payload, next revision and absence of execution in both POST and recovery responses. */
function verify(receipt:BudgetReceipt,action:BudgetAction){if(receipt.project_id!==action.projectId||receipt.revision!==action.body.expected_revision+1||receipt.inference_started!==false||Object.entries(action.body).some(([k,v])=>receipt[k as keyof BudgetReceipt]!==v))throw new Error('El recibo no corresponde a la decisión original. Conservamos la solicitud.');return receipt}
/** Submit or explicitly retry the identical packet; server identity prevents applying it twice. */
export async function sendBudgetChange(action:BudgetAction){return verify(await fetchApi<BudgetReceipt>(`/api/projects/${action.projectId}/work-budget`,{method:'POST',body:JSON.stringify(action.body)}),action)}
/** Query a receipt without resending a mutation or substituting the current policy. */
export async function readBudgetReceipt(action:BudgetAction){return verify(await fetchApi<BudgetReceipt>(`/api/projects/${action.projectId}/work-budget/changes/${encodeURIComponent(action.body.operation_key)}`),action)}
