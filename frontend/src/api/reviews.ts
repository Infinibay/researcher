/** Owner review controls and attributed decisions; stored support never implies acceptance. @module */
import {buildUrl,fetchApi} from './client'
import type {RuntimeRun} from './runtime'

/** Actual admitted attempt metadata; a verdict is a reported decision, not task acceptance. */
export interface ReviewSummary {
 request_id:number;run_id:string;finding_id?:number;status:string;operation_key?:string
 decision_id:number|null;verdict?:string|null;subject_sha256?:string;context_version?:number
 subject_current?:boolean|null;currentness_reason?:string|null;created_at?:number
}
/** Observed subject identity and paged review history; reading this state never starts inference. */
export interface ReviewState {
 project_id:number;task_id:number;finding_id:number;context_version:number;subject_sha256:string
 reviewable:boolean;reason:string|null;author:{actor_id:string;attempt_id:string}|null
 source_count:number;report_count:number;active_review:ReviewSummary|null;latest_review?:ReviewSummary|null
 reviews:{items:ReviewSummary[];next_after_id:number|null}
}
/** An exact saved quotation with the reviewed source version and frozen metadata. */
export interface ReviewEvidence {
 source_id:number;source_sha256:string;quote:string;quote_offset?:number
 source:{id:number;title:string;locator:string;kind?:string}|null
}
/** Attributed decision and its current, changed or unverifiable dependency state. */
export interface ReviewDetail extends ReviewSummary {
 project_id:number;task_id:number;finding_id:number;subject_current:boolean|null
 reviewer_actor_id:string;reviewer_attempt_id:string|null;author_attempt_id:string
 subject_sha256:string;context_version:number;reviewer_fence:number|null
 decision:{verdict:string;rationale:string;checks:{criterion:string;outcome:string;explanation:string}[]
   limitations:string[];verified_evidence:ReviewEvidence[]}|null
}
/** Owner-submitted scope and observed version, retained unchanged across ambiguous retries. */
export interface ReviewIntent {
 projectId:number;taskId:number;findingId:number;operation_key:string;context_version:number
 subject_sha256:string;repository_id?:number
}

/** Bind one mutation to the observed task, project, finding and version, retaining its key on retry. */
export function requestReview(intent:ReviewIntent) {
 const {projectId,taskId,findingId,...body}=intent
 return fetchApi<RuntimeRun>(`/api/projects/${projectId}/tasks/${taskId}/finding-reviews`,{
  method:'POST',body:JSON.stringify({...body,finding_id:findingId})})
}
/** Retrieve history in the visible project; HTTP errors are not empty review lists. */
export function reviewState(projectId:number,findingId:number,afterId=0,signal?:AbortSignal) {
 return fetchApi<ReviewState>(buildUrl(`/api/projects/${projectId}/findings/${findingId}/review-state`,{after_id:afterId,limit:20}),{signal})
}
/** Inspect a stored decision including old context, actual attempt and explicit unavailable currentness. */
export function reviewDetail(projectId:number,requestId:number,signal?:AbortSignal) {
 return fetchApi<ReviewDetail>(`/api/projects/${projectId}/finding-reviews/${requestId}`,{signal})
}
