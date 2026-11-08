/** Task queries and mutations, with optional project-scoped detail lookup. @module */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { Task, TaskComment, TaskDependency } from '../types/api'
import type { TaskCreationBody } from '../api/taskCreation'
import type { TaskCommentPacket } from '../api/taskComments'

interface TaskFilters {
  status?: string
  epic_id?: number
  milestone_id?: number
  assigned_to?: string
}

/** Read the selected project task list with explicit optional filters. */
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

/** Read a task with a project-isolated cache for scoped links; retain legacy unscoped callers. */
export function useTask(taskId: number | null, projectId?: number | null) {
  return useQuery({
    queryKey: projectId == null ? ['task', taskId] : ['task', taskId, projectId],
    queryFn: () => fetchApi<Task>(buildUrl(`/api/tasks/${taskId}`, { project_id: projectId ?? undefined })),
    enabled: taskId != null,
  })
}

/** Create exact owner metadata with a stable key; recovery never changes the original captured input. */
export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TaskCreationBody) =>
      fetchApi<Task>('/api/tasks', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSettled: (_, __, data) => {
      qc.invalidateQueries({ queryKey: ['tasks',data.project_id] })
      qc.invalidateQueries({ queryKey: ['epics',data.project_id] })
      qc.invalidateQueries({ queryKey: ['milestones',data.project_id] })
    },
  })
}

/** Refresh original task/context reads after every reply, including an unconfirmed metadata write. */
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
    onSettled: (_, __, vars) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      qc.invalidateQueries({ queryKey: ['task', vars.id] })
      qc.invalidateQueries({ queryKey: ['task-workspace'] })
      qc.invalidateQueries({ queryKey: ['epics'] })
      qc.invalidateQueries({ queryKey: ['milestones'] })
    },
  })
}

/** Request manual retirement and preserve server explanations when native history prevents deletion. */
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

/** Read stored notes; a failed query does not prove an empty history. */
export function useTaskComments(taskId: number | null) {
  return useQuery({
    queryKey: ['task-comments', taskId],
    queryFn: () => fetchApi<TaskComment[]>(`/api/tasks/${taskId}/comments`),
    enabled: taskId != null,
    retry: false,
  })
}

/** Append a note and refresh its history even when the delivery response is unavailable. */
export function useAddTaskComment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      ...data
    }: {
      taskId: number
    } & TaskCommentPacket['body']) =>
      fetchApi<TaskComment>(`/api/tasks/${taskId}/comments`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSettled: (_, __, vars) => {
      qc.invalidateQueries({ queryKey: ['task-comments', vars.taskId] })
    },
  })
}

/** Preserve outgoing-only consumers; the inspector explicitly asks for both relation directions. */
export function useTaskDependencies(taskId: number | null, includeIncoming=false) {
  return useQuery({
    queryKey: includeIncoming ? ['task-dependencies', taskId, 'both'] : ['task-dependencies', taskId],
    queryFn: () => fetchApi<TaskDependency[]>(buildUrl(`/api/tasks/${taskId}/dependencies`,{include_incoming:includeIncoming?true:undefined})),
    enabled: taskId != null,
    retry: false,
  })
}

/** Replace confirmed relations and refresh their task context after successful or uncertain delivery. */
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
      fetchApi<TaskDependency[]>(`/api/tasks/${taskId}/dependencies`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSettled: (_, __, vars) => {
      qc.invalidateQueries({ queryKey: ['task-dependencies', vars.taskId] })
      qc.invalidateQueries({ queryKey: ['task-dependency-graph'] })
      qc.invalidateQueries({ queryKey: ['task', vars.taskId] })
      qc.invalidateQueries({ queryKey: ['task-workspace'] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}
