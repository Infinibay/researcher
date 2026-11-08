/** Scoped conversation readers and explanatory owner-note transport, separate from native work admission. @module */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { ChatMessage, ChatThread } from '../types/api'

/** Read the selected project's retained messages without sending a new instruction. */
export function useChatMessages(projectId: number | null, limit = 50) {
  return useQuery({
    queryKey: ['chat', projectId, limit],
    queryFn: () =>
      fetchApi<ChatMessage[]>(
        buildUrl(`/api/chat/${projectId}`, { limit }),
      ),
    enabled: projectId != null,
    refetchInterval: 3000,
  })
}

/** List project threads with explicit caller-controlled recovery after query failure. */
export function useChatThreads(projectId: number | null) {
  return useQuery({
    queryKey: ['chat-threads', projectId],
    queryFn: () => fetchApi<ChatThread[]>(`/api/chat/${projectId}/threads`),
    enabled: projectId != null,
    refetchInterval: 3000,
    retry: false,
  })
}

/** Read only the selected original project/thread pair. */
export function useThreadMessages(projectId: number | null, threadId: string | null) {
  return useQuery({
    queryKey: ['thread-messages', projectId, threadId],
    queryFn: () =>
      fetchApi<ChatMessage[]>(`/api/chat/${projectId}/threads/${encodeURIComponent(threadId!)}`),
    enabled: projectId != null && threadId != null,
    refetchInterval: 3000,
    retry: false,
  })
}

/** Record an advisory owner note; its destination labels do not grant execution authority. */
export function useSendMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      ...data
    }: {
      projectId: number
      operation_key?: string
      message: string
      to_agent?: string | null
      to_role?: string
      thread_id?: string
    }) =>
      fetchApi<ChatMessage>(`/api/chat/${projectId}`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    retry:false,
    onSettled: (_, __, vars) => {
      qc.invalidateQueries({ queryKey: ['chat', vars.projectId] })
      qc.invalidateQueries({ queryKey: ['chat-threads', vars.projectId] })
      qc.invalidateQueries({ queryKey: ['thread-messages', vars.projectId] })
    },
  })
}
