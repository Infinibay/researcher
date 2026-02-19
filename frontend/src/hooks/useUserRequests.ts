import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import { useProjectStore } from '../stores/project'
import type { UserRequest } from '../types/api'

interface UserRequestList {
  requests: UserRequest[]
  total: number
}

export function usePendingUserRequests() {
  const projectId = useProjectStore((s) => s.activeProjectId)

  return useQuery({
    queryKey: ['user-requests', projectId],
    queryFn: () =>
      fetchApi<UserRequestList>(`/api/user-requests/${projectId}/pending`),
    enabled: projectId != null,
    refetchInterval: 10_000,
  })
}

export function useRespondToRequest() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: ({ requestId, response }: { requestId: number; response: string }) =>
      fetchApi<UserRequest>(`/api/user-requests/${requestId}/respond`, {
        method: 'POST',
        body: JSON.stringify({ response }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['user-requests'] })
    },
  })
}
