import { useState, useMemo } from 'react'
import { useFlowState } from '../../hooks/useFlowState'
import { useProjectStore } from '../../stores/project'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { EmptyState } from '../common/EmptyState'

const MAIN_FLOW_STEPS = [
  { id: 'initialize_project', label: 'Initialize' },
  { id: 'consult_project_lead', label: 'Requirements' },
  { id: 'create_plan', label: 'Create Plan' },
  { id: 'setup_repository', label: 'Setup Repo' },
  { id: 'create_structure', label: 'Create Structure' },
  { id: 'check_and_launch_tasks', label: 'Execute Tasks' },
  { id: 'completion_or_brainstorm', label: 'Complete / Brainstorm / Evaluate' },
]

const SUBFLOWS = [
  {
    id: 'ticket_creation_flow',
    label: 'Ticket Creation',
    steps: ['initialize', 'create_epics_and_milestones', 'create_single_ticket', 'set_dependencies'],
  },
  {
    id: 'development_flow',
    label: 'Development',
    steps: ['assign_task', 'wait_for_checkin_approval', 'implement_code', 'request_review', 'finalize_task'],
  },
  {
    id: 'research_flow',
    label: 'Research',
    steps: ['assign_research', 'literature_review', 'formulate_hypothesis', 'investigate', 'write_report', 'request_peer_review', 'update_knowledge_base'],
  },
  {
    id: 'investigation_flow',
    label: 'Investigation',
    steps: ['assign_investigation', 'gather_information', 'write_summary', 'peer_review'],
  },
  {
    id: 'brainstorming_flow',
    label: 'Brainstorming',
    steps: ['start_session', 'consolidate_ideas', 'decision_phase', 'create_tasks_from_ideas'],
  },
]

function StepNode({ label, active }: { label: string; active: boolean }) {
  return (
    <div
      className={`rounded-lg border px-3 py-2 text-xs font-medium text-center min-w-[90px] ${
        active
          ? 'border-sky-400 bg-sky-500/30 text-sky-300 ring-1 ring-sky-400/50'
          : 'border-surface-700 bg-surface-800 text-slate-400'
      }`}
    >
      {label}
    </div>
  )
}

function StepRow({ steps, activeStep }: { steps: { id: string; label: string }[]; activeStep: string | null }) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto py-1">
      {steps.map((step, i) => (
        <div key={step.id} className="flex items-center gap-2 shrink-0">
          {i > 0 && <span className="text-slate-600 text-xs">&rarr;</span>}
          <StepNode label={step.label} active={activeStep === step.id} />
        </div>
      ))}
    </div>
  )
}

function humanizeStep(id: string): string {
  return id
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function FlowPage() {
  const projectId = useProjectStore((s) => s.activeProjectId)
  const { data: flowState, isLoading, isError } = useFlowState()

  const activeSubflowId = flowState?.subflow_name ?? null
  const activeSubflowStep = flowState?.subflow_step ?? null

  // Track open/closed state per subflow
  const initialOpen = useMemo(() => {
    const map: Record<string, boolean> = {}
    for (const sf of SUBFLOWS) {
      map[sf.id] = sf.id === activeSubflowId
    }
    return map
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSubflowId])

  const [openState, setOpenState] = useState<Record<string, boolean>>(initialOpen)

  // Sync open state when active subflow changes
  useMemo(() => {
    setOpenState((prev) => {
      const next = { ...prev }
      for (const sf of SUBFLOWS) {
        if (sf.id === activeSubflowId) next[sf.id] = true
      }
      return next
    })
  }, [activeSubflowId])

  const toggle = (id: string) => setOpenState((prev) => ({ ...prev, [id]: !prev[id] }))

  if (projectId == null) {
    return <EmptyState title="No project selected" description="Select a project to view the flow diagram." />
  }

  if (isLoading) {
    return <LoadingSpinner />
  }

  const hasSnapshot = flowState && !isError && flowState.current_step != null

  // Map backend final-phase step names to the composite node ID
  const FINAL_PHASE_STEPS = new Set([
    'evaluate_completion', 'brainstorm_or_continue', 'completion_or_brainstorm',
    'finalize', 'project_completed',
  ])

  let mainActiveStep: string | null = null
  if (hasSnapshot && flowState.current_step) {
    mainActiveStep = FINAL_PHASE_STEPS.has(flowState.current_step)
      ? 'completion_or_brainstorm'
      : flowState.current_step
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-100">Flow Progress</h1>

      {/* Main Flow */}
      <section>
        <h2 className="text-sm font-medium text-slate-300 mb-3">Main Flow</h2>
        <div className="rounded-lg border border-surface-700 bg-surface-900 p-4 overflow-x-auto">
          <StepRow
            steps={MAIN_FLOW_STEPS}
            activeStep={mainActiveStep}
          />
        </div>
      </section>

      {/* Subflows */}
      <section>
        <h2 className="text-sm font-medium text-slate-300 mb-3">Subflows</h2>
        <div className="space-y-3">
          {SUBFLOWS.map((sf) => {
            const isActive = activeSubflowId === sf.id
            const isOpen = openState[sf.id] ?? false

            // Find which step matches (use startsWith for dynamic steps like create_ticket_N_of_M)
            let matchedStep: string | null = null
            if (isActive && activeSubflowStep) {
              matchedStep = sf.steps.find((s) => activeSubflowStep.startsWith(s)) ?? null
            }

            const stepsWithLabels = sf.steps.map((s) => ({ id: s, label: humanizeStep(s) }))

            return (
              <div key={sf.id} className="rounded-lg border border-surface-700 bg-surface-900">
                <button
                  onClick={() => toggle(sf.id)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left"
                >
                  <span className={`text-sm font-medium ${isActive ? 'text-sky-300' : 'text-slate-300'}`}>
                    {sf.label}
                    {isActive && (
                      <span className="ml-2 text-xs text-sky-400/70">(active)</span>
                    )}
                  </span>
                  <span className="text-slate-500 text-xs">{isOpen ? '\u25BC' : '\u25B6'}</span>
                </button>
                {isOpen && (
                  <div className="border-t border-surface-700 px-4 py-3 overflow-x-auto">
                    <StepRow steps={stepsWithLabels} activeStep={matchedStep} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {!hasSnapshot && (
        <p className="text-sm text-slate-500 text-center">
          No active flow &mdash; start the project to see progress.
        </p>
      )}
    </div>
  )
}
