"""Helper utilities for PABADA flows — re-export shim.

All functions have been split into focused modules:
- db_helpers: project/task CRUD and queries
- messaging: inter-agent messaging
- parsing: review results, plans, ideas
- tech_detection: repository technology scanning
- ci_helpers: CI gate output parsing and recording
- reporting: final reports, event logging, agent execution
- stagnation: stagnation detection

This module re-exports every public symbol so that existing
``from backend.flows.helpers import X`` statements keep working.
"""

from backend.flows.helpers.ci_helpers import parse_ci_output, record_ci_result
from backend.flows.helpers.db_helpers import (
    all_objectives_met,
    atomic_claim_task,
    get_active_epic_count,
    check_task_dependencies,
    create_project,
    get_pending_tasks,
    get_project_name,
    get_project_progress_summary,
    get_repo_path_for_task,
    get_task_branch,
    get_task_by_id,
    get_task_count,
    increment_task_retry,
    load_project_state,
    promote_unblocked_dependents,
    set_task_branch,
    update_project_status,
    update_task_status,
    update_task_status_safe,
)
from backend.flows.helpers.messaging import notify_team_lead, send_agent_message
from backend.flows.helpers.parsing import (
    classify_approval_response,
    format_ideas,
    parse_created_ids,
    parse_created_task_id,
    parse_epics_milestones_from_result,
    parse_ideas,
    parse_plan_tasks,
    parse_review_result,
)
from backend.flows.helpers.reporting import (
    build_crew,
    calculate_time_elapsed,
    generate_final_report,
    kickoff_with_retry,
    log_flow_event,
    run_agent_task,
)
from backend.flows.helpers.stagnation import (
    detect_stagnation,
    get_completed_task_count,
    get_stuck_tasks,
    has_active_review_run,
)
from backend.flows.helpers.tech_detection import detect_tech_hints

__all__ = [
    # db_helpers
    "load_project_state",
    "create_project",
    "update_project_status",
    "atomic_claim_task",
    "get_active_epic_count",
    "get_pending_tasks",
    "get_project_name",
    "get_project_progress_summary",
    "get_repo_path_for_task",
    "get_task_by_id",
    "get_task_count",
    "check_task_dependencies",
    "update_task_status",
    "update_task_status_safe",
    "get_task_branch",
    "set_task_branch",
    "increment_task_retry",
    "promote_unblocked_dependents",
    "all_objectives_met",
    # messaging
    "send_agent_message",
    "notify_team_lead",
    # parsing
    "parse_review_result",
    "classify_approval_response",
    "parse_plan_tasks",
    "parse_created_ids",
    "parse_created_task_id",
    "parse_epics_milestones_from_result",
    "parse_ideas",
    "format_ideas",
    # tech_detection
    "detect_tech_hints",
    # ci_helpers
    "parse_ci_output",
    "record_ci_result",
    # reporting
    "build_crew",
    "generate_final_report",
    "kickoff_with_retry",
    "log_flow_event",
    "run_agent_task",
    "calculate_time_elapsed",
    # stagnation
    "detect_stagnation",
    "get_completed_task_count",
    "get_stuck_tasks",
    "has_active_review_run",
]
