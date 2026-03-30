"""Structure-related task prompts: creating project structure and repositories."""

from backend.prompts.team import build_state_context


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
- Note the returned epic ID \u2014 you will need it for milestones.

Create epics in dependency order (foundational epics first).

The `description` passed to **create_epic** must follow this structure:
- **Measurable Objective**: What does success look like in concrete, observable terms? (e.g., "All VM lifecycle operations are exposed via a versioned REST API with <200 ms p99 latency")
- **Problem It Solves**: Why does this epic exist? What user pain, system gap, or business need does it address?
- **Definition of Done**: The conditions under which this epic is considered fully complete (e.g., all child milestones closed, integration tests green, documentation published).

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (epic title and
error message) and continue creating the remaining epics. Do NOT stop the
entire process because one item failed \u2014 you will reconcile failures in
Step 6.

### Step 2: Create Milestones
Use **create_milestone** for each milestone. For each:
- Associate it with the correct epic (using the epic ID from Step 1).
- Set the target cycle if specified in the plan.
- Note the returned milestone ID \u2014 you will need it for tasks.

The `description` passed to **create_milestone** must follow this structure:
- **Objective Verification Criterion**: A single, concrete, testable condition that proves this milestone is done (e.g., "The `/vms` endpoint returns a 200 with a valid JSON body for all CRUD operations in the CI test suite").
- **Incremental Value Delivered**: What does the team or user gain the moment this milestone closes? Why does it matter as a standalone checkpoint?

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (milestone title,
parent epic, and error message) and continue with the remaining milestones.
Do NOT stop the entire process because one item failed \u2014 you will reconcile
failures in Step 6.

### Step 3: Create Tasks

**\u26a0\ufe0f Quality gate**: A task description that is only a sentence or two will be rejected. Every task must have all five sections below.

Use **create_task** for each task. For each:
- Associate it with the correct milestone and epic (using IDs from above).
- Set the type (development, investigation, research, optimization, test, etc.).
- Set priority (1-5).
- Set estimated complexity if available.
- Note the returned task ID \u2014 you will need it for dependencies.

The `description` passed to **create_task** must follow this mandatory structure. Do NOT use the plan's one-line title as the description \u2014 expand it fully:

**Context / Motivation**: Why this task exists. Reference the parent milestone goal and any relevant findings or prior work.

**Detailed Description**: Current state \u2192 desired state. What must be built, fixed, or investigated. Inputs, outputs, constraints. Be specific \u2014 name files, modules, APIs.

**Acceptance Criteria** _(minimum 3, each independently verifiable)_: Use Given/When/Then format or a concrete checklist. Vague criteria like "works correctly" are not acceptable.

**Technical Notes**: Relevant files, modules, libraries, or patterns from the plan. Include specific paths or code references where known.

**Definition of Done**: Final checklist before the task can be marked complete (e.g., code reviewed, tests passing, docs updated).

**After each call**, check the returned result. If the returned ID is null
or the tool returns an error, note the failure internally (task title,
parent milestone, and error message) and continue with the remaining tasks.
Do NOT stop the entire process because one item failed \u2014 you will reconcile
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
create tasks or dependencies \u2014 those will be handled in a separate step.

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
created IDs. This is critical \u2014 the system parses this block to proceed.

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

    forgejo_owner = settings.FORGEJO_OWNER or "infinibay"

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

## Step 1 \u2014 Validate the Repository Name
The repo name must be all-lowercase, no spaces, no special characters except
hyphens. It must match this pattern: `^[a-z0-9][a-z0-9-]{{0,38}}[a-z0-9]$`
(2-40 characters, starts and ends with alphanumeric).

Requested name: `{repo_name}`

If the name violates this pattern, reject the request and use
**send_message** to ask `{requested_by}` to provide a valid name.
Do NOT proceed to Step 2.

## Step 2 \u2014 Create the Repository via the Forgejo API
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

## Step 3 \u2014 Communicate the Remote URL
Use **send_message** to notify `{requested_by}` with:
- The repo name: `{repo_name}`
- The clone URL: `http://localhost:3000/{forgejo_owner}/{repo_name}.git`
- The exact commands to configure the remote on their local workspace:
  ```
  git remote add origin http://localhost:3000/{forgejo_owner}/{repo_name}.git
  git fetch origin
  ```

## Step 4 \u2014 Document
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
