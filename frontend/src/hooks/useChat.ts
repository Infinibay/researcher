import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApi, buildUrl } from '../api/client'
import type { ChatMessage, ChatThread } from '../types/api'

export function useChatMessages(projectId: number | null, limit = 50) {
  return useQuery({
    queryKey: ['chat', projectId, limit],
    queryFn: () =>
      fetchApi<ChatMessage[]>(
        buildUrl(`/api/chat/${projectId}`, { limit }),
      ),
    enabled: projectId != null,
  })
}

export function useChatThreads(projectId: number | null) {
  return useQuery({
    queryKey: ['chat-threads', projectId],
    queryFn: () => fetchApi<ChatThread[]>(`/api/chat/${projectId}/threads`),
    enabled: projectId != null,
  })
}

export function useThreadMessages(projectId: number | null, threadId: string | null) {
  return useQuery({
    queryKey: ['thread-messages', projectId, threadId],
    queryFn: () =>
      fetchApi<ChatMessage[]>(`/api/chat/${projectId}/threads/${threadId}`),
    enabled: projectId != null && threadId != null,
  })
}

export function useSendMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      projectId,
      ...data
    }: {
      projectId: number
      message: string
      to_agent?: string
      to_role?: string
      thread_id?: string
    }) =>
      fetchApi<ChatMessage>(`/api/chat/${projectId}`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['chat', vars.projectId] })
      qc.invalidateQueries({ queryKey: ['chat-threads', vars.projectId] })
    },
  })
}
