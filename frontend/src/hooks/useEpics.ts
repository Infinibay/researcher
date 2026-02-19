import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Epic } from '../types/api'

export function useEpics(projectId: number | null) {
  return useQuery({
    queryKey: ['epics', projectId],
    queryFn: () =>
      fetchApi<Epic[]>(buildUrl('/api/epics', { project_id: projectId! })),
    enabled: projectId != null,
  })
}

export function useEpic(epicId: number | null) {
  return useQuery({
    queryKey: ['epic', epicId],
    queryFn: () => fetchApi<Epic>(`/api/epics/${epicId}`),
    enabled: epicId != null,
  })
}

export function useCreateEpic() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { project_id: number; title: string; description?: string; priority?: number }) =>
      fetchApi<Epic>('/api/epics', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epics'] })
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useUpdateEpic() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; title?: string; description?: string; status?: string; priority?: number }) =>
      fetchApi<Epic>(`/api/epics/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['epics'] })
      qc.invalidateQueries({ queryKey: ['epic', vars.id] })
    },
  })
}

export function useDeleteEpic() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<void>(`/api/epics/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epics'] })
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
