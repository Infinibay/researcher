import { create } from 'zustand'
import type { AgentActivityEvent } from '../types/api'

const MAX_EVENTS = 100

interface ActivityFeedStore {
  events: AgentActivityEvent[]
  unreadCount: number
  feedOpen: boolean
  addEvent: (event: AgentActivityEvent) => void
  /** Load historical events without inflating unreadCount. */
  loadHistory: (events: AgentActivityEvent[]) => void
  clearFeed: () => void
  toggleFeed: () => void
}

export const useActivityFeedStore = create<ActivityFeedStore>()((set, get) => ({
  events: [],
  unreadCount: 0,
  feedOpen: false,
  addEvent: (event) =>
    set((state) => ({
      events: [event, ...state.events].slice(0, MAX_EVENTS),
      unreadCount: state.feedOpen ? state.unreadCount : state.unreadCount + 1,
    })),
  loadHistory: (history) =>
    set(() => ({
      events: history.slice(0, MAX_EVENTS),
      unreadCount: 0,
    })),
  clearFeed: () => set({ events: [], unreadCount: 0 }),
  toggleFeed: () => {
    const opening = !get().feedOpen
    set({ feedOpen: opening, ...(opening ? { unreadCount: 0 } : {}) })
  },
}))
