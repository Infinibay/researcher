/** Complete proposed hierarchy for owner review, with optional milestones and no implied execution authority. @module */
import type { ProjectPlanDraft } from '../../api/projectPlans'

/** Show every proposed epic, milestone, task and prerequisite before the owner decides on the exact plan. */
export function ProposedWork({ draft }: { draft: ProjectPlanDraft }) {
  const milestones = draft.milestones ?? []
  return <section className="space-y-3" aria-label="Trabajo propuesto">
    <h4 className="font-medium">Trabajo propuesto · {draft.tasks.length} tareas{milestones.length > 0 ? ` · ${milestones.length} hitos` : ''}</h4>
    {draft.epics.map(epic => <div className="space-y-2 rounded-md border border-[var(--work-line)] p-3" key={epic.key}>
      <h5 className="font-medium">{epic.title}</h5>
      <p className="text-[var(--work-muted)]">{epic.description}</p>
      {milestones.some(milestone => milestone.epic_key === epic.key) && <ul className="space-y-2" aria-label={`Hitos de ${epic.title}`}>
        {milestones.filter(milestone => milestone.epic_key === epic.key).map(milestone => <li className="border-l-2 border-[var(--work-line)] pl-3" key={milestone.key}>
          <h6 className="font-medium">Hito: {milestone.title}</h6>
          <p>{milestone.description}</p>
          <p className="text-xs text-[var(--work-muted)]">{milestone.due_date ? `Fecha propuesta: ${milestone.due_date}. Esta fecha no programa ejecuciones.` : 'Sin fecha propuesta.'}</p>
        </li>)}
      </ul>}
      <ol className="space-y-3">{draft.tasks.filter(task => task.epic_key === epic.key).map(task => <li className="space-y-1 border-t border-[var(--work-line)] pt-2" key={task.key}>
        <p className="font-medium">{task.title}</p>
        <p>{task.description}</p>
        <p className="text-[var(--work-muted)]">Resultado comprobable: {task.acceptance_criteria}</p>
        {task.milestone_key && <p className="text-xs text-[var(--work-muted)]">Hito: {milestones.find(milestone => milestone.key === task.milestone_key)?.title ?? task.milestone_key}</p>}
        <p className="text-xs text-[var(--work-muted)]">{task.type === 'research' ? 'Investigación' : task.type === 'bug_fix' ? 'Corrección' : task.type} · prioridad {task.priority} · {task.depends_on.length ? 'Depende de: ' + task.depends_on.map(key => draft.tasks.find(item => item.key === key)?.title ?? key).join(', ') : 'Sin prerrequisitos en este plan'}</p>
      </li>)}</ol>
    </div>)}
  </section>
}
