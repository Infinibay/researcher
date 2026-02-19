import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { wsManager } from '../api/websocket'
import { useProjectStore } from '../stores/project'
import { useActivityFeedStore } from '../stores/activityFeed'
import type { WSEvent, AgentActivityEvent } from '../types/api'

const ACTIVITY_EVENT_TYPES = new Set([
  'message_sent',
  'agent_message_received',
  'notification_sent',
  'user_request_created',
  'user_request_responded',
])

export function useWebSocketSync() {
  const queryClient = useQueryClient()
  const projectId = useProjectStore((s) => s.activeProjectId)

  useEffect(() => {
    if (projectId == null) return

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

      // Push activity events into the feed store
      if (ACTIVITY_EVENT_TYPES.has(t)) {
        const ts = event.timestamp ?? new Date().toISOString()
        const d = event.data ?? {}
        let activityEvent: AgentActivityEvent | null = null

        if (t === 'message_sent') {
          activityEvent = {
            id: `${t}-${event.entity_id ?? 0}-${ts}`,
            type: t,
            timestamp: ts,
            from_agent: d.from_agent,
            to_agent: d.to_agent,
            to_role: d.to_role,
            content: d.content ?? d.message ?? '(message sent)',
            entity_id: event.entity_id,
          }
        } else if (t === 'agent_message_received') {
          activityEvent = {
            id: `${t}-${event.entity_id ?? 0}-${ts}`,
            type: t,
            timestamp: ts,
            from_agent: d.from_agent,
            to_agent: d.to_agent ?? d.target_id,
            to_role: d.to_role,
            content: d.content,
            entity_id: event.entity_id,
          }
        } else if (t === 'notification_sent') {
          activityEvent = {
            id: `${t}-${event.entity_id ?? 0}-${ts}`,
            type: t,
            timestamp: ts,
            from_agent: d.from_agent,
            kind: d.kind,
            content: d.title ?? d.kind ?? 'Notification',
            entity_id: event.entity_id,
          }
        } else if (t === 'user_request_created') {
          activityEvent = {
            id: `${t}-${event.entity_id ?? 0}-${ts}`,
            type: t,
            timestamp: ts,
            content: 'User input requested',
            entity_id: event.entity_id,
          }
        } else if (t === 'user_request_responded') {
          activityEvent = {
            id: `${t}-${event.entity_id ?? 0}-${ts}`,
            type: t,
            timestamp: ts,
            content: 'User responded',
            entity_id: event.entity_id,
          }
        }

        if (activityEvent) {
          useActivityFeedStore.getState().addEvent(activityEvent)
        }
      }
    }

    wsManager.subscribe(handler)

    return () => {
      wsManager.unsubscribe(handler)
      wsManager.disconnect()
      useActivityFeedStore.getState().clearFeed()
    }
  }, [projectId, queryClient])
}
