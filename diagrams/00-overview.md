# System Overview - CrewAI Flow Architecture

## Flow Orchestration

```mermaid
graph TB
    subgraph Entry["Entry Points"]
        API["API Layer<br/>(flow_manager.py)"]
        EVT["Event Listeners<br/>(event_listeners.py)"]
    end

    subgraph Flows["CrewAI Flows"]
        MPF["MainProjectFlow<br/>(root orchestrator)"]
        DF["DevelopmentFlow<br/>(code tasks)"]
        CRF["CodeReviewFlow<br/>(review cycle)"]
        RF["ResearchFlow<br/>(research tasks)"]
        BF["BrainstormingFlow<br/>(ideation sessions)"]
    end

    subgraph Agents["Agent Roster (6 roles)"]
        PL["Project Lead"]
        TL["Team Lead"]
        DEV["Developer"]
        CR["Code Reviewer"]
        RES["Researcher"]
        RR["Research Reviewer"]
    end

    subgraph Infrastructure["Shared Infrastructure"]
        DB[(Database)]
        KB["Knowledge Service"]
        MEM["Memory Service"]
        EB["EventBus"]
        SP["State Persistence"]
    end

    API --> MPF
    EVT --> CRF
    EVT --> BF

    MPF -->|"dev tasks"| DF
    MPF -->|"research tasks"| RF
    MPF -->|"objectives not met"| BF
    DF -->|"implementation done"| CRF
    CRF -->|"escalation (>3 rejections)"| DF
    BF -->|"new tasks created"| MPF

    MPF --- PL
    MPF --- TL
    DF --- TL
    DF --- DEV
    CRF --- CR
    CRF --- DEV
    RF --- RES
    RF --- RR
    BF --- TL
    BF --- DEV
    BF --- RES

    Flows --> DB
    Flows --> SP
    RF --> KB
    RF --> MEM
    EVT --> EB
```

## Project Lifecycle (High Level)

```mermaid
stateDiagram-v2
    [*] --> NEW: Project created
    NEW --> PLANNING: Requirements gathered
    PLANNING --> PLANNING: Plan rejected / revise
    PLANNING --> EXECUTING: Plan approved + structure created
    EXECUTING --> EXECUTING: Tasks in progress
    EXECUTING --> EXECUTING: Brainstorming new tasks
    EXECUTING --> COMPLETED: All objectives met
    EXECUTING --> CANCELLED: User cancels
    COMPLETED --> [*]
    CANCELLED --> [*]
```

## Agent Roles Summary

| Agent | Primary Flow(s) | Responsibilities |
|-------|-----------------|-----------------|
| **Project Lead** | MainProjectFlow, BrainstormingFlow | User communication, requirements gathering, plan approval, final report |
| **Team Lead** | MainProjectFlow, DevelopmentFlow, BrainstormingFlow | Planning, task structure (epics/milestones/tasks), assignments, escalations, idea consolidation |
| **Developer** | DevelopmentFlow, CodeReviewFlow, BrainstormingFlow | Code implementation, rework on rejection, idea proposals |
| **Code Reviewer** | CodeReviewFlow | Code quality review, approve/reject decisions |
| **Researcher** | ResearchFlow, BrainstormingFlow | Literature review, hypothesis, investigation, report writing, idea proposals |
| **Research Reviewer** | ResearchFlow | Peer review of research findings, validation |
