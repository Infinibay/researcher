# ResearchFlow

**File:** `backend/flows/research_flow.py`
**State Model:** `ResearchState`
**Purpose:** Manages research task lifecycle including literature review, hypothesis formulation, investigation, report writing, peer review, and knowledge base integration.

## State Model

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | str | Parent project ID |
| `task_id` | str | Research task being worked on |
| `task_title` | str | Human-readable task title |
| `researcher_id` | str | Assigned Researcher agent ID |
| `hypothesis` | str | Formulated research hypothesis |
| `findings` | list | Accumulated research findings |
| `confidence_scores` | list | Confidence scores for findings |
| `peer_review_status` | str | `VALIDATED` or `REJECTED` |
| `validated` | bool | Whether research passed peer review |
| `report_path` | str | Path to the written research report |
| `references` | list | Collected references |
| `knowledge_service_enabled` | bool | Whether knowledge indexing is active |

## Flow Diagram

```mermaid
flowchart TD
    START(["START<br/>Called from MainProjectFlow"]) --> assign["assign_research<br/>Load task, assign to Researcher<br/>Status → in_progress"]

    assign -->|"task_assigned"| lit_review["literature_review<br/>🤖 Researcher<br/>Search for relevant papers/sources"]

    lit_review -->|"literature_reviewed"| hypothesis["formulate_hypothesis<br/>🤖 Researcher<br/>Formulate research hypothesis"]

    hypothesis -->|"hypothesis_created"| investigate["investigate<br/>🤖 Researcher<br/>In-depth investigation"]

    investigate -->|"findings_recorded"| write_report["write_report<br/>🤖 Researcher<br/>Write structured research report"]

    write_report -->|"report_written"| peer_review["request_peer_review<br/>🤖 Research Reviewer<br/>Evaluate research quality"]

    peer_review --> peer_router{"peer_review_router<br/>Route by review outcome"}

    peer_router -->|"validated<br/>(VALIDATED)"| update_kb["update_knowledge_base<br/>Index validated findings<br/>Persist researcher memory<br/>Task → done"]
    peer_router -->|"rejected<br/>(REJECTED)"| revise["revise_research<br/>🤖 Researcher<br/>Revise based on feedback"]

    revise -->|"findings_recorded"| write_report

    update_kb --> END_DONE(["END - Research Complete<br/>Returns to MainProjectFlow"])

    style START fill:#4CAF50,color:#fff
    style END_DONE fill:#2196F3,color:#fff
    style peer_router fill:#FF9800,color:#fff
    style update_kb fill:#00BCD4,color:#fff
```

## Research Pipeline Detail

```mermaid
sequenceDiagram
    participant RF as ResearchFlow
    participant RES as Researcher
    participant RR as Research Reviewer
    participant KB as Knowledge Service
    participant MEM as Memory Service

    RF->>RES: Assign research task
    RES->>RES: Literature review
    RES->>RES: Formulate hypothesis
    RES->>RES: Investigate in depth
    RES->>RES: Write research report

    RF->>RR: Request peer review

    alt VALIDATED
        RR->>RF: VALIDATED
        RF->>KB: Index findings
        RF->>MEM: Persist researcher memory
    else REJECTED
        RR->>RF: REJECTED + feedback
        RF->>RES: Revise research
        RES->>RES: Rewrite report
        Note over RF: Loop back to peer review
    end
```

## Knowledge Integration

When research is validated, the flow:

1. **Indexes findings** in the Knowledge Service for future reference by other agents
2. **Persists researcher memory** via the Memory Service, allowing the agent to learn from past research
3. **Marks task as done** in the database

```mermaid
flowchart LR
    validated["Validated Research"] --> KB["Knowledge Service<br/>📚 Index findings"]
    validated --> MEM["Memory Service<br/>🧠 Persist agent memory"]
    validated --> DB["Database<br/>✅ Task → done"]

    style KB fill:#00BCD4,color:#fff
    style MEM fill:#9C27B0,color:#fff
    style DB fill:#4CAF50,color:#fff
```

## Key Decision Points

1. **Peer Review Outcome** - Research Reviewer validates or rejects findings. Rejection triggers a revision loop.

## Agent Responsibilities

| Agent | Actions |
|-------|---------|
| **Researcher** | Literature review, hypothesis formulation, investigation, report writing, revisions |
| **Research Reviewer** | Peer review, validation/rejection with feedback |
