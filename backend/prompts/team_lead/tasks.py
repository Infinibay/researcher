"""Team Lead task prompts used in flows."""

from backend.prompts.shared import GIT_WORKFLOW_INSTRUCTIONS
from backend.prompts.team import build_conversation_context, build_state_context


def create_plan(
    project_name: str,
    project_id: int,
    requirements: str,
    conversation_context: str = "",
    planning_iteration: int = 0,
) -> tuple[str, str]:
    """Return (description, expected_output) for plan creation."""
    from backend.config.settings import settings

    max_epics = settings.MAX_ACTIVE_EPICS
    max_milestones = settings.MAX_MILESTONES_PER_EPIC
    max_tasks = settings.MAX_TASKS_PER_MILESTONE

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
Determine the highest-impact first batch of work for project \
'{project_name}' (ID: {project_id}).

{state_block}

## Requirements (PRD)
{requirements}

{ctx_block}

## Your Goal
Identify what work should start NOW to make the most progress toward the
project goals. You are NOT creating a comprehensive plan for the entire
project. You are determining the **minimum viable first batch** — the
smallest set of tickets that will produce the most learning and progress.

After this batch completes, you will be called again to evaluate results
and decide what comes next. Do NOT try to plan everything now. Create
only what you have enough information to define well.

**Key question**: "What are the 3-8 most impactful things that should
happen first, and do I have enough information to define them clearly?"

## Step-by-Step Process

### Step 1: Analyze the Requirements
Read the PRD above thoroughly. Identify:
- **Core objectives**: What are the main goals of this project?
- **What must happen FIRST**: What foundational work enables everything else?
- **What is uncertain**: What aspects need research before you can plan
  implementation?
- **What is clear**: What can be defined precisely right now?

### Step 2: Check Existing Context
Use **read_findings** to check for prior research relevant to this
project. If findings exist, factor them in.

Use **read_wiki** to check for existing documentation.

Use **read_messages** to read all unread messages before planning.

Use **code_search** to search the existing codebase for relevant patterns
and architecture.

**If any tool returns empty or errors**: Normal for new projects. Continue.

### Step 3: Decide WHAT to Create Now (CRITICAL STEP)
This is the most important step. Ask yourself:

1. **What work can start immediately** with the information I have?
   - If the project needs research to clarify direction → create research
     tickets ONLY. Do NOT create development tickets that depend on unknown
     research results.
   - If the direction is clear → create the foundational development tickets.

2. **What would I be guessing about?**
   - If defining a ticket requires assumptions about unknown results →
     do NOT create that ticket. Wait for results to inform it.

3. **How many tickets is the right number?**
   - Fewer, well-defined tickets > many vague tickets.
   - Typical first batch: 3-8 tickets total.
   - If research-heavy: maybe 2-3 research tickets only.
   - If well-defined: maybe 5-8 development tickets.

This is planning iteration #{planning_iteration}. Create at most
**{max_epics} epics** with ONLY the tickets needed NOW — not everything
that could ever be needed.

### Step 4: Define Structure
For each epic (max {max_epics}):
- Represent a high-level objective for THIS batch, not the whole project.
- Have a clear, measurable outcome.

For each milestone (max {max_milestones} per epic):
- Be a verifiable checkpoint with incremental value.

For each task (max {max_tasks} per milestone):
- Be completable by a single agent in a reasonable cycle.
- Type: `development`, `research`, `test`, `documentation`, `design`,
  `integration`, `bug_fix`.

### Step 5: Write Rich Task Descriptions
Gather context with tools BEFORE writing each task. Do not invent
context — gather it with read_findings, read_wiki, code_search.

Every task MUST include ALL of the following sections:

| Section | What to include |
|---|---|
| **Context / Motivation** | Why this task exists. For a feature: what user need it addresses. For a bug: how it manifests, reproduction steps, impact. For research: what question needs answering and why it blocks other work. |
| **Detailed Description** | Current state → desired state. What needs to be built/fixed/investigated. Inputs, outputs, constraints. Not just "implement X". |
| **Acceptance Criteria** | Minimum **3** specific, verifiable conditions. Use Given/When/Then format OR a concrete checklist. Each criterion must be independently testable. |
| **Technical Notes** | Relevant files, modules, libraries, APIs, performance/security constraints, links to related tasks or findings. |
| **Definition of Done** | Final checklist: code complete, criteria met, no regressions, docs updated if applicable. |

#### 5d. Bad vs. Good Examples

**BAD — vague, no context, no criteria:**
> Title: `RESTful API Specification and Implementation`
> Description: `Create RESTful API with CRUD operations for virtual machines, versioning, and full OpenAPI/Swagger documentation.`

This is bad because it has no context (why does this API exist? what is blocked
without it?), no acceptance criteria (what does "done" look like?), no technical
notes (what framework, what patterns, what constraints?), and no definition of
done.

**GOOD — context, description, criteria, notes, DoD:**
> **Title**: `Implement CRUD REST API for Virtual Machines`
>
> **Context / Motivation**: The platform has no programmatic interface for VM
> management. All client integrations (TypeScript SDK, CLI tool) are blocked
> until this API exists. This is the foundational layer for the entire
> integration epic.
>
> **Detailed Description**: Design and implement a RESTful API with full CRUD
> for the VM resource under `/api/v1/vms`. Endpoints: `POST /api/v1/vms`
> (create), `GET /api/v1/vms` (list with pagination), `GET /api/v1/vms/{id}`
> (get), `PUT /api/v1/vms/{id}` (update), `DELETE /api/v1/vms/{id}` (delete).
> Must follow REST conventions and be fully documented with OpenAPI 3.0.
>
> **Acceptance Criteria**:
> - Given a `POST /api/v1/vms` with a valid JSON body and a valid JWT, When
>   the request is processed, Then the response is `201` with the created VM
>   object including its assigned UUID
> - Given a `GET /api/v1/vms` with a valid token, Then the response is `200`
>   with a paginated JSON array; `page` and `limit` query params are supported
> - Given a `DELETE /api/v1/vms/{id}` for a non-existent ID, Then the response
>   is `404` with a structured JSON error body
> - Given any endpoint called without a token, Then the response is `401`
> - The generated OpenAPI spec renders without errors in Swagger UI
>
> **Technical Notes**: Use the existing FastAPI router pattern in `api/routes/`.
> VM schema: `id` (UUID), `name`, `status` (running/stopped/error), `cpu_count`,
> `memory_mb`, `created_at`. JWT middleware is already in
> `api/dependencies.py` — reuse it.
>
> **Definition of Done**: All 5 endpoints implemented and passing acceptance
> criteria. OpenAPI spec auto-generated and valid. Integration tests cover all
> AC. No existing tests broken.

---

**BAD — bug fix with no context:**
> Title: `Fix monitoring bug`
> Description: `Fix issue with metrics not showing correctly.`

**GOOD — bug fix with full context:**
> **Title**: `Fix: CPU metrics returning stale values after VM restart`
>
> **Context / Motivation**: After a VM is restarted, the monitoring module
> continues to report the CPU usage from before the restart for up to 5
> minutes. This was reported by the developer agent in thread
> `monitor-bug-42`. Users see incorrect dashboards and alerts fire
> incorrectly. Root cause appears to be a missing cache invalidation on VM
> state change events.
>
> **Detailed Description**: The `MetricsCollector` class caches CPU readings
> per VM ID. When a VM restarts, the cache is not invalidated because the
> `vm.restarted` event is not subscribed to. The fix must subscribe to
> `vm.restarted` and `vm.stopped` events and flush the cache entry for the
> affected VM ID.
>
> **Acceptance Criteria**:
> - Given a VM that has just restarted, When `GET /api/v1/vms/{id}/metrics`
>   is called within 30 seconds of restart, Then the returned CPU value
>   reflects post-restart state (not pre-restart cache)
> - Given a VM that is stopped, When metrics are requested, Then the response
>   returns `status: stopped` and `cpu_usage: null` rather than stale values
> - Given the fix is applied, When the existing metrics test suite runs, Then
>   all existing tests continue to pass
>
> **Technical Notes**: See `MetricsCollector` in `monitoring/collector.py`.
> Event bus subscription pattern is in `events/bus.py`. Cache is a dict keyed
> by VM ID in `_cache` attribute.
>
> **Definition of Done**: Cache invalidation implemented on `vm.restarted` and
> `vm.stopped`. Unit test added for the invalidation path. No regression in
> existing metrics tests.

Priority: 1 (critical/blocking) to 5 (nice-to-have).
Complexity: low / medium / high.

### Step 6: Define Dependencies
- A task that requires the output of another task is a dependency.
- Minimize dependency chains — parallelize where possible.
- Avoid circular dependencies.

### Step 7: Validate
Before outputting, verify:
- [ ] Every task has clear acceptance criteria.
- [ ] No task depends on unknown/speculative results.
- [ ] Dependencies form a DAG (no cycles).
- [ ] Work can start immediately — first tasks have no blockers.
- [ ] No duplicate or near-duplicate tasks.

### Step 8: If Anything Is Ambiguous
If the PRD has gaps or ambiguities that affect planning:
- Use **ask_project_lead** to ask a specific question.
- Do NOT guess at requirements — clarify before committing to a plan.
- Only ask about things that genuinely block planning. Technical decisions
  that you can make yourself should be documented as decisions, not
  escalated.
"""

    expected_output = f"""\
A focused plan for the minimum viable first batch of work (max {max_epics} epics):

## What I'm Creating and Why
Brief explanation: why these specific tickets? Why not more? Why not fewer?
What information am I waiting for before creating additional tickets?

## Epics
For each epic: title, description, and why it belongs in the FIRST batch.

## Tasks
For each task (grouped by milestone), include ALL sections:
- **Title**: Action-oriented, specific
- **Context / Motivation**: Why this task exists NOW
- **Detailed Description**: Current state → desired state
- **Type**: development / research / test / etc.
- **Acceptance Criteria**: Minimum 3 verifiable conditions
- **Technical Notes**: Relevant files, modules, libraries
- **Priority**: 1-5
- **Estimated Complexity**: low / medium / high
- **Dependencies**: Which tasks must complete first
- **Definition of Done**: Final checklist

## What Comes Next (NOT tickets — just direction)
What will likely be needed after this batch completes, and what
information you are waiting for to define those future tickets.
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
Use **create_epic** for each epic in the plan. For each:
- Set a clear title matching the plan.
- Set appropriate priority.
- Note the returned epic ID — you will need it for milestones.

Create epics in dependency order (foundational epics first).

The `description` passed to **create_epic** must follow this structure:
- **Measurable Objective**: What does success look like in concrete, observable terms? (e.g., "All VM lifecycle operations are exposed via a versioned REST API with <200 ms p99 latency")
- **Problem It Solves**: Why does this epic exist? What user pain, system gap, or business need does it address?
- **Definition of Done**: The conditions under which this epic is considered fully complete (e.g., all child milestones closed, integration tests green, documentation published).

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (epic title and
error message) and continue creating the remaining epics. Do NOT stop the
entire process because one item failed — you will reconcile failures in
Step 6.

### Step 2: Create Milestones
Use **create_milestone** for each milestone. For each:
- Associate it with the correct epic (using the epic ID from Step 1).
- Set the target cycle if specified in the plan.
- Note the returned milestone ID — you will need it for tasks.

The `description` passed to **create_milestone** must follow this structure:
- **Objective Verification Criterion**: A single, concrete, testable condition that proves this milestone is done (e.g., "The `/vms` endpoint returns a 200 with a valid JSON body for all CRUD operations in the CI test suite").
- **Incremental Value Delivered**: What does the team or user gain the moment this milestone closes? Why does it matter as a standalone checkpoint?

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (milestone title,
parent epic, and error message) and continue with the remaining milestones.
Do NOT stop the entire process because one item failed — you will reconcile
failures in Step 6.

### Step 3: Create Tasks

**⚠️ Quality gate**: A task description that is only a sentence or two will be rejected. Every task must have all five sections below.

Use **create_task** for each task. For each:
- Associate it with the correct milestone and epic (using IDs from above).
- Set the type (development, research, test, etc.).
- Set priority (1-5).
- Set estimated complexity if available.
- Note the returned task ID — you will need it for dependencies.

The `description` passed to **create_task** must follow this mandatory structure. Do NOT use the plan's one-line title as the description — expand it fully:

**Context / Motivation**: Why this task exists. Reference the parent milestone goal and any relevant findings or prior work.

**Detailed Description**: Current state → desired state. What must be built, fixed, or investigated. Inputs, outputs, constraints. Be specific — name files, modules, APIs.

**Acceptance Criteria** _(minimum 3, each independently verifiable)_: Use Given/When/Then format or a concrete checklist. Vague criteria like "works correctly" are not acceptable.

**Technical Notes**: Relevant files, modules, libraries, or patterns from the plan. Include specific paths or code references where known.

**Definition of Done**: Final checklist before the task can be marked complete (e.g., code reviewed, tests passing, docs updated).

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (task title,
parent milestone, and error message) and continue with the remaining tasks.
Do NOT stop the entire process because one item failed — you will reconcile
failures in Step 6.

### Step 4: Set Dependencies
Use **set_task_dependencies** to establish all task dependencies from the
plan. For each dependency:
- Specify the task that is blocked (depends on another).
- Specify the task it depends on.
- Verify the dependency makes logical sense (no cycles).

### Step 5: Verify the Structure
Use **read_tasks** to verify that all tasks were created correctly:
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
Use **send_message** to announce the plan structure is ready. Include:
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
6. **Verification**: Confirmation that read_tasks was used to verify
   the structure matches the plan.
7. **Failed items**: List of any epics, milestones, or tasks that could
   not be created (with error details), or explicit confirmation that all
   items were created successfully.
"""
    return description, expected_output


def create_epics_and_milestones(
    project_name: str,
    project_id: int,
    plan: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for creating only epics and milestones."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="structure_creation",
        summary=(
            "The plan has been approved. Create the epic and milestone "
            "structure in the database. Tasks will be created separately."
        ),
    )

    description = f"""\
Create the epic and milestone structure for project \
'{project_name}' (ID: {project_id}).

{state_block}

## Approved Plan
{plan}

## Your Goal
Create all epics and milestones from the plan in the database. Do NOT
create tasks or dependencies — those will be handled in a separate step.

## Step-by-Step Process

### Step 1: Create Epics
Use **create_epic** for each epic in the plan. For each:
- Set a clear title matching the plan.
- Set appropriate priority.
- Note the returned epic ID.

Create epics in dependency order (foundational epics first).

The `description` passed to **create_epic** must follow this structure:
- **Measurable Objective**: What does success look like in concrete, observable terms? (e.g., "All VM lifecycle operations are exposed via a versioned REST API with <200 ms p99 latency")
- **Problem It Solves**: Why does this epic exist? What user pain, system gap, or business need does it address?
- **Definition of Done**: The conditions under which this epic is considered fully complete (e.g., all child milestones closed, integration tests green, documentation published).

**After each call**, check the returned result. If the tool returns an
error, note the failure and continue with remaining epics.

### Step 2: Create Milestones
Use **create_milestone** for each milestone. For each:
- Associate it with the correct epic (using the epic ID from Step 1).
- Set the target cycle if specified.
- Note the returned milestone ID.

The `description` passed to **create_milestone** must follow this structure:
- **Objective Verification Criterion**: A single, concrete, testable condition that proves this milestone is done (e.g., "The `/vms` endpoint returns a 200 with a valid JSON body for all CRUD operations in the CI test suite").
- **Incremental Value Delivered**: What does the team or user gain the moment this milestone closes? Why does it matter as a standalone checkpoint?

**After each call**, check the returned result. If the tool returns an
error, note the failure and continue with remaining milestones.

### Step 3: Output the Results
You MUST output a JSON block at the very end of your response with ALL
created IDs. This is critical — the system parses this block to proceed.

Format your JSON output inside a code fence like this:

```json
{{"epics": [{{"title": "Epic Title Here", "id": 1}}, ...], "milestones": [{{"title": "Milestone Title Here", "id": 1, "epic_id": 1}}, ...]}}
```

Include every epic and milestone you created. If any failed, list them
separately after the JSON block.
"""

    expected_output = """\
A response ending with a JSON code block containing all created epics
and milestones with their database IDs:

```json
{"epics": [{"title": "...", "id": N}, ...], "milestones": [{"title": "...", "id": N, "epic_id": N}, ...]}
```

Before the JSON block, include a brief summary of what was created and
any items that failed creation.
"""
    return description, expected_output


def create_single_ticket(
    project_name: str,
    project_id: int,
    plan: str,
    ticket_title: str,
    ticket_index: int,
    total_tickets: int,
    epics_created: dict[str, int],
    milestones_created: dict[str, int],
    tasks_already_created: dict[str, int] | None = None,
) -> tuple[str, str]:
    """Return (description, expected_output) for creating a single task with research."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="ticket_creation",
        summary=(
            f"Creating ticket {ticket_index + 1} of {total_tickets}: "
            f"'{ticket_title}'."
        ),
    )

    epics_map = "\n".join(
        f"  - \"{title}\": epic_id={eid}" for title, eid in epics_created.items()
    )
    milestones_map = "\n".join(
        f"  - \"{title}\": milestone_id={mid}" for title, mid in milestones_created.items()
    )

    already_created_section = ""
    if tasks_already_created:
        tasks_list = "\n".join(
            f"  - \"{title}\": task_id={tid}" for title, tid in tasks_already_created.items()
        )
        already_created_section = f"""
## Tasks Already Created in This Project
The following tasks have already been created. Do NOT create duplicates or
near-duplicates of these. If the ticket you are about to create covers the
same scope as an existing task, SKIP it.
{tasks_list}
"""

    description = f"""\
Create a single task ticket for project '{project_name}' (ID: {project_id}).

{state_block}

## Ticket to Create
**Title**: {ticket_title}
**Progress**: Ticket {ticket_index + 1} of {total_tickets}

## Available Epic IDs
{epics_map}

## Available Milestone IDs
{milestones_map}
{already_created_section}
## Full Plan (for context)
{plan}

## Step-by-Step Process

### Step 1 — Orient
Read the plan section for "{ticket_title}". Identify:
- Which epic this task belongs to (look up the epic_id from the map above)
- Which milestone this task belongs to (look up the milestone_id from the map above)
- The task type (development / research / test / documentation / design / integration / bug_fix)
- Priority (1-5) and complexity (low / medium / high)

### Step 1.5 — Project Awareness & Deduplication
**Before doing anything else**, understand the current state of the project
and check for duplicates:

1. Use **read_tasks** to read ALL existing tasks for this project.
   For each task, note its title, type, status (backlog, pending, in_progress,
   done, etc.), and description summary.
2. Review the "Tasks Already Created" list above (if present).
3. From this, build a mental picture of:
   - **What has already been completed** — what work is done, what results
     were achieved, what findings were produced.
   - **What is currently in progress** — what is being worked on right now.
   - **What is already planned** — what pending/backlog tasks already cover.
   - **Where the project is heading** — the overall trajectory and remaining
     gaps.
4. Compare the title, scope, and intent of "{ticket_title}" against every
   existing task. A duplicate is any task that covers substantially the same
   work — even if the title uses different words.

**If you find a duplicate or near-duplicate:**
- Do NOT create a new task.
- Output: `SKIPPED_DUPLICATE: <existing task_id> — <reason>`
- Stop here. Do not proceed to Step 2.

**If no duplicate exists**, continue to Step 2. Use the project awareness
you built here to write a richer, more contextualized task description —
reference completed work, leverage findings from finished research tasks,
and position this ticket within the broader project trajectory.

### Step 2 — Research
Before writing the description, gather context using ALL of these tools:

1. **read_findings** — search for findings related to "{ticket_title}" or its topic area
2. **read_wiki** — search for wiki pages related to this task's domain
3. **read_messages** — check for bug reports, agent notes, or escalations about this area
4. **code_search** — search the codebase for relevant modules, functions, or patterns mentioned in the plan
5. **web_search** — if the task involves an external library, API, or technology, look up current best practices or known issues
6. **execute_command** — if needed, run a command to inspect the codebase (e.g., `find`, `cat`, `grep`) for additional context

**If any tool returns empty or errors**: This is normal for new projects.
Continue without that context — do NOT block or retry. An empty result
simply means no prior data exists yet. Use whatever context you gathered
from the tools that did return results.

### Step 3 — Write the Description
Write the full task description following this MANDATORY structure:

**Context / Motivation**: Why this task exists. Ground this in what you
found in Step 2 — reference specific findings, wiki pages, messages, or
code patterns discovered.

**Detailed Description**: Current state → desired state. What needs to be
built/fixed/investigated. Inputs, outputs, constraints. Be specific.

**Acceptance Criteria**: Minimum 3 specific, verifiable conditions. Use
Given/When/Then format OR a concrete checklist. Each must be independently
testable.

**Technical Notes**: Relevant files, modules, libraries, APIs found during
research. Include specific file paths or code patterns from code_search
results. Reference any findings from read_findings.

**Definition of Done**: Final checklist before marking complete.

### Step 4 — Create the Task
Call **create_task** with:
- `title`: {ticket_title}
- `description`: the full description from Step 3
- `type`: from the plan
- `epic_id`: looked up from the epic IDs map above
- `milestone_id`: looked up from the milestone IDs map above
- `priority`: from the plan (1-5)
- `complexity`: from the plan (low/medium/high)

### Step 5 — Confirm
Output the created task ID on its own line in this exact format:
CREATED_TASK_ID: <the numeric ID returned by create_task>
"""

    expected_output = f"""\
One of two possible responses:

**Option A — Task created:**
1. Research results gathered from the available tools (brief summary of
   what was found).
2. The full task description written following the mandatory anatomy
   (Context, Description, Acceptance Criteria, Technical Notes, DoD).
3. Confirmation that create_task was called successfully.
4. A line in this exact format: CREATED_TASK_ID: N
   Where N is the numeric task ID returned by create_task for the task
   titled "{ticket_title}".

**Option B — Duplicate detected:**
A line in this exact format: SKIPPED_DUPLICATE: <existing_task_id> — <reason>
This means the task was not created because a near-duplicate already exists.
"""
    return description, expected_output


def set_all_dependencies(
    project_id: int,
    plan: str,
    tasks_created: dict[str, int],
) -> tuple[str, str]:
    """Return (description, expected_output) for setting all task dependencies."""

    state_block = build_state_context(
        project_id=project_id,
        project_name="",
        phase="dependency_setting",
        summary=(
            f"{len(tasks_created)} tasks were just created in this batch. "
            "Set dependencies ONLY between these tasks and announce the "
            "structure to the team."
        ),
    )

    tasks_map = "\n".join(
        f"  - \"{title}\": task_id={tid}" for title, tid in tasks_created.items()
    )

    description = f"""\
Set dependencies between the newly created tasks and announce the structure.

{state_block}

## Newly Created Tasks (title → ID)
{tasks_map}

## IMPORTANT CONSTRAINT
You must ONLY set dependencies between the tasks listed above.
These are the tasks created in this batch. Do NOT look for or reference
tasks outside this list. If a dependency in the plan references a task
that is NOT in the list above, skip it entirely.

## Approved Plan (contains dependency information)
{plan}

## Step-by-Step Process

### Step 1: Read the Dependency Graph
Read the dependency section of the plan. For each dependency relationship,
check whether BOTH tasks exist in the "Newly Created Tasks" list above.
Only consider dependencies where both the blocked task and the dependency
are in that list.

### Step 2: Set Dependencies
For each valid dependency (both tasks in the list above), look up both
task IDs from the task map. Call **set_task_dependencies** for each.

Skip any dependency where either task is NOT in the created tasks map.

### Step 3: Verify the Structure
Use **read_tasks** to verify the final structure:
- Check that dependencies are correctly set.
- Confirm that initial tasks (no dependencies) are ready to be assigned.
- Identify the critical path.

### Step 4: Announce
Use **send_message** to announce the structure is ready. Include:
- Total tasks created in this batch: {len(tasks_created)}.
- The critical path among these tasks.
- Which tasks are ready to be assigned immediately (no dependencies).
- Any skipped dependency relationships (tasks not in this batch).
"""

    expected_output = """\
A summary containing:

1. **Dependencies set**: List of dependency relationships established
   (task A depends on task B).
2. **Verification**: Confirmation from read_tasks that the structure
   matches the plan.
3. **Ready to assign**: List of tasks with no dependencies that can be
   assigned immediately.
4. **Critical path**: The longest dependency chain identified.
5. **Failed items**: Any dependencies that could not be set (with reasons),
   or explicit confirmation that all were set successfully.
6. **Team notified**: Confirmation that send_message was used to
   announce the structure.
"""
    return description, expected_output


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
NOT to immediately create more work — it is to decide the **smartest
next move**, which might be creating tickets, brainstorming, or declaring
the project complete.

## Step-by-Step Process

### Step 1: Review the Progress Summary Above
The "Current Progress" section above already contains:
- Epic status, task counts by status, in-progress work, pending queue,
  recently completed tasks, research results, and any failed/blocked tasks.

Read it carefully. This is your primary source of truth — do NOT waste
time calling read_tasks to re-read everything. You already have it.

Only use **get_task** (with a specific task ID) if you need the full
description or acceptance criteria for a particular task.

### Step 2: Check Research Findings (if research tasks completed)
If the progress summary shows completed research tasks, use
**read_findings** to get the detailed findings. Research insights
often inform what development tasks come next.

Optionally use **read_wiki** if researchers produced reports.

### Step 3: Check Messages
Use **read_messages** to check for unread messages — bug reports,
blockers, or agent recommendations relevant to next steps.

### Step 4: Assess Remaining Gaps
Compare accomplished work against project objectives:
- Which epics are still open and what's missing?
- Do research findings change the direction?
- Are there blocked tasks that need unblocking?

### Step 5: Decide on Next Steps
Based on your analysis, choose ONE of these three paths:

**Path A — NEW_TICKETS**: You have enough information to define the next
batch of work. This is the correct choice when:
- Research findings provide clear direction for new development tasks.
- The remaining gaps are well-understood and can be broken into specific tasks.
- You know what needs to be built/fixed/investigated to move toward completion.

If choosing this path, produce a plan for ONLY the next batch of tickets.
Apply the same principle as the initial plan: create the **minimum viable
batch** — only tickets you have enough information to define clearly and
that should start now. Do NOT create speculative tickets.

**Path B — BRAINSTORM_NEEDED**: You do NOT have enough information to define
specific next steps. This is the correct choice ONLY when:
- Research findings were inconclusive and don't provide a clear path forward.
- The remaining gaps are unclear or ambiguous.
- You genuinely don't know what to do next and need the team to ideate.

**Path C — PROJECT_COMPLETE**: The project objectives from the original
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
or `PROJECT_COMPLETE` as the first word — the system parses this automatically.

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

— OR —

BRAINSTORM_NEEDED
(followed by an explanation of why brainstorming is necessary)

— OR —

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
→ Clarify the requirements. Update the task description with precise
acceptance criteria. If user input is needed, use **ask_project_lead**.

**B. Developer skill mismatch**: The task requires expertise the developer
lacks (unfamiliar technology, complex algorithm, etc.).
→ Provide specific technical guidance, break the task into simpler subtasks,
or reassign to a more experienced developer.

**C. Over-scoped task**: The task tries to do too much and keeps failing on
different aspects each round.
→ Split the task into smaller, focused tasks. Create new tasks with
**create_task** and close or simplify the original.

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
   unambiguous acceptance criteria via **add_comment** or by creating
   an updated task.
2. **Provide technical guidance**: Send specific implementation guidance
   to the developer via **send_message**. Be concrete — reference
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


def consolidate_ideas(
    ideas_text: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for idea consolidation."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
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


def select_ideas(
    consolidated_text: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for idea selection."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
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

### Step 2: Understand Project State & Check for Duplicates
Use **read_tasks** to read ALL existing tasks for this project. For each
task, note its title, type, status, and description. Build a mental picture of:
- **What has been completed** — what results and findings were produced.
- **What is in progress** — what is currently being worked on.
- **What is already planned** — what pending/backlog tasks exist.
- **Where the project is heading** — the overall trajectory.

**Deduplication**: Compare each approved idea against existing tasks. If an
idea's scope is already covered by existing work (even if worded differently),
do NOT create a duplicate. Instead, note it in your output and skip it.

If an approved idea extends existing functionality, consider adding tasks to
existing milestones rather than creating new epics.

### Step 2.5: Research Before Writing
Before creating any epics, milestones, or tasks, gather context using these tools:
1. **read_findings** — search for findings related to each approved idea's topic area.
2. **read_wiki** — look for wiki pages covering the domain of each idea.
3. **read_messages** — check for bug reports, agent notes, or prior discussions about these topics.
4. **code_search** — search the codebase for modules, patterns, or files relevant to each idea.
5. **web_search** — if an idea involves an external technology, look up current best practices.

Empty results are normal for new projects — continue without blocking. Use whatever context you gathered to write richer descriptions.

### Step 3: Create Epics
Use **create_epic** for each approved idea (unless it fits within an
existing epic). Set:
- Clear title matching the idea name.
- Appropriate priority based on the selection ranking.

The `description` passed to **create_epic** must follow this structure:
- **Measurable Objective**: What does success look like in concrete, observable terms? (e.g., "All VM lifecycle operations are exposed via a versioned REST API with <200 ms p99 latency")
- **Problem It Solves**: Why does this epic exist? What user pain, system gap, or business need does it address?
- **Definition of Done**: The conditions under which this epic is considered fully complete (e.g., all child milestones closed, integration tests green, documentation published).

### Step 4: Create Milestones
Use **create_milestone** for each milestone. Milestones should represent
verifiable checkpoints:
- A working prototype or proof of concept.
- Core functionality complete.
- Integration and testing complete.

The `description` passed to **create_milestone** must follow this structure:
- **Objective Verification Criterion**: A single, concrete, testable condition that proves this milestone is done (e.g., "The `/vms` endpoint returns a 200 with a valid JSON body for all CRUD operations in the CI test suite").
- **Incremental Value Delivered**: What does the team or user gain the moment this milestone closes? Why does it matter as a standalone checkpoint?

### Step 5: Create Tasks

**⚠️ Quality gate**: A task description that is only a sentence or two will be rejected. Every task must have all five sections below.

Use **create_task** for each task. For every task:
- Set the correct type (development, research, test, etc.).
- Set priority (1-5) based on the idea's priority and the task's role
  within the milestone.
- Set estimated complexity (low/medium/high).

The `description` passed to **create_task** must follow this mandatory structure. Do NOT use the plan's one-line title as the description — expand it fully:

**Context / Motivation**: Why this task exists. Reference the parent milestone goal and any relevant findings or prior work.

**Detailed Description**: Current state → desired state. What must be built, fixed, or investigated. Inputs, outputs, constraints. Be specific — name files, modules, APIs.

**Acceptance Criteria** _(minimum 3, each independently verifiable)_: Use Given/When/Then format or a concrete checklist. Vague criteria like "works correctly" are not acceptable.

**Technical Notes**: Relevant files, modules, libraries, or patterns from the plan. Include specific paths or code references where known.

**Definition of Done**: Final checklist before the task can be marked complete (e.g., code reviewed, tests passing, docs updated).

### Step 6: Set Dependencies
Use **set_task_dependencies** for all dependencies:
- Within each idea: tasks that depend on other tasks.
- Across ideas: if one idea requires output from another.
- With existing tasks: if new tasks depend on work already in progress.

### Step 7: Verify and Announce
Use **read_tasks** to verify the structure was created correctly.
Use **send_message** to announce to the team that new tasks are
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
**send_message** to ask `{requested_by}` to provide a valid name.
Do NOT proceed to Step 2.

## Step 2 — Create the Repository via the Forgejo API
Use **execute_command** with the following exact curl command:

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
  Report the error to `{requested_by}` via **send_message** and stop.

## Step 3 — Communicate the Remote URL
Use **send_message** to notify `{requested_by}` with:
- The repo name: `{repo_name}`
- The clone URL: `http://localhost:3000/{forgejo_owner}/{repo_name}.git`
- The exact commands to configure the remote on their local workspace:
  ```
  git remote add origin http://localhost:3000/{forgejo_owner}/{repo_name}.git
  git fetch origin
  ```

## Step 4 — Document
Use **add_comment** on the originating task (if a task_id was provided)
to record the repo URL and creation timestamp.
"""

    expected_output = """\
A confirmation of repository creation containing:

1. **Repo name**: The validated repository name.
2. **Clone URL**: The full clone URL on Forgejo.
3. **Requester notified**: Confirmation that the requesting agent was sent
   the clone URL and remote configuration commands via send_message.
4. **Error details**: If creation failed, the exact error message from the
   Forgejo API response.
"""
    return task_description, expected_output
