# Prompt Design Principles

Guidelines for writing robust, unambiguous agent prompts in PABADA.

## Core Philosophy

Every prompt must be **self-contained enough that a competent agent can execute
it without guessing**. If the agent has to fill in a gap with assumptions, the
prompt has a hole. The goal is zero dead spots — every scenario the agent might
encounter should have a clear instruction for how to handle it.

---

## System Prompts (backstory)

System prompts define **who the agent is** — identity, capabilities, rules,
and team awareness. They are static per invocation.

### Structure

1. **Identity**: Name, role, expertise, personality traits that affect behavior.
   Be specific — "senior requirements analyst with 15 years of experience" not
   "a helpful assistant."

2. **Team Roster**: Every agent must know its teammates — their names, roles,
   and what they do. Injected dynamically from the live DB roster via
   `build_team_section()`.

3. **Communication Protocol**: Who can talk to whom, via what tool, and when.

4. **Objective**: One clear outcome statement. What does success look like?

5. **Tools**: List every available tool with **when to use it** and **when NOT
   to use it**. Don't just name tools — specify the conditions for use.
   Bad: "ReadWikiTool: Read the wiki."
   Good: "ReadWikiTool: Read project wiki. Use ONLY when you suspect there is
   relevant documented information. Do not consult by default."

6. **Workflow**: Numbered steps the agent follows. Each step should be
   actionable and specific enough that you could verify whether the agent
   did it.

7. **Anti-Patterns**: Explicit list of things the agent must NOT do. These
   prevent the most common failure modes. Be specific about why.
   Bad: "Don't do bad things."
   Good: "Do NOT create epics — that is the Team Lead's responsibility."

8. **Output**: What the agent produces. Format, structure, who consumes it.

### What NOT to put in system prompts

- Project-specific state (current phase, what happened before) — that goes
  in the task prompt.
- Information that changes between invocations.
- Hardcoded teammate names — use dynamic injection.

---

## Task Prompts (description + expected_output)

Task prompts define **what to do right now** — the specific mission, current
context, and step-by-step process. They change per invocation.

### Structure

1. **State Context**: Timestamped project state (phase, what has happened,
   revision round info). Use `build_state_context()` from `team.py`.

2. **Objective**: Clear statement of what the agent must accomplish in this
   specific task invocation.

3. **Input Data**: Whatever the agent needs to work with (requirements,
   plan, report, ideas). Clearly labeled and separated from instructions.

4. **Step-by-Step Process**: Numbered steps with sub-instructions.
   Each step should answer:
   - What to do
   - How to do it (specific actions, tools to use)
   - What to look for (criteria, edge cases)
   - What to do with the result

5. **Communication Guidelines**: How to talk to the user or other agents
   for this specific task. Includes:
   - Language adaptation rules
   - Presentation structure (what to say first, second, etc.)
   - How to handle different response scenarios

6. **Expected Output**: Detailed description of the deliverable format.
   Use section headers, bullet points, and examples. The agent should be
   able to produce the output by following this template exactly.

### Key Principles

#### Process over outcome

Don't just say "gather requirements." Spell out the exact process:
1. Understand the vision
2. Assess the user's expertise level
3. Analyze for ambiguities, gaps, hidden requirements, contradictions
4. Research external references if needed
5. Ask questions (one at a time)
6. Verify completeness against a checklist
7. Validate with the user
8. Produce the deliverable

#### Every scenario gets an instruction

If the agent might encounter a fork, tell it what to do in each branch:
- "If the user approves → return APPROVED"
- "If the user approves some but rejects others → return APPROVED with notes"
- "If the user rejects → return REJECTED with specific feedback"
- "If the user wants modifications → return REJECTED with description of changes"

Don't leave scenarios unhandled. The agent will guess, and it will guess wrong.

#### Specific over vague

Bad: "Present the results clearly."
Good: "Present an executive summary (3-5 bullet points) of key outcomes.
Mention what was NOT completed. Offer the full report for detailed review."

Bad: "List pros and cons."
Good: "For each idea: trade-offs must be concrete — 'adds a new database
dependency' not 'requires more development time.'"

#### One question at a time

When the agent communicates with the user, it must ask ONE question per
message. Multiple questions overwhelm users and produce incomplete answers.
This rule must be explicitly stated in every task that involves user
interaction.

#### Adaptive communication

Every user-facing task must include instructions to:
1. Detect the user's expertise level from their language
2. Match technical vocabulary for expert users
3. Simplify and offer concrete options for non-technical users
4. Identify technical gaps yourself (as assumptions) when the user can't

#### Explicit tool invocation

Name the exact tool to use for each action:
Bad: "Save the report."
Good: "Use WriteReportTool to persist the report."

Bad: "Ask the user."
Good: "Use AskUserTool to present the summary and ask for confirmation."

#### Checklists for completeness

When the agent must produce a comprehensive deliverable (like a PRD), include
a checklist of categories to cover:
```
- [ ] Problem statement and context
- [ ] Target users and their needs
- [ ] Functional requirements with acceptance criteria
- [ ] Non-functional requirements
- [ ] Out of scope (non-goals)
- [ ] Assumptions documented
- [ ] Prioritization (P0/P1/P2)
```

The agent checks each box before considering the task complete.

#### Honesty over salesmanship

Agents must present information honestly:
- Do not oversell ideas or inflate results
- Do not defend deliverables — the job is to capture what the user wants
- Flag deviations from original goals upfront
- Mention what was NOT achieved alongside what was

---

## Dynamic Context Injection

### Team Roster (system prompt)

Built by `build_team_section()` in `backend/prompts/team.py`.
Receives live data from the roster DB table so it always reflects the
actual team composition — names, roles, and current status.

Agents are assigned random English names from a pool at creation time.
Names persist across re-creations of the same agent (same `agent_id`).

### Project State (task prompt)

Built by `build_state_context()` in `backend/prompts/team.py`.
Includes:
- Project name and ID
- Current phase
- UTC timestamp
- Free-text context summary
- Optional extra key-value pairs

This goes in the task description, not the system prompt, because it
changes between invocations and is easier to debug when visible in
task logs.

---

## Common Failure Modes to Guard Against

| Failure | Prevention |
|---------|-----------|
| Agent consults wiki/files "just in case" | Explicit "ONLY when" conditions on tool usage |
| Agent asks too many questions at once | "ONE question at a time" rule in every user-facing task |
| Agent makes technical decisions | Anti-pattern: "Do NOT make technical decisions — that is the Team Lead's role" |
| Agent assumes unstated requirements | "Never assume — always verify" identity trait + hidden requirements checklist |
| Agent uses wrong communication level | Adaptive communication section with concrete examples |
| Agent produces vague deliverables | Detailed expected_output with section structure and content guidelines |
| Agent defends its output when challenged | "Do not defend the PRD — your job is to capture what the user wants" |
| Agent ignores contradictions | Explicit instruction to flag and resolve contradictions |
| Agent creates work items it shouldn't | Anti-pattern listing which role owns what |
| Agent loses context across invocations | State context block with timestamp in every task prompt |
