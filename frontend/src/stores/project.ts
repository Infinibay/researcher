import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface ProjectStore {
  activeProjectId: number | null
  setActiveProject: (id: number | null) => void
}

export const useProjectStore = create<ProjectStore>()(
  persist(
    (set) => ({
      activeProjectId: null,
      setActiveProject: (id) => set({ activeProjectId: id }),
    }),
    { name: 'active-project' },
  ),
)
