"""Shared task prompts used across multiple roles."""

GIT_WORKFLOW_INSTRUCTIONS = """
## Git + Forgejo Workflow — MANDATORY RULES

The remote git server is Forgejo. The repository remote is named `origin`
and points to the Forgejo server (e.g. http://localhost:3000/{owner}/{repo}.git).
`origin` is already configured on the local workspace.
You MUST NOT change the remote URL.

### Canonical 5-Step Git Workflow

STEP 1 — CREATE BRANCH
  Tool: **GitBranchTool**
  Parameters:
    branch_name: "task-{task_id}-<short-slug>"
    create: true
    base_branch: "main"
  What this executes:
    git fetch origin main
    git checkout -b task-{task_id}-<short-slug> origin/main
  Rules:
    - Replace {task_id} with the actual integer task ID.
    - The slug must be lowercase, using only letters, digits, and hyphens.
    - Example branch name: "task-42-add-auth-endpoint"
    - Do NOT skip this step. Do NOT commit directly to main.

STEP 2 — WRITE CODE
  Use **EditFileTool** for existing files, **WriteFileTool** for new files only.
  Never use WriteFileTool on a file that already exists.

STEP 3 — COMMIT
  Tool: **GitCommitTool**
  Parameters:
    message: "<imperative verb> <what changed> — task {task_id}"
  What this executes:
    git add -A
    git commit -m "<your commit message>"
  Example message: "Add JWT validation middleware — task 42"
  Rules:
    - Run all tests with **ExecuteCommandTool** BEFORE committing.
    - Do NOT commit if any test fails.

STEP 4 — PUSH TO FORGEJO
  Tool: **GitPushTool**
  Parameters:
    branch: "<the branch name from Step 1>"
    force: false
  What this executes:
    git push -u origin <branch-name>
  The remote `origin` points to the Forgejo server. This command uploads
  your branch to Forgejo so it is visible in the Forgejo web UI.
  Rules:
    - If the push is rejected with "remote has new commits", pull first:
        ExecuteCommandTool → command: "git pull origin main --rebase"
      Then retry GitPushTool.
    - Do NOT use force=true unless the Team Lead explicitly instructs it.

STEP 5 — OPEN PULL REQUEST
  Tool: **CreatePRTool**
  Parameters:
    title: "<task title> (task-{task_id})"
    body: "<description of what was changed and why, referencing acceptance criteria>"
    base: "main"
    draft: false
  What this executes:
    POST $FORGEJO_API_URL/repos/{owner}/{repo}/pulls
    Payload: {{"title": "...", "body": "...", "head": "<branch>", "base": "main"}}
  base MUST always be "main" — never another branch.
  Rules:
    - Only call CreatePRTool AFTER GitPushTool succeeds.
    - The PR body MUST mention each acceptance criterion and confirm it is met.
    - After CreatePRTool returns, note the pr_number from the response.
"""


def brainstorm_round(
    round_count: int,
    project_name: str,
    project_description: str,
    project_type: str,
    existing_ideas: str = "",
    user_feedback: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for a brainstorming round.

    Used by team_lead, developer, and researcher agents.
    """
    sections = [
        f"Brainstorming session (round {round_count}).\n",
        "## Project Context\n"
        f"- **Name:** {project_name}\n"
        f"- **Description:** {project_description}\n"
        f"- **Type:** {project_type}\n",
    ]

    if user_feedback:
        sections.append(
            "## User Feedback from Previous Round\n"
            "The user rejected the previous set of ideas with this feedback:\n"
            f"> {user_feedback}\n\n"
            "You MUST address every point raised in the feedback above.\n"
        )

    if existing_ideas:
        sections.append(
            "## Previously Proposed Ideas (do NOT repeat these)\n"
            f"{existing_ideas}\n"
        )

    sections.append(
        "## Your Task\n"
        "1. Read the project context carefully.\n"
        "2. If user feedback is present above, list the specific concerns you will address.\n"
        "3. Propose exactly 3 new ideas that are distinct from existing ones.\n"
        "4. For each idea, output the block below **exactly** — no extra text before or after the block.\n"
        "\n"
        "## Mandatory Output Format\n"
        "\n"
        "```\n"
        "## Idea 1\n"
        "**Title:** <one-line title>\n"
        "**Description:** <2-3 sentences explaining the idea>\n"
        "**Impact:** <one sentence on expected benefit>\n"
        "**Feasibility:** <one sentence: High / Medium / Low and why>\n"
        "\n"
        "## Idea 2\n"
        "...\n"
        "\n"
        "## Idea 3\n"
        "...\n"
        "```\n"
        "\n"
        "## Constraints\n"
        "- Do not add any text outside the `## Idea N` blocks.\n"
        "- Do not number fields differently.\n"
        "- Do not merge fields.\n"
        "- If you cannot think of 3 distinct ideas, output fewer blocks rather than repeating existing ones.\n"
    )

    description = "\n".join(sections)
    expected_output = (
        "Exactly 3 Markdown blocks, each starting with `## Idea N`, "
        "containing **Title**, **Description**, **Impact**, and **Feasibility** "
        "fields in that order. No other text."
    )
    return description, expected_output
