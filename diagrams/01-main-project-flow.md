# MainProjectFlow

**File:** `backend/flows/main_project_flow.py`
**State Model:** `ProjectState`
**Purpose:** Root orchestrator for the complete project lifecycle. Manages requirements gathering, planning, task execution, and completion detection.

## State Model

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | str | Unique project identifier |
| `project_name` | str | Human-readable project name |
| `status` | str | `NEW` / `PLANNING` / `EXECUTING` / `COMPLETED` / `CANCELLED` |
| `requirements` | str | Gathered requirements from user |
| `plan` | str | Detailed project plan |
| `user_approved` | bool | Whether user approved the plan |
| `current_task_id` | str | Currently executing task ID |
| `current_task_type` | str | Type of current task (development/research) |
| `epics_created` | int | Count of created epics |
| `milestones_created` | int | Count of created milestones |
| `tasks_created` | int | Count of created tasks |
| `completed_tasks` | int | Count of completed tasks |

## Flow Diagram

```mermaid
flowchart TD
    START(["START"]) --> init["initialize_project<br/>Load or create project"]

    init -->|"new_project"| consult["consult_project_lead<br/>🤖 Project Lead<br/>Gather requirements from user"]
    init -->|"resume"| check_resume["check_pending_after_resume<br/>Query DB for pending tasks"]
    init -->|"already_complete"| END_COMPLETE(["END - Already Complete"])

    consult -->|"requirements_ready"| create_plan["create_plan<br/>🤖 Team Lead<br/>Create detailed plan"]

    create_plan -->|"plan_created"| plan_router{"plan_approval_router<br/>🤖 Project Lead<br/>Present plan to user"}

    plan_router -->|"rejected"| handle_reject["handle_rejection<br/>Clear plan, preserve feedback"]
    plan_router -->|"approved"| create_struct["create_structure<br/>🤖 Team Lead<br/>Create epics/milestones/tasks in DB"]

    handle_reject -->|"requirements_ready"| create_plan

    create_struct -->|"structure_created"| check_struct["check_pending_after_structure<br/>Query DB for pending tasks"]

    check_struct --> route_work
    check_resume --> route_work

    route_work{"route_pending_work<br/>Route by task type"}
    route_work -->|"development"| run_dev["run_development_flow<br/>➡️ DevelopmentFlow"]
    route_work -->|"research"| run_research["run_research_flow<br/>➡️ ResearchFlow"]
    route_work -->|"no_pending_tasks"| completion{"completion_router<br/>Check all objectives met"}

    run_dev -->|"task_flow_complete"| check_task["check_pending_after_task<br/>Query DB for pending tasks"]
    run_research -->|"task_flow_complete"| check_task

    check_task --> route_work

    completion -->|"project_complete"| finalize["finalize<br/>🤖 Project Lead<br/>Mark COMPLETED, generate final report"]
    completion -->|"not_complete"| brainstorm["trigger_brainstorming<br/>➡️ BrainstormingFlow<br/>Generate new tasks/ideas"]

    brainstorm -->|"brainstorming_done"| check_struct

    finalize --> END_DONE(["END - Project Complete"])

    stagnation["handle_stagnation<br/>(external event)"] -.->|"stagnation_detected"| brainstorm

    style START fill:#4CAF50,color:#fff
    style END_COMPLETE fill:#2196F3,color:#fff
    style END_DONE fill:#2196F3,color:#fff
    style plan_router fill:#FF9800,color:#fff
    style route_work fill:#FF9800,color:#fff
    style completion fill:#FF9800,color:#fff
    style run_dev fill:#9C27B0,color:#fff
    style run_research fill:#9C27B0,color:#fff
    style brainstorm fill:#9C27B0,color:#fff
```

## Key Decision Points

1. **Plan Approval Router** - User must approve the plan before execution begins. Rejection loops back with feedback.
2. **Route Pending Work** - Dispatches tasks by type: `development` or `research`. When no tasks remain, checks completion.
3. **Completion Router** - Determines if all project objectives are met. If not, triggers brainstorming for new ideas/tasks.

## Sub-Flow Invocations

| Sub-Flow | Trigger | Returns To |
|----------|---------|------------|
| `DevelopmentFlow` | Task type = development/bug_fix/test/integration/design | `check_pending_after_task` |
| `ResearchFlow` | Task type = research | `check_pending_after_task` |
| `BrainstormingFlow` | Objectives not met after all tasks done | `check_pending_after_structure` |
