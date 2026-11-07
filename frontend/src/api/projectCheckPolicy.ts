/** Explicit project CI decisions and recovery of their original receipts. @module */
import {fetchApi} from './client.ts'
import type {OwnerActionStorage} from './ownerActions.ts'

/** Strict mode requires executed tests; the alternate mode still requires explicit limits acknowledgement. */
export type CheckPolicyMode='require_tests'|'allow_missing'
/** Revision zero means the owner has not made a project choice. */
export interface CheckPolicy {revision:number;mode:CheckPolicyMode|null}
/** Durable project-scoped decision retained across reloads and uncertain responses. */
export interface CheckPolicyAction {schema:1;projectId:number;body:Readonly<{operation_key:string;expected_revision:number;mode:CheckPolicyMode}>}
/** Original immutable decision, distinct from the policy currently in force. */
export type CheckPolicyReceipt=CheckPolicyAction['body']&{project_id:number;revision:number;inference_started:false;applies_to:'future_code_acceptances'}
/** Keep policy commands separate from task acceptance and project budget commands. */
const key=(projectId:number)=>`researcher:project-check-policy:v1:${projectId}`
/** Validate a saved packet without silently changing its scope, revision or choice. */
function parse(value:unknown,projectId:number):CheckPolicyAction {
 const a=value as CheckPolicyAction,b=a?.body
 if(!Number.isSafeInteger(projectId)||projectId<1||a?.schema!==1||a.projectId!==projectId||!b||Object.keys(b).sort().join(',')!=='expected_revision,mode,operation_key'||!Number.isSafeInteger(b.expected_revision)||b.expected_revision<0||b.expected_revision>=Number.MAX_SAFE_INTEGER||!['require_tests','allow_missing'].includes(b.mode)||typeof b.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key))throw new Error('No se pudo validar la decisión guardada de comprobaciones.')
 return Object.freeze({...a,body:Object.freeze({...b})})
}
/** Freeze a fresh observed policy revision before any network mutation. */
export function prepareCheckPolicy(projectId:number,revision:number,mode:CheckPolicyMode){return parse({schema:1,projectId,body:{operation_key:crypto.randomUUID(),expected_revision:revision,mode}},projectId)}
/** Recover exactly the pending decision for this project. */
export function loadCheckPolicy(storage:Pick<Storage,'getItem'>,projectId:number){const raw=storage.getItem(key(projectId));if(raw===null)return null;if(raw.length>2000)throw new Error('La decisión guardada excede el tamaño permitido.');return parse(JSON.parse(raw),projectId)}
/** Persist before sending and refuse to replace an unresolved decision. */
export function saveCheckPolicy(storage:OwnerActionStorage,action:CheckPolicyAction){const checked=parse(action,action.projectId),old=loadCheckPolicy(storage,action.projectId);if(old&&JSON.stringify(old)!==JSON.stringify(checked))throw new Error('Consulta el recibo de la decisión pendiente.');storage.setItem(key(action.projectId),JSON.stringify(checked))}
/** Clear only the exact resolved or definitively rejected original packet. */
export function clearCheckPolicy(storage:OwnerActionStorage,action:CheckPolicyAction){if(JSON.stringify(loadCheckPolicy(storage,action.projectId))===JSON.stringify(action))storage.removeItem(key(action.projectId))}
/** Compare the original payload and scope before presenting a receipt as this decision. */
function verify(receipt:CheckPolicyReceipt,action:CheckPolicyAction){if(receipt.project_id!==action.projectId||receipt.revision!==action.body.expected_revision+1||receipt.inference_started!==false||receipt.applies_to!=='future_code_acceptances'||Object.entries(action.body).some(([k,v])=>receipt[k as keyof CheckPolicyReceipt]!==v))throw new Error('El recibo no corresponde a la decisión original. Conservamos la solicitud.');return receipt}
/** Send the frozen choice; identical retries recover the same backend decision. */
export async function sendCheckPolicy(action:CheckPolicyAction){return verify(await fetchApi<CheckPolicyReceipt>(`/api/projects/${action.projectId}/check-policy`,{method:'POST',body:JSON.stringify(action.body)}),action)}
/** Recover a response without resending or substituting the newest project policy. */
export async function readCheckPolicyReceipt(action:CheckPolicyAction){return verify(await fetchApi<CheckPolicyReceipt>(`/api/projects/${action.projectId}/check-policy/changes/${encodeURIComponent(action.body.operation_key)}`),action)}
