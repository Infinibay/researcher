"""Tool schema conversion and execution for the loop engine.

Converts InfinibayBaseTool instances to OpenAI function-calling format
and dispatches tool calls by name.  Includes pseudo-tools (step_complete,
add_note, think) that the engine handles internally.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove Pydantic v2 artifacts that confuse LLM providers."""
    schema.pop("title", None)
    schema.pop("$defs", None)
    schema.pop("definitions", None)
    for prop in schema.get("properties", {}).values():
        if isinstance(prop, dict):
            prop.pop("title", None)
    return schema


def tool_to_openai_schema(tool: Any) -> dict[str, Any]:
    """Convert a InfinibayBaseTool to an OpenAI function-calling tool schema."""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    if hasattr(tool, "args_schema") and tool.args_schema is not None:
        try:
            parameters = tool.args_schema.model_json_schema()
        except Exception:
            try:
                parameters = tool.args_schema.schema()
            except Exception:
                pass
        parameters = _clean_schema(parameters)

    parameters.setdefault("type", "object")
    parameters.setdefault("properties", {})

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": (tool.description or "")[:1024],
            "parameters": parameters,
        },
    }


# ── Pseudo-tool schemas ──────────────────────────────────────────────────────

STEP_COMPLETE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "step_complete",
        "description": (
            "Signal that the current step is complete. "
            "You MUST call this after finishing each step. "
            "Include a structured summary: Read (files read), Changed (edits made), "
            "Remaining (what's left), Decisions (choices made)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "1-2 sentence summary of what you did and key facts discovered. "
                        "Format: Read: ... | Changed: ... | Remaining: ... | Decisions: ..."
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["continue", "done", "blocked", "explore"],
                    "description": (
                        "continue = more work to do, done = task complete, "
                        "blocked = cannot proceed, explore = need deeper investigation"
                    ),
                },
                "next_steps": {
                    "type": "array",
                    "description": "Operations to update the plan (add/modify/remove steps)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["add", "modify", "remove"],
                            },
                            "index": {"type": "integer"},
                            "description": {"type": "string"},
                        },
                        "required": ["op", "index"],
                    },
                },
                "final_answer": {
                    "type": "string",
                    "description": "When status=done, the final result to return",
                },
            },
            "required": ["summary", "status"],
        },
    },
}

ADD_NOTE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_note",
        "description": (
            "Save a persistent note to your scratchpad. Notes survive across all steps "
            "and are always visible in your context. Use for key facts, decisions, file paths, "
            "patterns discovered, or anything you'll need later. Max 20 notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "1-2 sentences capturing a key fact or decision",
                },
            },
            "required": ["note"],
        },
    },
}

THINK_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "think",
        "description": (
            "Use this tool to reason through a problem step by step before acting. "
            "This does NOT count as a tool call and does NOT advance the step. "
            "Use it when you need to analyze, compare options, or plan your approach."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Your reasoning or analysis",
                },
            },
            "required": ["thought"],
        },
    },
}


def build_tool_schemas(tools: list[Any]) -> list[dict[str, Any]]:
    """Convert a list of tools to OpenAI function-calling schemas.

    Always appends pseudo-tool schemas (step_complete, add_note, think).
    """
    schemas = [tool_to_openai_schema(t) for t in tools]
    schemas.append(STEP_COMPLETE_SCHEMA)
    schemas.append(ADD_NOTE_SCHEMA)
    schemas.append(THINK_SCHEMA)
    return schemas


def build_tool_dispatch(tools: list[Any]) -> dict[str, Any]:
    """Build a name->tool instance dispatch map."""
    return {t.name: t for t in tools}


# ── Tool aliases (backward compatibility) ────────────────────────────────────

_TOOL_ALIASES: dict[str, str] = {
    "edit_method": "edit_symbol",
    "add_method": "add_symbol",
    "remove_method": "remove_symbol",
    "write_file": "create_file",
    "find_definition": "search_symbols",
}

# Parameter name aliases (LLMs often use wrong names)
_PARAM_ALIASES: dict[str, str] = {
    "old_str": "old_string",
    "new_str": "new_string",
    "file_path": "path",
    "filepath": "path",
    "file": "path",
    "filename": "path",
    "directory": "path",
    "dir": "path",
    "query": "pattern",
    "search_query": "pattern",
}

# Metadata params that LLMs hallucinate -- strip silently
_METADATA_PARAMS: set[str] = {
    "description", "reason", "explanation", "language",
    "project_id", "agent_id", "task_id", "session_id",
}


def execute_tool_call(
    dispatch: dict[str, Any],
    name: str,
    arguments: str | dict[str, Any],
) -> str:
    """Execute a tool call and return the result as a string.

    Features:
    - Tool alias resolution (edit_method -> edit_symbol, etc.)
    - Parameter auto-correction (old_str -> old_string, etc.)
    - Metadata parameter stripping
    - Missing required parameter detection
    - Kwargs validation against _run() signature
    """
    # Resolve tool aliases
    resolved_name = _TOOL_ALIASES.get(name, name)
    tool = dispatch.get(resolved_name)
    if tool is None and resolved_name != name:
        # Alias target doesn't exist either -- try original
        tool = dispatch.get(name)
        resolved_name = name
    if tool is None:
        return json.dumps({"error": f"Unknown tool: {name}"})

    # Parse arguments
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            return json.dumps({"error": f"Invalid JSON arguments: {arguments[:200]}"})
    else:
        args = arguments or {}

    if not isinstance(args, dict):
        return json.dumps({"error": f"Expected dict arguments, got {type(args).__name__}"})

    # Strip metadata params
    for meta in _METADATA_PARAMS:
        args.pop(meta, None)

    # Apply parameter aliases
    sig = None
    try:
        sig = inspect.signature(tool._run)
        allowed = set(sig.parameters.keys())
    except (ValueError, TypeError):
        allowed = None

    if allowed:
        corrected_args: dict[str, Any] = {}
        for key, val in args.items():
            if key in allowed:
                corrected_args[key] = val
            elif key in _PARAM_ALIASES and _PARAM_ALIASES[key] in allowed:
                corrected_args[_PARAM_ALIASES[key]] = val
            else:
                corrected_args[key] = val
        args = corrected_args

    # Validate kwargs against _run() signature
    if sig is not None and allowed is not None:
        accepts_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        if not accepts_var_kw:
            extra = set(args.keys()) - allowed
            if extra:
                logger.warning("Tool %s: unexpected kwargs %s", resolved_name, extra)
                return json.dumps({
                    "error": (
                        f"Tool '{resolved_name}' does not accept parameter(s): "
                        f"{', '.join(sorted(extra))}. "
                        f"Valid parameters are: {', '.join(sorted(allowed))}. "
                        f"Re-call the tool with the correct parameter names."
                    ),
                })

        # Check for missing required params
        missing = []
        for pname, param in sig.parameters.items():
            if (
                param.default is inspect.Parameter.empty
                and param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                and pname not in args
            ):
                missing.append(pname)
        if missing:
            return json.dumps({
                "error": (
                    f"Tool '{resolved_name}' requires parameter(s): "
                    f"{', '.join(missing)}. "
                    f"Re-call the tool with all required parameters."
                ),
            })

    # Execute
    try:
        result = tool._run(**args)
        return str(result) if result is not None else ""
    except Exception as exc:
        logger.warning("Tool %s raised %s: %s", resolved_name, type(exc).__name__, exc)
        return json.dumps({"error": f"Tool '{resolved_name}' failed: {exc}"})
