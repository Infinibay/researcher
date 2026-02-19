import { useState, useRef, useEffect, useMemo } from 'react'
import { useProjectStore } from '../../stores/project'
import { useChatMessages, useChatThreads, useThreadMessages, useSendMessage } from '../../hooks/useChat'
import { usePendingUserRequests, useRespondToRequest } from '../../hooks/useUserRequests'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { EmptyState } from '../common/EmptyState'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { formatRelative } from '../../utils/date'

export function ChatPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const [selectedThread, setSelectedThread] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [requestReply, setRequestReply] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  const { data: allMessages, isLoading } = useChatMessages(projectId)
  const { data: threads } = useChatThreads(projectId)
  const { data: threadMessages } = useThreadMessages(projectId, selectedThread)
  const sendMessage = useSendMessage()
  const { data: pendingData } = usePendingUserRequests()
  const respondMutation = useRespondToRequest()

  const pendingRequest = pendingData?.requests?.[0] ?? null

  const options: string[] = useMemo(() => {
    if (!pendingRequest) return []
    try {
      const parsed = JSON.parse(pendingRequest.options_json)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }, [pendingRequest])

  const displayMessages = selectedThread ? threadMessages : allMessages

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [displayMessages, pendingRequest])

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  const handleSend = () => {
    if (!message.trim() || !projectId) return
    sendMessage.mutate(
      { projectId, message: message.trim(), to_role: 'project_lead' },
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

  return (
    <div className="flex h-full gap-4">
      {/* Thread sidebar */}
      <div className="flex w-64 shrink-0 flex-col rounded-lg border border-surface-700 bg-surface-800">
        <div className="border-b border-surface-700 p-3">
          <h3 className="text-sm font-semibold text-slate-200">Threads</h3>
        </div>
        <div className="flex-1 overflow-y-auto">
          <button
            onClick={() => setSelectedThread(null)}
            className={`flex w-full flex-col items-start p-3 text-left text-sm hover:bg-surface-700/50 ${
              selectedThread === null ? 'bg-sky-500/10 text-sky-300' : 'text-slate-400'
            }`}
          >
            <span className="font-medium">All Messages</span>
          </button>
          {(threads ?? []).map((t) => (
            <button
              key={t.thread_id}
              onClick={() => setSelectedThread(t.thread_id)}
              className={`flex w-full flex-col items-start border-t border-surface-700 p-3 text-left text-sm hover:bg-surface-700/50 ${
                selectedThread === t.thread_id ? 'bg-sky-500/10 text-sky-300' : 'text-slate-400'
              }`}
            >
              <span className="font-medium">{t.thread_type || t.thread_id}</span>
              {t.last_message && (
                <span className="mt-0.5 line-clamp-1 text-xs text-slate-500">{t.last_message}</span>
              )}
              <span className="mt-0.5 text-xs text-slate-600">
                {t.message_count} messages
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex flex-1 flex-col rounded-lg border border-surface-700 bg-surface-800">
        <div className="border-b border-surface-700 p-3">
          <h3 className="text-sm font-semibold text-slate-200">
            {selectedThread ? `Thread: ${selectedThread}` : 'Chat with Project Lead'}
          </h3>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {isLoading && (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          )}
          {displayMessages?.length === 0 && !isLoading && !pendingRequest && (
            <p className="text-center text-sm text-slate-500 py-8">No messages yet. Start the conversation!</p>
          )}
          {displayMessages?.map((msg) => {
            const isUser = msg.from_agent === 'user'
            return (
              <div key={msg.id} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[75%] rounded-lg px-4 py-2.5 ${
                    isUser ? 'bg-sky-600/30 text-slate-200' : 'bg-surface-900 text-slate-300'
                  }`}
                >
                  {!isUser && (
                    <div className="mb-1 text-xs font-medium text-sky-400">{msg.from_agent}</div>
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
          })}

          {/* Pending user request — inline in the chat */}
          {pendingRequest && (
            <div className="flex justify-start">
              <div className="max-w-[75%] rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-xs font-medium text-amber-400">
                    {pendingRequest.agent_id || 'Project Lead'}
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
                {options.length > 0 ? (
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
                ) : (
                  <div className="mt-3 flex gap-2">
                    <textarea
                      value={requestReply}
                      onChange={(e) => setRequestReply(e.target.value)}
                      onKeyDown={handleReplyKeyDown}
                      placeholder="Type your response..."
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
                )}
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
              placeholder="Send a message to Project Lead..."
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
