/** Scoped finding indexes, current text and exact source windows; never dispatch inference. @module */
import {useInfiniteQuery,useQuery,useQueryClient} from '@tanstack/react-query'
import {buildUrl,fetchApi} from '../api/client'
import type {FindingIndex,FindingDetail,FindingCitations,FindingRanking,FindingSource,FindingLegacySources} from '../types/api'
import type {FindingFilters} from '../components/findings/presentation'

/** Translate view filters without turning an absent confidence declaration into zero. */
function filterParams(filters:FindingFilters) {
 return {q:filters.query||undefined,finding_type:filters.finding_type||undefined,status:filters.status||undefined,min_confidence:filters.min_confidence??undefined}
}

/** Page stable metadata ids for exactly the visible project and combined filters. */
export function useFindings(projectId:number|null,filters:FindingFilters) {
 return useInfiniteQuery({queryKey:['finding-registry','index',projectId,filters],initialPageParam:0,
  queryFn:({pageParam,signal})=>fetchApi<FindingIndex>(buildUrl('/api/findings-index',{project_id:projectId,after_id:pageParam,limit:50,...filterParams(filters)}),{signal}),
  getNextPageParam:last=>last.next_after_id??undefined,enabled:projectId!=null})
}

/** Retrieve complete bounded local corpora only after explicit semantic search submission. */
export function useFindingsSearch(projectId:number|null,query:string,filters:FindingFilters,selected:number[]) {
 const client=useQueryClient()
 const key=['finding-registry','query',projectId,query,filters,selected]
 const result=useInfiniteQuery({queryKey:key,initialPageParam:{rank:0,corpus:undefined as string|undefined,records:undefined as string|undefined},
  queryFn:({pageParam,signal})=>fetchApi<FindingRanking>(buildUrl('/api/findings-query',{project_id:projectId,query,finding_ids:selected.length?selected.join(','):undefined,finding_type:filters.finding_type||undefined,status:filters.status||undefined,min_confidence:filters.min_confidence??undefined,after_rank:pageParam.rank,expected_corpus_sha256:pageParam.corpus,expected_record_set_sha256:pageParam.records,limit:10}),{signal}),
  getNextPageParam:last=>last.next_rank==null?undefined:{rank:last.next_rank,corpus:last.corpus_sha256,records:last.record_set_sha256},enabled:projectId!=null&&query.length>0})
 return {...result,restart:()=>client.resetQueries({queryKey:key,exact:true})}
}

/** Each body window owns project/finding/offset; late reads cannot replace another selection. */
export function useFinding(projectId:number|null,id:number|null,offset=0) {
 return useQuery({queryKey:['finding-registry','detail',projectId,id,offset],
  queryFn:({signal})=>fetchApi<FindingDetail>(buildUrl(`/api/findings/${id}`,{project_id:projectId,offset,max_chars:12000}),{signal}),
  enabled:projectId!=null&&id!=null})
}

/** Load citation pages independently, making continuation and failure visible. */
export function useFindingEvidence(projectId:number|null,id:number|null) {
 return useInfiniteQuery({queryKey:['finding-registry','evidence',projectId,id],initialPageParam:0,
  queryFn:({pageParam,signal})=>fetchApi<FindingCitations>(buildUrl(`/api/findings/${id}/evidence`,{project_id:projectId,offset:pageParam}),{signal}),
  getNextPageParam:last=>last.next_evidence_offset??undefined,enabled:projectId!=null&&id!=null})
}

/** Inspect only an actually cited saved snapshot; a failed hash check remains an error. */
export function useFindingSource(projectId:number,id:number,sourceId:number,offset:number) {
 return useQuery({queryKey:['finding-registry','source',projectId,id,sourceId,offset],
  queryFn:({signal})=>fetchApi<FindingSource>(buildUrl(`/api/findings/${id}/sources/${sourceId}`,{project_id:projectId,offset,max_chars:12000}),{signal})})
}

/** Page unverified historical declarations only when requested; never follow their URLs automatically. */
export function useFindingLegacySources(projectId:number,id:number,offset:number) {
 return useQuery({queryKey:['finding-registry','legacy-sources',projectId,id,offset],
  queryFn:({signal})=>fetchApi<FindingLegacySources>(buildUrl(`/api/findings/${id}/legacy-sources`,{project_id:projectId,offset,max_chars:8000}),{signal}),enabled:offset>0})
}
