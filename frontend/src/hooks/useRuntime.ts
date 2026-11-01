import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { taskWorkspace, sendInstruction, stopRun, recordCorrection, sendAnswer } from '../api/runtime'

export function useAnswer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sendAnswer, retry: false,
    onSettled: (_, __, intent) => {
      qc.invalidateQueries({ queryKey: ['task-workspace', intent.projectId, intent.taskId] })
      qc.invalidateQueries({ queryKey: ['chat', intent.projectId] })
      qc.invalidateQueries({ queryKey: ['chat-threads', intent.projectId] })
    },
  })
}

export function useTaskWorkspace(projectId: number, taskId: number) {
  return useQuery({
    queryKey: ['task-workspace', projectId, taskId],
    queryFn: () => taskWorkspace(projectId, taskId),
    refetchInterval: 2000,
    retry: false,
  })
}

export function useInstruction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: sendInstruction, retry: false,
    onSettled: (_, __, intent) => {
      qc.invalidateQueries({ queryKey: ['task-workspace', intent.projectId, intent.body.task_id] })
      qc.invalidateQueries({ queryKey: ['chat', intent.projectId] })
      qc.invalidateQueries({ queryKey: ['chat-threads', intent.projectId] })
      qc.invalidateQueries({ queryKey: ['tasks', intent.projectId] })
      qc.invalidateQueries({ queryKey: ['task', intent.body.task_id] })
    },
  })
}

export function useStopRun(projectId: number, taskId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (runId: string) => stopRun(projectId, runId), retry: false,
    onSettled: () => qc.invalidateQueries({ queryKey: ['task-workspace', projectId, taskId] }),
  })
}

export function useCorrection(projectId: number, taskId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Parameters<typeof recordCorrection>[2]) => recordCorrection(projectId, taskId, body),
    retry: false,
    onSettled: () => qc.invalidateQueries({ queryKey: ['task-workspace', projectId, taskId] }),
  })
}
