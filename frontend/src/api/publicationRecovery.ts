/** Exact owner requests for readonly recovery of original local publication effects. @module */
import {fetchApi} from './client.ts'
import {ownerActionStore} from './ownerActions.ts'

/** Keep author selection separate from the actual publication run and original fenced attempt. */
export type PublicationRecoveryAction=Readonly<{schema:1;kind:'observe-publication';projectId:number;taskId:number;runId:string;publicationRunId:string;body:Readonly<{operation_key:string;attempt_id:string;expected_fence:number}>}>
/** Historical observation; published, not applied and uncertain remain distinct. */
export interface PublicationRecoveryReceipt {run_id:string;source_attempt_id:string;recovery_operation_key:string;publication_performed:boolean;completed_after_withdrawal:boolean;observed:{state:'published'|'not_applied'|'uncertain';target_current:boolean}}

/** Refuse damaged original provenance instead of silently replacing the attempt being inspected. */
function parse(value:unknown):PublicationRecoveryAction {
  const action=value as PublicationRecoveryAction,body=action.body
  if(action.kind!=='observe-publication' || typeof action.publicationRunId!=='string' || !action.publicationRunId || action.publicationRunId.length>128 || typeof body.attempt_id!=='string' || !/^[A-Za-z0-9_.:-]{1,128}$/.test(body.attempt_id) || !Number.isSafeInteger(body.expected_fence) || body.expected_fence<1 || Object.keys(body).sort().join(',')!=='attempt_id,expected_fence,operation_key')throw new Error('Invalid original publication recovery packet')
  return action
}
/** Persist the recovery intent independently of the original publication intent. */
export const publicationRecoveryActions=ownerActionStore<PublicationRecoveryAction>('publication-recovery',parse)

/** Save the original observation target; retries never refresh its attempt or fence. */
export function preparePublicationRecovery(projectId:number,taskId:number,runId:string,publicationRunId:string,attemptId:string,fence:number):PublicationRecoveryAction {
  const action:PublicationRecoveryAction={schema:1,kind:'observe-publication',projectId,taskId,runId,publicationRunId,body:{operation_key:crypto.randomUUID(),attempt_id:attemptId,expected_fence:fence}}
  parse(action);return Object.freeze({...action,body:Object.freeze({...action.body})})
}
/** A lost reply retries the same readonly recovery command and validates its original durable receipt. */
export async function sendPublicationRecovery(action:PublicationRecoveryAction) {
  const result=await fetchApi<PublicationRecoveryReceipt>(`/api/projects/${action.projectId}/code-publications/${encodeURIComponent(action.publicationRunId)}/recovery`,{method:'POST',body:JSON.stringify(action.body)})
  if(result.run_id!==action.publicationRunId || result.source_attempt_id!==action.body.attempt_id || result.recovery_operation_key!==action.body.operation_key || !['published','not_applied','uncertain'].includes(result.observed.state))throw new Error('El recibo no corresponde al intento original. Conservamos la solicitud para comprobarla.')
  return result
}
