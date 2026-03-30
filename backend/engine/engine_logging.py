"""Logging and event emission for the loop engine.

Centralizes stdout logging, ANSI formatting, tool detail extraction,
and EventBus event emission so loop_engine.py stays focused on control flow.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from backend.engine.loop_models import LoopPlan


# ── UI visibility -- emit events to EventBus -> WebSocket ─────────────────────


def emit_loop_event(
    event_type: str,
    project_id: int,
    agent_id: str,
    data: dict[str, Any],
) -> None:
    """Emit a loop progress event to the UI via EventBus -> WebSocket."""
    try:
        from backend.flows.event_listeners import FlowEvent, event_bus

        event_bus.emit(FlowEvent(
            event_type=event_type,
            project_id=project_id,
            entity_type="agent",
            entity_id=None,
            data=data,
        ))
    except Exception:
        pass  # Never let event emission break the engine


# ── Pretty stdout logging ────────────────────────────────────────────────────

DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

STATUS_ICON = {
    "continue": f"{CYAN}\u2192{RESET}",
    "done": f"{GREEN}\u2713{RESET}",
    "blocked": f"{RED}\u2717{RESET}",
    "explore": f"{MAGENTA}\u2192{RESET}",
}


def log(msg: str) -> None:
    """Print to stderr with flush (visible immediately in logs)."""
    print(msg, file=sys.stderr, flush=True)


# ── Tool detail extraction for UI visibility ─────────────────────────────────

# Maps tool name -> list of arg keys to show in UI (in priority order).
TOOL_DETAIL_KEYS: dict[str, list[str]] = {
    "read_file": ["file_path", "path"],
    "write_file": ["file_path", "path"],
    "edit_file": ["file_path", "path"],
    "create_file": ["file_path", "path"],
    "list_directory": ["path", "directory"],
    "code_search": ["query", "pattern", "search_query"],
    "glob": ["pattern", "glob_pattern"],
    "execute_command": ["command", "cmd"],
    "git_branch": ["branch_name", "name"],
    "git_commit": ["message"],
    "git_push": ["branch"],
    "git_diff": ["branch", "file_path"],
    "git_status": [],
    "create_pr": ["title"],
    "merge_pr": ["pr_number"],
    "web_search": ["query", "search_query"],
    "web_fetch": ["url"],
    "send_message": ["to_agent", "to_role"],
    "reply_to_user": [],
    "create_task": ["title"],
    "update_task_status": ["task_id", "status"],
    "get_task": ["task_id"],
    "read_tasks": [],
    "search_knowledge": ["query"],
    "record_finding": ["topic", "title"],
    "replace_lines": ["file_path", "path"],
    "partial_read": ["path", "file_path"],
    "multi_edit_file": ["path", "file_path"],
    "apply_patch": [],
}


def extract_tool_detail(tool_name: str, arguments: str) -> str:
    """Extract a short human-readable detail from tool call arguments."""
    keys = TOOL_DETAIL_KEYS.get(tool_name)
    if keys is None:
        keys = ["path", "file_path", "query", "title", "name"]
    if not keys:
        return ""

    try:
        args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else {}
    except (json.JSONDecodeError, TypeError):
        return ""

    if not isinstance(args, dict):
        return ""

    for key in keys:
        val = args.get(key)
        if val is not None:
            s = str(val).strip()
            if len(s) > 80:
                s = s[:77] + "..."
            return s
    return ""


def extract_tool_error(result: str) -> str:
    """Extract error message from a tool result, if any."""
    if not result:
        return ""
    stripped = result.strip()
    if not stripped.startswith("{"):
        return ""
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict) and "error" in parsed:
            err = str(parsed["error"])
            if "Unknown tool:" in err:
                tool_name = err.split("Unknown tool:", 1)[1].strip()
                return f"hallucinated tool '{tool_name}'"
            if len(err) > 120:
                err = err[:117] + "..."
            return err
    except (json.JSONDecodeError, TypeError):
        pass
    return ""


def log_start(agent_id: str, agent_name: str, role: str, desc: str, tool_count: int) -> None:
    log(f"\n{BOLD}{'─' * 70}{RESET}")
    log(f"{BOLD}{CYAN}⚡ LoopEngine{RESET}  {BOLD}{agent_name}{RESET} {DIM}({role}){RESET}  {DIM}[{agent_id}]{RESET}")
    log(f"{DIM}   Task:{RESET} {desc[:120]}{'…' if len(desc) > 120 else ''}")
    log(f"{DIM}   Tools: {tool_count} available{RESET}")
    log(f"{BOLD}{'─' * 70}{RESET}")


def log_step_start(iteration: int, step_desc: str | None) -> None:
    label = step_desc or "planning"
    log(f"\n{BLUE}┌─ Step {iteration}{RESET} {label}")


def log_tool(agent_name: str, iteration: int, tool_name: str, call_num: int, total: int) -> None:
    log(f"{BLUE}│{RESET}  {MAGENTA}🔧 {tool_name}{RESET}  {DIM}[{agent_name} step {iteration} · call {call_num}, {total} total]{RESET}")


def log_step_done(iteration: int, status: str, summary: str, tool_calls: int, tokens: int) -> None:
    icon = STATUS_ICON.get(status, "?")
    log(f"{BLUE}└─{RESET} {icon} {BOLD}{status}{RESET}  {DIM}[{tool_calls} tools, {tokens} tokens]{RESET}")
    log(f"   {DIM}{summary[:150]}{RESET}")


def log_plan(plan: LoopPlan) -> None:
    if not plan.steps:
        return
    log(f"{DIM}   Plan:{RESET}")
    for s in plan.steps:
        if s.status == "done":
            icon, color = "✓", GREEN
        elif s.status == "active":
            icon, color = "▶", CYAN
        elif s.status == "skipped":
            icon, color = "⊘", DIM
        else:
            icon, color = "○", DIM
        log(f"   {color}{icon} {s.index}. {s.description[:80]}{RESET}")


def log_prompt(user_prompt: str, max_section: int = 300) -> None:
    """Log the XML-structured prompt sent to the LLM, truncating each section."""
    import re
    sections = re.findall(r"<(\w[\w-]*)>\n?(.*?)\n?</\1>", user_prompt, re.DOTALL)
    if not sections:
        log(f"{DIM}   Prompt: {user_prompt[:max_section]}{RESET}")
        return
    log(f"{DIM}   Prompt:{RESET}")
    for tag, content in sections:
        preview = content.strip().replace("\n", " ↵ ")
        if len(preview) > max_section:
            preview = preview[:max_section] + "…"
        log(f"   {DIM}<{tag}>{RESET} {preview}")


def log_finish(agent_name: str, status: str, iterations: int, total_tools: int, total_tokens: int) -> None:
    icon = STATUS_ICON.get(status, "?")
    log(f"\n{BOLD}{'─' * 70}{RESET}")
    log(
        f"{icon} {BOLD}{agent_name}{RESET} finished  "
        f"{DIM}status={status}  iterations={iterations}  "
        f"tools={total_tools}  tokens={total_tokens}{RESET}"
    )
    log(f"{BOLD}{'─' * 70}{RESET}\n")
