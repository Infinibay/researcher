import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { WikiPage, WikiSearchResult } from '../types/api'

export function useWikiPages(projectId: number | null) {
  return useQuery({
    queryKey: ['wiki-pages', projectId],
    queryFn: () =>
      fetchApi<WikiPage[]>(buildUrl('/api/wiki', { project_id: projectId! })),
    enabled: projectId != null,
  })
}

export function useWikiPage(projectId: number | null, path: string | null) {
  return useQuery({
    queryKey: ['wiki-page', projectId, path],
    queryFn: () =>
      fetchApi<WikiPage>(
        buildUrl(`/api/wiki/${path}`, { project_id: projectId! }),
      ),
    enabled: projectId != null && path != null,
  })
}

export function useWikiSearch(projectId: number | null, query: string) {
  return useQuery({
    queryKey: ['wiki-search', projectId, query],
    queryFn: () =>
      fetchApi<WikiSearchResult[]>(
        buildUrl('/api/wiki-search', { project_id: projectId!, q: query }),
      ),
    enabled: projectId != null && query.length >= 2,
  })
}

export function useCreateWikiPage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { project_id: number; path: string; title?: string; content: string }) =>
      fetchApi<WikiPage>('/api/wiki', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wiki-pages'] })
    },
  })
}

export function useUpdateWikiPage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      path,
      ...data
    }: {
      projectId: number
      path: string
      title?: string
      content?: string
    }) =>
      fetchApi<WikiPage>(
        buildUrl(`/api/wiki/${path}`, { project_id: projectId }),
        { method: 'PUT', body: JSON.stringify(data) },
      ),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['wiki-pages'] })
      qc.invalidateQueries({ queryKey: ['wiki-page', vars.projectId, vars.path] })
    },
  })
}

export function useDeleteWikiPage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, path }: { projectId: number; path: string }) =>
      fetchApi<void>(
        buildUrl(`/api/wiki/${path}`, { project_id: projectId }),
        { method: 'DELETE' },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wiki-pages'] })
    },
  })
}
