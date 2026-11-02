/** Scoped review reads and explicit owner mutations; inference is never automatically retried. @module */
import {useInfiniteQuery,useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {reviewState,reviewDetail,requestReview} from '../api/reviews'
import {stopRun,taskWorkspace} from '../api/runtime'

/** Poll only actual working attempts; each response stays under its project/finding key. */
export function useReviewState(projectId:number,findingId:number) {
 return useQuery({queryKey:['finding-reviews','state',projectId,findingId],
  queryFn:({signal})=>reviewState(projectId,findingId,0,signal),retry:false,
  refetchInterval:query=>['queued','running','cancelling','reconciling','waiting_input'].includes(query.state.data?.active_review?.status??'')?3000:false})
}
/** Page all retained review attempts without truncating the history to the newest screen. */
export function useReviewHistory(projectId:number,findingId:number,after:number|null) {
 return useInfiniteQuery({queryKey:['finding-reviews','history',projectId,findingId,after],initialPageParam:after??0,
  queryFn:({pageParam,signal})=>reviewState(projectId,findingId,pageParam,signal),
  getNextPageParam:last=>last.reviews.next_after_id??undefined,enabled:after!=null,retry:false})
}
/** Resolve a selected review under explicit project/finding/request identity before display. */
export function useReviewDetail(projectId:number,findingId:number,requestId:number|null) {
 return useQuery({queryKey:['finding-reviews','detail',projectId,findingId,requestId],
  queryFn:({signal})=>reviewDetail(projectId,requestId!,signal),enabled:requestId!=null,retry:false,
  refetchInterval:query=>['queued','running','cancelling','reconciling','waiting_input'].includes(query.state.data?.status??'')?3000:false})
}
/** Reuse the task workspace's registered repositories and configuration, without starting work. */
export function useReviewWorkspace(projectId:number,taskId:number|null) {
 return useQuery({queryKey:['task-workspace',projectId,taskId],queryFn:()=>taskWorkspace(projectId,taskId!),enabled:taskId!=null,retry:false})
}
/** Invalidate only the submitted scope; late mutation responses never change the selected project. */
export function useRequestReview() {
 const client=useQueryClient()
 return useMutation({mutationFn:requestReview,retry:false,onSettled:(_,__,intent)=>{
  client.invalidateQueries({queryKey:['finding-reviews','state',intent.projectId,intent.findingId]})
  client.invalidateQueries({queryKey:['finding-registry','detail',intent.projectId,intent.findingId]})
  client.invalidateQueries({queryKey:['task-workspace',intent.projectId,intent.taskId]})
 }})
}
/** Stop or archive the original attempt; committed decisions remain in the history. */
export function useCloseReview(projectId:number,findingId:number) {
 const client=useQueryClient()
 return useMutation({mutationFn:(runId:string)=>stopRun(projectId,runId),retry:false,onSettled:()=>{
  client.invalidateQueries({queryKey:['finding-reviews','state',projectId,findingId]})
  client.invalidateQueries({queryKey:['finding-reviews','detail',projectId,findingId]})
 }})
}
