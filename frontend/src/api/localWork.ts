/** Bounded local-work history and exact owner permission recovery; no worker execution endpoint. @module */
import {fetchApi} from './client.ts'
import type {OwnerActionStorage} from './ownerActions.ts'

/** One original calculation and a current read-only observation of whether it can have a successor. */
export interface LocalCalculation {sequence:number;project_id:number;operation_id:string;kind:string;input_bytes:number;attempt_id:string|null;status:string;observed_cpu_ms:number|null;cpu_ceiling_ms:number;created_at:number;diagnosis:{code:string;message:string;can_continue:boolean}}
/** A bounded page retains the exact project and a stable original-record cursor. */
export interface LocalPage {project_id:number;items:LocalCalculation[];next_before:number|null}
/** Freeze the project and exact original operation before sending an explicit continuation decision. */
export interface LocalAction {schema:1;projectId:number;body:Readonly<{operation_key:string;source_operation_id:string;reason:string}>}
/** Permission names one future calculation and explicitly confirms that this write started no work. */
export type LocalReceipt = LocalAction['body'] & {project_id:number;successor_operation_id:string;generation:number;work_started:false}
/** Keep unresolved local-work decisions separate from policy changes and from every other project. */
const key=(projectId:number)=>`researcher:local-continuation:v1:${projectId}`
/** Validate stored decisions without silently repairing scope, identities or payload fields. */
function parse(value:unknown,projectId:number):LocalAction {
 const a=value as LocalAction,b=a?.body
 if(!Number.isSafeInteger(projectId)||projectId<1||a?.schema!==1||a.projectId!==projectId||!b||Object.keys(b).sort().join(',')!=='operation_key,reason,source_operation_id'||typeof b.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(b.operation_key)||typeof b.source_operation_id!=='string'||!/^[0-9a-f]{64}$/.test(b.source_operation_id)||typeof b.reason!=='string'||new TextEncoder().encode(b.reason).length>2000)throw new Error('No se pudo validar la autorización original. Conserva su registro antes de continuar.')
 return Object.freeze({...a,body:Object.freeze({...b})})
}
/** Observe history on demand; an observation neither repeats work nor authorizes a successor. */
export function localWork(projectId:number,before:number|null=null){return fetchApi<LocalPage>(`/api/projects/${projectId}/local-work${before===null?'':`?before=${before}`}`)}
/** Construct an explicit decision for one original operation without sending or persisting it. */
export function prepareLocalContinuation(projectId:number,operation:string,reason:string):LocalAction{return parse({schema:1,projectId,body:{operation_key:crypto.randomUUID(),source_operation_id:operation,reason}},projectId)}
/** Restore the identical pending permission after reload; never substitute the currently selected calculation. */
export function loadLocalAction(storage:Pick<Storage,'getItem'>,projectId:number):LocalAction|null {const raw=storage.getItem(key(projectId));if(raw===null)return null;if(raw.length>10000)throw new Error('La autorización guardada supera el tamaño permitido.');return parse(JSON.parse(raw),projectId)}
/** Persist the complete decision before its first network write, refusing to replace unresolved intent. */
export function saveLocalAction(storage:OwnerActionStorage,action:LocalAction){const checked=parse(action,action.projectId),old=loadLocalAction(storage,action.projectId);if(old&&JSON.stringify(old)!==JSON.stringify(checked))throw new Error('Hay una autorización pendiente. Consulta primero su recibo.');storage.setItem(key(action.projectId),JSON.stringify(checked))}
/** Remove only a resolved original packet; leave any newer decision untouched. */
export function clearLocalAction(storage:OwnerActionStorage,action:LocalAction){if(JSON.stringify(loadLocalAction(storage,action.projectId))===JSON.stringify(action))storage.removeItem(key(action.projectId))}
/** Match project, command, source and explicit non-execution before clearing uncertain local state. */
function verify(receipt:LocalReceipt,action:LocalAction){if(receipt.project_id!==action.projectId||receipt.work_started!==false||typeof receipt.successor_operation_id!=='string'||!/^[0-9a-f]{64}$/.test(receipt.successor_operation_id)||!Number.isSafeInteger(receipt.generation)||receipt.generation<1||Object.entries(action.body).some(([k,v])=>receipt[k as keyof LocalReceipt]!==v))throw new Error('El recibo no corresponde a esta autorización. Conservamos la solicitud original.');return receipt}
/** Submit or explicitly resend the same permission; server identity prevents a second successor. */
export async function sendLocalContinuation(action:LocalAction){return verify(await fetchApi<LocalReceipt>(`/api/projects/${action.projectId}/local-work/continuations`,{method:'POST',body:JSON.stringify(action.body)}),action)}
/** Recover a lost response using a read only, without repeating the mutation or the calculation. */
export async function readLocalContinuation(action:LocalAction){return verify(await fetchApi<LocalReceipt>(`/api/projects/${action.projectId}/local-work/continuations/${encodeURIComponent(action.body.operation_key)}`),action)}
