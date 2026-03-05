"""Project Lead task prompts used in flows."""

from backend.prompts.team import build_conversation_context, build_state_context


def gather_requirements(
    project_name: str,
    project_id: int,
    existing_reqs: str,
    feedback_context: str = "",
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for requirements gathering."""

    is_revision = bool(feedback_context)
    phase_summary = (
        "Revision round — the user rejected the previous plan and provided "
        "feedback. Adjust requirements accordingly."
        if is_revision
        else "Initial requirements gathering from user input."
    )
    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="planning",
        summary=phase_summary,
    )

    ctx_block = conversation_context or ""

    description = f"""\
You are gathering and refining requirements for this project.

{state_block}

## Current Requirements
{existing_reqs}
{feedback_context}

## Your Goal
Produce a complete, unambiguous, and prioritized PRD (Product Requirements
Document) that Jordan Chen (Team Lead) can use directly to plan the project.

## Step-by-Step Process

### Step 1: Understand the Vision
Read the existing requirements and extract:
- What problem does this project solve?
- Who does it solve it for?
- What is the expected outcome if the project succeeds?

### Step 2: Assess the User
Before asking questions, analyze the language of the existing requirements:
- If they use specific technical terminology fluently → technical user.
  You can ask direct, technical questions.
- If it is vague or uses outcome language without detail → non-technical user.
  Offer concrete options instead of open-ended questions.
  Identify the missing technical points yourself and document them as
  reasonable assumptions.

### Step 3: Deep Analysis
Review the existing requirements looking for:

**Ambiguities** — requirements that can be interpreted in more than one way.
Example: "it should be fast" → what does fast mean? Response in <200ms?
Initial load in <3s?

**Missing Information** — data needed for execution that was not given.
Example: a web project without mentioning whether it needs authentication.

**Hidden Requirements** — logical consequences of what was requested that the
user did not explicitly mention. If they ask for an app with login, that
implies: session management, password recovery, personal data security, etc.
If they ask for a public API, that implies: rate limiting, versioning,
documentation.

**Contradictions** — requirements that are mutually exclusive.
Example: using a technology known to be slow while demanding high performance.
Flag these contradictions to the user and ask them to choose.

### Step 4: Research if Needed
- If the user mentions or references something external (a news article, a
  link, a technology, a standard), use web_search or web_fetch to get
  context.
- If there are reference files attached to the project, review them with
  read_reference_files.
- If the project wiki has documentation relevant to the context, consult it
  with read_wiki.
Do NOT consult these sources "just in case." Only when there is evidence that
they contain information you need.

### Step 5: Ask the User ONLY Blocking Questions

{ctx_block}

**IMPORTANT:** If the User Q&A History above already contains answers to your
questions, DO NOT ask them again. Use the existing answers directly. Only ask
NEW questions about information that is genuinely missing.

Use ask_user ONLY for questions that are **blocking** — questions whose
answer is essential to start the project. If you can make a reasonable
assumption instead, do so and document it in the PRD.

**The bar for asking a question:**
A question is blocking ONLY if getting it wrong would lead to building the
wrong thing entirely. Examples:
- The project description says "build an app" but you cannot tell if it is
  a web app, mobile app, or CLI tool → blocking.
- The project mentions "users" but you cannot tell if it needs authentication
  → NOT blocking (assume yes and document it).
- The project says "integrate with X" but you do not know which X API
  version → NOT blocking (assume latest, document it).

**Rules:**
- **ONE question at a time.** Never ask multiple questions in one message.
- **Prefer assumptions over questions.** Every question delays the project.
  When in doubt, make a reasonable assumption, document it in the PRD, and
  move on. The user can correct assumptions during plan approval.
- If you offer options, give 2-3 alternatives with a brief explanation.
- For non-technical users: identify technical decisions yourself and document
  them as assumptions. Only ask about business or functionality decisions.
- For technical users: only ask about technical preferences if the choice
  has major architectural consequences.
- **Do NOT ask for confirmation of your understanding.** That is handled in
  a separate step (plan approval). Your job is to produce the PRD — not to
  get the user to validate it.

### Step 6: Verify Completeness
Before producing the final PRD, check that you have an answer for each of
these categories. You do NOT need to ask the user all of them — most you can
deduce or document as assumptions:

- [ ] Problem statement and context
- [ ] Target users and their needs
- [ ] Functional requirements with acceptance criteria
- [ ] Non-functional requirements (performance, security, scalability)
- [ ] Integrations and external dependencies
- [ ] Explicit technical constraints from the user (if any)
- [ ] What is out of scope (non-goals)
- [ ] Documented assumptions
- [ ] Prioritization (P0: must-have / P1: important / P2: nice-to-have)
- [ ] Measurable success criteria

**Do NOT call ask_user during this step.** If information is missing,
write it as an assumption or an open question in the PRD. The user will
review and correct the plan during the approval phase.

### Step 7: Produce the PRD as Task Output
Generate the final PRD following the expected output structure below.
**Do NOT present the PRD to the user here** — that is handled by a
separate step in the flow (plan approval). Your only job here is to
return the complete PRD document as the output of this task.
**Do NOT call ask_user for confirmation.** Just produce the PRD.
"""

    expected_output = """\
A structured PRD in markdown with the following sections:

## 1. Executive Summary
3-5 line paragraph: what will be done, for whom, and why.

## 2. Problem
Current situation, pain points, who is affected.

## 3. Target Users
Primary and secondary personas/roles. Who is NOT a user (anti-personas)
if relevant.

## 4. Goals and Success Metrics
3-5 measurable metrics that define success. Definition of "done" / MVP.

## 5. Functional Requirements
Grouped by functional area. Each requirement includes:
- Clear description
- Acceptance criteria (verifiable conditions)
- Priority: P0 (must-have) / P1 (important) / P2 (nice-to-have)

## 6. Non-Functional Requirements
Performance, security, scalability, accessibility, availability.
Only those relevant to the project.

## 7. Technical Constraints
Only if the user specified explicit constraints (technologies, platforms,
mandatory integrations). If none, omit this section.

## 8. Out of Scope (Non-Goals)
What this project will NOT address, with brief rationale.

## 9. Assumptions and Dependencies
Assumptions being made. Known external dependencies.

## 10. Open Questions
Unresolved items that may need additional input later.
"""
    return description, expected_output


def present_plan_for_approval(
    plan: str,
    project_name: str = "",
    project_id: int = 0,
    requirements: str = "",
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for presenting the Team Lead's plan to the user for approval."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="plan_approval",
        summary="The Team Lead has created a project plan based on the PRD. Present it to the user for approval.",
    )
    reqs_summary = requirements[:2000] if requirements else "No requirements available."
    ctx_block = conversation_context or ""

    description = f"""\
Present the following project plan — created by the Team Lead based on the
PRD — to the user for approval.

{state_block}

## Project Requirements (Summary)
{reqs_summary}

{ctx_block}

## Team Lead's Plan to Present
{plan}

## How to Present the Plan

### Presentation Structure
1. **Start with a brief executive summary** (3-5 key points) that captures
   the essence of the plan. Do not dump the entire plan at once — first
   give the big picture.

2. **Highlight the epics, milestones, and key tasks** proposed by the Team
   Lead. These define the execution roadmap and the user must explicitly
   validate them.

3. **Mention what was left out of scope** according to the plan so the user
   confirms they agree with the exclusions.

4. **Flag open questions** if any — items that may need resolution during
   execution.

5. **Present the complete plan** for detailed review.

### How to Ask for Approval
After presenting, ask the user clearly:
- "Does this plan correctly reflect how you want the project to be executed?"
- "Is there anything you want to change, add, or remove?"
- "If you agree, confirm with APPROVED. If you want adjustments, tell me
  what to change."

### How to Handle Feedback
- If the user gives partial feedback (wants to change something specific),
  acknowledge the feedback and confirm you understand what they want changed.
- If the user rejects, try to understand the root cause. Is it a scope
  problem? Prioritization? Misunderstood requirements?
- Do not defend the plan — your job is to capture what the user wants, not
  to convince them of anything.

### Communication
- Adapt language to the user's level (same as in the requirements phase).
- Be concise but complete. Do not repeat information unnecessarily.
- If the plan is extensive, offer to present it by sections.

## Expected Response
**⚠️ CRITICAL FORMAT RULE**: Return ONLY one of these two options as your
**complete response**. Your response MUST start with `APPROVED` or
`REJECTED` as the very first word — no preamble, no explanation before
the keyword:
- `APPROVED` — if the user approves the plan
- `REJECTED: <detailed feedback>` — if the user wants changes, including
  a clear and specific description of what should change
"""

    expected_output = "Exactly one of: the single word `APPROVED`, or `REJECTED` followed by a colon and the feedback. The very first word of your response MUST be `APPROVED` or `REJECTED`. No other text before the keyword."
    return description, expected_output


def write_final_report(
    report: str,
    project_name: str = "",
    project_id: int = 0,
    requirements: str = "",
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for final report delivery."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="finalization",
        summary="The project is complete. Write the final report and deliver it to the user.",
    )
    reqs_summary = requirements[:2000] if requirements else "No requirements available."
    ctx_block = conversation_context or ""

    description = f"""\
The project is complete. Your task is to write the final report and deliver
it to the user.

{state_block}

## Project Requirements (Summary)
{reqs_summary}

{ctx_block}

## Raw Report Data
{report}

## Step-by-Step Process

### Step 1: Analyze the Raw Data
Review the raw report data above. It contains:
- Task summary (how many tasks completed, failed, pending)
- Epic overview (what was planned vs. what was delivered)
- Agent performance metrics

Identify:
- What was accomplished vs. what was originally planned
- Any tasks that were not completed and why (if apparent)
- Notable successes or challenges

### Step 2: Write the Report
Use the **write_report** to persist the final report. Structure it as
a polished, human-readable document — not a raw data dump. The report
should be understandable by someone who was not involved in the project.

### Step 3: Notify the User
Use **ask_user** to inform the user that the project is complete.

**How to structure the notification:**
1. Start with a clear statement: the project is complete.
2. Present an executive summary (3-5 bullet points) of the key outcomes:
   - What was built/researched/delivered
   - How many tasks were completed out of the total
   - Any notable results or metrics
3. Mention anything that was NOT completed or that deviated from the
   original PRD, with brief explanation.
4. Offer the full detailed report for review: "The complete report has
   been saved. Would you like me to walk you through the details?"

**Communication guidelines:**
- Adapt language to the user's level (consistent with how you communicated
  during requirements gathering).
- Be honest about what was and was not achieved. Do not inflate results.
- If there were significant issues or deviations, mention them upfront
  rather than burying them.
- Keep the notification concise — the detailed report is available
  separately.
"""

    expected_output = """\
Confirmation that:
1. The final report was written using write_report
2. The user was notified via ask_user with an executive summary
   of outcomes and an offer to review the full report
"""
    return description, expected_output


def present_brainstorm_ideas(
    ideas_text: str,
    project_name: str = "",
    project_id: int = 0,
    requirements: str = "",
    conversation_context: str = "",
) -> tuple[str, str]:
    """Return (description, expected_output) for presenting brainstorm ideas."""

    state_block = build_state_context(
        project_id=project_id,
        project_name=project_name,
        phase="brainstorming_presentation",
        summary="The team has completed a brainstorming session. Present the selected ideas to the user for approval.",
    )
    reqs_summary = requirements[:2000] if requirements else "No requirements available."
    ctx_block = conversation_context or ""

    description = f"""\
The team has completed a brainstorming session and selected the most
promising ideas. Your task is to present these ideas to the user for
approval before the team invests time implementing them.

{state_block}

## Project Requirements (Summary)
{reqs_summary}

{ctx_block}

## Selected Ideas
{ideas_text}

## Step-by-Step Process

### Step 1: Understand Each Idea
Before presenting to the user, make sure you understand each idea well
enough to explain it clearly. For each idea, identify:
- What it proposes (the "what")
- What problem it solves or what value it adds (the "why")
- Any obvious risks, costs, or trade-offs

### Step 2: Assess Relevance to the Original PRD
Check whether each idea:
- Directly supports the original project goals
- Extends the project in a useful direction
- Is potentially out of scope or contradicts existing requirements

Flag any ideas that seem to drift from the original objectives — the user
should be aware of this when deciding.

### Step 3: Present to the User
Use **ask_user** to present the ideas. Structure the presentation:

1. **Context first**: Briefly remind the user why brainstorming was needed
   (e.g., "The team explored new approaches to move the project forward").

2. **For each idea**, present:
   - **Title and one-line summary**: What it is, in plain language.
   - **Value**: What problem it solves or what improvement it brings.
   - **Trade-offs**: Any costs, risks, or complexity involved.
     Be specific — "requires more development time" is vague;
     "adds a new database dependency" is concrete.
   - **Alignment**: Whether it supports the original goals or extends scope.

3. **Your recommendation** (if appropriate):
   - If one idea clearly stands out as highest value / lowest risk,
     say so and briefly explain why.
   - If ideas are complementary (can be combined), mention it.
   - If any idea seems risky or out of scope, flag it honestly.
   - If you have no strong recommendation, say so — do not force one.

4. **Ask for a decision**: "Would you like to proceed with these ideas?
   You can approve all, approve some and reject others, or suggest
   modifications."

### Step 4: Handle the Response
- If the user approves all ideas → return "APPROVED"
- If the user approves some but not others → return "APPROVED" with a note
  about which ones (the flow will handle the filtering)
- If the user rejects → return "REJECTED: <specific feedback>" including
  what the user wants changed or why they rejected
- If the user wants modifications → return "REJECTED: <modifications>"
  with clear description of what to change

**Communication guidelines:**
- Adapt language to the user's level (consistent with previous interactions).
- Present ONE message with all ideas — do not ask about each one separately.
  The user should see the full picture to make an informed decision.
- Keep each idea description concise (3-5 lines max). The user can ask for
  more detail if needed.
- Do not oversell ideas. Present them honestly with both upsides and
  downsides.

## Expected Response
Return ONLY one of these:
- "APPROVED" — if the user approves proceeding with the ideas
- "REJECTED: <detailed feedback>" — if the user wants changes, including
  what specifically should change
"""

    expected_output = "Exactly one of: the single word APPROVED, or REJECTED followed by a colon and the feedback. No other text."
    return description, expected_output
