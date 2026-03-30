"""Progress-related task prompts: evaluating progress, handling escalations."""

from backend.prompts.team import build_state_context


def evaluate_progress(
    project_id: int,
    project_name: str,
    progress_summary: str,
    plan: str = "",
    requirements: str = "",
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for evaluating project progress.

    Called when all current tasks are done but the project objectives are not
    yet fully met. The Team Lead must evaluate the current state and decide
    whether to create new tickets or trigger a brainstorming session.
    """

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="progress_evaluation",
        summary=(
            "All current tasks have completed but the project objectives are "
            "not yet fully met. You must evaluate the current state, review "
            "research findings, and decide how to proceed."
        ),
    )

    ctx_block = conversation_context or ""

    plan_section = ""
    if plan:
        plan_section = f"""
## Original Plan
{plan}
"""

    requirements_section = ""
    if requirements:
        requirements_section = f"""
## Requirements (PRD)
{requirements}
"""

    description = f"""\
Evaluate the current progress of project '{project_name}' (ID: {project_id}) \
and decide the next steps.

{state_block}

{ctx_block}
{requirements_section}
## Current Progress
{progress_summary}
{plan_section}
## Your Goal
All current tasks have been completed. Before creating ANY new tickets,
you must evaluate what was accomplished and what was learned. Your job is
NOT to immediately create more work \u2014 it is to decide the **smartest
next move**, which might be creating tickets, brainstorming, or declaring
the project complete.

## Step-by-Step Process

### Step 1: Review the Progress Summary Above
The "Current Progress" section above already contains:
- Epic status, task counts by status, in-progress work, pending queue,
  recently completed tasks, research results, and any failed/blocked tasks.

Read it carefully. This is your primary source of truth \u2014 do NOT waste
time calling read_tasks to re-read everything. You already have it.

Only use **get_task** (with a specific task ID) if you need the full
description or acceptance criteria for a particular task.

### Step 2: Check Research Findings (if research tasks completed)
If the progress summary shows completed research tasks, use
**read_findings** to get the detailed findings. Research insights
often inform what development tasks come next.

Optionally use **read_wiki** if researchers produced reports.

### Step 3: Check Messages
Use **read_messages** to check for unread messages \u2014 bug reports,
blockers, or agent recommendations relevant to next steps.

### Step 4: Assess Remaining Gaps
Compare accomplished work against project objectives:
- Which epics are still open and what's missing?
- Do research findings change the direction?
- Are there blocked tasks that need unblocking?

### Step 5: Decide on Next Steps
Based on your analysis, choose ONE of these three paths:

**Path A \u2014 NEW_TICKETS**: You have enough information to define the next
batch of work. This is the correct choice when:
- Research findings provide clear direction for new development tasks.
- The remaining gaps are well-understood and can be broken into specific tasks.
- You know what needs to be built/fixed/investigated to move toward completion.

If choosing this path, produce a plan for ONLY the next batch of tickets.
Apply the same principle as the initial plan: create the **minimum viable
batch** \u2014 only tickets you have enough information to define clearly and
that should start now. Do NOT create speculative tickets.

**Path B \u2014 BRAINSTORM_NEEDED**: You do NOT have enough information to define
specific next steps. This is the correct choice ONLY when:
- Research findings were inconclusive and don't provide a clear path forward.
- The remaining gaps are unclear or ambiguous.
- You genuinely don't know what to do next and need the team to ideate.

**Path C \u2014 PROJECT_COMPLETE**: The project objectives from the original
requirements have been fully met. All required functionality is built,
all research questions answered, and no significant gaps remain. This is
the correct choice ONLY when you have verified (via read_tasks,
read_findings, etc.) that the project can be considered done.

**Important**: Prefer Path A whenever possible. Brainstorming is expensive
(multiple agents, time-limited sessions). If you can define even a few
concrete tasks based on what you know, that is better than brainstorming.
Choose Path C only when the project is genuinely complete.

### Step 6: Output Your Decision
Your response MUST begin with exactly `NEW_TICKETS`, `BRAINSTORM_NEEDED`,
or `PROJECT_COMPLETE` as the first word \u2014 the system parses this automatically.

If NEW_TICKETS: Follow with a complete plan for new tasks. Include:
- Which epic(s) the new tasks belong to (reference existing epic IDs).
- Task titles, types, descriptions with acceptance criteria.
- Dependencies between new tasks and any existing tasks.

If BRAINSTORM_NEEDED: Follow with a clear explanation of:
- What specific gaps or unknowns prevent you from defining tasks.
- What questions the brainstorming session should focus on.
- What constraints or context the brainstorming participants should know.

If PROJECT_COMPLETE: Follow with a summary of:
- Which original requirements were met and how.
- Key deliverables produced.
- Verification that no significant gaps remain.
"""

    expected_output = """\
Your response MUST begin with one of these three verdicts:

NEW_TICKETS
(followed by a detailed plan for new tasks)

\u2014 OR \u2014

BRAINSTORM_NEEDED
(followed by an explanation of why brainstorming is necessary)

\u2014 OR \u2014

PROJECT_COMPLETE
(followed by a summary of completed objectives)

If NEW_TICKETS, include:
1. **Analysis**: Brief summary of what was accomplished and what gaps remain.
2. **New Tasks Plan**: For each new task:
   - Title and type (development/research/test/etc.)
   - Parent epic (reference existing epic ID)
   - Context/Motivation
   - Detailed Description
   - Acceptance Criteria (minimum 3)
   - Technical Notes
   - Definition of Done
   - Priority and complexity
   - Dependencies
3. **Expected Outcome**: What completing these tasks will achieve.

If BRAINSTORM_NEEDED, include:
1. **Analysis**: What was accomplished and what is unclear.
2. **Specific Unknowns**: What questions need to be answered.
3. **Focus Areas**: What the brainstorming session should target.

If PROJECT_COMPLETE, include:
1. **Objectives Met**: Which original requirements were fulfilled.
2. **Key Deliverables**: What was produced.
3. **Verification**: Evidence that no significant gaps remain.

Do not use any other word as the first word. The system parses your
response automatically.
"""
    return description, expected_output


def handle_escalation(
    task_id: int,
    task_title: str,
    branch_name: str,
    developer_id: str,
    project_id: int = 0,
    project_name: str = "",
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for escalation handling."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="escalation",
        summary=(
            f"Task {task_id} ({task_title}) has been escalated after multiple "
            f"code review rejections. Developer: {developer_id}, "
            f"branch: {branch_name}."
        ),
    )

    ctx_block = conversation_context or ""

    description = f"""\
Task {task_id} ({task_title}) has been escalated after multiple review \
rejections.

{state_block}

{ctx_block}

## Escalation Details
- **Task ID**: {task_id}
- **Title**: {task_title}
- **Branch**: `{branch_name}`
- **Developer**: {developer_id}

## Your Goal
Diagnose why the task is stuck in a rejection cycle and take decisive action
to unblock it. The task has failed multiple code reviews, which means either
the requirements are unclear, the developer is struggling with the
implementation, or there is a fundamental mismatch between expectations.

## Step-by-Step Process

### Step 1: Understand the History
Use **get_task** to read the full task with all comments. Trace the
review history:
- What were the original requirements and acceptance criteria?
- What feedback did the Code Reviewer give in each rejection?
- How did the Developer respond to each round of feedback?
- Is the feedback consistent across rounds, or are new issues appearing?

### Step 2: Examine the Code
Use **git_diff** on branch `{branch_name}` to review the current state
of the code. Assess:
- Does the code demonstrate understanding of the requirements?
- Are the reviewer's concerns valid? (Sometimes reviewers are overly strict
  or misunderstand the requirements.)
- Is the developer making progress between iterations, or going in circles?

Use **read_file** if you need more context about the codebase.

### Step 3: Diagnose the Root Cause
The escalation is typically caused by one of these:

**A. Unclear requirements**: The task description or acceptance criteria are
ambiguous, causing the developer and reviewer to interpret them differently.
\u2192 Clarify the requirements. Update the task description with precise
acceptance criteria. If user input is needed, use **ask_project_lead**.

**B. Developer skill mismatch**: The task requires expertise the developer
lacks (unfamiliar technology, complex algorithm, etc.).
\u2192 Provide specific technical guidance, break the task into simpler subtasks,
or reassign to a more experienced developer.

**C. Over-scoped task**: The task tries to do too much and keeps failing on
different aspects each round.
\u2192 Split the task into smaller, focused tasks. Create new tasks with
**create_task** and close or simplify the original.

**D. Reviewer-developer misalignment**: The reviewer expects something
the developer cannot deliver given the constraints (time, technology, etc.).
\u2192 Mediate by clarifying what "good enough" looks like for this task.
Add a comment with the agreed standard.

**E. Persistent technical issue**: A bug or integration problem that the
developer cannot resolve alone.
\u2192 Provide specific technical guidance or pair the developer with another
agent who has relevant expertise.

### Step 4: Take Action
Based on your diagnosis, choose one or more of these actions:

1. **Clarify requirements**: Update the task description with precise,
   unambiguous acceptance criteria via **add_comment** or by creating
   an updated task.
2. **Provide technical guidance**: Send specific implementation guidance
   to the developer via **send_message**. Be concrete \u2014 reference
   specific files, patterns, or approaches.
3. **Simplify the task**: Reduce scope. Remove non-essential requirements.
   Focus on the core functionality.
4. **Split the task**: Create 2-3 smaller tasks with **create_task**,
   each with clear, achievable acceptance criteria. Set dependencies with
   **set_task_dependencies**.
5. **Reassign**: If the developer is fundamentally stuck, assign to another
   developer via **send_message**.
6. **Escalate to Project Lead**: If the root cause is a requirements issue
   that needs user input, use **ask_project_lead**.

### Step 5: Document the Resolution
Use **add_comment** to document on the task:
- Your diagnosis of the root cause.
- The action taken and why.
- Updated expectations for the next iteration.
- Any changes to scope, requirements, or assignment.

### Step 6: Follow Up
After taking action, use **read_tasks** to monitor whether the
resolution is effective. If the task continues to be rejected, consider
more aggressive intervention (further scope reduction, reassignment, or
escalation to the Project Lead).

### Step 7: Make a Decision
Based on your diagnosis and actions, you MUST decide one of two outcomes:

**READY_FOR_MERGE**: The code on the branch is acceptable as-is (perhaps
after you made direct fixes or clarified that the reviewer was being too
strict). The task can be marked as done without another review cycle.
Use this when:
- You reviewed the code and it meets the acceptance criteria.
- The reviewer's objections were invalid or overly strict.
- You made direct fixes that resolve all outstanding issues.

**NEEDS_REVIEW**: The developer needs to rework the code based on your
guidance, and the result must go through another (shorter) code review
cycle. Use this when:
- You provided technical guidance that the developer must implement.
- You clarified requirements that change what the code should do.
- You simplified the task scope and the developer must adjust.
- The code has genuine issues that need to be fixed before merge.

Your response MUST begin with exactly `READY_FOR_MERGE` or `NEEDS_REVIEW`
as the first word \u2014 no exceptions. The system parses your response
automatically to determine the next step.
"""

    expected_output = """\
Your response MUST begin with one of these two verdicts:

READY_FOR_MERGE
(followed by the escalation resolution details below)

\u2014 OR \u2014

NEEDS_REVIEW
(followed by the escalation resolution details below)

Then include:

1. **Root cause diagnosis**: Which of the common causes (unclear requirements,
   skill mismatch, over-scoping, misalignment, technical issue) applies,
   with evidence from the review history.
2. **Action taken**: Specific steps taken to resolve the situation (guidance
   sent, task split, reassigned, requirements clarified, etc.).
3. **Task updates**: Any changes to the task description, acceptance criteria,
   or assignment documented via add_comment.
4. **New tasks created** (if task was split): List of new task IDs with
   titles and descriptions.
5. **Communication**: Messages sent to the developer, reviewer, or Project
   Lead as part of the resolution.
6. **Expected outcome**: What should happen next and when to check back.

Do not use any other word as the first word. The system parses your
response automatically.
"""
    return description, expected_output
