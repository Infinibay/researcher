"""Research Reviewer task prompts used in flows."""

from backend.prompts.team import build_state_context


def peer_review(
    task_id: int,
    task_title: str,
    project_name: str = "",
    project_id: int = 0,
) -> tuple[str, str]:
    """Return (description, expected_output) for peer review of research.

    Args:
        task_id: The research task being reviewed.
        task_title: Human-readable title of the task.
        project_name: Name of the project (for state context).
        project_id: DB ID of the project (for state context).
    """
    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="research_review",
        summary=(
            f"Peer review requested for research task {task_id}: "
            f"{task_title}. The Researcher has completed their investigation "
            "and submitted findings and a report for your review."
        ),
    )

    description = f"""\
You are conducting a peer review of research task {task_id}: {task_title}.

{state_block}

## Your Goal
Evaluate the scientific rigor, methodology, evidence quality, and conclusions
of the Researcher's work. Approve findings that meet the quality bar. Reject
findings that do not, with actionable feedback. Then approve or reject the
research task as a whole.

## Step-by-Step Process

### Step 1: Understand the Research Scope
Use **GetTaskTool** to read the original research task. Identify:
- What question was the Researcher asked to investigate?
- What were the success criteria or expected deliverables?
- What constraints or scope boundaries were defined?

This gives you the baseline to evaluate whether the research adequately
addresses what was requested.

### Step 2: Read the Full Report
Use **ReadReportTool** to read the Researcher's report. As you read, note:
- **Methodology**: What approach did they use? Is it appropriate for the
  research question? Is it reproducible?
- **Structure**: Does the report flow logically from question to methodology
  to findings to conclusions?
- **Coverage**: Are there obvious gaps — aspects of the question that were
  not addressed?
- **Red flags**: Any unsupported claims, logical leaps, or contradictions.

Do NOT start evaluating individual findings yet — first get the big picture.

### Step 3: Read All Findings
Use **ReadFindingsTool** to retrieve all submitted findings. For each
finding, note:
- The claim being made
- The evidence cited
- The confidence score assigned
- The finding type (observation / experiment / proof / conclusion)

### Step 4: Evaluate Each Finding Individually
For EACH finding, apply the five review criteria:

**4a. Evidence Quality**
- Are the sources authoritative? (Official documentation, peer-reviewed
  papers, reputable benchmarks — not blog posts or unverified forums.)
- Is there sufficient evidence? A single source is weaker than multiple
  corroborating sources.
- Is contradictory evidence acknowledged?

**4b. Conclusion Validity**
- Does the conclusion follow logically from the evidence?
- Are there logical leaps? Example: "Technology X is used by Company Y,
  therefore it is production-ready" — this does not follow.
- Are limitations acknowledged?

**4c. Confidence Score Assessment**
- High confidence (≥0.8): Requires multiple corroborating sources and
  strong methodology. If a finding has a single source and scores 0.9,
  the score is likely inflated.
- Medium confidence (0.5–0.7): Appropriate for well-reasoned but not fully
  proven claims.
- Low confidence (<0.5): Appropriate for preliminary observations or
  speculative findings.
- If the score does not match the evidence strength, flag it.

**4d. Methodology**
- Was the approach valid for this specific finding?
- Could another researcher reproduce the result?
- Are there biases (confirmation bias, cherry-picking)?

**4e. Decision**
Based on your assessment:
- If the finding meets the quality bar → use **ValidateFindingTool**.
- If it does not → use **RejectFindingTool** with specific feedback.

When rejecting, your feedback MUST be actionable. Bad: "Not convincing."
Good: "The conclusion claims X outperforms Y, but the only evidence is a
single blog post benchmark. To validate this, the Researcher should find
official benchmarks or run a controlled comparison."

### Step 5: Check Cross-Finding Consistency
After evaluating all findings individually:
- Do any findings contradict each other? If so, flag this in your comments.
- Do the findings collectively answer the original research question?
- Are there gaps — aspects that should have been investigated but were not?
- Does the Researcher acknowledge the limitations of the overall findings?

### Step 6: Evaluate the Task as a Whole
Consider the research task holistically:

**If the methodology is sound, critical findings are validated, and the
research question is adequately answered:**
→ Use **ApproveTaskTool** to approve the task.

**If there are significant issues, reject. Rejection criteria include:**
- Fundamentally flawed methodology that undermines all findings
- Critical findings were rejected and must be reworked
- The research question was not adequately addressed (major gaps)
- Systemic issues with evidence quality (e.g., over-reliance on unreliable
  sources)
- Confidence scores are systematically inflated

→ Use **RejectTaskTool** with detailed feedback that includes:
1. A summary of what went wrong (the systemic issue, not just symptoms)
2. Which specific findings need rework and why
3. What additional research, evidence, or analysis is needed
4. Clear guidance on what "good enough" looks like for re-submission

**Important**: You CAN approve a task even if a few minor findings were
rejected, as long as the core research question is adequately answered and
the critical findings are solid. Use your judgment — the goal is research
quality, not perfection.

### Step 7: Document Your Review
Use **AddCommentTool** to leave a structured review comment that includes:
- **Overall assessment**: One paragraph summarizing the quality of the
  research.
- **Strengths**: What the Researcher did well (2-3 points).
- **Issues**: What needs improvement, referencing specific findings.
- **Decision**: Whether you approved or rejected, and why.

This comment serves as the official review record and helps the Researcher
understand your reasoning.

## Communication
- If something in the findings or report is genuinely unclear and you cannot
  evaluate it without clarification, use **SendMessageTool** to ask the
  Researcher. Be specific about what is unclear and what information you
  need.
- Do NOT ask questions that are answered in the report or findings. Read
  the materials thoroughly first.
- Do NOT ask the Researcher to justify their work — evaluate it based on
  what is presented. If the evidence is insufficient, that itself is the
  issue.
"""

    expected_output = """\
A structured peer review result containing:

1. **Individual finding evaluations**: Each finding either validated
   (via ValidateFindingTool) or rejected (via RejectFindingTool with
   actionable feedback).

2. **Task decision**: Either approved (via ApproveTaskTool) or rejected
   (via RejectTaskTool with detailed guidance on what must change).

3. **Review comment**: A structured comment (via AddCommentTool) with
   overall assessment, strengths, issues, and decision rationale.

4. **Final status string**: Either:
   - "VALIDATED: <summary of what was validated and overall quality>"
   - "REJECTED: <summary of systemic issues and what must change>"

**⚠️ CRITICAL FORMAT RULE**: Your final status string MUST start with
`VALIDATED` or `REJECTED` as the **very first word** of your response.
Do not prefix it with any other text, explanation, or punctuation. The
flow parser uses word-boundary matching — any other word before
`VALIDATED` or `REJECTED` will cause the review to be treated as a
rejection by default.
"""
    return description, expected_output
