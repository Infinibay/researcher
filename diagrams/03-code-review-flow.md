# CodeReviewFlow

**File:** `backend/flows/code_review_flow.py`
**State Model:** `CodeReviewState`
**Purpose:** Manages the code review cycle with iterative feedback, rework, and escalation after repeated rejections.

## State Model

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | str | Parent project ID |
| `task_id` | str | Task being reviewed |
| `branch_name` | str | Git branch under review |
| `review_status` | str | Current review status |
| `reviewer_id` | str | Assigned Code Reviewer agent ID |
| `developer_id` | str | Developer who wrote the code |
| `agent_run_id` | str | Current agent run ID |
| `reviewer_comments` | list | Accumulated review comments |
| `rejection_count` | int | Number of times review was rejected |
| `max_rejections` | int | Maximum rejections before escalation (default: 3) |

## Flow Diagram

```mermaid
flowchart TD
    START(["START<br/>Called from DevelopmentFlow"]) --> receive["receive_review_request<br/>Load task and branch info"]

    receive -->|"review_requested"| review["perform_review<br/>🤖 Code Reviewer<br/>Review code on branch"]

    review -->|"review_approved<br/>(APPROVED)"| finalize["finalize_approval<br/>Mark task as done"]
    review -->|"review_rejected<br/>(REJECTED)"| rejection_router{"rejection_router<br/>Check rejection count"}

    rejection_router -->|"rejection_count < 3<br/>→ request_rework"| rework["notify_developer_rework<br/>🤖 Developer<br/>Rework code based on feedback"]
    rejection_router -->|"rejection_count >= 3<br/>→ escalate"| escalate["handle_escalation<br/>Notify Team Lead with full context"]

    rework -->|"review_ready<br/>(resubmit)"| review

    finalize --> END_APPROVED(["END - APPROVED<br/>Returns to DevelopmentFlow"])
    escalate --> END_ESCALATED(["END - ESCALATED<br/>Returns to DevelopmentFlow"])

    style START fill:#4CAF50,color:#fff
    style END_APPROVED fill:#2196F3,color:#fff
    style END_ESCALATED fill:#f44336,color:#fff
    style rejection_router fill:#FF9800,color:#fff
```

## Review Cycle Detail

```mermaid
sequenceDiagram
    participant CRF as CodeReviewFlow
    participant CR as Code Reviewer
    participant DEV as Developer
    participant TL as Team Lead

    CRF->>CR: Request review (branch)

    alt APPROVED
        CR->>CRF: APPROVED
        CRF->>CRF: Finalize (task = done)
    else REJECTED (attempt 1-2)
        CR->>CRF: REJECTED + comments
        CRF->>DEV: Rework request + feedback
        DEV->>CRF: Code reworked, resubmit
        Note over CRF: Loop back to review
    else REJECTED (attempt 3 - escalation)
        CR->>CRF: REJECTED + comments
        Note over CRF: rejection_count >= max_rejections
        CRF->>TL: Escalate with full context
        Note over CRF: Returns ESCALATED to DevelopmentFlow
    end
```

## Escalation Warning

At `rejection_count == 2`, the flow notifies the Team Lead with an escalation warning, giving visibility before the final attempt.

```mermaid
flowchart LR
    R1["Rejection #1<br/>→ Rework"] --> R2["Rejection #2<br/>→ Rework + ⚠️ Warning to TL"] --> R3["Rejection #3<br/>→ 🚨 Escalation"]

    style R1 fill:#FFC107,color:#000
    style R2 fill:#FF9800,color:#fff
    style R3 fill:#f44336,color:#fff
```

## Key Decision Points

1. **Review Outcome** - Code Reviewer decides APPROVED or REJECTED based on code quality.
2. **Rejection Router** - Counts rejections. Under threshold: rework loop. At/over threshold: escalation.

## Agent Responsibilities

| Agent | Actions |
|-------|---------|
| **Code Reviewer** | Reviews code on branch, provides comments, decides APPROVED/REJECTED |
| **Developer** | Reworks code based on reviewer feedback, resubmits for review |
| **Team Lead** | Receives escalation notification with full review history (notified, not an active participant) |
