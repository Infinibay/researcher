"""Parallel tool execution, file change tracking, and cache management.

Provides batching (reads parallel, writes sequential), file change
tracking with unified diffs, and opened files cache synchronization.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from backend.engine.engine_logging import emit_loop_event
from backend.engine.file_change_tracker import FileChangeTracker
from backend.engine.loop_models import LoopState
from backend.engine.loop_tools import execute_tool_call

logger = logging.getLogger(__name__)

# Tools that modify files and should trigger diff tracking
FILE_CHANGE_TOOLS: frozenset[str] = frozenset({
    "edit_file", "write_file", "create_file",
    "replace_lines", "add_content_before_line", "add_content_after_line",
    "multi_edit_file", "apply_patch",
    "edit_symbol", "add_symbol", "remove_symbol",
    "rename_symbol", "move_symbol",
})

# Tools with side effects -- act as barriers in parallel execution.
# Reads before a write batch are parallelized; writes execute sequentially.
WRITE_TOOLS: frozenset[str] = FILE_CHANGE_TOOLS | frozenset({
    "git_commit", "git_branch", "git_push",
    "execute_command",
    "record_finding", "write_wiki", "write_report",
    "send_message", "reply_to_user",
    "create_task", "update_task_status",
    "create_epic", "create_milestone",
})

# Max file size to track (skip very large files)
MAX_TRACK_FILE_SIZE = 1_000_000  # 1MB


def batch_tool_calls(calls: list) -> list[list]:
    """Group tool calls into batches for parallel/sequential execution.

    Consecutive read-only tools are grouped into a single parallel batch.
    Each write tool gets its own single-item batch (sequential barrier).
    """
    if not calls:
        return []

    batches: list[list] = []
    current_reads: list = []

    for tc in calls:
        name = tc.function.name
        if name in WRITE_TOOLS:
            # Flush accumulated reads as a parallel batch
            if current_reads:
                batches.append(current_reads)
                current_reads = []
            # Write tool gets its own batch (sequential)
            batches.append([tc])
        else:
            current_reads.append(tc)

    # Flush remaining reads
    if current_reads:
        batches.append(current_reads)

    return batches


def execute_tool_calls_parallel(
    batch: list,
    tool_dispatch: dict[str, Any],
) -> list[tuple[Any, str]]:
    """Execute a batch of tool calls, parallelizing if possible.

    Returns list of (tool_call, result_string) tuples in original order.
    """
    if len(batch) <= 1:
        results = []
        for tc in batch:
            result = execute_tool_call(
                tool_dispatch,
                tc.function.name,
                tc.function.arguments,
            )
            results.append((tc, result))
        return results

    # Parallel execution for read-only batches
    indexed_results: list[tuple[int, Any, str]] = [None] * len(batch)  # type: ignore

    def _run_one(idx: int, tc: Any) -> tuple[int, Any, str]:
        result = execute_tool_call(
            tool_dispatch,
            tc.function.name,
            tc.function.arguments,
        )
        return (idx, tc, result)

    max_workers = min(len(batch), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_run_one, i, tc)
            for i, tc in enumerate(batch)
        ]
        for future in futures:
            idx, tc, result = future.result()
            indexed_results[idx] = (idx, tc, result)

    return [(tc, result) for _, tc, result in indexed_results]


def update_opened_files_cache(
    state: LoopState,
    tool_name: str,
    arguments: str | dict[str, Any],
    result: str,
) -> None:
    """Synchronize the opened files cache after a tool call.

    - read_file: cache returned content
    - write_file / create_file: cache content from arguments (pinned)
    - edit_file / replace_lines: re-read and cache (pinned)
    - list_directory / glob / code_search: cache search results
    """
    path = _extract_path_from_args(tool_name, arguments)

    if tool_name in ("read_file", "partial_read"):
        if path and result and not result.startswith('{"error'):
            state.cache_file(path, result)

    elif tool_name in ("write_file", "create_file"):
        # Cache the written content (pinned -- agent wrote it)
        content = _extract_content_from_args(arguments)
        if path and content:
            state.refresh_file(path, content)

    elif tool_name in ("edit_file", "replace_lines", "add_content_before_line",
                        "add_content_after_line", "multi_edit_file"):
        # Re-read file after edit and cache (pinned)
        if path:
            content = _safe_read_file(path)
            if content is not None:
                state.refresh_file(path, _number_lines(content))

    elif tool_name in ("edit_symbol", "add_symbol", "remove_symbol"):
        # Extract path from result JSON
        result_path = _extract_path_from_result(result)
        if result_path:
            content = _safe_read_file(result_path)
            if content is not None:
                state.refresh_file(result_path, _number_lines(content))

    elif tool_name == "rename_symbol":
        # May affect multiple files -- re-read from result
        result_path = _extract_path_from_result(result)
        if result_path:
            content = _safe_read_file(result_path)
            if content is not None:
                state.refresh_file(result_path, _number_lines(content))


def capture_pre_content(
    tool_name: str,
    arguments: str | dict[str, Any],
    tracker: FileChangeTracker,
) -> str | None:
    """Snapshot file content before a mutation tool runs.

    Returns the pre-content string, or None if not applicable.
    """
    if tool_name not in FILE_CHANGE_TOOLS:
        return None
    if not tracker.active:
        return None

    path = _extract_path_from_args(tool_name, arguments)
    if not path:
        return None

    try:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            return None  # New file -- no pre-content
        size = os.path.getsize(abs_path)
        if size > MAX_TRACK_FILE_SIZE:
            return None  # Too large to track
        with open(abs_path) as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def maybe_emit_file_change(
    tool_name: str,
    arguments: str | dict[str, Any],
    result: str,
    pre_content: str | None,
    tracker: FileChangeTracker,
    project_id: int,
    agent_id: str,
) -> None:
    """Record a file change and emit an event for the UI."""
    if tool_name not in FILE_CHANGE_TOOLS:
        return
    if not tracker.active:
        return

    path = _extract_path_from_args(tool_name, arguments)
    if not path:
        return

    # Read post-content
    try:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            return
        with open(abs_path) as f:
            post_content = f.read()
    except (OSError, UnicodeDecodeError):
        return

    # Record in tracker
    diff = tracker.record(path, pre_content, post_content)

    # Record reason
    reason = _extract_reason_from_args(arguments)
    if reason:
        tracker.record_reason(path, reason)

    # Emit event
    if diff:
        emit_loop_event("loop_file_changed", project_id, agent_id, {
            "agent_id": agent_id,
            "file_path": path,
            "action": tracker.get_action(path),
            "diff": diff[:2000],  # Truncate for WebSocket
            "change_count": tracker.get_change_count(path),
        })


def reindex_if_enabled(file_path: str) -> None:
    """Trigger incremental code intelligence reindex after file modification.

    Currently a no-op -- will be implemented when code_intel is ported.
    """
    try:
        from backend.config.settings import settings
        if not settings.CODE_INTEL_ENABLED or not settings.CODE_INTEL_AUTO_INDEX:
            return
        # Future: call reindex_file(project_id, file_path)
    except Exception:
        pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_path_from_args(tool_name: str, arguments: str | dict[str, Any]) -> str | None:
    """Extract file path from tool arguments."""
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        args = arguments or {}

    if not isinstance(args, dict):
        return None

    for key in ("path", "file_path", "filepath"):
        val = args.get(key)
        if val and isinstance(val, str):
            return val
    return None


def _extract_content_from_args(arguments: str | dict[str, Any]) -> str | None:
    """Extract content/code from tool arguments."""
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        args = arguments or {}

    if not isinstance(args, dict):
        return None

    for key in ("content", "code", "text"):
        val = args.get(key)
        if val and isinstance(val, str):
            return val
    return None


def _extract_path_from_result(result: str) -> str | None:
    """Extract file path from a JSON tool result."""
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            for key in ("path", "file_path", "filepath"):
                val = parsed.get(key)
                if val and isinstance(val, str):
                    return val
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _extract_reason_from_args(arguments: str | dict[str, Any]) -> str:
    """Extract reason/description from arguments."""
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except (json.JSONDecodeError, TypeError):
            return ""
    else:
        args = arguments or {}

    if not isinstance(args, dict):
        return ""

    for key in ("reason", "description"):
        val = args.get(key)
        if val and isinstance(val, str):
            return val
    return ""


def _safe_read_file(path: str) -> str | None:
    """Read a file safely, returning None on any error."""
    try:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            return None
        with open(abs_path) as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _number_lines(content: str) -> str:
    """Add line numbers to file content."""
    lines = content.splitlines()
    width = len(str(len(lines)))
    numbered = [f"{i + 1:>{width}}  {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered)
