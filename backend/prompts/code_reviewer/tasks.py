"""Code Reviewer task prompts used in flows."""

from backend.prompts.shared import GIT_WORKFLOW_INSTRUCTIONS  # noqa: F401 — referenced in description text
from backend.prompts.team import build_state_context


def perform_review(
    task_id: int,
    task_title: str,
    branch_name: str,
    task_desc: str,
    project_id: int = 0,
    project_name: str = "",
    rejection_count: int = 0,
) -> tuple[str, str]:
    """Return (description, expected_output) for performing a code review.

    Args:
        task_id: The task being reviewed.
        task_title: Human-readable title of the task.
        branch_name: Git branch containing the code changes.
        task_desc: Full task description with acceptance criteria.
        project_id: DB ID of the project (for state context).
        project_name: Name of the project (for state context).
        rejection_count: How many times this code has been rejected so far.
    """
    is_rereview = rejection_count > 0

    if is_rereview:
        phase_summary = (
            f"Re-review round {rejection_count} — the code was previously "
            f"rejected and the Developer has submitted reworked changes."
        )
    else:
        phase_summary = (
            "Initial code review. The Developer has submitted code for "
            "your evaluation."
        )

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="code_review",
        summary=phase_summary,
        extra={"Review attempt": str(rejection_count + 1)}
        if is_rereview else None,
    )

    rereview_section = ""
    if is_rereview:
        rereview_section = f"""
### Re-Review Context
This is re-review round {rejection_count}. The Developer has reworked the
code based on your previous feedback. You MUST:
1. **Verify every previously reported blocking issue was addressed.** Read
   the new diff and confirm each issue is resolved. Do not assume fixes
   were applied correctly — verify.
2. **Check for regressions.** Sometimes fixing one issue introduces another.
   Review the new changes with fresh eyes, not just the areas you flagged.
3. **Apply the same quality bar.** Do not lower your standards because this
   is a re-review. The code either meets the bar or it does not.
4. **Acknowledge improvements.** If the Developer addressed your feedback
   well, note it in your review comment. Constructive feedback includes
   recognizing good work.

Your feedback must be clear and actionable so the Developer can resolve all
remaining issues in the next iteration.
"""

    description = f"""\
You are reviewing code for task {task_id}: {task_title}.
Branch: `{branch_name}`

{state_block}

## Task Specifications
{task_desc}

## Your Goal
Determine whether the code on branch `{branch_name}` meets the quality bar
for approval: it fulfills the task specifications, is free of bugs and
security vulnerabilities, performs adequately, and is maintainable. Either
approve or reject with specific, actionable feedback.
{rereview_section}
## Step-by-Step Process

### Step 1: Understand the Requirements
Use **GetTaskTool** to read the full task specifications. Before looking at
any code, make sure you understand:
- What the code is supposed to accomplish (the "what").
- The acceptance criteria — what conditions must be true for the task to be
  considered complete.
- Any constraints or technical requirements mentioned.

Also read the task comments — the Developer should have posted the branch
name, a summary of changes, and testing instructions. This is your map to
their work.

### Step 2: Survey the Changes
Use **GitStatusTool** to see which files were modified, added, or deleted.

**If GitStatusTool or GitDiffTool show no changes on the branch**: This is
a blocking issue. The Developer was required to commit and push code to the
branch before submitting for review. If the branch is empty or does not
exist, REJECT immediately — use **RejectTaskTool** with feedback: "No code
changes found on branch `{branch_name}`. You must commit and push your
changes before submitting for review."
This gives you a map of the change scope:
- How many files were touched?
- Are the changes concentrated in one area or spread across the codebase?
- Are there any unexpected files (generated files, unrelated changes)?

### Step 3: Review the Full Diff
Use **GitDiffTool** to read the complete diff. Go through every change
line by line. For each change, assess:

**3a. Relevance**: Does this change serve the task objective? Flag any
changes that seem unrelated to the task (scope creep).

**3b. Correctness**: Does the logic work? Look for:
- Off-by-one errors
- Null/undefined handling
- Missing error handling for failure paths
- Race conditions in concurrent code
- Incorrect use of APIs or libraries

**3c. Security**: Scan for:
- User input reaching queries/commands without sanitization (injection)
- User-controlled data rendered without escaping (XSS)
- Missing or incorrect authorization checks
- Hardcoded secrets (API keys, passwords, tokens)
- Sensitive data in logs or error messages

**3d. Performance**: Look for:
- Database queries inside loops (N+1)
- Blocking operations in async contexts
- Unnecessary memory allocation (loading large datasets entirely)
- Redundant network calls or I/O operations

### Step 3b: Post Forgejo PR Comments (REQUIRED)
After reading the diff, post your findings as comments directly on the
Forgejo Pull Request. This is SEPARATE from AddCommentTool (which posts
on the task, not the PR).

**3b-i. Fetch the PR diff** to confirm what is on the remote:
Use **ExecuteCommandTool** with this exact curl command:

  curl -s -X GET \
    -H "Content-Type: application/json" \
    "http://localhost:8000/api/git/prs/{{pr_id}}"

Where {{pr_id}} is the internal PR ID (visible in the task comments as
"pr_number: N"). The response contains the PR metadata including branch
name, status, and repo information. Verify the branch matches `{branch_name}`.

**3b-ii. Post review comments** on the PR:
Use **ExecuteCommandTool** with this exact curl command:

  curl -s -X POST \
    -H "Content-Type: application/json" \
    -d '{{"body": "<your comment text>", "comment_type": "<type>"}}' \
    "http://localhost:8000/api/git/prs/{{pr_id}}/comments"

Where:
  - {{pr_id}}       → the internal PR ID from step 3b-i
  - comment_type → set to "approval" when approving, or "change_request"
                   when requesting changes

Post ONE comment per blocking issue. Each comment body must follow this format:
  **[BLOCKING]** File: `<filename>`, Line: ~<line_number>
  Problem: <clear description of the bug/security issue/missing test>
  Why it matters: <impact if not fixed>
  How to fix: <specific, actionable instruction>

For non-blocking issues, use:
  **[SUGGESTION]** <description>

For the final verdict comment, post with the appropriate comment_type:
  comment_type: "approval"
  body: **[VERDICT: APPROVED]** All acceptance criteria are met. <brief summary>
  — OR —
  comment_type: "change_request"
  body: **[VERDICT: CHANGE_REQUEST]** N blocking issues must be resolved before merge.
  <list of blocking issues>

IMPORTANT: You MUST post the verdict comment BEFORE calling ApproveTaskTool
or RejectTaskTool. The Forgejo PR comment is the official review record.

### Step 4: Read Full Files for Context
Use **ReadFileTool** for files where the diff alone is insufficient:
- When you need to see how a modified function is called elsewhere.
- When you need to understand the class or module structure.
- When import changes affect code you cannot see in the diff.

Use **DirectorySearchTool** when you need to find related code by meaning
rather than exact text — for example, to find similar patterns, related
implementations, or code that handles the same concern but uses different
naming. This complements **CodeSearchTool** (exact/regex match).

Do NOT read every file in the project — only those directly relevant to
understanding the changes.

### Step 5: Verify Test Coverage
Apply the mandatory test-coverage checklist below. For each unchecked item
in the first five, create a `[BLOCKING]` PR comment (Step 3b) before
calling `RejectTaskTool`.

- [ ] New or modified functions/classes have at least one test.
- [ ] Happy path is covered.
- [ ] At least one error/exception path is covered.
- [ ] Edge cases relevant to the feature are covered (empty input, boundary values, etc.).
- [ ] Existing tests that exercise modified code were not silently deleted.
- [ ] Tests are meaningful — they assert on observable behavior, not just that the code runs.

Items 1-5 unchecked → **Blocking**. Item 6 unchecked → **Important**.

### Step 6: Compile Your Findings
Organize your findings by severity:
- **Blocking**: Issues that must be fixed (bugs, security, missing critical
  functionality, broken tests).
- **Important**: Issues that should be fixed (maintainability, missing error
  handling for likely scenarios, missing tests for important paths).
- **Suggestion**: Nice to have (style, minor refactoring, documentation).

### Step 7: Make Your Decision

**If there are NO blocking issues:**
1. Use **ApproveTaskTool** to approve the task.
2. Use **AddCommentTool** to leave a structured review comment that includes:
   - A brief summary of what was reviewed and that it meets the quality bar.
   - Any "important" or "suggestion" level notes for the Developer to
     consider in future work (these do not block approval).
   - Acknowledgment of anything done particularly well.
3. Return "APPROVED: <brief summary of what was reviewed and approved>".

**If there are blocking issues:**
1. Use **RejectTaskTool** to reject the task with your detailed feedback.
2. Use **AddCommentTool** to leave a structured review comment that includes:
   - A summary of the review outcome.
   - Each blocking issue with: file, line (if applicable), description of
     the problem, why it matters, and how to fix it.
   - Each important issue, similarly documented.
   - Any suggestions (clearly marked as non-blocking).
3. Return "REJECTED: <summary of blocking issues and what must change>".

After calling ApproveTaskTool or RejectTaskTool, verify the Forgejo PR
comment was posted (Step 3b). If the curl command failed, retry it once.
The PR comment is required — it is the record visible to the team in the
Forgejo UI.

### Communication
- If something in the code is genuinely ambiguous and you cannot evaluate it
  by reading the code and task specs, use **SendMessageTool** to ask the
  Developer. Be specific about what you need to know.
- Do NOT ask questions that are answered by the task description, the code,
  or the diff. Read thoroughly before asking.
"""

    expected_output = """\
A structured code review result containing:

1. **Review action**: Either approved (via ApproveTaskTool) or rejected
   (via RejectTaskTool with actionable feedback).

2. **Review comment**: A structured comment (via AddCommentTool) with:
   - Summary of what was reviewed
   - Blocking issues (if any): file, line, problem, impact, fix
   - Important issues: file, line, problem, recommendation
   - Suggestions (non-blocking): optional improvements
   - Acknowledgment of good practices (if applicable)

3. **Final status string**: Either:
   - "APPROVED: <summary of what was reviewed and why it passes>"
   - "REJECTED: <summary of blocking issues and required changes>"

4. **Test Coverage Checklist**: Mark each item `[x]` or `[ ]` and provide
   a one-line justification for any unchecked item:
   - [ ] New or modified functions/classes have at least one test.
   - [ ] Happy path is covered.
   - [ ] At least one error/exception path is covered.
   - [ ] Edge cases relevant to the feature are covered.
   - [ ] Existing tests that exercise modified code were not silently deleted.
   - [ ] Tests are meaningful — they assert on observable behavior.

5. **Forgejo PR comments**: Confirmation that curl was used to post:
   - One [BLOCKING] comment per blocking issue found (or none if approved).
   - One [VERDICT: APPROVED] or [VERDICT: CHANGE_REQUEST] comment.
   Include the HTTP response from each curl call to confirm success (look
   for `"id":` in the JSON response — that means the comment was created).

**⚠️ CRITICAL FORMAT RULE**: Your final status string MUST start with
`APPROVED` or `REJECTED` as the **very first word** of your response.
Do not prefix it with any other text, explanation, or punctuation. The
flow parser uses word-boundary matching — any other word before
`APPROVED` or `REJECTED` will cause the review to be treated as a
rejection by default.
"""
    return description, expected_output
