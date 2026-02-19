import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Milestone } from '../types/api'

export function useMilestones(projectId: number | null, epicId?: number | null) {
  return useQuery({
    queryKey: ['milestones', projectId, epicId],
    queryFn: () =>
      fetchApi<Milestone[]>(
        buildUrl('/api/milestones', { project_id: projectId!, epic_id: epicId }),
      ),
    enabled: projectId != null,
  })
}

export function useMilestone(milestoneId: number | null) {
  return useQuery({
    queryKey: ['milestone', milestoneId],
    queryFn: () => fetchApi<Milestone>(`/api/milestones/${milestoneId}`),
    enabled: milestoneId != null,
  })
}

export function useCreateMilestone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { epic_id: number; title: string; description?: string; due_date?: string }) =>
      fetchApi<Milestone>('/api/milestones', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['milestones'] })
      qc.invalidateQueries({ queryKey: ['epics'] })
    },
  })
}

export function useUpdateMilestone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; title?: string; description?: string; status?: string; due_date?: string }) =>
      fetchApi<Milestone>(`/api/milestones/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['milestones'] })
      qc.invalidateQueries({ queryKey: ['milestone', vars.id] })
    },
  })
}

export function useDeleteMilestone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<void>(`/api/milestones/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['milestones'] })
      qc.invalidateQueries({ queryKey: ['epics'] })
    },
  })
}
