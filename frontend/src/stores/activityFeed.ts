import { create } from 'zustand'
import type { AgentActivityEvent } from '../types/api'

const MAX_EVENTS = 100

interface ActivityFeedStore {
  events: AgentActivityEvent[]
  addEvent: (event: AgentActivityEvent) => void
  clearFeed: () => void
}

export const useActivityFeedStore = create<ActivityFeedStore>()((set) => ({
  events: [],
  addEvent: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, MAX_EVENTS),
    })),
  clearFeed: () => set({ events: [] }),
}))
