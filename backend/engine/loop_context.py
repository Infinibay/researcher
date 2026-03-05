"""Prompt construction for the plan-execute-summarize loop engine."""

from __future__ import annotations

import json
from typing import Any

from backend.engine.loop_models import LoopState

LOOP_PROTOCOL = """\
## Loop Execution Protocol

You operate in a plan-execute-summarize loop. Follow these rules:

### Planning Philosophy
- **Never plan what you can't concretely anticipate.** Only create steps for actions you know are needed based on what you've seen so far.
- Start with 2-3 concrete steps. After each step, add the next 1-2 based on what you discovered.
- A plan that grows from 2 initial steps to 12+ total is normal and expected.
- BAD: Planning 8 steps upfront with vague descriptions like "Implement the feature"
- GOOD: Planning 2-3 specific steps, executing them, then adding more based on findings

### Step Granularity
- Each step = 1-4 tool calls. If a step needs more, split it.
- Steps must name specific files, functions, or commands.
- BAD: "Set up authentication" / "Write the code" / "Test everything"
- GOOD: "Read src/auth.py to find verify_token()" / "Add JWT check to handle_request() in api.py"
- Start with reading/exploration steps before modification steps.

### Step Execution
- You are given one step at a time from your plan.
- Use tools to complete each step (aim for 1-4 tool calls per step).
- When finished with a step, call the `step_complete` tool.

### Completing Steps — the `step_complete` tool

After finishing each step, you MUST call the `step_complete` tool with these parameters:

- **summary** (required): 1-2 sentence summary of what you did and key facts discovered.
- **status** (required): One of `continue`, `done`, or `blocked`.
- **next_steps** (optional): Array of operations to update your plan. Each operation is an object with:
  - `op`: `"add"`, `"modify"`, or `"remove"`
  - `index`: Step number (integer)
  - `description`: Step description (required for add/modify, ignored for remove)
- **final_answer** (optional): When status=done, provide the final result here.

Example step_complete call:
```json
{
  "summary": "Found auth module at src/auth.py with verify_token() on line 42",
  "status": "continue",
  "next_steps": [
    {"op": "add", "index": 5, "description": "Run pytest tests/test_auth.py to verify the fix"},
    {"op": "add", "index": 6, "description": "Update error messages in handle_request()"},
    {"op": "modify", "index": 4, "description": "Also check rollback behavior, not just forward migration"},
    {"op": "remove", "index": 3}
  ]
}
```

### Rules for next_steps operations
- Only operate on pending steps — you cannot modify done or skipped steps.
- When status is `continue`, you MUST have at least one pending step. Add steps if needed.
- After completing your last planned step, either add more steps or set status: done.
- NEVER create speculative steps for things you haven't investigated yet.

### Status Values
- **continue**: More work to do. Ensure there are pending steps in the plan.
- **done**: Task is fully complete. Provide your final answer in the `final_answer` parameter.
- **blocked**: Cannot proceed. Explain why in the summary.

### Summary Guidelines
- Capture key facts: file paths, function names, decisions made, values found.
- Be concise (~50 tokens). Raw tool output is discarded — only your summary survives.

### Important
- Do NOT repeat previous action summaries — they are already provided to you.
- Focus only on the current step.
- If a step turns out to be unnecessary, remove it (op: remove) and explain in summary.
- You MUST call `step_complete` after every step. Do NOT just output text without calling it.
"""


def build_system_prompt(backstory: str) -> str:
    """Combine agent backstory with the loop protocol instructions."""
    return f"{backstory}\n\n{LOOP_PROTOCOL}"


def build_iteration_prompt(
    description: str,
    expected_output: str,
    state: LoopState,
) -> str:
    """Build the user prompt for one iteration of the loop.

    Assembles <task>, <plan>, <previous-actions>, <current-action>,
    <next-actions>, and <expected-output> XML blocks.
    """
    parts: list[str] = []

    # Task description
    parts.append(f"<task>\n{description}\n</task>")

    # Plan (if we have one)
    if state.plan.steps:
        parts.append(f"<plan>\n{state.plan.render()}\n</plan>")
    else:
        parts.append(
            "<plan>\nNo plan yet. Create 2-3 concrete steps by calling step_complete "
            "with next_steps operations. You will add more steps as you discover what's needed.\n</plan>"
        )

    # Previous action summaries
    if state.history:
        summaries = []
        for record in state.history:
            summaries.append(f"- [{record.step_index}] {record.summary}")
        parts.append(f"<previous-actions>\n{chr(10).join(summaries)}\n</previous-actions>")

    # Current action
    active = state.plan.active_step
    if active:
        parts.append(
            f"<current-action>\nStep {active.index}: {active.description}\n</current-action>"
        )
    elif state.plan.steps:
        # All planned steps are done — prompt to continue or finish
        parts.append(
            "<current-action>\n"
            "All planned steps are complete. Review what was accomplished against the task requirements.\n"
            "Either add new steps via step_complete(next_steps=[...]) if more work is needed,\n"
            "or call step_complete(status=\"done\", final_answer=\"...\") if the task is fully complete.\n"
            "</current-action>"
        )

    # Next actions (pending steps after current)
    if state.plan.steps:
        next_steps = [
            s for s in state.plan.steps
            if s.status == "pending" and (active is None or s.index > active.index)
        ]
        if next_steps:
            lines = [f"{s.index}. {s.description}" for s in next_steps]
            parts.append(f"<next-actions>\n{chr(10).join(lines)}\n</next-actions>")

    # Expected output
    if expected_output:
        parts.append(f"<expected-output>\n{expected_output}\n</expected-output>")

    return "\n\n".join(parts)


def build_tools_prompt_section(tool_schemas: list[dict[str, Any]]) -> str:
    """Render tool schemas as a text section for non-FC models.

    When the model doesn't support native function calling, tool descriptions
    are embedded directly in the system prompt. The model is instructed to
    respond with a JSON object containing a "tool_calls" array.
    """
    lines = [
        "## Available Tools",
        "",
        "You MUST respond with a JSON object containing a \"tool_calls\" array.",
        "Each tool call has \"name\" and \"arguments\" fields.",
        "",
        "When done with the current step, call \"step_complete\".",
        "",
        "Response format:",
        '```json',
        '{"tool_calls": [{"name": "tool_name", "arguments": {"param": "value"}}]}',
        '```',
        "",
        "You may call multiple tools in one response:",
        '```json',
        '{"tool_calls": [',
        '  {"name": "read_file", "arguments": {"file_path": "src/main.py"}},',
        '  {"name": "step_complete", "arguments": {"summary": "Read the file", "status": "continue"}}',
        ']}',
        '```',
        "",
        "---",
        "",
    ]

    for schema in tool_schemas:
        func = schema.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "")
        params = func.get("parameters", {})

        lines.append(f"### {name}")
        if desc:
            lines.append(desc)

        props = params.get("properties", {})
        required = set(params.get("required", []))
        if props:
            lines.append("Parameters:")
            for pname, pschema in props.items():
                ptype = pschema.get("type", "any")
                pdesc = pschema.get("description", "")
                req_marker = " (required)" if pname in required else ""
                lines.append(f"  - `{pname}` ({ptype}{req_marker}): {pdesc}")

        lines.append("")

    return "\n".join(lines)
