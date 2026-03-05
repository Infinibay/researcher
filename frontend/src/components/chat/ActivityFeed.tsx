import { memo } from 'react'
import { useAgentActivity } from '../../hooks/useAgentActivity'
import { StatusDot } from '../common/StatusDot'
import { formatRelative } from '../../utils/date'
import type { AgentActivityEvent } from '../../types/api'

// --- Icon + accent color config per event type ---

const EVENT_META: Record<string, { icon: string; accent: string }> = {
  message_sent: { icon: '📨', accent: 'sky' },
  agent_message_received: { icon: '📨', accent: 'sky' },
  notification_sent: { icon: '🔔', accent: 'amber' },
  user_request_created: { icon: '❓', accent: 'amber' },
  user_request_responded: { icon: '💬', accent: 'emerald' },
  task_assigned: { icon: '📋', accent: 'sky' },
  task_completed: { icon: '🚀', accent: 'emerald' },
  implementation_done: { icon: '🚀', accent: 'emerald' },
  task_status_changed: { icon: '🔄', accent: 'slate' },
  review_started: { icon: '🔍', accent: 'violet' },
  checkin_reviewed: { icon: '🔍', accent: 'violet' },
  review_approved: { icon: '✅', accent: 'emerald' },
  ticket_checkin_approved: { icon: '✅', accent: 'emerald' },
  review_finalized: { icon: '✅', accent: 'emerald' },
  escalation_resolved: { icon: '✅', accent: 'emerald' },
  review_rejected: { icon: '❌', accent: 'red' },
  flow_error: { icon: '❌', accent: 'red' },
  sub_flow_failed: { icon: '❌', accent: 'red' },
  review_escalated: { icon: '⚠️', accent: 'amber' },
  rework_completed: { icon: '🔧', accent: 'amber' },
  post_escalation_rework_completed: { icon: '🔧', accent: 'amber' },
  ci_gate_passed: { icon: '✅', accent: 'emerald' },
  brainstorm_ideas_approved: { icon: '✅', accent: 'emerald' },
  plan_approved: { icon: '✅', accent: 'emerald' },
  ci_gate_failed: { icon: '⚙️', accent: 'red' },
  ci_gate_rejected: { icon: '⚙️', accent: 'red' },
  brainstorm_ideas_rejected: { icon: '⚙️', accent: 'red' },
  brainstorm_started: { icon: '💡', accent: 'violet' },
  ideas_consolidated: { icon: '💡', accent: 'violet' },
  ideas_selected: { icon: '💡', accent: 'violet' },
  brainstorm_tasks_created: { icon: '📋', accent: 'violet' },
  plan_created: { icon: '🏗️', accent: 'sky' },
  structure_created: { icon: '🏗️', accent: 'sky' },
  task_created: { icon: '📋', accent: 'sky' },
  wiki_updated: { icon: '📝', accent: 'violet' },
  git_committed: { icon: '💾', accent: 'emerald' },
  git_pushed: { icon: '🚀', accent: 'emerald' },
  branch_created: { icon: '🔀', accent: 'sky' },
  pr_created: { icon: '🔀', accent: 'violet' },
  _default: { icon: '🤖', accent: 'slate' },
}

function getMeta(type: string) {
  return EVENT_META[type] ?? EVENT_META._default
}

// --- Type-specific verb map for building descriptive fallback labels ---

const EVENT_VERBS: Record<string, string> = {
  message_sent: 'sent a message',
  agent_message_received: 'received a message',
  notification_sent: 'sent a notification',
  user_request_created: 'requested user input',
  user_request_responded: 'received a user response',
  task_assigned: 'was assigned a task',
  task_completed: 'completed a task',
  implementation_done: 'finished implementation',
  task_status_changed: 'updated task status',
  review_started: 'started a review',
  checkin_reviewed: 'reviewed a check-in',
  review_approved: 'approved the review',
  ticket_checkin_approved: 'approved the check-in',
  review_finalized: 'finalized the review',
  escalation_resolved: 'resolved an escalation',
  review_rejected: 'rejected the review',
  flow_error: 'encountered a flow error',
  sub_flow_failed: 'sub-flow failed',
  review_escalated: 'escalated the review',
  rework_completed: 'completed rework',
  post_escalation_rework_completed: 'completed post-escalation rework',
  ci_gate_passed: 'passed CI gate',
  ci_gate_failed: 'failed CI gate',
  ci_gate_rejected: 'CI gate was rejected',
  brainstorm_started: 'started brainstorming',
  ideas_consolidated: 'consolidated ideas',
  ideas_selected: 'selected ideas',
  brainstorm_ideas_approved: 'approved brainstorm ideas',
  brainstorm_ideas_rejected: 'rejected brainstorm ideas',
  brainstorm_tasks_created: 'created brainstorm tasks',
  plan_created: 'created a plan',
  plan_approved: 'approved the plan',
  structure_created: 'created project structure',
  task_created: 'created a task',
  wiki_updated: 'updated the wiki',
  git_committed: 'committed changes',
  git_pushed: 'pushed to remote',
  branch_created: 'created a branch',
  pr_created: 'created a pull request',
}

// --- Label helper ---

export function getActivityLabel(event: AgentActivityEvent): string {
  if (event.content) return typeof event.content === 'string' ? event.content : String(event.content)

  const verb = EVENT_VERBS[event.type]
  const agent = event.from_agent
  const parts: string[] = []

  if (agent) parts.push(agent)
  parts.push(verb ?? event.type.replace(/_/g, ' '))

  if (event.task_title) parts.push(`"${event.task_title}"`)
  if (event.branch_name) parts.push(`on ${event.branch_name}`)

  return parts.join(' ')
}

// --- Accent class helpers ---

function accentClasses(accent: string) {
  switch (accent) {
    case 'sky':
      return { border: 'border-sky-500/30', iconBg: 'bg-sky-500/10', text: 'text-sky-300' }
    case 'emerald':
      return { border: 'border-emerald-500/30', iconBg: 'bg-emerald-500/10', text: 'text-emerald-300' }
    case 'amber':
      return { border: 'border-amber-500/30', iconBg: 'bg-amber-500/10', text: 'text-amber-300' }
    case 'red':
      return { border: 'border-red-500/30', iconBg: 'bg-red-500/10', text: 'text-red-300' }
    case 'violet':
      return { border: 'border-violet-500/30', iconBg: 'bg-violet-500/10', text: 'text-violet-300' }
    default:
      return { border: 'border-slate-500/30', iconBg: 'bg-slate-500/10', text: 'text-slate-300' }
  }
}

// --- ActivityFeedItem ---

const ActivityFeedItem = memo(function ActivityFeedItem({ event }: { event: AgentActivityEvent }) {
  const meta = getMeta(event.type)
  const ac = accentClasses(meta.accent)
  const label = getActivityLabel(event)
  const agent = event.from_agent || 'Sistema'

  return (
    <div className={`animate-feed-in border-l-2 ${ac.border} pl-3 py-2 rounded-r-md bg-surface-900/60`}>
      <div className="flex items-center gap-2">
        <span className={`flex h-5 w-5 items-center justify-center rounded text-xs ${ac.iconBg}`}>
          {meta.icon}
        </span>
        <span className={`text-xs font-semibold ${ac.text}`}>{agent}</span>
        <span className="text-[10px] text-slate-600">{formatRelative(event.timestamp)}</span>
      </div>
      <p className="text-xs text-slate-300 line-clamp-2 mt-0.5 ml-7">{label}</p>
    </div>
  )
})

// --- ActivityFeed main ---

export function ActivityFeed() {
  const { events, clearFeed } = useAgentActivity()

  return (
    <div className="flex h-full flex-col bg-surface-800">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-surface-700 p-3">
        <div className="flex items-center gap-2">
          <StatusDot status={events.length > 0 ? 'active' : 'inactive'} animated />
          <h3 className="text-sm font-semibold text-slate-200">Activity</h3>
        </div>
        {events.length > 0 && (
          <button
            onClick={clearFeed}
            className="text-xs text-slate-500 hover:text-slate-300"
          >
            Clear
          </button>
        )}
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {events.length === 0 ? (
          <p className="py-8 text-center text-xs text-slate-600">Waiting for activity...</p>
        ) : (
          events.map((event) => <ActivityFeedItem key={event.id} event={event} />)
        )}
      </div>
    </div>
  )
}
