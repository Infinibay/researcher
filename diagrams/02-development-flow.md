# DevelopmentFlow

**File:** `backend/flows/development_flow.py`
**State Model:** `DevelopmentState`
**Purpose:** Manages the development lifecycle for a single code task, including assignment, check-in protocol, implementation, and code review.

## State Model

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | str | Parent project ID |
| `task_id` | str | Task being worked on |
| `task_title` | str | Human-readable task title |
| `task_description` | str | Detailed task description |
| `branch_name` | str | Git branch for the implementation |
| `developer_id` | str | Assigned developer agent ID |
| `review_status` | str | Review outcome (`APPROVED` / `ESCALATED`) |
| `escalated` | bool | Whether the task was escalated |
| `dependencies_met` | bool | Whether task dependencies are satisfied |
| `checkin_thread_id` | str | Thread ID for TicketProtocol check-in |
| `checkin_approved` | bool | Whether Team Lead approved the check-in |

## Flow Diagram

```mermaid
flowchart TD
    START(["START<br/>Called from MainProjectFlow"]) --> assign["assign_task<br/>🤖 Team Lead (TakeTask tool)<br/>🤖 Developer (review assignment)<br/>Initiate TicketProtocol check-in"]

    assign -->|"blocked"| handle_blocked["handle_blocked<br/>Return task to backlog"]
    assign -->|"checkin_initiated"| wait_checkin["wait_for_checkin_approval<br/>Poll for Team Lead approval<br/>⏱️ Max wait: 30 min"]

    handle_blocked --> END_BLOCKED(["END - Task Blocked"])

    wait_checkin -->|"Team Lead requests clarification"| dev_clarify["🤖 Developer<br/>Responds to clarification"]
    dev_clarify --> wait_checkin

    wait_checkin -->|"task_assigned<br/>(checkin approved)"| implement["implement_code<br/>🤖 Developer<br/>Create branch, write code, commit"]

    wait_checkin -->|"timeout (30 min)"| implement

    implement -->|"implementation_done"| request_review["request_review<br/>➡️ CodeReviewFlow"]

    request_review -->|"review_complete<br/>(APPROVED)"| finalize["finalize_task<br/>Mark task as done"]
    request_review -->|"escalated"| handle_escalation["handle_escalation<br/>🤖 Team Lead<br/>Create escalation task"]

    handle_escalation --> finalize_esc["finalize_after_escalation<br/>Mark task as done"]

    finalize --> END_DONE(["END - Task Complete<br/>Returns to MainProjectFlow"])
    finalize_esc --> END_DONE

    style START fill:#4CAF50,color:#fff
    style END_BLOCKED fill:#f44336,color:#fff
    style END_DONE fill:#2196F3,color:#fff
    style request_review fill:#9C27B0,color:#fff
    style handle_escalation fill:#FF9800,color:#fff
```

## TicketProtocol Check-in Sequence

```mermaid
sequenceDiagram
    participant TL as Team Lead
    participant DEV as Developer
    participant DB as Database

    DEV->>DB: Review assigned task
    DEV->>TL: Submit check-in (understanding of task)

    alt Needs Clarification
        TL->>DEV: Request clarification
        DEV->>TL: Respond with details
    end

    TL->>DB: Approve check-in
    Note over DEV: Proceeds to implementation
```

## Key Decision Points

1. **Dependency Check** - If task dependencies are not met, the task is returned to the backlog (blocked).
2. **Check-in Gate** - Developer must demonstrate understanding of the task before implementation begins. Team Lead can request clarification.
3. **Review Outcome** - After CodeReviewFlow, either the task is approved or escalated (after 3+ rejections).

## Agent Responsibilities

| Agent | Actions |
|-------|---------|
| **Team Lead** | Takes task (TakeTask tool), approves check-in, handles escalations |
| **Developer** | Reviews assignment, submits check-in, creates branch, implements code, commits |
