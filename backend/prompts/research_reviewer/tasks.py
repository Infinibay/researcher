"""Research Reviewer task prompts used in flows.

Contains prompts for both research peer review (full 7-criteria framework)
and investigation review (simplified 4-criteria framework).
"""

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
Evaluate the Researcher's work against the 7-criteria review framework
in your system prompt. Approve work that demonstrates sound methodology.
Reject with specific, actionable feedback referencing the framework
criteria by name.

## Start Here
1. **Read the task** (get_task) — understand what was requested,
   success criteria, and scope. Check task comments for the Researcher's
   artifact inventory (report title, finding count, wiki articles).
2. **Read the report** (read_report) — get the big picture:
   methodology, narrative, quality.
   - If no report exists → **immediate reject** via reject_task:
     "No research report found. You must use write_report to create
     a formal report before submitting for review."
3. **Read all findings** (read_findings) — understand what was
   claimed and at what confidence.
   - If no findings exist → **immediate reject** via reject_task:
     "No findings recorded. You must use record_finding to record
     your key findings before submitting for review."

## Evaluate Against the Review Framework
Apply all 7 criteria from your system prompt:

1. **Question Decomposition** — Was the question decomposed into
   sub-questions? Is the decomposition visible in the methodology?
2. **Competing Hypotheses** — Were alternatives considered? Is there
   disconfirmation analysis? (Less applicable for purely exploratory
   tasks.)
3. **Source Quality** — Are sources credible and diverse? Are claims
   corroborated? Primary sources traced?
4. **Synthesis Quality** — Is the report organized by theme? Are
   sources in conversation? Or is it source-by-source summary?
5. **Confidence Calibration** — Do scores match evidence strength?
   Any systematic inflation?
6. **Completeness** — Were all sub-questions addressed? Key findings
   have ≥2-3 sources? Contradictions investigated?
7. **Devil's Advocate** — Are counter-arguments discussed? Limitations
   acknowledged?

## Evaluate Each Finding Individually
For each finding:
- Is the evidence sufficient and from reliable sources?
- Does the conclusion follow from the evidence?
- Is the confidence score calibrated?
- If it meets the bar → validate_finding.
- If not → reject_finding with specific, actionable feedback.

## Make the Task Decision
- **Approve** (approve_task) when: methodology sound, critical
  findings validated, research question adequately answered. You CAN
  approve even if minor findings were rejected, as long as core
  findings are solid.
- **Reject** (reject_task) when: no artifacts, no decomposition,
  no alternative hypotheses for evaluative questions, summary instead
  of synthesis, systematically inflated confidence, major gaps.
  Include: what is wrong (which criteria), where, how to fix, priority.

## Document Your Review
Use add_comment to post a structured review:
- **Overall assessment**: One paragraph on research quality.
- **Strengths**: 2-3 things the Researcher did well.
- **Issues**: What needs improvement, referencing framework criteria.
- **Decision**: Approved or rejected, with rationale.
"""

    expected_output = """\
A structured peer review result containing:

1. **Individual finding evaluations**: Each finding either validated
   (via validate_finding) or rejected (via reject_finding with
   actionable feedback referencing the review framework).

2. **Task decision**: Either approved (via approve_task) or rejected
   (via reject_task with detailed guidance on what must change,
   referencing specific criteria from the review framework).

3. **Review comment**: A structured comment (via add_comment) with
   overall assessment, strengths, issues, and decision rationale.

4. **Final status string**: Either:
   - "VALIDATED: <summary of what was validated and overall quality>"
   - "REJECTED: <summary of systemic issues and what must change>"

**\u26a0\ufe0f CRITICAL FORMAT RULE**: Your final status string MUST start with
`VALIDATED` or `REJECTED` as the **very first word** of your response.
Do not prefix it with any other text, explanation, or punctuation. The
flow parser uses word-boundary matching — any other word before
`VALIDATED` or `REJECTED` will cause the review to be treated as a
rejection by default.
"""
    return description, expected_output


def investigation_review(
    task_id: int,
    task_title: str,
    project_name: str = "",
    project_id: int = 0,
) -> tuple[str, str]:
    """Return (description, expected_output) for peer review of an investigation.

    Uses the simplified 4-criteria framework instead of the full 7-criteria
    research review framework.
    """
    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="investigation_review",
        summary=(
            f"Peer review requested for investigation task {task_id}: "
            f"{task_title}. The Researcher has completed their investigation "
            "and submitted findings and a report for your review."
        ),
    )

    description = f"""\
You are conducting a peer review of investigation task {task_id}: {task_title}.

{state_block}

## Your Goal
Evaluate the Researcher's work against the **4-criteria investigation
review framework** in your system prompt. This is an investigation task,
NOT a research task — do NOT apply PICO, ACH, GRADE, or devil's advocate
criteria.

## Start Here
1. **Read the task** (get_task) — understand what was requested,
   success criteria, and scope. Check task comments for the Researcher's
   artifact inventory (report title, finding count, wiki articles).
2. **Read the report** (read_report) — get the big picture:
   scope, approach, findings, quality.
   - If no report exists -> **immediate reject** via reject_task:
     "No investigation report found. You must use write_report to create
     a report before submitting for review."
3. **Read all findings** (read_findings) — understand what was found.
   - If no findings exist -> **immediate reject** via reject_task:
     "No findings recorded. You must use record_finding to record
     your key findings before submitting for review."

## Evaluate Against the Investigation Review Framework
Apply the 4 criteria from your system prompt:

1. **Scope Coverage** — Was the scope clearly defined? Were all scope
   areas explored? Were any areas mentioned but not investigated?
2. **Source Quality** — Are sources credible and diverse? Are claims
   corroborated? Primary sources traced?
3. **Clarity & Organization** — Is the report organized by topic?
   Clear and actionable? Easy to navigate?
4. **Completeness** — Were open questions identified? Are findings
   recorded? Is there enough information for the team to make decisions?

## Evaluate Each Finding Individually
For each finding:
- Is the evidence from reliable sources?
- Is the finding clearly stated and useful?
- If it meets the bar -> validate_finding.
- If not -> reject_finding with specific, actionable feedback.

## Make the Task Decision
- **Approve** (approve_task) when: scope covered, sources credible,
  report clear and organized, findings sufficient for decisions.
- **Reject** (reject_task) when: no artifacts, major scope gaps,
  unreliable sources, disorganized report, insufficient findings.
  Include: what is wrong (which criteria), where, how to fix, priority.

## Document Your Review
Use add_comment to post a structured review:
- **Overall assessment**: One paragraph on investigation quality.
- **Strengths**: 2-3 things the Researcher did well.
- **Issues**: What needs improvement, referencing the 4 criteria.
- **Decision**: Approved or rejected, with rationale.
"""

    expected_output = """\
A structured peer review result containing:

1. **Individual finding evaluations**: Each finding either validated
   (via validate_finding) or rejected (via reject_finding with
   actionable feedback).

2. **Task decision**: Either approved (via approve_task) or rejected
   (via reject_task with detailed guidance on what must change,
   referencing the 4 investigation criteria).

3. **Review comment**: A structured comment (via add_comment) with
   overall assessment, strengths, issues, and decision rationale.

4. **Final status string**: Either:
   - "VALIDATED: <summary of what was validated and overall quality>"
   - "REJECTED: <summary of issues and what must change>"

**\u26a0\ufe0f CRITICAL FORMAT RULE**: Your final status string MUST start with
`VALIDATED` or `REJECTED` as the **very first word** of your response.
Do not prefix it with any other text, explanation, or punctuation. The
flow parser uses word-boundary matching — any other word before
`VALIDATED` or `REJECTED` will cause the review to be treated as a
rejection by default.
"""
    return description, expected_output
