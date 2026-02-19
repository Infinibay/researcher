import { useActivityFeedStore } from '../stores/activityFeed'

export function useAgentActivity() {
  const events = useActivityFeedStore((s) => s.events)
  const clearFeed = useActivityFeedStore((s) => s.clearFeed)
  return { events, clearFeed }
}
