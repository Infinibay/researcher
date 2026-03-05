"""Researcher task prompts used in flows."""

from backend.prompts.shared import GIT_WORKFLOW_INSTRUCTIONS
from backend.prompts.team import build_state_context


def assign_research(
    task_id: int,
    task_title: str,
    task_description: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for research task assignment."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="task_assignment",
        summary=f"Research task {task_id} has been assigned to you.",
    )

    description = f"""\
You have been assigned research task {task_id}: {task_title}

{state_block}

## Task Specifications
{task_description}

## Your Goal
Produce a research plan that demonstrates you understand the question,
have decomposed it into sub-questions, checked existing knowledge, and
have a clear strategy for investigation.

## What Good Looks Like
- The research question restated in your own words (proving you
  understand it).
- 3-5 sub-questions derived using PICO decomposition.
- Existing knowledge reviewed (search_knowledge, read_findings,
  read_wiki) — what does the team already know?
- A search strategy per sub-question: what queries, what source types.
- Any ambiguities identified and clarified (ask_team_lead) or
  documented as assumptions (add_comment with ASSUMPTION: prefix).

## Step 0: Resume Check
Call **load_session_note** with this task_id. If a previous session
exists, resume from the saved phase instead of starting over. If no
session exists, proceed with a fresh start.

## Methodology Guidance
Start by reading the task with get_task. Then check existing
knowledge — do NOT duplicate prior work. Decompose the question before
searching. If the scope is ambiguous, clarify with the Team Lead
BEFORE starting.

Call **save_session_note** with phase="decomposing" after posting your
research plan.

**Before posting anything**, call read_comments to see what has already
been discussed on this task. If a research plan already exists in the
comments, do NOT post another one — summarize what exists and finish.
Only post a new plan via add_comment if no prior plan exists.
"""

    expected_output = """\
A structured research plan containing:

1. **Research question**: Clear restatement of what needs to be investigated.
2. **Sub-questions**: 3-5 PICO-decomposed sub-questions.
3. **Existing knowledge**: Summary of what the team already knows.
4. **Search strategy**: Planned queries and source types per sub-question.
5. **Methodology**: How the investigation will be conducted.
6. **Questions or assumptions**: Any remaining ambiguities or documented
   assumptions.
"""
    return description, expected_output


def literature_review(
    task_id: int,
    task_title: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for literature review."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="literature_review",
        summary=(
            f"Conducting literature review for task {task_id}. "
            "Find, evaluate, and synthesize relevant sources."
        ),
    )

    description = f"""\
Conduct a literature review for research task {task_id}: {task_title}

{state_block}

## Your Goal
Map the state of the art for each sub-question. Find, evaluate, and
record the most relevant sources. Produce a structured literature review
that identifies key contributions, areas of consensus, disagreements,
and gaps.

## Step 0: Resume Check
Call **load_session_note** with this task_id. If a previous session
exists, resume from the saved phase and skip already-completed work.

## Methodology Guidance
- Search each sub-question independently using multiple query
  formulations per sub-question. Use deep_web_research for in-depth
  multi-source investigation; use web_search only for quick
  supplementary lookups.
- Apply SIFT on every source you intend to cite: investigate the
  source's reputation, find corroboration, trace claims to primary
  sources.
- Before recording a finding, call search_findings with the topic to
  check if a similar one already exists. Only call record_finding if
  no match above 0.85 similarity is found.
- Record findings as you discover them (record_finding) — do not
  batch at the end. Each finding needs: specific title, evidence with
  source, confidence score, finding type (observation).
- Track coverage: which sub-questions have adequate sources? Which
  remain under-covered? Direct additional searches at gaps.
- Actively search for contradictory evidence and alternative
  viewpoints — frame queries around limitations, criticisms, or
  failure cases.
- Write a state-of-the-art wiki article (write_wiki) covering key
  papers, consensus, debates, and gaps.
- Call **save_session_note** with phase="searching" after completing
  each sub-question, and phase="evaluating" when moving to synthesis.

## Artifact Checkpoint
Before finishing, verify your work is persisted:
1. read_findings returns ≥3 findings you recorded.
2. read_wiki returns the wiki article you wrote.

If either check fails, your work is lost and subsequent steps will
have nothing to build on. Re-record immediately.
"""

    expected_output = """\
A structured literature review containing:

1. **Search methodology**: Queries used per sub-question and sources
   consulted.
2. **Key sources**: The most important sources found, with credibility
   assessment.
3. **State of the art**: What is currently known, per sub-question.
4. **Areas of debate**: Where evidence is mixed or experts disagree.
5. **Knowledge gaps**: What questions remain unanswered.
6. **Recorded findings**: Exact count of findings recorded via
   record_finding.
7. **Wiki updated**: Article title written via write_wiki.
"""
    return description, expected_output


def formulate_hypothesis(
    task_id: int,
    task_title: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for hypothesis formulation."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="hypothesis_formulation",
        summary=(
            f"Formulating hypothesis for task {task_id} based on the "
            "completed literature review."
        ),
    )

    description = f"""\
Formulate competing hypotheses for research task {task_id}: {task_title}

{state_block}

## Your Goal
Based on your literature review, generate 3-5 competing hypotheses
that could answer the research question. Define what evidence would
distinguish between them. Register the primary hypothesis formally
and document all alternatives.

## Methodology Guidance
- Review your recorded findings (read_findings) to identify the
  strongest patterns, unresolved contradictions, and gaps.
- Generate 3-5 competing hypotheses — not just one. Each must be
  specific, testable, and falsifiable.
- For each hypothesis, define: what evidence would support it, what
  would refute it, and what would be inconclusive.
- Identify **diagnostic evidence** — evidence that supports one
  hypothesis but contradicts others. This is the most valuable
  evidence to search for during investigation.
- Register the primary hypothesis with create_hypothesis (include
  statement and rationale). If an existing hypothesis already covers
  your primary hypothesis (check with read_findings), reference it
  by ID instead of creating a duplicate.
- Before posting, call read_comments to check if hypotheses were
  already documented. Only add_comment if no hypothesis analysis
  exists yet.

Bad hypothesis: "LLMs are useful for code review."
Good hypothesis: "GPT-4 can identify security vulnerabilities in
Python code with precision ≥70%, based on CWE Top 25 categories."
"""

    expected_output = """\
A competing hypotheses analysis containing:

1. **Competing hypotheses**: 3-5 alternative hypotheses with rationale.
2. **Diagnostic evidence**: What evidence would distinguish between them.
3. **Primary hypothesis**: The most promising hypothesis, registered
   via create_hypothesis (or existing hypothesis ID if reusing one).
4. **Investigation plan**: How each hypothesis will be tested.
5. **Task comment**: Confirmation that all hypotheses were documented
   via add_comment.
"""
    return description, expected_output


def investigate(
    task_id: int,
    task_title: str,
    hypothesis: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for hypothesis investigation."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="investigation",
        summary=(
            f"Investigating hypothesis for task {task_id}. "
            "Gather evidence, analyze data, and record findings."
        ),
    )

    description = f"""\
Investigate the hypothesis for research task {task_id}: {task_title}

{state_block}

## Hypothesis
{hypothesis}

## Your Goal
Systematically investigate all competing hypotheses by gathering
evidence for each testable prediction. The correct answer is the one
with the LEAST contradicting evidence, not the most supporting
evidence.

## Methodology Guidance
- For each testable prediction, search for BOTH supporting AND
  contradicting evidence. Use deep_web_research with targeted queries
  per prediction. Run separate queries for limitations and criticisms.
- Cross-reference sources: for every important claim, find at least
  one additional independent source.
- Before recording, call search_findings to check for duplicates.
  Record findings immediately as you discover them (record_finding).
  Apply GRADE-inspired confidence scoring:
  - 0.85-1.0: Multiple independent credible sources, consistent.
  - 0.6-0.8: Good evidence, limited scope or few sources.
  - 0.35-0.55: Mixed evidence or single source.
  - 0.1-0.3: Speculative, based on reasoning not direct evidence.
- For each prediction, assess: supported, refuted, or inconclusive.
- Evaluate the overall hypothesis by disconfirmation: count
  inconsistencies, not confirmations.

## Devil's Advocate Check
Before concluding:
- What is the strongest counter-argument to your main conclusion?
- Would the conclusion change if you removed the single strongest
  piece of evidence?
- Do all your sources come from the same perspective or ecosystem?

Record your overall conclusion as a finding with type `conclusion`.
Call **save_session_note** with phase="synthesizing" after recording
your conclusion.

## Artifact Checkpoint
Use read_findings to confirm your findings are saved. If it returns
fewer than expected, some record_finding calls may have failed
silently — re-record immediately.
"""

    expected_output = """\
A structured investigation summary containing:

1. **Evidence per prediction**: Supporting and contradicting evidence
   found for each testable prediction.
2. **Prediction outcomes**: Each prediction assessed as supported,
   refuted, or inconclusive with confidence.
3. **Hypothesis assessment**: Overall assessment via disconfirmation
   analysis (which hypothesis has least inconsistent evidence).
4. **Recorded findings**: Exact count of findings recorded via
   record_finding.
5. **Devil's advocate results**: Counter-arguments considered and
   their impact on conclusions.
6. **Limitations**: Honest assessment of evidence gaps or
   methodological limitations.
"""
    return description, expected_output


def write_report(
    task_id: int,
    task_title: str,
    hypothesis: str,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for research report writing."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="report_writing",
        summary=(
            f"Writing formal research report for task {task_id}. "
            "Synthesize all findings into a structured deliverable."
        ),
    )

    description = f"""\
Write a comprehensive research report for task {task_id}: {task_title}

{state_block}

## Hypothesis
{hypothesis}

## Your Goal
Synthesize all findings into a formal report organized by theme, not
by source. The report must be clear enough for the Research Reviewer
to evaluate your methodology, evidence, and conclusions on their own.

## Methodology Guidance
- Review all findings (read_findings) and organize by topic or
  sub-question, NOT chronologically.
- Use **thematic synthesis**: group related findings together, put
  sources in conversation (where they agree, disagree, complement),
  highlight emergent insights.
- Apply the report structure:
  - **Executive Summary**: Research question, key findings, conclusions,
    confidence levels, recommendations. Must be self-contained.
  - **Methodology**: Search strategy, queries used, source evaluation
    criteria, analysis approach, limitations.
  - **Findings and Analysis**: Per theme — evidence, sources, confidence,
    analysis. Sources in conversation, not listed sequentially.
  - **Discussion**: How findings relate to hypotheses, contradictions
    and resolution, limitations, alternative interpretations.
  - **Conclusions**: Direct answers per sub-question. Clearly separate
    well-supported from speculative. Overall confidence.
  - **Recommendations**: Actionable next steps linked to specific
    findings. Priority ranked.
  - **References**: All sources cited with URLs.

Before writing the report, call **summarize_findings** to get a
compact overview of what you have — use it to plan report structure.

Write the report with write_report. Update wiki with key insights
(write_wiki). Post artifact inventory on task (add_comment):
finding count, report title, wiki articles. Set status to
`review_ready` (update_task_status).

If you produced code or notebooks, commit and push to Forgejo:
1. git_branch — `research-{task_id}-artifacts` from main.
2. git_commit — stage and commit artifacts.
3. git_push — push to origin.
4. create_pr — open PR against main.

## Quality Checklist
Before submitting, verify:
- [ ] Every claim traceable to a recorded finding.
- [ ] Confidence scores consistent and justified.
- [ ] Contradictory evidence acknowledged and discussed.
- [ ] Methodology documented clearly enough to reproduce.
- [ ] Executive summary accurately reflects the full report.
- [ ] References complete with URLs.
- [ ] read_findings returns your findings.
- [ ] read_report returns your report.
- [ ] Submission comment lists all artifacts created.
"""

    expected_output = """\
A confirmation of report completion containing:

1. **Report title**: The title created via write_report.
2. **Report structure**: Confirmation all sections are present.
3. **Findings referenced**: Count of recorded findings cited.
4. **Wiki updates**: Wiki articles created or updated.
5. **Status**: Confirmation task moved to `review_ready`.
6. **Artifact inventory**: Report title, finding count, wiki article
   titles — so the Research Reviewer can locate them.
"""
    return description, expected_output


def revise_research(
    task_id: int,
    reviewer_feedback: str = "",
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for research revision after rejection."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="revision",
        summary=(
            f"Research for task {task_id} was rejected in peer review. "
            "You must address all reviewer feedback."
        ),
    )

    description = f"""\
Your research for task {task_id} has been rejected in peer review.

{state_block}

## Reviewer Feedback
---
{reviewer_feedback}
---

## Your Goal
Address ALL issues identified by the Research Reviewer. Every concern
must be resolved before resubmission.

## Classify the Rejection
Determine the primary type to guide your revision strategy:

**Type A — Insufficient or Missing Sources**
Indicators: "not enough sources", "single source", "unverified".
Priority: find additional credible sources first, then update findings
and report.

**Type B — Incorrect or Unsupported Conclusions**
Indicators: "conclusion does not follow", "confidence too high",
"cherry-picking".
Priority: re-analyze existing findings, adjust confidence scores, and
rewrite conclusions before adding new sources.

**Type C — Both**
Address sources first, then conclusions.

## Methodology Guidance
- Read your current findings (read_findings) and report
  (read_report) to map each concern to specific sections.
- For Type A: run targeted searches for evidence addressing each
  concern. Apply SIFT. Record new findings.
- For Type B: adjust confidence scores, rewrite conclusions to match
  evidence. If the reviewer flagged confirmation bias, run a devil's
  advocate pass.
- Rewrite the report (write_report) incorporating all changes.
  The revised report should mention what changed in response to review.
- Self-review: go through the feedback point by point and confirm
  each concern is addressed.

## Artifact Checkpoint
Before resubmitting:
1. read_findings returns your findings (old + new).
2. read_report with task_id={task_id} returns the updated report.

If either check fails, re-record immediately. Do NOT submit without
verification.

Post a revision summary with add_comment mapping each reviewer
concern to the change made. Set status to `review_ready`
(update_task_status).
"""

    expected_output = f"""\
A summary of revisions containing:

1. **Feedback addressed**: For EACH reviewer concern, what was changed.
2. **Rejection type**: Type A, B, or C, and how that shaped the
   revision.
3. **Additional research** (Type A): New sources and findings recorded.
4. **Confidence adjustments** (Type B): Findings whose scores changed.
5. **Report updates**: Sections revised.
6. **Artifact verification**: read_findings and read_report
   (task_id={task_id}) both return data.
7. **Status**: Task moved to `review_ready`.
"""
    return description, expected_output


def update_knowledge_base(
    task_id: int,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for knowledge base update after validation."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="knowledge_update",
        summary=(
            f"Research for task {task_id} has been validated by peer review. "
            "Finalize knowledge base entries and archive results."
        ),
    )

    description = f"""\
The research for task {task_id} has been validated by peer review.

{state_block}

## Your Goal
Ensure all validated findings are properly indexed in the knowledge base,
wiki articles are up to date, and key patterns are saved to memory for
future research sessions.

## Step-by-Step Process

### Step 1: Review Validated Findings
Use **read_findings** to read all findings from this task. Verify that:
- All findings have appropriate confidence scores.
- Finding titles and content are clear and useful for future reference.
- No important findings were missed.

### Step 2: Update Wiki Articles
Use **read_wiki** to check existing wiki articles related to this task.
Use **write_wiki** to:
- Update existing articles with validated insights.
- Create new articles for key topics that are not yet documented.
- Add cross-references between related articles.

Focus on information that will be useful to other team members:
- State-of-the-art summaries.
- Key definitions, metrics, or benchmarks.
- Methodology notes and best practices.
- Important reference lists.

### Step 3: Finalize Task
Use **update_task_status** to move the task to `done`.
Use **add_comment** to post a final summary of the research
contribution to the project.
"""

    expected_output = """\
A final summary containing:

1. **Validated findings**: Count and summary of findings in the knowledge
   base.
2. **Wiki articles**: List of wiki articles created or updated.
3. **Memory entries**: Key patterns saved for future sessions.
4. **Task status**: Confirmation that the task was moved to `done`.
5. **Contribution summary**: Brief description of how this research
   contributes to the project's goals.
"""
    return description, expected_output


def push_artifacts(
    task_id: int,
    task_title: str,
    artifact_paths: list[str],
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for pushing research artifacts to Forgejo."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="artifact_push",
        summary=(
            f"Pushing research artifacts for task {task_id} to the Forgejo "
            "repository so the team can access and reproduce your work."
        ),
    )

    paths_list = "\n".join(f"- `{p}`" for p in artifact_paths)

    description = f"""\
Push research artifacts for task {task_id}: {task_title}

{state_block}

## Context
You have produced research artifacts (notebooks, scripts, data files) that
must be committed to the Forgejo repository so the team can access and
reproduce your work.

{GIT_WORKFLOW_INSTRUCTIONS}

## Researcher-Specific Rules

### Branch Name Format
Use: `research-{task_id}-<slug>` (e.g. `research-{task_id}-llm-benchmark-notebooks`)

### What to Commit
Only commit files listed below. Do NOT commit raw data files larger than
50 MB — use **execute_command** to check file sizes with `du -sh <file>`
first. If a file exceeds 50 MB, skip it and note the omission in the PR body.

**Artifacts to commit:**
{paths_list}

### Commit Message Format
`"Add research artifacts for task {task_id}: <brief description>"`

### PR Body Requirements
The PR body MUST include:
1. What each artifact contains.
2. How to run / reproduce the results.
3. Which research findings it supports.
"""

    expected_output = f"""\
A confirmation of artifact push containing:

1. **Branch name**: The exact branch name created (format: research-{task_id}-<slug>).
2. **Files committed**: List of artifact files committed, with sizes.
3. **Files skipped**: Any files exceeding the 50 MB limit (or "none").
4. **PR created**: Confirmation that a PR was opened against main, with the
   PR number from create_pr.
5. **PR body**: Confirmation that the body includes artifact descriptions,
   reproduction steps, and links to research findings.
"""
    return description, expected_output


def rescue_missing_artifacts(
    task_id: int,
    task_title: str,
    missing_findings: bool = True,
    missing_report: bool = True,
    project_id: int = 0,
    project_name: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for the rescue prompt.

    This is invoked by the flow guardrail when the researcher completed
    a step but failed to persist artifacts (findings/reports) in the DB.
    The prompt is intentionally short and direct to maximise the chance
    that weaker models actually call the tools.
    """
    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="artifact_rescue",
        summary=(
            f"URGENT: Research task {task_id} has missing artifacts that must "
            "be created before peer review can proceed."
        ),
    )

    missing_parts = []
    if missing_findings:
        missing_parts.append(
            "- **FINDINGS**: You have ZERO findings recorded for this task. "
            "Use **record_finding** RIGHT NOW to record at least 3 findings "
            "from your research. Each finding needs: a clear title, content with "
            "evidence, a confidence score, and finding_type (observation/conclusion)."
        )
    if missing_report:
        missing_parts.append(
            "- **REPORT**: You have ZERO reports for this task. "
            "Use **write_report** RIGHT NOW to write a research report. "
            "The report must cover: executive summary, methodology, findings, "
            "conclusions, and references."
        )
    missing_block = "\n".join(missing_parts)

    description = f"""\
CRITICAL: Your research for task {task_id} ({task_title}) is about to go to
peer review, but the system detected that you have NOT saved your work using
the required tools. The following artifacts are MISSING from the database:

{missing_block}

{state_block}

## What Happened
You completed your research steps but did NOT call the required tools to
persist your work. Without these artifacts in the database, the peer
reviewer will reject your work immediately.

## What You Must Do NOW
1. Use **read_findings** to check what findings exist for this task.
2. If findings are missing: call **record_finding** for each key finding.
3. Use **read_report** with task_id={task_id} to check if a report exists.
4. If the report is missing: call **write_report** to create the report.
5. Use **read_findings** again to VERIFY your findings were saved.

DO NOT explain what you plan to do. DO NOT summarize your research.
CALL THE TOOLS IMMEDIATELY. Every response that is not a tool call is wasted.
"""

    expected_output = f"""\
Confirmation that ALL missing artifacts were created:
1. Number of findings recorded via record_finding (minimum 3).
2. Report title created via write_report.
3. Verification via read_findings showing findings exist for task {task_id}.
"""
    return description, expected_output
