import { useState, useRef, useEffect, useMemo } from 'react'
import { useProjectStore } from '../../stores/project'
import { useChatMessages, useSendMessage } from '../../hooks/useChat'
import { useAgents } from '../../hooks/useAgents'
import { usePendingUserRequests, useRespondToRequest } from '../../hooks/useUserRequests'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { EmptyState } from '../common/EmptyState'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { formatRelative } from '../../utils/date'

interface ChatMessage {
  id: number
  thread_id?: string
  from_agent: string
  message: string
  created_at?: string
}

interface ThreadGroup {
  threadId: string
  first: ChatMessage
  replyCount: number
}

export function ChatPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const [expandedThread, setExpandedThread] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [requestReply, setRequestReply] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  const { data: allMessages, isLoading } = useChatMessages(projectId)
  const sendMessage = useSendMessage()
  const { data: agentsData } = useAgents(projectId)

  const agentDisplayName = useMemo(() => {
    const map = new Map<string, string>()
    for (const a of agentsData?.agents ?? []) {
      const role = a.role.replace(/_/g, ' ')
      map.set(a.agent_id, `${a.name} (${role})`)
    }
    return (agentId: string) => map.get(agentId) ?? agentId
  }, [agentsData])
  const { data: pendingData } = usePendingUserRequests()
  const respondMutation = useRespondToRequest()

  const pendingRequest = pendingData?.requests?.[0] ?? null

  const options: string[] = useMemo(() => {
    if (!pendingRequest) return []
    try {
      const parsed = JSON.parse(pendingRequest.options_json)
      if (!Array.isArray(parsed)) return []
      // Normalize: backend may store strings or {text, value} objects
      return parsed.map((item: unknown) => {
        if (typeof item === 'string') return item
        if (item && typeof item === 'object' && 'text' in item) return String((item as any).text)
        return String(item)
      })
    } catch {
      return []
    }
  }, [pendingRequest])

  // Group messages by thread_id → extract first message + reply count
  const threadGroups: ThreadGroup[] = useMemo(() => {
    if (!allMessages || allMessages.length === 0) return []
    const grouped = new Map<string, ChatMessage[]>()
    for (const msg of allMessages) {
      const tid = msg.thread_id || `__no_thread_${msg.id}`
      if (!grouped.has(tid)) grouped.set(tid, [])
      grouped.get(tid)!.push(msg)
    }
    const groups: ThreadGroup[] = []
    for (const [threadId, msgs] of grouped) {
      // Sort by id to ensure first message is the earliest
      msgs.sort((a, b) => a.id - b.id)
      groups.push({
        threadId,
        first: msgs[0],
        replyCount: msgs.length - 1,
      })
    }
    // Sort groups by first message id (chronological order)
    groups.sort((a, b) => a.first.id - b.first.id)
    return groups
  }, [allMessages])

  // Get all messages for the expanded thread
  const expandedMessages: ChatMessage[] = useMemo(() => {
    if (!expandedThread || !allMessages) return []
    return allMessages
      .filter((m) => m.thread_id === expandedThread)
      .sort((a, b) => a.id - b.id)
  }, [expandedThread, allMessages])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [threadGroups, expandedMessages, pendingRequest])

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  const handleSend = () => {
    if (!message.trim() || !projectId) return
    sendMessage.mutate(
      {
        projectId,
        message: message.trim(),
        to_role: 'project_lead',
        ...(expandedThread ? { thread_id: expandedThread } : {}),
      },
      { onSuccess: () => setMessage('') },
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleRespond = (response: string) => {
    if (!response.trim() || !pendingRequest) return
    respondMutation.mutate(
      { requestId: pendingRequest.id, response: response.trim() },
      { onSuccess: () => setRequestReply('') },
    )
  }

  const handleReplyKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleRespond(requestReply)
    }
  }

  const renderMessage = (msg: ChatMessage) => {
    const isUser = msg.from_agent === 'user'
    return (
      <div key={msg.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div
          className={`max-w-[75%] rounded-lg px-4 py-2.5 ${
            isUser ? 'bg-sky-600/30 text-slate-200' : 'bg-surface-900 text-slate-300'
          }`}
        >
          {!isUser && (
            <div className="mb-1 text-xs font-medium text-sky-400">{agentDisplayName(msg.from_agent)}</div>
          )}
          <div className="text-sm">
            <MarkdownRenderer content={msg.message} />
          </div>
          {msg.created_at && (
            <div className={`mt-1 text-[10px] ${isUser ? 'text-sky-300/50' : 'text-slate-600'}`}>
              {formatRelative(msg.created_at)}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full">
      <div className="flex flex-1 flex-col rounded-lg border border-surface-700 bg-surface-800">
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-surface-700 p-3">
          {expandedThread && (
            <button
              onClick={() => setExpandedThread(null)}
              className="rounded-md px-2 py-1 text-xs font-medium text-sky-400 hover:bg-surface-700 hover:text-sky-300"
            >
              &larr; All messages
            </button>
          )}
          <h3 className="text-sm font-semibold text-slate-200">
            {expandedThread ? 'Thread' : 'Chat with Project Lead'}
          </h3>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {isLoading && (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          )}

          {/* Expanded thread view: show all messages in the thread */}
          {expandedThread ? (
            <>
              {expandedMessages.map(renderMessage)}
            </>
          ) : (
            <>
              {threadGroups.length === 0 && !isLoading && !pendingRequest && (
                <p className="text-center text-sm text-slate-500 py-8">No messages yet. Start the conversation!</p>
              )}
              {threadGroups.map((group) => (
                <div key={group.threadId}>
                  {renderMessage(group.first)}
                  {group.replyCount > 0 && (
                    <div className="ml-12 mt-1">
                      <button
                        onClick={() => setExpandedThread(group.threadId)}
                        className="text-xs font-medium text-sky-400/80 hover:text-sky-300 hover:underline"
                      >
                        View thread ({group.replyCount} {group.replyCount === 1 ? 'reply' : 'replies'})
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </>
          )}

          {/* Pending user request — inline in the chat */}
          {pendingRequest && (
            <div className="flex justify-start">
              <div className="max-w-[75%] rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-xs font-medium text-amber-400">
                    {pendingRequest.agent_id ? agentDisplayName(pendingRequest.agent_id) : 'Project Lead'}
                  </span>
                  <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-medium text-amber-300">
                    Waiting for your response
                  </span>
                </div>
                <div className="text-sm text-slate-200">
                  <MarkdownRenderer content={pendingRequest.body} />
                </div>
                {pendingRequest.created_at && (
                  <div className="mt-1 text-[10px] text-slate-600">
                    {formatRelative(pendingRequest.created_at)}
                  </div>
                )}

                {/* Response area */}
                {options.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {options.map((opt) => (
                      <button
                        key={opt}
                        disabled={respondMutation.isPending}
                        onClick={() => handleRespond(opt)}
                        className="rounded-md border border-amber-500/30 bg-surface-800 px-3 py-1.5 text-sm text-slate-200 hover:border-amber-400/50 hover:bg-surface-700 disabled:opacity-50"
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}
                <div className={`${options.length > 0 ? 'mt-2' : 'mt-3'} flex gap-2`}>
                  <textarea
                    value={requestReply}
                    onChange={(e) => setRequestReply(e.target.value)}
                    onKeyDown={handleReplyKeyDown}
                    placeholder={options.length > 0 ? 'Or type a custom response...' : 'Type your response...'}
                    rows={1}
                    className="flex-1 resize-none rounded-md border border-surface-600 bg-surface-900 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:border-amber-500/50 focus:outline-none"
                  />
                  <button
                    disabled={respondMutation.isPending || !requestReply.trim()}
                    onClick={() => handleRespond(requestReply)}
                    className="shrink-0 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
                  >
                    {respondMutation.isPending ? 'Sending...' : 'Reply'}
                  </button>
                </div>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>

        {/* Input */}
        <div className="border-t border-surface-700 p-3">
          <div className="flex gap-2">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={expandedThread ? 'Reply in thread...' : 'Send a message to Project Lead...'}
              rows={1}
              className="flex-1 resize-none rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:border-sky-500/50 focus:outline-none"
            />
            <button
              onClick={handleSend}
              disabled={!message.trim() || sendMessage.isPending}
              className="shrink-0 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
