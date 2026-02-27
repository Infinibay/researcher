"""Developer task prompts used in flows."""

from backend.prompts.shared import GIT_WORKFLOW_INSTRUCTIONS
from backend.prompts.team import build_conversation_context, build_state_context


def implement_code(
    task_id: int,
    task_title: str,
    task_description: str,
    conversation_context: str = "",
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for code implementation."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="implementation",
        summary=f"Implementing task {task_id}. Create branch, write code, test, commit, push.",
    )

    ctx_block = conversation_context or ""

    from backend.config.settings import settings

    description = f"""\
Implement task {task_id}: {task_title}

{state_block}

## Task Specifications
{task_description}

{ctx_block}

## Repository Requirement
A git repository MUST exist before you start working. The repository should
already be configured with `origin` pointing to Forgejo.

If `git status` fails or `git remote -v` shows no remotes:
1. Use **SendMessageTool** to inform the Team Lead that no repository is
   configured for this project.
2. The Team Lead will coordinate with the Project Lead to create one.
3. Do NOT proceed with code changes until a repository is available.
4. Do NOT attempt to create a repository yourself.

{GIT_WORKFLOW_INSTRUCTIONS}

## Forgejo Remote Context
The remote `origin` on this workspace points to the Forgejo server.
FORGEJO_API_URL = {settings.FORGEJO_API_URL or "http://localhost:3000/api/v1"}
FORGEJO_OWNER   = {settings.FORGEJO_OWNER or "pabada"}
FORGEJO_REPO    = $FORGEJO_REPO   (set in environment — format: "owner/repo-name")

If `git push` fails with "repository not found", the remote is not configured.
Fix it with:
  ExecuteCommandTool → "git remote set-url origin http://localhost:3000/$FORGEJO_OWNER/$FORGEJO_REPO_NAME.git"
Then retry GitPushTool.

## Your Goal
Implement the code changes required by this task. The code must fulfill all
acceptance criteria, be tested, committed on a properly named branch, and
pushed to the remote.

## Step-by-Step Process

### Step 0: Resume Check
Call **LoadSessionNoteTool** with the current task_id. If a prior session
exists, read `notes_json` and look for the `"step"` key to know exactly
which step was last completed. Recover your branch name, files already
modified, and last known state from the rest of `notes_json`. Resume from
step **N+1** where N is the last completed step. If no session exists,
start from Step 1.

### Step 1: Create a Branch
Use **GitBranchTool** with branch_name=`task-{task_id}-<slug>`, create=true,
base_branch="main". This runs:
  git fetch origin main
  git checkout -b task-{task_id}-<slug> origin/main

Post the branch name as a comment on the task using **AddCommentTool**.

Save progress: call **SaveSessionNoteTool** with phase="implementing",
notes_json={{"branch": "<branch_name>", "step": 1}}.

### Step 2: Read Existing Code
Before writing anything, use **ReadFileTool** to read the files you plan
to modify. Understand:
- The existing code structure and patterns.
- How the code you will change is used by other parts of the system.
- What conventions are followed (naming, error handling, imports).

Use **CodeSearchTool** to find all usages of functions or classes you plan
to modify. This helps you understand the impact of your changes and avoid
breaking callers.

Save progress: call **SaveSessionNoteTool** with phase="implementing",
notes_json={{"branch": "...", "files_inspected": [...], "step": 2}},
last_file=<last file you read>.

### Step 3: Implement the Changes
For each change, follow existing codebase conventions, handle error conditions
appropriately, do NOT introduce security vulnerabilities (injection, XSS,
hardcoded secrets), and keep changes focused on the task scope — do not
refactor unrelated code.

**Modifying an existing file** (preferred path):
1. Use **CodeSearchTool** to locate the exact code to change.
2. Use **ReadFileTool** with `offset` and `limit` to read the relevant
   section — do NOT read entire large files when you only need a fragment.
3. Use **EditFileTool** to apply a surgical edit. The `old_string` must be
   unique within the file — include enough surrounding context to guarantee
   uniqueness.

**Creating a new file** (only when the file does not exist yet):
- Use **WriteFileTool** with the full absolute path.

**IMPORTANT**: Never use **WriteFileTool** to overwrite an existing file.
Overwriting destroys the change history and makes code review impossible.
If the file already exists, always use **EditFileTool**.

Save progress: call **SaveSessionNoteTool** with phase="implementing",
notes_json={{"branch": "...", "files_changed": [...], "step": 3}},
last_file=<last file edited>.

### Step 4: Write Tests
Write tests for new or modified functionality:
- Happy path: the feature works as specified.
- Error cases: invalid input, missing data, failures.
- Edge cases: boundary conditions, empty inputs, large inputs.

Place tests in the project's test directory following existing conventions.

Save progress: call **SaveSessionNoteTool** with phase="testing",
notes_json={{"branch": "...", "tests_written": [...], "step": 4}}.

### Step 5: Run Tests

#### 5a. Estimate suite duration
Before running the full suite, estimate its size:
1. Run **ExecuteCommandTool** with `pytest --co -q` (collect-only) to count
   the total number of tests.
2. If the count exceeds **500 tests**, or if a previous CI run recorded a
   duration > 600 seconds, switch to **relevant-only mode** (Step 5c).
   Otherwise use **full suite mode** (Step 5b).

#### 5b. Full suite mode (≤ threshold)
Run **ExecuteCommandTool** with `pytest -x -q` — all tests, stop on first
failure. ALL tests must pass — both your new tests and existing ones.

#### 5c. Relevant-only mode (> threshold)
Derive the list of test files directly related to the files you modified in
this task and run only those:
  `pytest <test_file_1> <test_file_2> ... -x -q`
This keeps CI under the 10-minute budget while still validating your changes.

#### 5d. Fix-and-rerun
If tests fail:
- Read the failure output carefully.
- Fix the issue in your code (not the test, unless the test is wrong).
- Re-run until all tests pass.

**Clarification during implementation**: You may ask at most **1 clarification
question** during implementation. If no response, proceed with assumptions
and document with AddCommentTool (prefix: `ASSUMPTION:`). Do NOT create new
tasks, epics, or other resources as a workaround — only continue working on
your assigned task.

**Escalation — persistently failing tests**: If after **3 fix-and-rerun
cycles** the tests still fail, STOP trying and escalate:
1. Use **AskTeamLeadTool** with a structured message containing:
   - The exact test command that fails.
   - The full error output.
   - A summary of the 3 fixes you already attempted and why each did not
     resolve the issue.
   - A specific question (not "what should I do?" — describe the concrete
     blocker).
2. Do NOT move the task to `review_ready` while tests are failing.
3. Do NOT commit or push code with failing tests.
4. Wait for the Team Lead's response before continuing.

**⚠️ HARD GATE: Setting the task status to `review_ready` with failing tests
is a protocol violation and will be treated as a blocking defect by the Code
Reviewer. The CI gate will automatically reject the submission before the
reviewer even sees it.**

Save progress: call **SaveSessionNoteTool** with phase="testing",
notes_json={{"branch": "...", "test_command": "...", "tests_passed": true/false, "step": 5}}.

### Step 6: Self-Review
Use **GitDiffTool** to review your own changes before committing. Check for:
- Unintended changes (debug prints, commented-out code, unrelated edits).
- Missing error handling.
- Security issues.
- Code that does not match the surrounding style.

Remove any debugging artifacts before committing.

Save progress: call **SaveSessionNoteTool** with phase="implementing",
notes_json={{"branch": "...", "self_review_clean": true/false, "step": 6}}.

### Step 7: Commit, Push, and Open PR
Follow STEPS 3, 4, and 5 of the Git + Forgejo Workflow above. Concretely:
1. **GitCommitTool** — stages all changes (`git add -A`) and commits
   (`git commit -m "<message>"`).
2. **GitPushTool** — pushes the branch to origin on the Forgejo server
   (`git push -u origin <branch>`).
3. **CreatePRTool** — opens a pull request against base="main" via
   `POST $FORGEJO_API_URL/repos/{{owner}}/{{repo}}/pulls`.
   The PR body must list each acceptance criterion from the task and
   confirm it is satisfied.

Save progress: call **SaveSessionNoteTool** with phase="implementing",
notes_json={{"branch": "...", "commit_sha": "...", "pr_url": "...", "step": 7}}.

### Step 8: Submit for Review
Use **UpdateTaskStatusTool** to set the status to `review_ready`.

Save progress: call **SaveSessionNoteTool** with phase="implementing",
notes_json={{"branch": "...", "status": "review_ready", "step": 8}}.

## Handoff to Code Reviewer
After you submit, a **Code Reviewer** will evaluate your work. The reviewer
is a different agent — they do NOT have access to your memory, your terminal
history, or anything you did not explicitly commit and push. If it is not
on the branch, it does not exist for the reviewer.

**The reviewer will use these tools to find your work:**
- **GitDiffTool** — to read the diff on your branch vs main.
- **GitStatusTool** — to see which files changed.
- **ReadFileTool** — to read specific files for context.
- **GetTaskTool** — to read the task description and your comments.

**Your AddCommentTool submission comment must include:**
1. The exact branch name (e.g., `task-7-auth-middleware`).
2. A summary of what changed and why.
3. How to test it (test command or manual steps).
4. Any assumptions made (prefix: `ASSUMPTION:`).

This is not optional — it is the reviewer's map to your work. A vague
comment like "implementation done" forces the reviewer to guess, which
slows down the entire review cycle.

## Important Reminders
- Do NOT move to `review_ready` without running tests.
- Do NOT push code with failing tests.
- Do NOT make changes outside the scope of the task.
- Do NOT forget to post the branch name as a task comment.
"""

    expected_output = """\
A summary of the implementation containing:

1. **Branch name**: The exact branch name created (format: task-{id}-{slug}).
2. **Files changed**: List of files created or modified with a brief
   description of each change.
3. **Tests written**: What tests were added and what they verify.
4. **Test results**: Confirmation that all tests pass.
5. **Test execution strategy**: State whether full suite or relevant-only
   mode was used, and why (test count, estimated duration).
6. **Status**: Confirmation that the task was moved to `review_ready`.
7. **Escalations** (if applicable): If tests failed persistently and
   AskTeamLeadTool was used, document what was asked and what response
   was received.
8. **Session State**: Whether a prior session was loaded and that progress
   was saved at each step with the correct step number in notes_json.
"""
    return description, expected_output


def respond_to_clarification(
    task_id: int,
    task_title: str,
    clarification_message: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for responding to team lead clarification."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="clarification",
        summary=(
            f"The Team Lead has requested clarification on task {task_id}. "
            "You must respond with a clear, detailed answer."
        ),
    )

    description = f"""\
The Team Lead has requested clarification on task {task_id}: {task_title}

{state_block}

## Clarification Request
{clarification_message}

## Your Goal
Provide a clear, detailed response that addresses every point raised by the
Team Lead. If answering requires you to inspect code or search the codebase,
do so before responding.

## Step-by-Step Process

### Step 1: Understand the Question
Read the clarification request carefully. Identify every specific question
or concern that needs to be addressed.

### Step 2: Gather Context (if needed)
If the Team Lead's questions require looking at code:
- Use **ReadFileTool** to read relevant files.
- Use **CodeSearchTool** to find usages or patterns related to the question.
- Use **ListDirectoryTool** to check project structure if relevant.

### Step 3: Respond
Use **SendMessageTool** to send a structured response to the Team Lead:
- Address each question or concern individually.
- Be specific — reference file paths, line numbers, and code patterns.
- If you are uncertain about something, say so clearly rather than guessing.
- If the clarification changes your implementation plan, describe how.
"""

    expected_output = """\
A confirmation that a detailed clarification response was sent to the Team
Lead via SendMessageTool, addressing every point raised in the original
request.
"""
    return description, expected_output


def rework_code(
    task_id: int,
    rejection_count: int,
    latest_feedback: str,
    branch_name: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for reworking rejected code."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="rework",
        summary=(
            f"Code for task {task_id} was rejected (attempt {rejection_count})."
            " You must address all reviewer feedback."
        ),
        extra={"Rework attempt": str(rejection_count)},
    )

    description = f"""\
Your code for task {task_id} has been rejected (attempt {rejection_count}).

{state_block}

## Reviewer Feedback
{latest_feedback}

## Branch
`{branch_name}`

## Your Goal
Address ALL issues identified by the Code Reviewer. The review cycle will
continue until the reviewer approves your code, so it is critical that you
resolve every blocking issue in this iteration.

## Step-by-Step Process

### Step 1: Understand the Feedback
Read the reviewer's feedback above carefully. For each issue, identify:
- **What** the problem is (file, line, specific code).
- **Why** it matters (bug, security, performance, maintainability).
- **How** the reviewer suggests fixing it.

Make a mental checklist of every issue that must be addressed.

### Step 2: Read the Current Code
Use **ReadFileTool** to read the current state of the files mentioned in
the feedback. Understand the code as it is now, not as you remember it.

Use **CodeSearchTool** if you need to find related usages or verify the
scope of a change (e.g., if the reviewer says "this function is called
from multiple places" — verify which places).

### Step 3: Apply Fixes
For each issue in the feedback:
1. Make the specific fix requested.
2. Verify the fix addresses the root cause, not just the symptom.
3. Check that the fix does not introduce new issues.

**Applying fixes to existing files** (the common case in a rework):
1. Use **CodeSearchTool** to locate the exact code to change.
2. Use **ReadFileTool** with `offset` and `limit` to read the relevant
   section.
3. Use **EditFileTool** to apply a surgical edit. Ensure `old_string` is
   unique within the file by including enough surrounding context.

**IMPORTANT**: In a rework you are almost always modifying existing files.
Never use **WriteFileTool** on an existing file — it would overwrite the
entire file, destroying prior changes the reviewer already evaluated. Always
use **EditFileTool** instead. Only use **WriteFileTool** if you need to
create a completely new file that does not exist yet.

### Step 4: Run Tests
Use **ExecuteCommandTool** to run the full test suite. ALL tests must pass.
If the reviewer identified missing tests, write them now.

### Step 5: Self-Review Against Feedback
Use **GitDiffTool** to review your rework diff. Go through the reviewer's
feedback point by point and verify:
- [ ] Each blocking issue has been addressed.
- [ ] No new issues were introduced.
- [ ] Tests pass.
- [ ] No unrelated changes were added.

### Step 6: Commit and Push
Push to the SAME branch `{branch_name}` — do NOT create a new branch for
a rework. Concretely:
1. **GitCommitTool** — stages all changes (`git add -A`) and commits
   (`git commit -m "<message>"`).
2. **GitPushTool** with branch=`{branch_name}` — pushes to origin on the
   Forgejo server (`git push -u origin {branch_name}`).

Commit message example:
"Fix injection vulnerability and add input validation per review feedback."

### Step 7: Submit for Re-Review
Use **UpdateTaskStatusTool** to set the status to `review_ready`.

## Critical Reminders
- Address ALL blocking issues — partial fixes will result in another
  rejection.
- Do NOT introduce new issues while fixing old ones.
- Do NOT argue with feedback silently by ignoring it — if you disagree,
  add a comment explaining your reasoning via **AddCommentTool**.
- Run tests BEFORE submitting. Broken tests are an automatic rejection.
- This is rejection attempt {rejection_count}. The review will continue
  until the reviewer approves, so resolve every issue now.
"""

    expected_output = f"""\
A summary of the rework containing:

1. **Issues addressed**: For each piece of reviewer feedback, what was
   changed and how.
2. **Files modified**: List of files changed during rework.
3. **Tests**: New tests added (if any) and confirmation all tests pass.
4. **Self-review**: Confirmation that the diff was reviewed against all
   feedback points.
5. **Status**: Confirmation that the task was moved to `review_ready`.
"""
    return description, expected_output
