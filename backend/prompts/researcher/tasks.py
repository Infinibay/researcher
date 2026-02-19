"""Researcher task prompts used in flows."""

from backend.prompts.shared import GIT_WORKFLOW_INSTRUCTIONS
from backend.prompts.team import build_state_context


def assign_research(
    task_id: int,
    task_title: str,
    task_description: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for research task assignment."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="task_assignment",
        summary=f"Research task {task_id} has been assigned to you.",
    )

    description = f"""\
You have been assigned research task {task_id}: {task_title}

{state_block}

## Task Specifications
{task_description}

## Your Goal
Understand the research task thoroughly and produce a clear research plan
that demonstrates you understand what needs to be investigated, what sources
are available, and what approach you will take.

## Step-by-Step Process

### Step 1: Understand the Research Question
Read the task specifications above carefully. Identify:
- **What** question needs to be answered.
- **Scope** — the boundaries of the investigation (what is in scope, what
  is explicitly out of scope).
- **Acceptance criteria** — the specific conditions that must be true for
  the research to be considered complete.
- **Deliverables** — what outputs are expected (findings, report, wiki
  articles, etc.).

### Step 2: Check Existing Knowledge
Use **SearchKnowledgeTool** and **ReadFindingsTool** to check what the team
already knows about this topic. Identify:
- Prior findings that are relevant to this task.
- Gaps in existing knowledge that this task should fill.
- Related research tasks and their outcomes.

Use **ReadWikiTool** to check for existing wiki articles on the topic.

### Step 3: Explore Available References
Use **ListDirectoryTool** and **ReadFileTool** to check for reference files,
datasets, or prior outputs in the project that may be relevant.

Use **CodeSearchTool** to find mentions of the topic across the codebase
and existing research artifacts.

### Step 4: Identify Ambiguities
If anything about the task is unclear after reading the specifications and
existing knowledge:
- Use **AskTeamLeadTool** to ask specific questions.
- Do NOT guess at the research direction — clarify before starting.

### Step 5: Produce Your Research Plan
Write a structured research plan covering:
1. **Research question restatement** — your understanding of what needs to
   be answered.
2. **Preliminary search strategy** — what search queries and sources you
   plan to start with.
3. **Methodology** — how you will conduct the investigation (literature
   review, data analysis, comparison, etc.).
4. **Expected deliverables** — what findings, reports, and wiki articles
   you plan to produce.
5. **Known risks** — potential challenges (limited sources, rapidly evolving
   field, controversial topic).
"""

    expected_output = """\
A structured research plan containing:

1. **Research question**: Clear restatement of what needs to be investigated.
2. **Existing knowledge**: Summary of what the team already knows about this
   topic (from knowledge base and wiki).
3. **Search strategy**: Planned search queries and source types.
4. **Methodology**: How the investigation will be conducted.
5. **Expected deliverables**: List of planned outputs.
6. **Questions or concerns**: Any remaining ambiguities (or confirmation
   that everything is clear).
"""
    return description, expected_output


def literature_review(task_id: int, task_title: str) -> tuple[str, str]:
    """Return (description, expected_output) for literature review."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
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
Find, read, and synthesize the most relevant and credible sources on this
topic. Produce a structured literature review that maps the state of the art,
identifies key contributions, and highlights gaps in existing knowledge.

## Step-by-Step Process

### Step 1: Systematic Search
Use **WebSearchTool** to conduct a systematic search. Execute multiple
search queries to cover different angles:
- The main topic using different phrasings and keywords.
- Specific subtopics, techniques, or methods mentioned in the task.
- Recent surveys, meta-analyses, or review papers.
- Contradictory viewpoints and alternative approaches.

Record each search query you use — this is part of your methodology
documentation.

### Step 2: Source Selection and Evaluation
From the search results, select the most relevant sources. For each:
- Evaluate credibility: peer-reviewed > official docs > established blogs
  > forums.
- Check recency: prioritize recent sources in fast-moving fields.
- Check relevance: does it directly address the research question?

Use **WebFetchTool** to read full articles and documentation pages.
Use **ReadPaperTool** to read academic papers in depth.

Aim for at least 5-10 high-quality sources, but prioritize quality over
quantity.

### Step 3: Record Key Findings
As you read each source, use **RecordFindingTool** to record significant
findings immediately. For each finding:
- Write a clear, specific title.
- Include the source URL and a brief assessment of its credibility.
- Assign a confidence score based on evidence strength.
- Set finding type to `observation`.

### Step 4: Synthesize and Document
Use **WriteWikiTool** to write a state-of-the-art summary. This should:
- Map the key papers and their contributions.
- Identify areas of consensus and disagreement.
- Highlight gaps that your investigation could address.
- List the most important references.

### Step 5: Check for Contradictions
Actively search for evidence that contradicts the emerging consensus.
Record contradictory findings with the same rigor as supporting ones.
"""

    expected_output = """\
A structured literature review containing:

1. **Search methodology**: Queries used and sources consulted.
2. **Key papers and contributions**: The most important sources found,
   with brief summaries of their relevance.
3. **State of the art**: What is currently known about this topic.
4. **Areas of debate**: Where experts disagree or evidence is mixed.
5. **Knowledge gaps**: What questions remain unanswered.
6. **Recorded findings**: Confirmation that key findings were recorded
   in the knowledge base with confidence scores.
7. **Wiki updated**: Confirmation that the wiki was updated with the
   state-of-the-art summary.
"""
    return description, expected_output


def formulate_hypothesis(task_id: int, task_title: str) -> tuple[str, str]:
    """Return (description, expected_output) for hypothesis formulation."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="hypothesis_formulation",
        summary=(
            f"Formulating hypothesis for task {task_id} based on the "
            "completed literature review."
        ),
    )

    description = f"""\
Formulate a research hypothesis for task {task_id}: {task_title}

{state_block}

## Your Goal
Based on your literature review, formulate a clear, testable hypothesis
that directly addresses the research question. Define specific predictions
and outline the methodology you will use to investigate the hypothesis.

## Step-by-Step Process

### Step 1: Review Your Findings
Use **ReadFindingsTool** to review all findings recorded during the
literature review. Identify:
- The strongest patterns in the evidence.
- Gaps or unresolved questions that a hypothesis could address.
- Contradictions that need to be resolved.

### Step 2: Formulate the Hypothesis
A good hypothesis must be:
- **Specific**: Makes a clear, unambiguous claim.
- **Testable**: Can be investigated with available tools and data.
- **Falsifiable**: Can be proven wrong by evidence.
- **Relevant**: Directly addresses the research question from the task.

Bad: "LLMs are useful for code review."
Good: "GPT-4 can identify security vulnerabilities in Python code with
a precision of at least 70%, based on the CWE Top 25 categories."

### Step 3: Define Testable Predictions
For each hypothesis, define 2-4 specific, testable predictions:
- What results would **support** the hypothesis?
- What results would **refute** the hypothesis?
- What results would be **inconclusive**?

### Step 4: Outline the Investigation Methodology
Describe how you will test each prediction:
- What data or evidence will you search for?
- What comparisons or analyses will you perform?
- What sources will you consult?
- What would constitute sufficient evidence?

### Step 5: Register the Hypothesis
Use **CreateHypothesisTool** to formally register your hypothesis with:
- The hypothesis statement.
- Testable predictions.
- Investigation methodology.

### Step 6: Document in Task
Use **AddCommentTool** to post the hypothesis on the task for visibility.
"""

    expected_output = """\
A formal research hypothesis containing:

1. **Hypothesis statement**: A clear, specific, testable claim.
2. **Testable predictions**: 2-4 specific predictions with criteria for
   support, refutation, and inconclusive outcomes.
3. **Investigation methodology**: How each prediction will be tested.
4. **Registration**: Confirmation that the hypothesis was registered via
   CreateHypothesisTool.
"""
    return description, expected_output


def investigate(
    task_id: int,
    task_title: str,
    hypothesis: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for hypothesis investigation."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
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
Systematically investigate the hypothesis by gathering evidence for each
testable prediction. Record every significant finding with appropriate
confidence scores. Actively seek both supporting and contradicting evidence.

## Step-by-Step Process

### Step 1: Plan Your Investigation
Review the hypothesis and its testable predictions. For each prediction,
identify:
- What specific evidence would support or refute it.
- Where to find that evidence (web search, papers, data, existing findings).
- What analysis or comparison is needed.

### Step 2: Gather Evidence Systematically
For each testable prediction:

**2a. Search for supporting evidence**
Use **WebSearchTool** with targeted queries. Use **WebFetchTool** and
**ReadPaperTool** to read sources in depth.

**2b. Search for contradicting evidence**
This is equally important. Actively search for evidence that would disprove
the prediction. Queries like "<topic> limitations", "<topic> criticism",
"<topic> fails" are valuable.

**2c. Analyze data if available**
If the investigation involves data analysis, use **ReadFileTool** to read
datasets and **CodeSearchTool** to find relevant data across the project.

**2d. Cross-reference sources**
Do not rely on a single source. For every important claim, find at least
one additional independent source that confirms or contradicts it.

### Step 3: Record Findings Immediately
Use **RecordFindingTool** for each significant finding as you discover it.
For each finding:
- **Title**: Specific and descriptive (not vague).
- **Content**: What was found, from which source, with what evidence.
- **Confidence score**: Apply the confidence scoring guidelines:
  - 0.9-1.0: Multiple independent credible sources, sound methodology.
  - 0.7-0.8: Good evidence, limited scope or minor concerns.
  - 0.5-0.6: Mixed evidence or single source only.
  - 0.3-0.4: Weak evidence, limited data, uncertain credibility.
  - 0.1-0.2: Speculative, based on reasoning not direct evidence.
- **Finding type**: `observation` (what was found), `experiment` (what was
  tested), `proof` (what was demonstrated), or `conclusion` (what was
  inferred).

### Step 4: Evaluate Each Prediction
For each testable prediction, summarize:
- What evidence was found (supporting and contradicting).
- Whether the prediction is supported, refuted, or inconclusive.
- The overall confidence level.

### Step 5: Assess the Hypothesis
Based on the evidence across all predictions:
- Is the hypothesis supported, partially supported, or refuted?
- What caveats or limitations apply?
- What follow-up questions emerge?

Record your overall conclusion as a finding with type `conclusion`.
"""

    expected_output = """\
A structured investigation summary containing:

1. **Evidence gathered**: For each testable prediction, a summary of
   supporting and contradicting evidence found.
2. **Prediction outcomes**: For each prediction, whether it is supported,
   refuted, or inconclusive, with confidence assessment.
3. **Overall hypothesis assessment**: Whether the hypothesis is supported,
   partially supported, or refuted.
4. **Recorded findings**: Confirmation that all significant findings were
   recorded in the knowledge base with confidence scores.
5. **Limitations and caveats**: Honest assessment of evidence gaps or
   methodological limitations.
"""
    return description, expected_output


def write_report(
    task_id: int,
    task_title: str,
    hypothesis: str,
) -> tuple[str, str]:
    """Return (description, expected_output) for research report writing."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
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
Synthesize all findings from your investigation into a formal, structured
research report. The report must be clear enough for the Research Reviewer
to evaluate your methodology, evidence, and conclusions.

## Step-by-Step Process

### Step 1: Review All Findings
Use **ReadFindingsTool** to review all findings you recorded during the
literature review and investigation. Organize them logically by topic
or prediction, not chronologically.

Use **SearchKnowledgeTool** to check for related findings from other
tasks that should be referenced.

### Step 2: Write the Report
Use **WriteReportTool** to create the report with the following structure:

**Executive Summary** (2-3 paragraphs)
- The research question that was investigated.
- The hypothesis and key findings.
- The main conclusions and their confidence levels.
- Key recommendations.

**Methodology**
- Research design: How the investigation was structured.
- Search strategy: Queries used, databases consulted, time period covered.
- Source evaluation criteria: How sources were assessed for credibility.
- Analysis approach: How evidence was evaluated and synthesized.

**Findings and Analysis**
For each major finding or cluster of findings:
- What was found (the evidence).
- The source(s) and their credibility.
- The confidence score and justification.
- Analysis: what the finding means in context.

Organize findings logically — group related findings together, present
them in order of importance or by prediction.

**Discussion**
- How the findings relate to the hypothesis.
- Contradictions and how they were resolved (or not).
- Limitations of the research (scope, sources, methodology).
- Alternative interpretations of the evidence.
- Comparison with prior work (reference existing knowledge base findings).

**Conclusions**
- Direct answers to the research question.
- Clearly distinguish between well-supported conclusions and speculative
  interpretations.
- Overall confidence assessment.

**Recommendations**
- Actionable next steps based on the findings.
- Suggested areas for further research.
- Practical implications for the project.

**References**
- All sources cited, with URLs where available.
- Organize by type (papers, documentation, articles, etc.) if there are
  many references.

### Step 3: Update the Wiki
Use **WriteWikiTool** to update wiki articles with key insights from your
research. Focus on information that other team members may need:
- State-of-the-art summaries.
- Key definitions or concepts.
- Important reference lists.
- Methodology notes.

### Step 4: Submit for Review
Use **AddCommentTool** to post a summary of your report on the task.
Use **UpdateTaskStatusTool** to set the status to `review_ready`.

If you produced any code, notebooks, or scripts during this research,
commit them to a branch and push to Forgejo:
1. **GitBranchTool** — create branch `research-{task_id}-artifacts` from
   main (`git fetch origin main && git checkout -b research-{task_id}-artifacts origin/main`).
2. **GitCommitTool** — stage and commit the artifacts
   (`git add -A && git commit -m "Add research artifacts for task {task_id}"`).
3. **GitPushTool** — push the branch to origin on the Forgejo server
   (`git push -u origin research-{task_id}-artifacts`).
4. **CreatePRTool** — open a PR with base="main" via
   `POST $FORGEJO_API_URL/repos/{{owner}}/{{repo}}/pulls`.

## Quality Checklist
Before submitting, verify:
- [ ] Every claim in the report is traceable to a recorded finding.
- [ ] Confidence scores are consistent and justified.
- [ ] Contradictory evidence is acknowledged and discussed.
- [ ] Methodology is documented clearly enough to reproduce.
- [ ] Executive summary accurately reflects the full report.
- [ ] References are complete with URLs.
"""

    expected_output = """\
A confirmation of report completion containing:

1. **Report title**: The title of the report created via WriteReportTool.
2. **Report structure**: Confirmation that all required sections are present
   (executive summary, methodology, findings, discussion, conclusions,
   recommendations, references).
3. **Findings referenced**: Number of recorded findings cited in the report.
4. **Wiki updates**: Confirmation of which wiki articles were created or
   updated.
5. **Status**: Confirmation that the task was moved to `review_ready`.
"""
    return description, expected_output


def revise_research(task_id: int, reviewer_feedback: str = "") -> tuple[str, str]:
    """Return (description, expected_output) for research revision after rejection."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
        phase="revision",
        summary=(
            f"Research for task {task_id} was rejected in peer review. "
            "You must address all reviewer feedback."
        ),
    )

    description = f"""\
Your research for task {task_id} has been rejected in peer review.

{state_block}

## Your Goal
Address ALL issues identified by the Research Reviewer. Every concern about
methodology, evidence, confidence scores, or conclusions must be resolved
before resubmission.

## Step-by-Step Process

### Step 0: Read the Reviewer Feedback
The reviewer has rejected your research. Their exact feedback is:

---
{reviewer_feedback}
---

Read every point carefully before proceeding. Do NOT skip this step.
Identify each concern and write a mental checklist of what must change.

### Step 1: Review Current State of Your Research
Use **ReadFindingsTool** to review all your current findings.
Use **ReadReportTool** to re-read your current report.
Identify which specific sections and findings correspond to each concern
in the reviewer's feedback.

### Step 1.5: Classify the Rejection Type
Based on the feedback above, determine the PRIMARY reason for rejection:

**Type A — Insufficient or Missing Sources**
Indicators: "not enough sources", "single source", "no evidence for",
"needs more references", "unverified", "blog post only".
→ Your priority is to find additional credible sources. Proceed to Step 2,
  then go directly to Step 3 (Additional Research) before updating findings.

**Type B — Incorrect or Unsupported Conclusions**
Indicators: "conclusion does not follow", "logical leap", "confidence too high",
"contradicts", "not supported by evidence", "cherry-picking".
→ Your priority is to re-analyze existing findings and adjust conclusions.
  Proceed to Step 2, then go directly to Step 4 (Update Findings) to adjust
  confidence scores and rewrite conclusions before adding new sources.

**Type C — Both (Mixed)**
→ Address sources first (Step 3), then conclusions (Step 4).

### Step 2: Map Feedback to Report Sections
For each concern in the reviewer's feedback, identify:
- **What** the issue is (methodology gap, insufficient evidence, confidence
  too high, missing analysis, etc.).
- **Where** in the report it manifests (which section, which finding).
- **How** to fix it (add sources, adjust scores, rewrite conclusions, etc.).

### Step 3: Conduct Additional Research (if needed)
If the rejection is Type A or Type C:
- Use **WebSearchTool** and **ReadPaperTool** to find additional sources.
- Search specifically for evidence addressing the reviewer's concerns.
- Look for contradictory evidence if the reviewer flagged confirmation bias.

Use **CodeSearchTool** if the reviewer pointed to data or references you
missed in the project.

### Step 4: Update Findings
Use **RecordFindingTool** to record new findings from additional research.

For existing findings that need revision:
- Adjust confidence scores if the reviewer identified they were too high
  or too low.
- Add additional supporting or contradicting evidence.
- Clarify sources or methodology.

### Step 5: Rewrite the Report
Use **WriteReportTool** to create an updated report that addresses all
reviewer concerns:
- Strengthen methodology documentation if flagged.
- Add missing analysis or discussion.
- Adjust conclusions if evidence warrants it.
- Ensure all new findings are incorporated.

### Step 6: Self-Review Against Feedback
Go through the reviewer's feedback from Step 0 point by point:
- [ ] Each concern listed by the reviewer has been addressed.
- [ ] For Type A rejections: at least 2 additional credible sources were found
      for each flagged finding.
- [ ] For Type B rejections: confidence scores were adjusted and conclusions
      were rewritten to match the evidence.
- [ ] The revised report explicitly mentions what changed in response to review.
- [ ] No new unsupported claims were introduced during revision.

### Step 7: Submit for Re-Review
Use **AddCommentTool** to post a summary of revisions on the task,
explicitly mapping each reviewer concern to the change made.
Use **UpdateTaskStatusTool** to set the status to `review_ready`.
"""

    expected_output = """\
A summary of revisions containing:

1. **Reviewer feedback addressed**: For EACH point in the reviewer's feedback,
   state exactly what was changed (new sources found, confidence score adjusted,
   conclusion rewritten, etc.).
2. **Rejection type**: Whether this was Type A (sources), Type B (conclusions),
   or Type C (both), and how that shaped the revision strategy.
3. **Additional research** (Type A): New sources consulted and findings recorded.
4. **Confidence adjustments** (Type B): Findings whose scores were changed and why.
5. **Report updates**: Summary of report sections revised.
6. **Status**: Confirmation that the task was moved to `review_ready`.
"""
    return description, expected_output


def update_knowledge_base(task_id: int) -> tuple[str, str]:
    """Return (description, expected_output) for knowledge base update after validation."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
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
Use **ReadFindingsTool** to read all findings from this task. Verify that:
- All findings have appropriate confidence scores.
- Finding titles and content are clear and useful for future reference.
- No important findings were missed.

### Step 2: Update Wiki Articles
Use **ReadWikiTool** to check existing wiki articles related to this task.
Use **WriteWikiTool** to:
- Update existing articles with validated insights.
- Create new articles for key topics that are not yet documented.
- Add cross-references between related articles.

Focus on information that will be useful to other team members:
- State-of-the-art summaries.
- Key definitions, metrics, or benchmarks.
- Methodology notes and best practices.
- Important reference lists.

### Step 3: Save Research Patterns to Memory
Use **KnowledgeManagerTool** (action=`save`) to persist valuable patterns for future sessions:
- Effective search strategies for this topic area.
- Key sources and their credibility assessments.
- Methodological lessons learned.
- Common pitfalls or challenges encountered.

### Step 4: Finalize Task
Use **UpdateTaskStatusTool** to move the task to `done`.
Use **AddCommentTool** to post a final summary of the research
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
) -> tuple[str, str]:
    """Return (description, expected_output) for pushing research artifacts to Forgejo."""

    state_block = build_state_context(
        project_id=0,
        project_name="",
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
50 MB — use **ExecuteCommandTool** to check file sizes with `du -sh <file>`
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
   PR number from CreatePRTool.
5. **PR body**: Confirmation that the body includes artifact descriptions,
   reproduction steps, and links to research findings.
"""
    return description, expected_output
