import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { ProjectProgress } from '../types/api'

export function useProjectProgress(projectId: number | null) {
  return useQuery({
    queryKey: ['project-progress', projectId],
    queryFn: () => fetchApi<ProjectProgress>(`/api/projects/${projectId}/progress`),
    enabled: projectId != null,
    refetchInterval: 15_000,
  })
}
