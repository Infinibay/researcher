"""Tool call parsing for the loop engine.

Handles parsing tool calls from LLM text responses when native function
calling is unavailable, plus step_complete argument parsing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.engine.loop_models import StepOperation, StepResult


class ManualToolCall:
    """Lightweight stand-in for native tool call objects in manual TC mode.

    Mirrors the attribute structure of litellm/OpenAI tool call objects
    so the rest of the pipeline (dispatch, logging) works unchanged.
    """

    __slots__ = ("id", "function")

    class _Function:
        __slots__ = ("name", "arguments")

        def __init__(self, name: str, arguments: str) -> None:
            self.name = name
            self.arguments = arguments

    def __init__(self, id: str, name: str, arguments: str) -> None:
        self.id = id
        self.function = self._Function(name, arguments)


def parse_text_tool_calls(content: str) -> list[dict[str, Any]] | None:
    """Parse tool calls from model text when native FC is unavailable.

    Supports multiple formats that models use to express tool calls:

    1. Our manual-mode JSON: ``{"tool_calls": [{"name": ..., "arguments": ...}]}``
    2. Qwen/GLM ``<tool_call>{"name": ..., "arguments": ...}</tool_call>``
    3. Qwen pipe-delimited ``<|tool_call|>...<|/tool_call|>``
    4. Mistral ``[TOOL_CALLS] [{"name": ..., "arguments": ...}]``
    5. Llama ``<|python_tag|>`` function calls
    6. ``<function_call>`` / ``<functioncall>`` wrappers
    7. Markdown code blocks with JSON
    8. Bare JSON objects

    Returns a list of dicts with "name" and "arguments" keys,
    or None if no valid tool calls found.
    """
    if not content or not content.strip():
        return None

    # Strip thinking sections (various model formats)
    cleaned = re.sub(
        r"<(?:thinking|think|\|thinking\|)>.*?</(?:thinking|think|\|thinking\|)>",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 1. Native model tool-call tokens
    # Qwen / GLM: <tool_call>{...}</tool_call>
    tc_tag_matches = re.findall(
        r"<tool_call>\s*(.*?)\s*</tool_call>",
        cleaned, re.DOTALL,
    )
    if tc_tag_matches:
        calls = _extract_calls_from_fragments(tc_tag_matches)
        if calls:
            return calls

    # Qwen pipe-delimited: <|tool_call|>{...}<|/tool_call|>
    tc_pipe_matches = re.findall(
        r"<\|tool_call\|>\s*(.*?)\s*<\|/tool_call\|>",
        cleaned, re.DOTALL,
    )
    if tc_pipe_matches:
        calls = _extract_calls_from_fragments(tc_pipe_matches)
        if calls:
            return calls

    # Mistral: [TOOL_CALLS] [{...}, ...]
    mistral_match = re.search(
        r"\[TOOL_CALLS\]\s*(\[.*?\])",
        cleaned, re.DOTALL,
    )
    if mistral_match:
        calls = _extract_calls_from_array(mistral_match.group(1))
        if calls:
            return calls

    # Llama: <|python_tag|> followed by JSON
    python_tag_match = re.search(
        r"<\|python_tag\|>\s*(.*)",
        cleaned, re.DOTALL,
    )
    if python_tag_match:
        calls = _extract_calls_from_fragments([python_tag_match.group(1)])
        if calls:
            return calls

    # Generic: <function_call>{...}</function_call> or <functioncall>{...}</functioncall>
    fc_matches = re.findall(
        r"<function_?call>\s*(.*?)\s*</function_?call>",
        cleaned, re.DOTALL | re.IGNORECASE,
    )
    if fc_matches:
        calls = _extract_calls_from_fragments(fc_matches)
        if calls:
            return calls

    # 2. Our manual-mode JSON: {"tool_calls": [...]}
    json_candidates: list[str] = []

    code_blocks = re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
    json_candidates.extend(code_blocks)
    json_candidates.append(cleaned.strip())

    for candidate in json_candidates:
        candidate = candidate.strip()
        if not candidate:
            continue

        brace_start = candidate.find("{")
        if brace_start == -1:
            continue

        depth = 0
        for i, ch in enumerate(candidate[brace_start:], start=brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_str = candidate[brace_start : i + 1]
                    try:
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict):
                            if "tool_calls" in parsed:
                                calls = _normalize_call_list(parsed["tool_calls"])
                                if calls:
                                    return calls
                            if "name" in parsed:
                                calls = _normalize_call_list([parsed])
                                if calls:
                                    return calls
                    except (json.JSONDecodeError, TypeError):
                        pass
                    break

    return None


def _extract_calls_from_fragments(fragments: list[str]) -> list[dict[str, Any]] | None:
    """Parse JSON tool call objects from text fragments."""
    calls: list[dict[str, Any]] = []
    for frag in fragments:
        frag = frag.strip()
        if not frag:
            continue
        try:
            parsed = json.loads(frag)
        except (json.JSONDecodeError, TypeError):
            brace = frag.find("{")
            if brace == -1:
                continue
            depth = 0
            for i, ch in enumerate(frag[brace:], start=brace):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            parsed = json.loads(frag[brace : i + 1])
                        except (json.JSONDecodeError, TypeError):
                            break
                        break
            else:
                continue

        if not isinstance(parsed, dict):
            continue

        call = _normalize_single_call(parsed)
        if call:
            calls.append(call)

    return calls if calls else None


def _extract_calls_from_array(text: str) -> list[dict[str, Any]] | None:
    """Parse a JSON array of tool call objects."""
    try:
        arr = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(arr, list):
        return None
    return _normalize_call_list(arr)


def _normalize_call_list(raw: list) -> list[dict[str, Any]] | None:
    """Normalize a list of raw tool call dicts into [{name, arguments}, ...]."""
    calls: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            call = _normalize_single_call(item)
            if call:
                calls.append(call)
    return calls if calls else None


def _normalize_single_call(obj: dict) -> dict[str, Any] | None:
    """Normalize a single tool call dict.

    Handles variants:
    - {"name": "x", "arguments": {...}}
    - {"function": {"name": "x", "arguments": {...}}}
    - {"function": "x", "arguments": {...}}  (Llama-style)
    - {"name": "x", "parameters": {...}}
    """
    name = obj.get("name")
    arguments = obj.get("arguments") or obj.get("parameters") or {}

    if not name and "function" in obj:
        func = obj["function"]
        if isinstance(func, dict):
            name = func.get("name")
            arguments = func.get("arguments") or func.get("parameters") or {}
        elif isinstance(func, str):
            name = func

    if not name or not isinstance(name, str):
        return None

    return {"name": name, "arguments": arguments}


def parse_step_complete_args(arguments: str | dict[str, Any]) -> StepResult:
    """Parse step_complete tool call arguments into a StepResult."""
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments or {}

    raw_next_steps = args.get("next_steps", [])
    next_steps: list[StepOperation] = []
    if isinstance(raw_next_steps, list):
        for item in raw_next_steps:
            if isinstance(item, dict) and "op" in item and "index" in item:
                try:
                    next_steps.append(StepOperation(
                        op=item["op"],
                        index=item["index"],
                        description=item.get("description", ""),
                    ))
                except Exception:
                    pass

    return StepResult(
        summary=args.get("summary", "Step completed (no summary provided)"),
        status=args.get("status", "continue"),
        next_steps=next_steps,
        final_answer=args.get("final_answer"),
    )
