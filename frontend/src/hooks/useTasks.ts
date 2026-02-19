import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Task, TaskComment, TaskDependency } from '../types/api'

interface TaskFilters {
  status?: string
  epic_id?: number
  milestone_id?: number
  assigned_to?: string
}

export function useTasks(projectId: number | null, filters?: TaskFilters) {
  return useQuery({
    queryKey: ['tasks', projectId, filters],
    queryFn: () =>
      fetchApi<Task[]>(
        buildUrl('/api/tasks', { project_id: projectId!, ...filters }),
      ),
    enabled: projectId != null,
  })
}

export function useTask(taskId: number | null) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () => fetchApi<Task>(`/api/tasks/${taskId}`),
    enabled: taskId != null,
  })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      project_id?: number
      epic_id?: number
      milestone_id?: number
      type: string
      title: string
      description?: string
      priority?: number
      estimated_complexity?: string
      depends_on?: number[]
    }) =>
      fetchApi<Task>('/api/tasks', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      qc.invalidateQueries({ queryKey: ['epics'] })
      qc.invalidateQueries({ queryKey: ['milestones'] })
    },
  })
}

export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: number
      title?: string
      description?: string
      status?: string
      assigned_to?: string
      reviewer?: string
      branch_name?: string
      priority?: number
    }) =>
      fetchApi<Task>(`/api/tasks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      qc.invalidateQueries({ queryKey: ['task', vars.id] })
      qc.invalidateQueries({ queryKey: ['epics'] })
      qc.invalidateQueries({ queryKey: ['milestones'] })
    },
  })
}

export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      fetchApi<void>(`/api/tasks/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      qc.invalidateQueries({ queryKey: ['epics'] })
      qc.invalidateQueries({ queryKey: ['milestones'] })
    },
  })
}

export function useTaskComments(taskId: number | null) {
  return useQuery({
    queryKey: ['task-comments', taskId],
    queryFn: () => fetchApi<TaskComment[]>(`/api/tasks/${taskId}/comments`),
    enabled: taskId != null,
  })
}

export function useAddTaskComment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      ...data
    }: {
      taskId: number
      author: string
      content: string
      comment_type: string
    }) =>
      fetchApi<TaskComment>(`/api/tasks/${taskId}/comments`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['task-comments', vars.taskId] })
    },
  })
}

export function useTaskDependencies(taskId: number | null) {
  return useQuery({
    queryKey: ['task-dependencies', taskId],
    queryFn: () => fetchApi<TaskDependency[]>(`/api/tasks/${taskId}/dependencies`),
    enabled: taskId != null,
  })
}

export function useSetTaskDependencies() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      ...data
    }: {
      taskId: number
      depends_on: number[]
      dependency_type?: string
    }) =>
      fetchApi<any>(`/api/tasks/${taskId}/dependencies`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['task-dependencies', vars.taskId] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
