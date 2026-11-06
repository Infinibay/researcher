/** Native agent history read through the owner session. @module */
import {fetchApi,buildUrl} from './client'
/** Saved run and current-attempt observations; missing usage remains null. */
export interface AgentRun {
 seq:string;run_id:string;project_id:number;task_id:number;task_title:string;task_type:string
 actor_id:string;execution_kind:string;context_version:number;status:string;cancel_requested:boolean
 attempt_id:string|null;attempt_count:number;attempt_status:string|null;started_at:number|null;created_at:number
 model:string|null;model_selection:{model:string;reasoning_effort:string;source:string}|null
 dispatch_status:string|null;observed_tokens:number|null;token_ceiling:number|null
 peer_count:number;unclosed_peer_count:number
}
/** Descending project page, with counts of saved records rather than live processes. */
export interface AgentRunPage {
 project_id:number;total_runs:number;total_actors:number;runtime_configured:boolean
 items:AgentRun[];next_before_seq:string|null
}
/** Retrieve older native runs without issuing execution authority or probing processes. */
export function agentRuns(projectId:number,beforeSeq:string|null=null){
 return fetchApi<AgentRunPage>(buildUrl(`/api/projects/${projectId}/agent-runs`,{before_seq:beforeSeq??undefined,limit:25}))
}
