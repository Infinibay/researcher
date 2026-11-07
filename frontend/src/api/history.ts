/** Owner history and local work accounting, without native execution authority. @module */
import {buildUrl, fetchApi} from './client'
import type {RuntimeRun} from './runtime'

/** Stable descending history page within one explicit project and subject. */
export interface HistoryPage<T> {
 project_id:number;task_id?:number;run_id?:string;total:number;items:T[];next_before_seq:string|null
}
/** Original attempt observations; missing dispatch and usage remain unknown. */
export interface RunAttempt {
 seq:string;attempt_id:string;is_current:boolean;status:string;started_at:number;ended_at:number|null
 model:string|null;model_selection:{reasoning_effort:string}|null
 observed_tokens:number|null;token_ceiling:number|null;dispatch_status:string|null
 result:{native_status:string;summary:string}|null
}
/** Lifetime admission capacity, not physical token consumption or subscription billing. */
export interface ProjectWorkBudget {
 project_id:number;policy:{turn_limit:number;token_limit:number;revision:number}|null
 used_turns:number;observed_tokens:number|null;unmeasured_dispatches:number;unsettled_dispatches:number
 accounted_tokens:number;held_tokens:number;remaining_turns:number|null;remaining_tokens:number|null;overrun_tokens:number|null
 auxiliary?:{policy:{operation_limit:number;cpu_ms_limit:number};used_operations:number;observed_cpu_ms:number|null;unknown_operations:number;pending_operations:number;accounted_cpu_ms:number;held_cpu_ms:number;remaining_operations:number;remaining_cpu_ms:number;input_bytes:number}
}
/** Read older task runs independently of the current execution controls. */
export function taskRunHistory(projectId:number,taskId:number,beforeSeq:string|null=null){
 return fetchApi<HistoryPage<RuntimeRun>>(buildUrl(`/api/projects/${projectId}/tasks/${taskId}/run-history`,{before_seq:beforeSeq,limit:25}))
}
/** Read original attempt receipts instead of substituting the current model or result. */
export function runAttempts(projectId:number,runId:string,beforeSeq:string|null=null){
 return fetchApi<HistoryPage<RunAttempt>>(buildUrl(`/api/projects/${projectId}/runs/${encodeURIComponent(runId)}/attempts`,{before_seq:beforeSeq,limit:25}))
}
/** Read the same recorded capacity used by project admission. */
export function workBudget(projectId:number){return fetchApi<ProjectWorkBudget>(`/api/projects/${projectId}/work-budget`)}

/** Keep absent measurements distinct from a recorded zero. */
export function measuredTokens(value:number|null){return value==null?'No disponible':new Intl.NumberFormat('es-AR').format(value)}
