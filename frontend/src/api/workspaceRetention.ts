/** Original owner decisions for retained native work; response loss never changes the selected attempt or archive. @module */
import { fetchApi } from './client'

export interface RetainedWork { project_id:number;attempt_id:string;run_id:string;task_id:number;title:string;state:'available'|'quarantined'|'retained'|'removing'|'removed';preparation_state:string;retain_until:number|null;archive_sha256:string|null;bytes:number|null;changes:{state:string;tracked:number|null;untracked:number|null;ignored:number|null}|null }
export interface RetentionOperation {project_id:number;attempt_id:string;operation_key:string;kind:'archive'|'remove'|'restore';state:'pending'|'completed'|'superseded';issue:string|null;receipt:Record<string,unknown>|null;created_at:number;updated_at:number}
export interface RetentionAction {projectId:number;attemptId:string;kind:RetentionOperation['kind'];body:{operation_key:string;retention_days?:number;acknowledge_unavailability?:true;archive_sha256?:string}}
const key=(projectId:number)=>`researcher:retention:v1:${projectId}`

/** Freeze and validate the complete original decision before any request can be sent. */
export function saveRetentionAction(storage:Storage,action:RetentionAction){validate(action,action.projectId);storage.setItem(key(action.projectId),JSON.stringify(action))}
/** Reject malformed or foreign persisted actions instead of deriving a new target from the current selection. */
function validate(value:RetentionAction,projectId:number){
 if(!value||value.projectId!==projectId||!Number.isSafeInteger(projectId)||projectId<1||typeof value.attemptId!=='string'||!value.attemptId||!['archive','remove','restore'].includes(value.kind)||!value.body||typeof value.body.operation_key!=='string'||!/^[A-Za-z0-9_.:-]{1,128}$/.test(value.body.operation_key))throw new Error('La solicitud guardada no corresponde a este proyecto.')
 if(value.kind==='archive'?(value.body.acknowledge_unavailability!==true||!Number.isInteger(value.body.retention_days)||value.body.retention_days!<1||value.body.retention_days!>3650):!/^[0-9a-f]{64}$/.test(value.body.archive_sha256??''))throw new Error('La solicitud guardada está incompleta. Consulta su historial.')
 return value
}
/** Load an uncertain original request without automatically replaying it after navigation or reload. */
export function loadRetentionAction(storage:Storage,projectId:number){const raw=storage.getItem(key(projectId));return raw?validate(JSON.parse(raw),projectId):null}
/** Compare a received operation with the exact project, attempt, key and action before displaying it as confirmed admission. */
export function verifyRetentionOperation(operation:RetentionOperation,action:RetentionAction){if(operation.project_id!==action.projectId||operation.attempt_id!==action.attemptId||operation.operation_key!==action.body.operation_key||operation.kind!==action.kind)throw new Error('La respuesta no corresponde a la solicitud original. Se conserva para comprobarla.');return operation}
/** Send only the frozen original action; neither archive refresh nor a new restoration is inferred on retry. */
export async function sendRetentionAction(action:RetentionAction){validate(action,action.projectId);return verifyRetentionOperation(await fetchApi<RetentionOperation>(`/api/projects/${action.projectId}/retained-work/${encodeURIComponent(action.attemptId)}/${action.kind==='archive'?'quarantine':action.kind}`,{method:'POST',body:JSON.stringify(action.body)}),action)}
/** Observe the original receipt without admitting another filesystem effect. */
export async function readRetentionAction(action:RetentionAction){return verifyRetentionOperation(await fetchApi<RetentionOperation>(`/api/projects/${action.projectId}/retained-work/operations/${encodeURIComponent(action.body.operation_key)}`),action)}
/** Clear only the exact acknowledged packet; a later owner decision cannot be erased by an old response. */
export function clearRetentionAction(storage:Storage,action:RetentionAction){if(JSON.stringify(loadRetentionAction(storage,action.projectId))===JSON.stringify(action))storage.removeItem(key(action.projectId))}
