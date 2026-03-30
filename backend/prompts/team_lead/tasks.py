# Re-export all task prompt functions for backward compatibility.
from backend.prompts.team_lead.plan_tasks import (
    consolidate_ideas,
    create_plan,
    create_single_ticket,
    create_tasks_from_ideas,
    select_ideas,
    set_all_dependencies,
)
from backend.prompts.team_lead.progress_tasks import (
    evaluate_progress,
    handle_escalation,
)
from backend.prompts.team_lead.structure_tasks import (
    create_epics_and_milestones,
    create_repository,
    create_structure,
)

__all__ = [
    "consolidate_ideas",
    "create_epics_and_milestones",
    "create_plan",
    "create_repository",
    "create_single_ticket",
    "create_structure",
    "create_tasks_from_ideas",
    "evaluate_progress",
    "handle_escalation",
    "select_ideas",
    "set_all_dependencies",
]
