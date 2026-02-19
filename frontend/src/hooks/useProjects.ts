import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi } from '../api/client'
import type { Project } from '../types/api'
import { useProjectStore } from '../stores/project'

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => fetchApi<{ projects: Project[]; total: number }>('/api/projects'),
  })
}

export function useProject(projectId: number | null) {
  return useQuery({
    queryKey: ['project', projectId],
    queryFn: () => fetchApi<Project>(`/api/projects/${projectId}`),
    enabled: projectId != null,
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      fetchApi<Project>('/api/projects', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; name?: string; description?: string; status?: string }) =>
      fetchApi<Project>(`/api/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['project', vars.id] })
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  const store = useProjectStore()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<void>(`/api/projects/${id}`, { method: 'DELETE' }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      if (store.activeProjectId === id) {
        store.setActiveProject(null)
      }
    },
  })
}

export function useStartProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<any>(`/api/projects/${id}/start`, { method: 'POST' }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}

export function useStopProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<any>(`/api/projects/${id}/stop`, { method: 'POST' }),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['project', id] })
    },
  })
}
