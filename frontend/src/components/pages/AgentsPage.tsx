import { useProjectStore } from '../../stores/project'
import { useAgents } from '../../hooks/useAgents'
import { useAgentActivity } from '../../hooks/useAgentActivity'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ErrorMessage } from '../common/ErrorMessage'
import { EmptyState } from '../common/EmptyState'
import { Badge } from '../common/Badge'
import { StatusDot } from '../common/StatusDot'
import type { Agent, AgentActivityEvent } from '../../types/api'

const roleLabels: Record<string, string> = {
  project_lead: 'Project Lead',
  team_lead: 'Team Lead',
  developer: 'Developer',
  code_reviewer: 'Code Reviewer',
  researcher: 'Researcher',
  research_reviewer: 'Research Reviewer',
}

const roleVariant: Record<string, string> = {
  project_lead: 'info',
  team_lead: 'violet',
  developer: 'success',
  code_reviewer: 'warning',
  researcher: 'neutral',
  research_reviewer: 'neutral',
}

function timeSince(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const eventBadgeVariant: Record<string, string> = {
  message_sent: 'info',
  agent_message_received: 'info',
  notification_sent: 'warning',
  user_request_created: 'violet',
  user_request_responded: 'success',
}

const eventDotColor: Record<string, string> = {
  message_sent: 'bg-sky-400',
  agent_message_received: 'bg-sky-400',
  notification_sent: 'bg-amber-400',
  user_request_created: 'bg-violet-400',
  user_request_responded: 'bg-emerald-400',
}

function ActivityFeedItem({ event }: { event: AgentActivityEvent }) {
  const target = event.to_agent ?? event.to_role
  const arrow = event.from_agent && target
    ? `${event.from_agent} → ${target}`
    : event.from_agent ?? target ?? '—'

  return (
    <div className="flex items-start gap-2.5 py-2 border-b border-surface-700 last:border-b-0">
      <div className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${eventDotColor[event.type] ?? 'bg-slate-400'}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={eventBadgeVariant[event.type] ?? 'neutral'}>
            {event.type.replace(/_/g, ' ')}
          </Badge>
          <span className="text-xs text-slate-400">{arrow}</span>
          <span className="text-xs text-slate-500 ml-auto flex-shrink-0">
            {timeSince(event.timestamp)}
          </span>
        </div>
        {event.content && (
          <p className="text-xs text-slate-400 mt-0.5 truncate">{event.content}</p>
        )}
        {event.kind && (
          <p className="text-xs text-slate-500 mt-0.5">kind: {event.kind}</p>
        )}
      </div>
    </div>
  )
}

function AgentCard({ agent }: { agent: Agent }) {
  const isActive = agent.status === 'active'

  return (
    <div className="rounded-lg border border-surface-700 bg-surface-800 p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-3">
        <StatusDot status={isActive ? 'active' : 'inactive'} animated={isActive} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-100">{agent.name}</span>
            <Badge variant={roleVariant[agent.role] || 'neutral'}>
              {roleLabels[agent.role] || agent.role}
            </Badge>
          </div>
          <span className="text-xs text-slate-500">{agent.agent_id}</span>
        </div>
        <Badge variant={isActive ? 'success' : 'neutral'}>
          {agent.status}
        </Badge>
      </div>

      {/* Current activity */}
      {agent.current_run && (
        <div className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2">
          <div className="text-xs font-medium text-emerald-300">Working on:</div>
          <div className="text-sm text-slate-200 mt-0.5">
            #{agent.current_run.task_id} {agent.current_run.task_title || 'Untitled task'}
          </div>
          {agent.current_run.started_at && (
            <div className="text-xs text-slate-500 mt-0.5">
              Started {timeSince(agent.current_run.started_at)}
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-slate-400">
        <span>Runs: {agent.total_runs}</span>
        {agent.performance && (
          <>
            <span className="text-emerald-400">{agent.performance.successful_runs} ok</span>
            {agent.performance.failed_runs > 0 && (
              <span className="text-red-400">{agent.performance.failed_runs} failed</span>
            )}
            {agent.performance.total_tokens > 0 && (
              <span>{(agent.performance.total_tokens / 1000).toFixed(1)}k tokens</span>
            )}
          </>
        )}
        {agent.last_active_at && (
          <span className="ml-auto">Active {timeSince(agent.last_active_at)}</span>
        )}
      </div>
    </div>
  )
}

export function AgentsPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const { data, isLoading, error, refetch } = useAgents(projectId)

  if (!projectId) {
    return <EmptyState title="No project selected" description="Select a project from the header." />
  }

  if (isLoading) return <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
  if (error) return <ErrorMessage message={(error as Error).message} retry={() => refetch()} />

  const agents = data?.agents ?? []
  const activeAgents = agents.filter((a) => a.status === 'active')
  const idleAgents = agents.filter((a) => a.status === 'idle')

  if (agents.length === 0) {
    return <EmptyState title="No agents yet" description="Start the project to initialize the agent team." />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-100">Agents</h1>
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span className="flex items-center gap-1.5">
            <StatusDot status="active" animated />
            {activeAgents.length} active
          </span>
          <span className="flex items-center gap-1.5">
            <StatusDot status="inactive" />
            {idleAgents.length} idle
          </span>
        </div>
      </div>

      {/* Active agents first */}
      {activeAgents.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Currently Working</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {activeAgents.map((agent) => (
              <AgentCard key={agent.agent_id} agent={agent} />
            ))}
          </div>
        </div>
      )}

      {/* Idle agents */}
      {idleAgents.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Idle</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {idleAgents.map((agent) => (
              <AgentCard key={agent.agent_id} agent={agent} />
            ))}
          </div>
        </div>
      )}

      {/* Activity Feed */}
      <ActivityFeed />
    </div>
  )
}

function ActivityFeed() {
  const { events, clearFeed } = useAgentActivity()

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">Activity Feed</h2>
        {events.length > 0 && (
          <button
            onClick={clearFeed}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Clear
          </button>
        )}
      </div>
      <div className="rounded-lg border border-surface-700 bg-surface-800 p-3">
        {events.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-4">No activity yet</p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            {events.map((event) => (
              <ActivityFeedItem key={event.id} event={event} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
