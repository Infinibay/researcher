/** Render the actual owner hierarchy preview without an API, model or approval action. @module */
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { ProposedWork } from '../src/components/tasks/ProposedWork'
import type { ProjectPlanDraft } from '../src/api/projectPlans'

/** Keep both historical drafts and new milestones readable through the production component. */
export function renderPlan(withMilestones = true) {
  const draft: ProjectPlanDraft = {
    title: 'Improve the parser', rationale: 'Observe before changing behavior.', assumptions: [], basis: [],
    epics: [{key:'parser',title:'Parser checks',description:'Preserve the observed input contract.'}],
    tasks: [
      {key:'read',epic_key:'parser',type:'research',title:'Read current behavior',description:'Compare original inputs.',acceptance_criteria:'Exact source references.',priority:2,depends_on:[]},
      {key:'change',epic_key:'parser',type:'code',title:'Change the parser',description:'Preserve source locations.',acceptance_criteria:'Demonstrated cases pass.',priority:2,depends_on:['read']},
    ],
  }
  if (withMilestones) {
    draft.milestones = [{key:'evidence',epic_key:'parser',title:'Evidence gathered',description:'Observed cases and limits.',due_date:'2027-01-15'}]
    draft.tasks[0].milestone_key = 'evidence'
  }
  return renderToStaticMarkup(<ProposedWork draft={draft} />)
}
