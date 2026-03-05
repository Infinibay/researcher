import { create } from 'zustand'

interface LoopPlanStep {
  index: number
  description: string
  status: 'pending' | 'active' | 'done' | 'skipped'
}

interface AgentLoopState {
  iteration: number
  stepDescription: string
  status: string
  summary: string
  planSteps: LoopPlanStep[]
  toolCallsStep: number
  toolCallsTotal: number
  tokensTotal: number
  lastToolName?: string
  lastToolDetail?: string
}

interface LoopStateStore {
  agents: Record<string, AgentLoopState>
  updateStep: (agentId: string, data: Omit<AgentLoopState, 'lastToolName' | 'lastToolDetail'>) => void
  updateToolCall: (agentId: string, toolName: string, toolDetail: string, callNum: number, total: number) => void
  clearAgent: (agentId: string) => void
}

export const useLoopStateStore = create<LoopStateStore>()((set) => ({
  agents: {},
  updateStep: (agentId, data) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentId]: { ...data, lastToolName: state.agents[agentId]?.lastToolName },
      },
    })),
  updateToolCall: (agentId, toolName, toolDetail, _callNum, total) =>
    set((state) => ({
      agents: {
        ...state.agents,
        [agentId]: {
          ...(state.agents[agentId] ?? {
            iteration: 0,
            stepDescription: '',
            status: 'continue',
            summary: '',
            planSteps: [],
            toolCallsStep: 0,
            toolCallsTotal: 0,
            tokensTotal: 0,
          }),
          lastToolName: toolName,
          lastToolDetail: toolDetail || undefined,
          toolCallsTotal: total,
        },
      },
    })),
  clearAgent: (agentId) =>
    set((state) => {
      const { [agentId]: _, ...rest } = state.agents
      return { agents: rest }
    }),
}))
