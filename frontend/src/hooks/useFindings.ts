import { useQuery } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Finding } from '../types/api'

interface FindingFilters {
  q?: string
  finding_type?: string
  status?: string
  min_confidence?: number
  limit?: number
}

export function useFindings(projectId: number | null, filters?: FindingFilters) {
  return useQuery({
    queryKey: ['findings', projectId, filters],
    queryFn: () =>
      fetchApi<Finding[]>(
        buildUrl('/api/findings', {
          project_id: projectId!,
          ...filters,
        }),
      ),
    enabled: projectId != null,
  })
}

export function useFindingsSearch(projectId: number | null, query: string, threshold?: number) {
  return useQuery({
    queryKey: ['findings-search', projectId, query, threshold],
    queryFn: () =>
      fetchApi<Finding[]>(
        buildUrl('/api/findings/search', {
          project_id: projectId!,
          query,
          threshold,
        }),
      ),
    enabled: projectId != null && query.length >= 3,
  })
}

export function useFinding(findingId: number | null) {
  return useQuery({
    queryKey: ['finding', findingId],
    queryFn: () => fetchApi<Finding>(`/api/findings/${findingId}`),
    enabled: findingId != null,
  })
}
