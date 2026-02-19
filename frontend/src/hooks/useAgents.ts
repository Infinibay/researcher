import { useQuery } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Agent } from '../types/api'

export function useAgents(projectId: number | null) {
  return useQuery({
    queryKey: ['agents', projectId],
    queryFn: () =>
      fetchApi<{ agents: Agent[]; total: number }>(
        buildUrl('/api/agents', { project_id: projectId ?? undefined }),
      ),
    enabled: projectId != null,
    refetchInterval: 10_000,
  })
}
