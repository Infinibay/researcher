"""Plan-related task prompts: creating plans, tickets, dependencies, and brainstorming."""

from backend.prompts.team import build_state_context


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
This is the most important step. Apply **Zero-Assumption Planning**:

1. **What work can start immediately** with the facts I have NOW?
   - If the project lacks facts or context \u2192 create `investigation` tickets to map the territory.
   - If there is a clear observation-based hypothesis to test \u2192 create `research` tickets.
   - If there is a metric to hit without a clear path \u2192 create `optimization` tickets.
   - If the direction is clear (e.g. following a successful research finding) \u2192 create the foundational development tickets.

**\u26a0\ufe0f STOP AND EVALUATE:** Are you creating a ticket whose description starts with "Assuming the investigation shows..." or "Once we have the results from..."? If yes, **DELETE** that ticket. You cannot create work that depends on unearned results.

**Wait for the findings.** It is better to have 2 active investigation tickets and zero pending code tickets in the same stream, than to have 10 code tickets based on a wrong assumption. You may still plan other unrelated and independent streams if you have clear information.

2. **What would I be guessing about?**
   - If defining a ticket requires assumptions about unknown results \u2192
     do NOT create that ticket. Wait for results to inform it.
   - If you cannot write concrete acceptance criteria, you are guessing. Stop.

3. **How many tickets is the right number?**
   - Fewer, well-defined tickets > many vague tickets.
   - Typical first batch: 3-8 tickets total.
   - If research-heavy: maybe 2-3 research tickets only.
   - If well-defined: maybe 5-8 development tickets.

This is planning iteration #{planning_iteration}. Create at most
**{max_epics} epics** with ONLY the tickets needed NOW \u2014 not everything
that could ever be needed.

### Step 4: Define Structure
For each epic (max {max_epics}):
- Represent a high-level objective for THIS batch, not the whole project.
- Have a clear, measurable outcome.

For each milestone (max {max_milestones} per epic):
- Be a verifiable checkpoint with incremental value.

For each task (max {max_tasks} per milestone):
- Be completable by a single agent in a reasonable cycle.
- Type: `development`, `research`, `investigation`, `experimentation`, `optimization`, `test`, `documentation`,
  `design`, `integration`, `bug_fix`.
  - Use `investigation` for mapping current state, gathering facts, logs, or codebase context WITHOUT proposing solutions.
  - Use `research` (or `experimentation`) ONLY for scientific validation of a pre-existing hypothesis via experiments.
  - Use `optimization` for goals defined by a success metric requiring a benchmark -> change -> measure cycle.

### Step 5: Write Rich Task Descriptions
Gather context with tools BEFORE writing each task. Do not invent
context \u2014 gather it with read_findings, read_wiki, code_search.

Every task MUST include ALL of the following sections:

| Section | What to include |
|---|---|
| **Context / Motivation** | Why this task exists. For a feature: what user need it addresses. For a bug: how it manifests, reproduction steps, impact. For research: what question needs answering and why it blocks other work. |
| **Detailed Description** | Current state \u2192 desired state. What needs to be built/fixed/investigated. Inputs, outputs, constraints. Not just "implement X". |
| **Acceptance Criteria** | Minimum **3** specific, verifiable conditions. Use Given/When/Then format OR a concrete checklist. Each criterion must be independently testable. |
| **Technical Notes** | Relevant files, modules, libraries, APIs, performance/security constraints, links to related tasks or findings. |
| **Definition of Done** | Final checklist: code complete, criteria met, no regressions, docs updated if applicable. |

#### 5d. Bad vs. Good Examples

**BAD \u2014 vague, no context, no criteria:**
> Title: `RESTful API Specification and Implementation`
> Description: `Create RESTful API with CRUD operations for virtual machines, versioning, and full OpenAPI/Swagger documentation.`

This is bad because it has no context (why does this API exist? what is blocked
without it?), no acceptance criteria (what does "done" look like?), no technical
notes (what framework, what patterns, what constraints?), and no definition of
done.

**GOOD \u2014 context, description, criteria, notes, DoD:**
> **Title**: `Implement CRUD REST API for Virtual Machines`
>
> **Context / Motivation**: The platform has no programmatic interface for VM
> management. All client integrations (TypeScript SDK, CLI tool) are blocked
> until this API exists. This is the foundational layer for the entire
> integration epic.
>
> **Detailed Description**: Design and implement a RESTful API with full CRUD
> for the VM resource under `/api/v1/vms`. Endpoints: `POST /api/v1/vms`
> (create), `GET /api/v1/vms` (list with pagination), `GET /api/v1/vms/{{id}}`
> (get), `PUT /api/v1/vms/{{id}}` (update), `DELETE /api/v1/vms/{{id}}` (delete).
> Must follow REST conventions and be fully documented with OpenAPI 3.0.
>
> **Acceptance Criteria**:
> - Given a `POST /api/v1/vms` with a valid JSON body and a valid JWT, When
>   the request is processed, Then the response is `201` with the created VM
>   object including its assigned UUID
> - Given a `GET /api/v1/vms` with a valid token, Then the response is `200`
>   with a paginated JSON array; `page` and `limit` query params are supported
> - Given a `DELETE /api/v1/vms/{{id}}` for a non-existent ID, Then the response
>   is `404` with a structured JSON error body
> - Given any endpoint called without a token, Then the response is `401`
> - The generated OpenAPI spec renders without errors in Swagger UI
>
> **Technical Notes**: Use the existing FastAPI router pattern in `api/routes/`.
> VM schema: `id` (UUID), `name`, `status` (running/stopped/error), `cpu_count`,
> `memory_mb`, `created_at`. JWT middleware is already in
> `api/dependencies.py` \u2014 reuse it.
>
> **Definition of Done**: All 5 endpoints implemented and passing acceptance
> criteria. OpenAPI spec auto-generated and valid. Integration tests cover all
> AC. No existing tests broken.

---

**BAD \u2014 bug fix with no context:**
> Title: `Fix monitoring bug`
> Description: `Fix issue with metrics not showing correctly.`

**GOOD \u2014 bug fix with full context:**
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
> - Given a VM that has just restarted, When `GET /api/v1/vms/{{id}}/metrics`
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

**GOOD \u2014 optimization ticket with measurable goal:**
> **Title**: `Optimize app data consumption by at least 25%`
>
> **Context / Motivation**: The current mobile app consumes 5MB per session on average. This is a significant cost and performance issue for users on limited data plans. No single solution is obvious, so we need to experiment with multiple approaches.
>
> **Detailed Description**: Reduce the data consumption of the main feed from ~5MB to <3.75MB per session. Follow an iterative cycle: (1) Benchmark current consumption, (2) Propose a hypothesis (e.g., image compression, lazy loading, payload pruning), (3) Experiment and Measure. If a change improves the metric, merge it and proceed to the next hypothesis until the goal is met or proven impossible.
>
> **Acceptance Criteria**:
> - Baseline benchmark result recorded as an artifact.
> - At least 3 different optimization hypotheses tested and documented with evidence.
> - Final benchmark shows data consumption < 3.75MB per session OR a comprehensive report explains the technical limit reached.
> - No regressions in image quality or load times.
>
> **Technical Notes**: Metrics are available via `NetworkProfiler` in `tools/net_bench.py`. Target endpoint for testing is `api/v1/feed`.
>
> **Definition of Done**: Goal reached or experimental limit documented. All evidence linked to findings.

Priority: 1 (critical/blocking) to 5 (nice-to-have).
Complexity: low / medium / high.

### Step 6: Define Dependencies
- A task that requires the output of another task is a dependency.
- Minimize dependency chains \u2014 parallelize where possible.
- Avoid circular dependencies.

### Step 7: Validate
Before outputting, verify:
- [ ] Every task has clear acceptance criteria.
- [ ] No task depends on unknown/speculative results.
- [ ] Dependencies form a DAG (no cycles).
- [ ] Work can start immediately \u2014 first tasks have no blockers.
- [ ] No duplicate or near-duplicate tasks.

### Step 8: If Anything Is Ambiguous
If the PRD has gaps or ambiguities that affect planning:
- Use **ask_project_lead** to ask a specific question.
- Do NOT guess at requirements \u2014 clarify before committing to a plan.
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
- **Detailed Description**: Current state \u2192 desired state
- **Type**: development / research / test / etc.
- **Acceptance Criteria**: Minimum 3 verifiable conditions
- **Technical Notes**: Relevant files, modules, libraries
- **Priority**: 1-5
- **Estimated Complexity**: low / medium / high
- **Dependencies**: Which tasks must complete first
- **Definition of Done**: Final checklist

## What Comes Next (NOT tickets \u2014 just direction)
What will likely be needed after this batch completes, and what
information you are waiting for to define those future tickets.
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

### Step 1 \u2014 Orient
Read the plan section for "{ticket_title}". Identify:
- Which epic this task belongs to (look up the epic_id from the map above)
- Which milestone this task belongs to (look up the milestone_id from the map above)
- The task type (development / research / investigation / test / documentation / design / integration / bug_fix)
- Priority (1-5) and complexity (low / medium / high)

### Step 1.5 \u2014 Project Awareness & Deduplication
**Before doing anything else**, understand the current state of the project
and check for duplicates:

1. Use **read_tasks** to read ALL existing tasks for this project.
   For each task, note its title, type, status (backlog, pending, in_progress,
   done, etc.), and description summary.
2. Review the "Tasks Already Created" list above (if present).
3. From this, build a mental picture of:
   - **What has already been completed** \u2014 what work is done, what results
     were achieved, what findings were produced.
   - **What is currently in progress** \u2014 what is being worked on right now.
   - **What is already planned** \u2014 what pending/backlog tasks already cover.
   - **Where the project is heading** \u2014 the overall trajectory and remaining
     gaps.
4. Compare the title, scope, and intent of "{ticket_title}" against every
   existing task. A duplicate is any task that covers substantially the same
   work \u2014 even if the title uses different words.

**If you find a duplicate or near-duplicate:**
- Do NOT create a new task.
- Output: `SKIPPED_DUPLICATE: <existing task_id> \u2014 <reason>`
- Stop here. Do not proceed to Step 2.

**If no duplicate exists**, continue to Step 2. Use the project awareness
you built here to write a richer, more contextualized task description \u2014
reference completed work, leverage findings from finished research tasks,
and position this ticket within the broader project trajectory.

### Step 2 \u2014 Research
Before writing the description, gather context using ALL of these tools:

1. **read_findings** \u2014 search for findings related to "{ticket_title}" or its topic area
2. **read_wiki** \u2014 search for wiki pages related to this task's domain
3. **read_messages** \u2014 check for bug reports, agent notes, or escalations about this area
4. **code_search** \u2014 search the codebase for relevant modules, functions, or patterns mentioned in the plan
5. **web_search** \u2014 if the task involves an external library, API, or technology, look up current best practices or known issues
6. **execute_command** \u2014 if needed, run a command to inspect the codebase (e.g., `find`, `cat`, `grep`) for additional context

**If any tool returns empty or errors**: This is normal for new projects.
Continue without that context \u2014 do NOT block or retry. An empty result
simply means no prior data exists yet. Use whatever context you gathered
from the tools that did return results.

### Step 3 \u2014 Write the Description
Write the full task description following this MANDATORY structure:

**Context / Motivation**: Why this task exists. Ground this in what you
found in Step 2 \u2014 reference specific findings, wiki pages, messages, or
code patterns discovered.

**Detailed Description**: Current state \u2192 desired state. What needs to be
built/fixed/investigated. Inputs, outputs, constraints. Be specific.

**Acceptance Criteria**: Minimum 3 specific, verifiable conditions. Use
Given/When/Then format OR a concrete checklist. Each must be independently
testable.

**Technical Notes**: Relevant files, modules, libraries, APIs found during
research. Include specific file paths or code patterns from code_search
results. Reference any findings from read_findings.

**Definition of Done**: Final checklist before marking complete.

### Step 4 \u2014 Create the Task
Call **create_task** with:
- `title`: {ticket_title}
- `description`: the full description from Step 3
- `type`: from the plan
- `epic_id`: looked up from the epic IDs map above
- `milestone_id`: looked up from the milestone IDs map above
- `priority`: from the plan (1-5)
- `complexity`: from the plan (low/medium/high)

### Step 5 \u2014 Confirm
Output the created task ID on its own line in this exact format:
CREATED_TASK_ID: <the numeric ID returned by create_task>
"""

    expected_output = f"""\
One of two possible responses:

**Option A \u2014 Task created:**
1. Research results gathered from the available tools (brief summary of
   what was found).
2. The full task description written following the mandatory anatomy
   (Context, Description, Acceptance Criteria, Technical Notes, DoD).
3. Confirmation that create_task was called successfully.
4. A line in this exact format: CREATED_TASK_ID: N
   Where N is the numeric task ID returned by create_task for the task
   titled "{ticket_title}".

**Option B \u2014 Duplicate detected:**
A line in this exact format: SKIPPED_DUPLICATE: <existing_task_id> \u2014 <reason>
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

## Newly Created Tasks (title \u2192 ID)
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

Ideas should be sorted by impact \u00d7 viability (highest first), with notes
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
Check if any selected ideas are complementary \u2014 they work better together
than individually. If so, note this in your output. Also identify any
ideas that conflict with each other (implementing one makes the other
unnecessary or impossible).

### Step 4: Prepare for Presentation
For each selected idea, write:
- A clear description suitable for a non-technical audience.
- Concrete pros and cons (not vague \u2014 "adds database dependency" not
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

Plus a brief note explaining the selection rationale \u2014 why these ideas were
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
- What task types are needed (development, investigation, research, optimization, test, etc.).

### Step 2: Understand Project State & Check for Duplicates
Use **read_tasks** to read ALL existing tasks for this project. For each
task, note its title, type, status, and description. Build a mental picture of:
- **What has been completed** \u2014 what results and findings were produced.
- **What is in progress** \u2014 what is currently being worked on.
- **What is already planned** \u2014 what pending/backlog tasks exist.
- **Where the project is heading** \u2014 the overall trajectory.

**Deduplication**: Compare each approved idea against existing tasks. If an
idea's scope is already covered by existing work (even if worded differently),
do NOT create a duplicate. Instead, note it in your output and skip it.

If an approved idea extends existing functionality, consider adding tasks to
existing milestones rather than creating new epics.

### Step 2.5: Research Before Writing
Before creating any epics, milestones, or tasks, gather context using these tools:
1. **read_findings** \u2014 search for findings related to each approved idea's topic area.
2. **read_wiki** \u2014 look for wiki pages covering the domain of each idea.
3. **read_messages** \u2014 check for bug reports, agent notes, or prior discussions about these topics.
4. **code_search** \u2014 search the codebase for modules, patterns, or files relevant to each idea.
5. **web_search** \u2014 if an idea involves an external technology, look up current best practices.

Empty results are normal for new projects \u2014 continue without blocking. Use whatever context you gathered to write richer descriptions.

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

**\u26a0\ufe0f Quality gate**: A task description that is only a sentence or two will be rejected. Every task must have all five sections below.

Use **create_task** for each task. For every task:
- Set the correct type (development, investigation, research, optimization, test, etc.).
- Set priority (1-5) based on the idea's priority and the task's role
  within the milestone.
- Set estimated complexity (low/medium/high).

The `description` passed to **create_task** must follow this mandatory structure. Do NOT use the plan's one-line title as the description \u2014 expand it fully:

**Context / Motivation**: Why this task exists. Reference the parent milestone goal and any relevant findings or prior work.

**Detailed Description**: Current state \u2192 desired state. What must be built, fixed, or investigated. Inputs, outputs, constraints. Be specific \u2014 name files, modules, APIs.

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
