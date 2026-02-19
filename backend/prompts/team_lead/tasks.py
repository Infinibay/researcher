"""Team Lead task prompts used in flows."""

from backend.prompts.shared import GIT_WORKFLOW_INSTRUCTIONS
from backend.prompts.team import build_conversation_context, build_state_context


def create_plan(
    project_name: str,
    project_id: int,
    requirements: str,
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for plan creation."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="planning",
        summary=(
            "Initial planning phase. The Project Lead has delivered the PRD. "
            "Your task is to decompose it into an executable plan."
        ),
    )

    ctx_block = conversation_context or ""

    description = f"""\
Create a detailed project plan for project '{project_name}' (ID: {project_id}).

{state_block}

## Requirements (PRD)
{requirements}

{ctx_block}

## Your Goal
Produce a complete, structured execution plan that decomposes the PRD into
epics, milestones, and tasks with clear dependencies and priorities. The plan
must be detailed enough that developers and researchers can work autonomously
on individual tasks without needing additional context.

## Step-by-Step Process

### Step 1: Analyze the Requirements
Read the PRD above thoroughly. Identify:
- **Core objectives**: What are the 2-5 main goals of this project?
- **Functional areas**: What distinct domains or features does the project
  cover? (e.g., authentication, data pipeline, UI, API, research topics)
- **Dependencies**: What must be built first for other parts to work?
- **Technical risks**: What aspects are uncertain or complex?
- **Non-functional requirements**: Performance, security, scalability
  constraints that affect planning.

### Step 2: Check Existing Context
Use **ReadFindingsTool** to check if there is prior research relevant to
this project. If research findings exist, factor them into your plan —
you may not need to duplicate research that has already been done.

Use **ReadWikiTool** to check for existing documentation about the project
domain or technology stack.

**If either tool returns empty or errors**: This is normal for new projects.
Continue planning without that context — do NOT block or retry. An empty
result simply means no prior research or documentation exists yet.

### Step 3: Define Epics
Group the requirements into 3-7 epics. Each epic should:
- Represent a high-level objective or feature area.
- Be as independent as possible from other epics (minimize cross-epic
  dependencies).
- Have a clear, measurable outcome — "Authentication system" not
  "Various auth stuff".
- Be ordered by priority and dependency (foundational epics first).

### Step 4: Define Milestones
For each epic, define 2-4 milestones. Each milestone should:
- Be a verifiable checkpoint — you can objectively confirm it is done.
- Deliver incremental value — even if the project stops at this milestone,
  something useful has been produced.
- Have a target cycle estimate (relative, not calendar dates).
- Build on the previous milestone within the epic.

Good milestone: "User registration and login functional with email/password"
Bad milestone: "Backend work done"

### Step 5: Define Tasks
For each milestone, create specific tasks. Each task should:
- Be completable by a single agent (developer or researcher) in a
  reasonable cycle.
- Have a clear type:
  - `development`: Code implementation.
  - `research`: Investigation, analysis, literature review.
  - `test`: Test writing, test infrastructure.
  - `documentation`: User docs, API docs, technical docs.
  - `design`: Architecture, API design, schema design.
  - `integration`: Connecting components, end-to-end wiring.
  - `bug_fix`: Fixing defects found during development.
- Include detailed acceptance criteria — specific, verifiable conditions
  that define "done". Not "implement X" but "X accepts input Y and returns
  Z with status 200, validated by tests A, B, C".
- Have a priority: 1 (critical/blocking) to 5 (nice-to-have).
- Have an estimated complexity when possible (low/medium/high).

### Step 6: Define Dependencies
Identify which tasks depend on others:
- A task that requires the output of another task is a dependency.
- Minimize dependency chains — look for opportunities to parallelize.
- Avoid circular dependencies.
- Mark dependencies explicitly, not implicitly (don't rely on ordering).

### Step 7: Validate the Plan
Before outputting, verify:
- [ ] Every PRD requirement is covered by at least one task.
- [ ] Every task has acceptance criteria.
- [ ] Dependencies form a DAG (no cycles).
- [ ] The critical path is identified (the longest dependency chain).
- [ ] Research tasks that inform development are scheduled before the
  development tasks that depend on them.
- [ ] The plan can start immediately — the first tasks have no unresolved
  dependencies.

### Step 8: If Anything Is Ambiguous
If the PRD has gaps or ambiguities that affect planning:
- Use **AskProjectLeadTool** to ask a specific question.
- Do NOT guess at requirements — clarify before committing to a plan.
- Only ask about things that genuinely block planning. Technical decisions
  that you can make yourself should be documented as decisions, not
  escalated.
"""

    expected_output = """\
A structured project plan in markdown containing:

## Plan Summary
Brief overview: number of epics, milestones, tasks. Critical path identified.
Key technical decisions made during planning.

## Epics
For each epic:
- Title and description
- Priority and rationale
- Expected outcome

## Milestones
For each milestone (grouped by epic):
- Title and description
- Target cycle
- Verification criteria
- Dependencies on other milestones (if any)

## Tasks
For each task (grouped by milestone):
- Title and detailed description
- Type (development/research/test/documentation/design/integration/bug_fix)
- Acceptance criteria (specific, verifiable)
- Priority (1-5)
- Estimated complexity (low/medium/high)
- Dependencies (which tasks must complete first)

## Dependency Graph
Summary of the task dependency structure, identifying:
- The critical path
- Parallelizable work streams
- Potential bottlenecks

## Assumptions and Decisions
Technical decisions made during planning and their rationale.
Any assumptions about the project that influenced the plan.
"""
    return description, expected_output


def create_structure(
    project_name: str,
    project_id: int,
    plan: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for DB structure creation."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="structure_creation",
        summary=(
            "The plan has been approved. Create the project structure in the "
            "database using the planning tools."
        ),
    )

    description = f"""\
Create the project structure in the database for project \
'{project_name}' (ID: {project_id}).

{state_block}

## Approved Plan
{plan}

## Your Goal
Translate the approved plan into the project database by creating all epics,
milestones, tasks, and dependencies using the appropriate tools. Every element
from the plan must be represented in the database.

## Step-by-Step Process

### Step 1: Create Epics
Use **CreateEpicTool** for each epic in the plan. For each:
- Set a clear title matching the plan.
- Include the full description from the plan.
- Set appropriate priority.
- Note the returned epic ID — you will need it for milestones.

Create epics in dependency order (foundational epics first).

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (epic title and
error message) and continue creating the remaining epics. Do NOT stop the
entire process because one item failed — you will reconcile failures in
Step 6.

### Step 2: Create Milestones
Use **CreateMilestoneTool** for each milestone. For each:
- Associate it with the correct epic (using the epic ID from Step 1).
- Set the title and description from the plan.
- Set the target cycle if specified in the plan.
- Note the returned milestone ID — you will need it for tasks.

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (milestone title,
parent epic, and error message) and continue with the remaining milestones.
Do NOT stop the entire process because one item failed — you will reconcile
failures in Step 6.

### Step 3: Create Tasks
Use **CreateTaskTool** for each task. For each:
- Associate it with the correct milestone and epic (using IDs from above).
- Set the type (development, research, test, etc.).
- Include the full description with acceptance criteria.
- Set priority (1-5).
- Set estimated complexity if available.
- Note the returned task ID — you will need it for dependencies.

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (task title,
parent milestone, and error message) and continue with the remaining tasks.
Do NOT stop the entire process because one item failed — you will reconcile
failures in Step 6.

### Step 4: Set Dependencies
Use **SetTaskDependenciesTool** to establish all task dependencies from the
plan. For each dependency:
- Specify the task that is blocked (depends on another).
- Specify the task it depends on.
- Verify the dependency makes logical sense (no cycles).

### Step 5: Verify the Structure
Use **ReadTasksTool** to verify that all tasks were created correctly:
- Check that the number of tasks matches the plan.
- Verify dependencies are correctly set.
- Confirm that initial tasks (no dependencies) are ready to be assigned.

### Step 6: Reconcile Failures
Compare the items successfully created against the plan:
- Count the epics, milestones, and tasks that were created vs. planned.
- If there are discrepancies (items that failed in Steps 1-3), attempt to
  create them again now. A transient error (e.g., database busy) may have
  resolved itself.
- If a retry also fails, the item is permanently failed. Collect all
  permanently failed items for the summary in Step 7.
- The final summary (Step 7) must list any items that could not be created.

### Step 7: Post Summary
Use **SendMessageTool** to announce the plan structure is ready. Include:
- Total epics, milestones, and tasks created.
- The critical path.
- Which tasks are ready to be assigned immediately.
- Any items that permanently failed creation (from Step 6), with their
  titles and error details so the team can investigate manually.
"""

    expected_output = """\
A structured summary of the created database structure containing:

1. **Epics created**: List of epic titles with their database IDs.
2. **Milestones created**: List of milestone titles with their IDs,
   grouped by epic.
3. **Tasks created**: List of task titles with their IDs, types, and
   priorities, grouped by milestone.
4. **Dependencies set**: List of dependency relationships (task A depends
   on task B).
5. **Ready to assign**: List of tasks with no dependencies that can be
   assigned immediately.
6. **Verification**: Confirmation that ReadTasksTool was used to verify
   the structure matches the plan.
7. **Failed items**: List of any epics, milestones, or tasks that could
   not be created (with error details), or explicit confirmation that all
   items were created successfully.
"""
    return description, expected_output


def assign_task(
    task_id: int,
    task_title: str,
    task_description: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for task assignment."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="task_assignment",
        summary=(
            f"Task {task_id} is ready to be assigned. Evaluate the task "
            "requirements and assign it to the appropriate agent."
        ),
    )

    description = f"""\
Assign task {task_id} to the appropriate team member.

{state_block}

## Task Details
**Title**: {task_title}
**Description**: {task_description}

## Your Goal
Assign this task to the right agent (developer or researcher) with
sufficient context for them to work autonomously. Ensure the agent
understands what is expected, what the acceptance criteria are, and
any relevant context they might need.

## Step-by-Step Process

### Step 1: Analyze the Task
Read the task description and acceptance criteria. Determine:
- **Task type**: Is this development, research, testing, etc.?
- **Complexity**: Is this straightforward or does it require significant
  context?
- **Dependencies**: Are all prerequisite tasks complete? Use **ReadTasksTool**
  to verify.
- **Context needed**: What additional context does the assignee need beyond
  the task description?

### Step 2: Check for Blockers
Use **ReadTasksTool** to verify that all tasks this one depends on are
complete. If dependencies are not met:
- Do NOT assign the task yet.
- Document the blocker.
- Check if the blocking task can be expedited.

### Step 3: Select the Agent
Choose the appropriate agent based on the task type:
- `development`, `test`, `bug_fix`, `integration` → Developer
- `research` → Researcher
- `documentation` → Developer or Researcher depending on content
- `design` → Developer (for technical design)

If multiple agents of the same role are available, consider workload
balance — check which agents have fewer active tasks.

### Step 4: Provide Context
Use **SendMessageTool** to send the assigned agent a message with:
- A brief summary of what the task requires.
- Any relevant context not in the task description (e.g., architectural
  decisions, related tasks, reference material locations).
- Specific guidance if the task is complex or has non-obvious requirements.
- Pointers to related files, existing code, or prior research findings
  that the agent should review.

### Step 5: Monitor Assignment
Use **AddCommentTool** to document the assignment on the task:
- Who was assigned.
- Any context or guidance provided.
- Expected approach or timeline considerations.
"""

    expected_output = """\
A confirmation of task assignment containing:

1. **Assigned to**: The agent name and role assigned to the task.
2. **Context provided**: Summary of the additional context sent to the agent.
3. **Dependencies verified**: Confirmation that all prerequisite tasks are
   complete (or note of any pending blockers).
4. **Task comment**: Confirmation that the assignment was documented on the
   task via AddCommentTool.
"""
    return description, expected_output


def handle_escalation(
    task_id: int,
    task_title: str,
    branch_name: str,
    developer_id: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for escalation handling."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="escalation",
        summary=(
            f"Task {task_id} ({task_title}) has been escalated after multiple "
            f"code review rejections. Developer: {developer_id}, "
            f"branch: {branch_name}."
        ),
    )

    description = f"""\
Task {task_id} ({task_title}) has been escalated after multiple review \
rejections.

{state_block}

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
Use **GetTaskTool** to read the full task with all comments. Trace the
review history:
- What were the original requirements and acceptance criteria?
- What feedback did the Code Reviewer give in each rejection?
- How did the Developer respond to each round of feedback?
- Is the feedback consistent across rounds, or are new issues appearing?

### Step 2: Examine the Code
Use **GitDiffTool** on branch `{branch_name}` to review the current state
of the code. Assess:
- Does the code demonstrate understanding of the requirements?
- Are the reviewer's concerns valid? (Sometimes reviewers are overly strict
  or misunderstand the requirements.)
- Is the developer making progress between iterations, or going in circles?

Use **ReadFileTool** if you need more context about the codebase.

### Step 3: Diagnose the Root Cause
The escalation is typically caused by one of these:

**A. Unclear requirements**: The task description or acceptance criteria are
ambiguous, causing the developer and reviewer to interpret them differently.
→ Clarify the requirements. Update the task description with precise
acceptance criteria. If user input is needed, use **AskProjectLeadTool**.

**B. Developer skill mismatch**: The task requires expertise the developer
lacks (unfamiliar technology, complex algorithm, etc.).
→ Provide specific technical guidance, break the task into simpler subtasks,
or reassign to a more experienced developer.

**C. Over-scoped task**: The task tries to do too much and keeps failing on
different aspects each round.
→ Split the task into smaller, focused tasks. Create new tasks with
**CreateTaskTool** and close or simplify the original.

**D. Reviewer-developer misalignment**: The reviewer expects something
the developer cannot deliver given the constraints (time, technology, etc.).
→ Mediate by clarifying what "good enough" looks like for this task.
Add a comment with the agreed standard.

**E. Persistent technical issue**: A bug or integration problem that the
developer cannot resolve alone.
→ Provide specific technical guidance or pair the developer with another
agent who has relevant expertise.

### Step 4: Take Action
Based on your diagnosis, choose one or more of these actions:

1. **Clarify requirements**: Update the task description with precise,
   unambiguous acceptance criteria via **AddCommentTool** or by creating
   an updated task.
2. **Provide technical guidance**: Send specific implementation guidance
   to the developer via **SendMessageTool**. Be concrete — reference
   specific files, patterns, or approaches.
3. **Simplify the task**: Reduce scope. Remove non-essential requirements.
   Focus on the core functionality.
4. **Split the task**: Create 2-3 smaller tasks with **CreateTaskTool**,
   each with clear, achievable acceptance criteria. Set dependencies with
   **SetTaskDependenciesTool**.
5. **Reassign**: If the developer is fundamentally stuck, assign to another
   developer via **SendMessageTool**.
6. **Escalate to Project Lead**: If the root cause is a requirements issue
   that needs user input, use **AskProjectLeadTool**.

### Step 5: Document the Resolution
Use **AddCommentTool** to document on the task:
- Your diagnosis of the root cause.
- The action taken and why.
- Updated expectations for the next iteration.
- Any changes to scope, requirements, or assignment.

### Step 6: Follow Up
After taking action, use **ReadTasksTool** to monitor whether the
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
as the first word — no exceptions. The system parses your response
automatically to determine the next step.
"""

    expected_output = """\
Your response MUST begin with one of these two verdicts:

READY_FOR_MERGE
(followed by the escalation resolution details below)

— OR —

NEEDS_REVIEW
(followed by the escalation resolution details below)

Then include:

1. **Root cause diagnosis**: Which of the common causes (unclear requirements,
   skill mismatch, over-scoping, misalignment, technical issue) applies,
   with evidence from the review history.
2. **Action taken**: Specific steps taken to resolve the situation (guidance
   sent, task split, reassigned, requirements clarified, etc.).
3. **Task updates**: Any changes to the task description, acceptance criteria,
   or assignment documented via AddCommentTool.
4. **New tasks created** (if task was split): List of new task IDs with
   titles and descriptions.
5. **Communication**: Messages sent to the developer, reviewer, or Project
   Lead as part of the resolution.
6. **Expected outcome**: What should happen next and when to check back.

Do not use any other word as the first word. The system parses your
response automatically.
"""
    return description, expected_output


def review_checkin(
    task_id: int,
    task_title: str,
    developer_plan: str,
    thread_id: str,
    project_id: int,
) -> tuple[str, str]:
    """Return (description, expected_output) for check-in review."""

    state_block = build_state_context(
        project_id=project_id,
        project_name="",
        phase="checkin_review",
        summary=(
            f"Task {task_id} check-in review. The developer has posted their "
            f"implementation plan in thread {thread_id}. Review it before they "
            "start writing code."
        ),
    )

    description = f"""\
Review the developer's check-in plan for task {task_id} ({task_title}).

{state_block}

## Context
The developer has taken the task and published their implementation plan in \
the check-in thread. Your job is to review that plan before they begin \
writing code.

## Developer's Plan
```
{developer_plan}
```

## Step-by-Step Process

### Step 1 — Read the Plan
Read the developer's plan above word by word. Identify:
- Does the developer understand the requirements?
- Does the plan mention the acceptance criteria?
- Is the technical approach coherent with the task?

### Step 2 — Verify Acceptance Criteria
Use **GetTaskTool** with task_id={task_id} to read the official acceptance \
criteria for the task. Compare them against the developer's plan point by point.

### Step 3 — Decide
You have two options:

**If the plan is correct and complete**: Use **SendMessageTool** to send a \
message to thread `{thread_id}` with the exact text: \
`[Approved] El plan es correcto. Puedes comenzar la implementación.` \
Then write `APPROVED` as the first word of your final response.

**If there are doubts or the plan is incomplete**: Use **SendMessageTool** \
to send a message to thread `{thread_id}` with the exact text: \
`[Clarification Needed] <your specific question>`. \
Then write `CLARIFICATION_NEEDED: <the same question>` as the first line \
of your final response.

## Strict Rules
- Do NOT approve if the developer does not mention how they will verify \
the acceptance criteria.
- Do NOT request clarification about things already in the task description.
- Only one question per clarification round.
- Your response MUST begin with `APPROVED` or `CLARIFICATION_NEEDED:` — \
no exceptions.
"""

    expected_output = """\
Your response must begin OBLIGATORILY with one of these two options:

APPROVED
(followed by a 2-3 line summary of why the plan is acceptable)

— OR —

CLARIFICATION_NEEDED: <specific and concise question>
(followed by the justification of why you need this information)

Do not use any other word as the first word. The system parses your \
response automatically.
"""
    return description, expected_output


def consolidate_ideas(ideas_text: str) -> tuple[str, str]:
    """Return (description, expected_output) for idea consolidation."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="brainstorming_consolidation",
        summary=(
            "The team has generated brainstorming ideas. Your task is to "
            "consolidate, deduplicate, and rank them."
        ),
    )

    description = f"""\
Consolidate the following brainstorming ideas from the team.

{state_block}

## Raw Ideas
{ideas_text}

## Your Goal
Transform the raw brainstorming output into a structured, ranked list of
unique ideas. Remove duplicates, merge similar ideas, and evaluate each
one for viability and impact.

## Step-by-Step Process

### Step 1: Categorize and Group
Read through all ideas and group them by theme or functional area:
- Identify ideas that are essentially the same thing phrased differently
  (duplicates).
- Identify ideas that are different but closely related (candidates for
  merging).
- Identify truly distinct ideas that stand on their own.

### Step 2: Merge and Deduplicate
For each group of similar ideas:
- Combine them into a single, well-defined idea that captures the best
  aspects of each.
- Write a clear title and merged description.
- Preserve any unique nuances from individual ideas.

### Step 3: Evaluate Each Consolidated Idea
For each unique idea, assess:

**Viability** (1-10): Can this be implemented with available resources
and technology?
- 9-10: Straightforward implementation, well-understood technology.
- 6-8: Feasible but requires some exploration or new capabilities.
- 3-5: Significant unknowns or dependencies that add risk.
- 1-2: Highly speculative or requires resources not available.

**Impact** (1-10): How much value does this add to the project?
- 9-10: Core to the project's success, addresses primary user need.
- 6-8: Significant improvement, addresses secondary needs.
- 3-5: Nice to have, incremental improvement.
- 1-2: Marginal value, mostly cosmetic or speculative.

**Effort** (small/medium/large):
- Small: 1-2 tasks, a few days of work.
- Medium: 3-5 tasks, roughly a week of work.
- Large: 6+ tasks, multiple weeks of work.

### Step 4: Rank
Sort the consolidated ideas by a combination of impact and viability,
with effort as a tiebreaker (prefer lower effort when impact/viability
are similar).

### Step 5: Format Output
Present each idea in the format specified in the expected output.
"""

    expected_output = """\
A ranked list of consolidated ideas. For each idea:

- **Title**: Clear, concise name for the idea.
- **Description**: What the idea proposes, merged from all contributing raw
  ideas.
- **Viability**: Score (1-10) with brief justification.
- **Impact**: Score (1-10) with brief justification.
- **Effort**: small / medium / large.
- **Contributing ideas**: Which raw ideas were consolidated into this one.

Ideas should be sorted by impact × viability (highest first), with notes
on any ideas that were discarded as duplicates.
"""
    return description, expected_output


def select_ideas(consolidated_text: str) -> tuple[str, str]:
    """Return (description, expected_output) for idea selection."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="brainstorming_selection",
        summary=(
            "Consolidated ideas are ready. Select the top ideas to present "
            "to the Project Lead for user approval."
        ),
    )

    description = f"""\
Select the top 3-5 ideas from the consolidated list to present to the \
Project Lead.

{state_block}

## Consolidated Ideas
{consolidated_text}

## Your Goal
Select the ideas that offer the best combination of strategic value,
feasibility, and alignment with project goals. These will be presented
to the user via the Project Lead for final approval.

## Step-by-Step Process

### Step 1: Review Against Project Goals
For each consolidated idea, evaluate:
- **Strategic alignment**: Does this directly support the project's stated
  goals and user needs?
- **Technical feasibility**: Given the current codebase, team skills, and
  available time, can this be implemented well?
- **Resource efficiency**: Is the effort justified by the expected impact?
- **Risk**: What could go wrong? How would failure affect the project?

### Step 2: Select Top Ideas
Choose 3-5 ideas based on:
- High impact ideas that are technically feasible should always be included.
- If two ideas are similar in value, prefer the one with lower risk/effort.
- Include at least one "safe bet" (high viability, moderate impact) and
  consider one "high upside" idea (high impact, moderate viability) if
  available.
- Exclude ideas that are clearly out of scope or would require resources
  not available.

### Step 3: Identify Complementary Ideas
Check if any selected ideas are complementary — they work better together
than individually. If so, note this in your output. Also identify any
ideas that conflict with each other (implementing one makes the other
unnecessary or impossible).

### Step 4: Prepare for Presentation
For each selected idea, write:
- A clear description suitable for a non-technical audience.
- Concrete pros and cons (not vague — "adds database dependency" not
  "more complex").
- Recommended priority relative to other selected ideas.
"""

    expected_output = """\
The top 3-5 selected ideas. For each:

- **Title**: The idea name.
- **Description**: Clear, concise description of what will be done.
- **Pros**: Specific benefits and value added.
- **Cons**: Specific risks, costs, or trade-offs.
- **Priority**: Recommended priority (1 = highest) among selected ideas.
- **Complementary ideas**: Other selected ideas that pair well with this one.

Plus a brief note explaining the selection rationale — why these ideas were
chosen over others in the consolidated list.
"""
    return description, expected_output


def create_tasks_from_ideas(
    project_id: int,
    ideas_text: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for creating tasks from brainstorm ideas."""

    state_block = build_state_context(
        project_id=project_id,
        project_name="",
        phase="brainstorming_execution",
        summary=(
            "The user has approved brainstorming ideas. Create the project "
            "structure to execute them."
        ),
    )

    description = f"""\
Create project structure from the approved ideas for project (ID: {project_id}).

{state_block}

## Approved Ideas
{ideas_text}

## Your Goal
Translate the approved brainstorming ideas into actionable project structure
(epics, milestones, tasks with dependencies). Each idea should become an
epic with its own milestones and tasks, ready for assignment.

## Step-by-Step Process

### Step 1: Plan the Structure
For each approved idea, determine:
- How many milestones are needed (typically 2-3 per idea).
- What specific tasks are required for each milestone.
- What dependencies exist between tasks (within and across ideas).
- What task types are needed (development, research, test, etc.).

### Step 2: Check Existing Structure
Use **ReadTasksTool** to check what already exists in the project. Avoid
creating duplicate epics or tasks that overlap with existing work. If an
approved idea extends existing functionality, consider adding tasks to
existing milestones rather than creating new epics.

### Step 3: Create Epics
Use **CreateEpicTool** for each approved idea (unless it fits within an
existing epic). Set:
- Clear title matching the idea name.
- Description that captures the full scope of the idea.
- Appropriate priority based on the selection ranking.

### Step 4: Create Milestones
Use **CreateMilestoneTool** for each milestone. Milestones should represent
verifiable checkpoints:
- A working prototype or proof of concept.
- Core functionality complete.
- Integration and testing complete.

### Step 5: Create Tasks
Use **CreateTaskTool** for each task. For every task:
- Set the correct type (development, research, test, etc.).
- Write detailed acceptance criteria — specific, verifiable conditions.
- Set priority (1-5) based on the idea's priority and the task's role
  within the milestone.
- Set estimated complexity (low/medium/high).

### Step 6: Set Dependencies
Use **SetTaskDependenciesTool** for all dependencies:
- Within each idea: tasks that depend on other tasks.
- Across ideas: if one idea requires output from another.
- With existing tasks: if new tasks depend on work already in progress.

### Step 7: Verify and Announce
Use **ReadTasksTool** to verify the structure was created correctly.
Use **SendMessageTool** to announce to the team that new tasks are
available for assignment. Include a summary of what was created and
which tasks are ready to start immediately.
"""

    expected_output = """\
A summary of the created project structure containing:

1. **Epics created**: List with IDs, titles, and which approved idea each
   represents.
2. **Milestones created**: List with IDs, titles, and associated epics.
3. **Tasks created**: List with IDs, titles, types, priorities, and
   associated milestones.
4. **Dependencies set**: List of dependency relationships between tasks.
5. **Ready to assign**: Tasks with no unmet dependencies that can be
   assigned immediately.
6. **Team notified**: Confirmation that the team was informed of the
   new tasks.
"""
    return description, expected_output


def create_repository(
    project_id: int,
    repo_name: str,
    description_text: str,
    requested_by: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for creating a Forgejo repository.

    Only the Team Lead is authorised to create repositories. Developers and
    Researchers must request a repo by sending a message to the Team Lead.
    """
    from backend.config.settings import settings

    forgejo_owner = settings.FORGEJO_OWNER or "pabada"

    state_block = build_state_context(
        project_id=project_id,
        project_name="",
        phase="repository_creation",
        summary=(
            f"Agent '{requested_by}' has requested the creation of a new "
            f"Forgejo repository named '{repo_name}'."
        ),
    )

    task_description = f"""\
Create a new Forgejo repository.

{state_block}

## Authority
You (the Team Lead) are the ONLY agent authorised to create repositories.
Developers and Researchers must request a repo by sending a message to you
explaining the purpose. You received this request from: **{requested_by}**.

## Step 1 — Validate the Repository Name
The repo name must be all-lowercase, no spaces, no special characters except
hyphens. It must match this pattern: `^[a-z0-9][a-z0-9-]{{0,38}}[a-z0-9]$`
(2-40 characters, starts and ends with alphanumeric).

Requested name: `{repo_name}`

If the name violates this pattern, reject the request and use
**SendMessageTool** to ask `{requested_by}` to provide a valid name.
Do NOT proceed to Step 2.

## Step 2 — Create the Repository via the Forgejo API
Use **ExecuteCommandTool** with the following exact curl command:

```
curl -s -X POST \\
  -H "Authorization: token $FORGEJO_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{{"name": "{repo_name}", "description": "{description_text}", "private": false, "auto_init": true}}' \\
  "$FORGEJO_API_URL/user/repos"
```

Parse the JSON response:
- If the response contains `"id"`, the creation succeeded. The field
  `clone_url` contains the remote URL.
- If the response contains `"message"` and no `"id"`, the creation failed.
  Report the error to `{requested_by}` via **SendMessageTool** and stop.

## Step 3 — Communicate the Remote URL
Use **SendMessageTool** to notify `{requested_by}` with:
- The repo name: `{repo_name}`
- The clone URL: `http://localhost:3000/{forgejo_owner}/{repo_name}.git`
- The exact commands to configure the remote on their local workspace:
  ```
  git remote add origin http://localhost:3000/{forgejo_owner}/{repo_name}.git
  git fetch origin
  ```

## Step 4 — Document
Use **AddCommentTool** on the originating task (if a task_id was provided)
to record the repo URL and creation timestamp.
"""

    expected_output = """\
A confirmation of repository creation containing:

1. **Repo name**: The validated repository name.
2. **Clone URL**: The full clone URL on Forgejo.
3. **Requester notified**: Confirmation that the requesting agent was sent
   the clone URL and remote configuration commands via SendMessageTool.
4. **Error details**: If creation failed, the exact error message from the
   Forgejo API response.
"""
    return task_description, expected_output
