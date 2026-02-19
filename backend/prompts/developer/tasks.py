"""Developer task prompts used in flows."""

from backend.prompts.shared import GIT_WORKFLOW_INSTRUCTIONS
from backend.prompts.team import build_conversation_context, build_state_context


def review_assigned_task(
    task_id: int,
    task_title: str,
    task_description: str,
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for reviewing an assigned task."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="task_assignment",
        summary=f"Task {task_id} has been assigned to you for implementation.",
    )

    ctx_block = conversation_context or ""

    description = f"""\
You have been assigned task {task_id}: {task_title}

{state_block}

## Task Specifications
{task_description}

{ctx_block}

## Your Goal
Understand the task requirements thoroughly before writing any code. Produce
a clear implementation plan that demonstrates you understand what needs to
be built, how it fits into the existing codebase, and what approach you will
take. You MUST complete all 6 stages below and document each one explicitly.

## Step-by-Step Process

### Stage 1: Problem Analysis
Read the task specifications above carefully and produce the following:
- **What is being asked?** — Rewrite the objective of the ticket in your own
  words. Do not copy-paste the task description.
- **Alignment with the project** — Verify that the ticket fits the general
  purpose of the system. If you detect a contradiction or scope ambiguity,
  document it explicitly.
- **Boundaries** — What is explicitly out of scope. What you must NOT change.
- **Acceptance criteria** — List every condition that must be true for this
  task to be considered complete.
- **Dependencies** — References to other tasks, modules, or external systems.

### Stage 2: Technologies Involved
Before exploring the code, identify the technology stack relevant to this ticket:
- Programming languages involved (Python, TypeScript, SQL, Bash, etc.).
- Key frameworks, libraries, or tools that will be used or modified.
- Relevant infrastructure (Docker, Redis, PostgreSQL, etc.).

Use **ListDirectoryTool** to confirm the project structure and detect
configuration files (`pyproject.toml`, `package.json`, `Containerfile`,
`docker-compose.yml`) that reveal the actual stack.

### Stage 3: Locating Changes
Use **ListDirectoryTool** to understand the project structure. Identify where
the relevant source code and tests live.

Use **ReadFileTool** to read the files most relevant to this task. Understand
the existing code you will modify or extend.

Use **CodeSearchTool** to find related code:
- Search for functions, classes, or modules mentioned in the task.
- Find existing patterns you should follow.
- Locate tests for related functionality.
- **Find all callers** of the functions you plan to modify to evaluate the
  impact of the change.

Produce a concrete list of:
- **Files to create or modify** — exact path and reason.
- **Classes and functions affected** — name and file.
- **External tools or services** the change touches (DB, git, APIs).
- **Existing related tests** — where they are and what they currently cover.

### Stage 4: Solution Evaluation
Before choosing an approach, you must:
1. Propose **at least 2 distinct approaches** to solve the problem.
2. For each approach, briefly describe: advantages, disadvantages, complexity,
   and risks.
3. **Choose one** and justify your choice with concrete criteria (simplicity,
   consistency with the codebase, performance, maintainability).
4. Document your decision with **AddCommentTool** (prefix: `DECISION:`) so
   it is recorded on the task.

If only one reasonable approach exists, document why the alternatives were
discarded.

### Stage 5: Test Plan
Before writing any code, define the test plan:
- **Happy path**: What correct behavior must be verified.
- **Error cases**: Invalid inputs, missing data, dependency failures.
- **Edge cases**: Boundary conditions, empty inputs, extreme values.
- **Regression cases**: Existing tests that could be affected by the change.

For each test case specify: tentative test name, what it verifies, and which
file it will go in.

### Stage 6: Clarification
If anything is unclear after completing the stages above:
- **First**, use **ReadMessagesTool** to check if your question was already
  answered in a previous conversation.
- If not answered, use **AskTeamLeadTool** to ask **ONE specific question**
  with 2-3 concrete options.
- You may ask at most **2 clarification questions** for this task. After that,
  proceed with your best judgment.
- If AskTeamLeadTool times out, make a reasonable assumption and document it
  with **AddCommentTool** (prefix: `ASSUMPTION:`). Then continue working.
"""

    expected_output = """\
A structured implementation plan with the following mandatory sections:

1. **Stage 1 — Problem Analysis**
   - Restatement of the objective in your own words.
   - Confirmation of alignment with the project (or description of any
     contradiction detected).
   - List of explicit boundaries (what is NOT being changed).
   - Acceptance criteria enumerated.
   - Dependencies identified.

2. **Stage 2 — Technologies Involved**
   - Technology stack relevant to this ticket.
   - Configuration files that confirm it.

3. **Stage 3 — Locating Changes**
   - List of files to create/modify with reason.
   - Classes and functions affected.
   - External services touched.
   - Existing related tests.

4. **Stage 4 — Solution Evaluation**
   - At least 2 proposed approaches with pros/cons.
   - Chosen approach and justification.
   - Confirmation that the decision was recorded with AddCommentTool
     (DECISION:).

5. **Stage 5 — Test Plan**
   - List of test cases (happy path, errors, edge cases, regression).
   - For each case: tentative name, what it verifies, target file.

6. **Clarifications / Assumptions**
   - Questions sent to the Team Lead (if any).
   - Assumptions documented with AddCommentTool (ASSUMPTION:).
"""
    return description, expected_output


def implement_code(
    task_id: int,
    task_title: str,
    task_description: str,
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for code implementation."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
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

### Step 1: Create a Branch
Use **GitBranchTool** with branch_name=`task-{task_id}-<slug>`, create=true,
base_branch="main". This runs:
  git fetch origin main
  git checkout -b task-{task_id}-<slug> origin/main

Post the branch name as a comment on the task using **AddCommentTool**.

### Step 2: Read Existing Code
Before writing anything, use **ReadFileTool** to read the files you plan
to modify. Understand:
- The existing code structure and patterns.
- How the code you will change is used by other parts of the system.
- What conventions are followed (naming, error handling, imports).

Use **CodeSearchTool** to find all usages of functions or classes you plan
to modify. This helps you understand the impact of your changes and avoid
breaking callers.

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

### Step 4: Write Tests
Write tests for new or modified functionality:
- Happy path: the feature works as specified.
- Error cases: invalid input, missing data, failures.
- Edge cases: boundary conditions, empty inputs, large inputs.

Place tests in the project's test directory following existing conventions.

### Step 5: Run Tests
Use **ExecuteCommandTool** to run the full test suite. ALL tests must pass —
both your new tests and existing ones. If tests fail:
- Read the failure output carefully.
- Fix the issue in your code (not the test, unless the test is wrong).
- Re-run until all tests pass.

**Clarification during implementation**: You may ask at most **1 clarification
question** during implementation. If no response, proceed with assumptions
and document with AddCommentTool (prefix: `ASSUMPTION:`).

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

### Step 6: Self-Review
Use **GitDiffTool** to review your own changes before committing. Check for:
- Unintended changes (debug prints, commented-out code, unrelated edits).
- Missing error handling.
- Security issues.
- Code that does not match the surrounding style.

Remove any debugging artifacts before committing.

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

### Step 8: Submit for Review
Use **UpdateTaskStatusTool** to set the status to `review_ready`.

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
5. **Status**: Confirmation that the task was moved to `review_ready`.
6. **Escalations** (if applicable): If tests failed persistently and
   AskTeamLeadTool was used, document what was asked and what response
   was received.
"""
    return description, expected_output


def respond_to_clarification(
    task_id: int,
    task_title: str,
    clarification_message: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for responding to team lead clarification."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
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
    max_rejections: int,
    latest_feedback: str,
    branch_name: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for reworking rejected code."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="rework",
        summary=(
            f"Code for task {task_id} was rejected (attempt {rejection_count}"
            f"/{max_rejections}). You must address all reviewer feedback."
        ),
        extra={"Rework attempt": f"{rejection_count} of {max_rejections}"},
    )

    description = f"""\
Your code for task {task_id} has been rejected (attempt \
{rejection_count}/{max_rejections}).

{state_block}

## Reviewer Feedback
{latest_feedback}

## Branch
`{branch_name}`

## Your Goal
Address ALL issues identified by the Code Reviewer. After {max_rejections}
total rejections the task will be escalated to the Team Lead, so it is
critical that you resolve every blocking issue in this iteration.

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
- This is attempt {rejection_count} of {max_rejections}. After
  {max_rejections} rejections the task is escalated to the Team Lead.
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
