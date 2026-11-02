/** Scoped wiki HTTP/cursors and identity-guarded edits; never start a research run. @module */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { buildUrl, fetchApi } from '../api/client'
import type { WikiPage, WikiNamespace, WikiRevision } from '../types/api'
import type { WikiDraft } from '../components/wiki/presentation'
import { scopedWiki, wikiPath } from '../components/wiki/presentation'
import { useWikiDrafts } from '../stores/wikiDrafts'

/** Cursor-bearing metadata distinguishes an empty wiki from an unqueried continuation. */
interface WikiIndex { pages: WikiPage[]; namespace: WikiNamespace; next_after_id: number | null }
/** History is metadata first; full retained text is read separately in bounded windows. */
interface WikiHistory { revisions: Omit<WikiRevision,'content'>[]; namespace: WikiNamespace; next_before_revision: number | null }

/** Read exactly one namespace and optional lexical FTS query with stable id pagination. */
export function useWikiPages(projectId: number | null, namespace: WikiNamespace, query: string) {
  return useInfiniteQuery({queryKey:['wiki','index',projectId,namespace,query],initialPageParam:0,
    queryFn:({pageParam})=>fetchApi<WikiIndex>(buildUrl('/api/wiki-index',{project_id:projectId,namespace,query,after_id:pageParam,limit:50})),
    getNextPageParam:last=>last.next_after_id ?? undefined,enabled:projectId!=null})
}

/** Keep the exact stored path, with no synthesized leading slash or global fallback. */
export function useWikiPage(projectId: number | null, namespace: WikiNamespace, path: string | null, offset=0, enabled=true) {
  return useQuery({queryKey:offset ? ['wiki','page',projectId,namespace,path,offset] : ['wiki','page',projectId,namespace,path],
    queryFn:()=>fetchApi<WikiPage>(buildUrl(wikiPath(path!),{project_id:projectId,namespace,offset})),enabled:enabled&&projectId!=null&&path!=null})
}

/** Build a complete mutation from the draft's original scope, not the current project selector. */
export function saveWikiRequest(draft: WikiDraft) {
  const common={title:draft.title,content:draft.content,parent_path:draft.parentPath,operation_key:draft.operationKey}
  return draft.pageId==null
    ? {url:'/api/wiki',method:'POST',body:{...common,project_id:draft.projectId,namespace:draft.namespace,path:draft.path}}
    : {url:buildUrl(wikiPath(draft.path),{project_id:draft.projectId,namespace:draft.namespace}),method:'PUT',body:{...common,page_id:draft.pageId,expected_revision:draft.revision}}
}

/** Retry an unchanged body with the same key; refresh readers after the actual committed receipt. */
export function useSaveWiki() {
  const client=useQueryClient()
  return useMutation({mutationFn:async(draft:WikiDraft)=>{
    const request=saveWikiRequest(draft)
    const page=await fetchApi<WikiPage>(request.url,{method:request.method,body:JSON.stringify(request.body)})
    if(!scopedWiki(page,draft.projectId,draft.namespace,draft.path)||(draft.pageId!=null&&page.id!==draft.pageId)) throw new Error('El guardado no devolvió la identidad esperada; consulta la página antes de repetir.')
    return page
  },onSuccess:(page,draft)=>{
    useWikiDrafts.getState().confirm(draft.key,draft.operationKey,page)
    client.invalidateQueries({queryKey:['wiki']})
  }})
}

/** Delete only the observed page identity/revision and preserve the retry key on uncertain response. */
export function useDeleteWikiPage() {
  const client=useQueryClient()
  return useMutation({mutationFn:({projectId,page,key}:{projectId:number;page:WikiPage;key:string})=>fetchApi<void>(buildUrl(wikiPath(page.path),{project_id:projectId,namespace:page.namespace,page_id:page.id,expected_revision:page.revision,operation_key:key}),{method:'DELETE'}),
    onSuccess:()=>{client.invalidateQueries({queryKey:['wiki']})}})
}

/** Lazily page the retained revision index, including after the active page has been deleted. */
export function useWikiHistory(projectId:number,namespace:WikiNamespace,pageId:number|null,enabled:boolean) {
  return useInfiniteQuery({queryKey:['wiki','history',projectId,namespace,pageId],initialPageParam:null as number|null,
    queryFn:({pageParam})=>fetchApi<WikiHistory>(buildUrl(`/api/wiki-revisions/${pageId}`,{project_id:projectId,namespace,before_revision:pageParam,limit:20})),
    getNextPageParam:last=>last.next_before_revision ?? undefined,enabled:enabled&&pageId!=null})
}

/** Read a selected retained version/window without replacing an editor's draft. */
export function useWikiRevision(projectId:number,namespace:WikiNamespace,pageId:number|null,revision:number|null,offset:number) {
  return useQuery({queryKey:['wiki','revision',projectId,namespace,pageId,revision,offset],
    queryFn:()=>fetchApi<WikiRevision>(buildUrl(`/api/wiki-revisions/${pageId}/${revision}`,{project_id:projectId,namespace,offset})),enabled:pageId!=null&&revision!=null})
}
