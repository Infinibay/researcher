import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { wsManager } from '../api/websocket'
import { fetchApi } from '../api/client'
import { useProjectStore } from '../stores/project'
import { useActivityFeedStore } from '../stores/activityFeed'
import { useLoopStateStore } from '../stores/loopState'
import type { WSEvent, AgentActivityEvent } from '../types/api'

const ACTIVITY_EVENT_TYPES = new Set([
  'message_sent',
  'agent_message_received',
  'notification_sent',
  'user_request_created',
  'user_request_responded',
  // Flow events
  'task_assigned',
  'task_completed',
  'task_status_changed',
  'review_started',
  'review_approved',
  'review_rejected',
  'review_escalated',
  'review_finalized',
  'rework_completed',
  'ci_gate_passed',
  'ci_gate_failed',
  'ci_gate_rejected',
  'checkin_reviewed',
  'ticket_checkin_approved',
  'brainstorm_started',
  'brainstorm_tasks_created',
  'ideas_consolidated',
  'ideas_selected',
  'brainstorm_ideas_approved',
  'brainstorm_ideas_rejected',
  'plan_approved',
  'plan_created',
  'structure_created',
  'task_created',
  'wiki_updated',
  'git_committed',
  'git_pushed',
  'branch_created',
  'pr_created',
  'implementation_done',
  'post_escalation_rework_completed',
  'escalation_resolved',
  'repo_created',
  'repo_archived',
  'flow_error',
  'sub_flow_failed',
  'flow_step_changed',
])

/** Build a human-readable content string for flow activity events. */
function buildFlowEventContent(t: string, d: Record<string, any>, entityId?: number): string {
  switch (t) {
    case 'task_assigned':
      return `Tarea asignada: ${d.task_title ?? entityId}`
    case 'task_completed':
      return `Tarea completada: ${d.task_title ?? entityId}`
    case 'task_status_changed':
      return `Tarea #${entityId} → ${d.new_status}`
    case 'review_started':
      return `Revisión iniciada en branch ${d.branch_name}`
    case 'review_approved':
      return `Código aprobado: ${d.task_title ?? entityId}`
    case 'review_rejected':
      return `Código rechazado (intento ${d.rejection_count}): ${d.task_title ?? entityId}`
    case 'review_escalated':
      return `Escalado al Team Lead: ${d.task_title ?? entityId}`
    case 'review_finalized':
      return `Revisión finalizada: tarea #${entityId}`
    case 'rework_completed':
      return `Rework completado (intento ${d.rejection_count})`
    case 'ci_gate_passed':
      return `CI pasó: ${d.test_pass}/${d.test_count} tests`
    case 'ci_gate_failed':
      return `CI falló: ${d.test_pass ?? 0}/${d.test_count ?? 0} tests`
    case 'ci_gate_rejected':
      return `CI rechazó la tarea #${entityId}`
    case 'checkin_reviewed':
      return `Check-in ${d.result}: ${d.task_title ?? entityId}`
    case 'ticket_checkin_approved':
      return `Check-in aprobado: tarea #${entityId}`
    case 'brainstorm_started':
      return `Brainstorm iniciado con ${d.participants?.join(', ') ?? 'equipo'}`
    case 'brainstorm_tasks_created':
      return 'Tareas creadas desde brainstorm'
    case 'ideas_consolidated':
      return `Ideas consolidadas: ${d.consolidated_count}`
    case 'ideas_selected':
      return `Ideas seleccionadas: ${d.selected_count}`
    case 'brainstorm_ideas_approved':
      return 'Ideas de brainstorm aprobadas'
    case 'brainstorm_ideas_rejected':
      return 'Ideas de brainstorm rechazadas'
    case 'plan_approved':
      return `Plan aprobado para ${d.project_name ?? 'proyecto'}`
    case 'plan_created':
      return 'Plan creado'
    case 'structure_created':
      return 'Estructura del proyecto creada'
    case 'repo_created':
      return `Repositorio creado: ${d.repo_name ?? d.name ?? 'repo'}`
    case 'repo_archived':
      return `Repositorio archivado: ${d.repo_name ?? d.name ?? 'repo'}`
    case 'branch_created':
      return `Branch creado: ${d.branch_name}`
    case 'pr_created':
      return `PR creado: ${d.title}${d.pr_number ? ` (#${d.pr_number})` : ''}`
    case 'task_created':
      return `Tarea creada: ${d.task_title ?? d.title ?? `#${entityId}`}`
    case 'wiki_updated':
      return `Wiki actualizada: ${d.title ?? d.page_title ?? 'página'}`
    case 'git_committed':
      return `Commit: ${d.message ?? d.commit_message ?? d.sha?.slice(0, 7) ?? 'cambios'}`
    case 'git_pushed':
      return `Push a ${d.branch_name ?? d.remote ?? 'remoto'}`
    case 'implementation_done':
      return `Implementación completada en ${d.branch_name}`
    case 'post_escalation_rework_completed':
      return `Rework post-escalamiento completado: ${d.task_title ?? entityId}`
    case 'escalation_resolved':
      return `Escalamiento resuelto: tarea #${entityId}`
    case 'flow_error':
      return `Error en flujo: tarea #${entityId}`
    case 'sub_flow_failed':
      return `Sub-flujo falló: tarea #${entityId}`
    case 'flow_step_changed':
      return `Flow: ${d.flow_name ?? 'main'} → ${d.step ?? d.subflow_step ?? 'unknown'}`
    default:
      return `${t}: #${entityId}`
  }
}

/** Ensure a value is a plain string (guards against backend sending objects). */
function asString(v: unknown, fallback = ''): string {
  if (v == null) return fallback
  if (typeof v === 'string') return v
  if (typeof v === 'object' && v !== null && 'text' in v) return String((v as any).text)
  try { return JSON.stringify(v) } catch { return fallback }
}

/** Unique event counter to avoid duplicate React keys. */
let _eventSeq = 0

/** Convert a WSEvent into an AgentActivityEvent, or null if not an activity type. */
function wsEventToActivity(event: WSEvent): AgentActivityEvent | null {
  const t = event.type
  if (!ACTIVITY_EVENT_TYPES.has(t)) return null

  const ts = event.timestamp ?? new Date().toISOString()
  const d = event.data ?? {}
  const seq = ++_eventSeq

  if (t === 'message_sent') {
    return {
      id: `${t}-${event.entity_id ?? 0}-${ts}-${seq}`,
      type: t,
      timestamp: ts,
      from_agent: d.from_agent,
      to_agent: d.to_agent,
      to_role: d.to_role,
      content: asString(d.content ?? d.message, '(message sent)'),
      entity_id: event.entity_id,
    }
  }
  if (t === 'agent_message_received') {
    return {
      id: `${t}-${event.entity_id ?? 0}-${ts}-${seq}`,
      type: t,
      timestamp: ts,
      from_agent: d.from_agent,
      to_agent: d.to_agent ?? d.target_id,
      to_role: d.to_role,
      content: asString(d.content),
      entity_id: event.entity_id,
    }
  }
  if (t === 'notification_sent') {
    return {
      id: `${t}-${event.entity_id ?? 0}-${ts}-${seq}`,
      type: t,
      timestamp: ts,
      from_agent: d.from_agent,
      kind: d.kind,
      content: asString(d.title ?? d.kind, 'Notification'),
      entity_id: event.entity_id,
    }
  }
  if (t === 'user_request_created') {
    return {
      id: `${t}-${event.entity_id ?? 0}-${ts}-${seq}`,
      type: t,
      timestamp: ts,
      content: 'User input requested',
      entity_id: event.entity_id,
    }
  }
  if (t === 'user_request_responded') {
    return {
      id: `${t}-${event.entity_id ?? 0}-${ts}-${seq}`,
      type: t,
      timestamp: ts,
      content: 'User responded',
      entity_id: event.entity_id,
    }
  }
  // All other flow events
  return {
    id: `${t}-${event.entity_id ?? 0}-${ts}-${seq}`,
    type: t,
    timestamp: ts,
    from_agent: d.agent_id ?? d.developer_id ?? d.reviewer_id,
    content: buildFlowEventContent(t, d, event.entity_id),
    entity_id: event.entity_id,
    task_title: asString(d.task_title),
    branch_name: asString(d.branch_name),
  }
}

export function useWebSocketSync() {
  const queryClient = useQueryClient()
  const projectId = useProjectStore((s) => s.activeProjectId)

  // Load historical events from the API on mount / project change
  useEffect(() => {
    if (projectId == null) return

    let cancelled = false

    fetchApi<WSEvent[]>(`/api/events/${projectId}?limit=100`).then((events) => {
      if (cancelled) return
      // API returns newest-first — convert and keep that order (newest at index 0).
      const activities: AgentActivityEvent[] = []
      for (const ev of events) {
        const a = wsEventToActivity(ev)
        if (a) activities.push(a)
      }
      useActivityFeedStore.getState().loadHistory(activities)
    }).catch(() => {
      // Silently ignore — feed will still work via WebSocket
    })

    return () => { cancelled = true }
  }, [projectId])

  useEffect(() => {
    if (projectId == null) {
      wsManager.disconnect()
      useActivityFeedStore.getState().clearFeed()
      return
    }

    useActivityFeedStore.getState().clearFeed()
    wsManager.connect(projectId)

    const handler = (event: WSEvent) => {
      const t = event.type

      if (t === 'task_created' || t === 'task_updated' || t === 'task_status_changed') {
        queryClient.invalidateQueries({ queryKey: ['tasks'] })
        queryClient.invalidateQueries({ queryKey: ['epics'] })
        queryClient.invalidateQueries({ queryKey: ['milestones'] })
        queryClient.invalidateQueries({ queryKey: ['project'] })
      }

      if (t === 'epic_created' || t === 'epic_updated') {
        queryClient.invalidateQueries({ queryKey: ['epics'] })
        queryClient.invalidateQueries({ queryKey: ['projects'] })
      }

      if (t === 'milestone_created' || t === 'milestone_updated') {
        queryClient.invalidateQueries({ queryKey: ['milestones'] })
        queryClient.invalidateQueries({ queryKey: ['epics'] })
      }

      if (t === 'chat_message') {
        queryClient.invalidateQueries({ queryKey: ['chat'] })
        queryClient.invalidateQueries({ queryKey: ['chat-threads'] })
      }

      if (t === 'wiki_updated') {
        queryClient.invalidateQueries({ queryKey: ['wiki'] })
        queryClient.invalidateQueries({ queryKey: ['wiki-pages'] })
        queryClient.invalidateQueries({ queryKey: ['wiki-page'] })
        queryClient.invalidateQueries({ queryKey: ['wiki-search'] })
      }

      if (t === 'file_uploaded' || t === 'file_deleted') {
        queryClient.invalidateQueries({ queryKey: ['files'] })
      }

      if (t === 'agent_status_changed' || t === 'agent_run_started' || t === 'agent_run_completed') {
        queryClient.invalidateQueries({ queryKey: ['agents'] })
      }

      if (t === 'project_updated') {
        queryClient.invalidateQueries({ queryKey: ['projects'] })
        queryClient.invalidateQueries({ queryKey: ['project'] })
      }

      if (t === 'user_request_created' || t === 'user_request_responded') {
        queryClient.invalidateQueries({ queryKey: ['user-requests'] })
      }

      // Also invalidate queries for specific flow events
      if (t === 'task_assigned' || t === 'task_completed') {
        queryClient.invalidateQueries({ queryKey: ['tasks'] })
        queryClient.invalidateQueries({ queryKey: ['agents'] })
      }

      if (t === 'review_approved' || t === 'review_rejected' || t === 'review_finalized') {
        queryClient.invalidateQueries({ queryKey: ['tasks'] })
      }

      if (t === 'plan_approved' || t === 'structure_created') {
        queryClient.invalidateQueries({ queryKey: ['tasks'] })
        queryClient.invalidateQueries({ queryKey: ['epics'] })
        queryClient.invalidateQueries({ queryKey: ['milestones'] })
        queryClient.invalidateQueries({ queryKey: ['projects'] })
        queryClient.invalidateQueries({ queryKey: ['project'] })
      }

      if (t === 'brainstorm_tasks_created') {
        queryClient.invalidateQueries({ queryKey: ['tasks'] })
        queryClient.invalidateQueries({ queryKey: ['epics'] })
      }

      if (t === 'branch_created' || t === 'pr_created') {
        queryClient.invalidateQueries({ queryKey: ['repos'] })
        queryClient.invalidateQueries({ queryKey: ['repo-branches'] })
        queryClient.invalidateQueries({ queryKey: ['prs'] })
      }

      if (t === 'repo_created' || t === 'repo_archived') {
        queryClient.invalidateQueries({ queryKey: ['repos'] })
      }

      if (t === 'flow_step_changed') {
        queryClient.invalidateQueries({ queryKey: ['flow-state'] })
      }

      // Loop engine progress events
      if (t === 'loop_step_update') {
        const d = event.data
        useLoopStateStore.getState().updateStep(d.agent_id, {
          iteration: d.iteration,
          stepDescription: d.step_description,
          status: d.status,
          summary: d.summary,
          planSteps: d.plan_steps,
          toolCallsStep: d.tool_calls_step,
          toolCallsTotal: d.tool_calls_total,
          tokensTotal: d.tokens_total,
        })
      }
      if (t === 'loop_tool_call') {
        const d = event.data
        useLoopStateStore.getState().updateToolCall(d.agent_id, d.tool_name, d.tool_detail ?? '', d.call_num, d.total_calls)
      }
      if (t === 'loop_finished') {
        useLoopStateStore.getState().clearAgent(event.data.agent_id)
      }

      // Push activity events into the feed store
      const activity = wsEventToActivity(event)
      if (activity) {
        useActivityFeedStore.getState().addEvent(activity)
      }
    }

    wsManager.subscribe(handler)

    return () => {
      wsManager.unsubscribe(handler)
    }
  }, [projectId, queryClient])
}
