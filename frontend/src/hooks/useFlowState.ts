import { useQuery } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import { useProjectStore } from '../stores/project'
import type { FlowState } from '../types/api'

export function useFlowState() {
  const projectId = useProjectStore((s) => s.activeProjectId)

  return useQuery<FlowState>({
    queryKey: ['flow-state', projectId],
    queryFn: () => fetchApi<FlowState>(`/api/flow-state/${projectId}`),
    enabled: projectId != null,
    refetchInterval: 30_000,
    retry: false,
  })
}
