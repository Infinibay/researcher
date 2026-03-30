"""Resilient LLM client for the loop engine.

Wraps litellm.completion with:
- Retry logic with exponential backoff for transient errors
- Model capability adaptation (/no_think, tool_choice downgrade, JSON mode)
- Transient vs permanent error classification
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Retry configuration
LLM_RETRIES = 5
LLM_RETRY_DELAY = 3.0  # Base delay; exponential backoff: 3, 6, 12, 24, 48s

# Transient LLM errors that should be retried
TRANSIENT_ERRORS = (
    "connection error",
    "connectionerror",
    "disconnected",
    "rate limit",
    "timeout",
    "503",
    "502",
    "429",
    "overloaded",
    "internal server error",
    "connection reset",
    "broken pipe",
    "eof occurred",
)

# Permanent errors that look transient but aren't (substrings that
# override a TRANSIENT_ERRORS match when present)
PERMANENT_ERRORS = (
    "does not support tools",
    "does not support function",
    "tool_choice is not supported",
    "tools is not supported",
    "not found",        # Ollama: {"error":"tool 'X' not found"}
)

# Patterns indicating the LLM produced a malformed tool call
MALFORMED_TOOL_PATTERNS = (
    "error parsing tool call",
    "invalid character",
    "looking for beginning of value",
    "unexpected end of json",
    "unterminated string",
    "invalid json",
)


def is_transient(exc: Exception) -> bool:
    """Check if an LLM error is transient (retryable)."""
    msg = str(exc).lower()
    if any(p in msg for p in PERMANENT_ERRORS):
        return False
    return any(p in msg for p in TRANSIENT_ERRORS)


def is_malformed_tool_call(exc: Exception) -> bool:
    """Check if an LLM error is due to a malformed tool call response."""
    msg = str(exc).lower()
    return any(p in msg for p in MALFORMED_TOOL_PATTERNS)


def call_llm(
    params: dict[str, Any],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] = "auto",
) -> Any:
    """Call litellm.completion with retry for transient errors.

    Adapts request parameters based on probed model capabilities:
    - Downgrades tool_choice="required" -> "auto" if unsupported
    - Injects /no_think prefix for models with thinking sections
    - Enables JSON mode when no tools present
    - Skips response_format=json_object when tools are present (grammar conflict)
    """
    import litellm
    from backend.config.model_capabilities import get_model_capabilities

    caps = get_model_capabilities()

    kwargs: dict[str, Any] = {**params, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        # Downgrade tool_choice if model doesn't support "required"
        if tool_choice == "required" and not caps.supports_tool_choice_required:
            kwargs["tool_choice"] = "auto"
        else:
            kwargs["tool_choice"] = tool_choice

        # Inject /no_think prefix for models with thinking sections
        # (Qwen 3.x emits <think> tags that break JSON tool call parsing)
        if caps.has_thinking_sections and messages:
            last_user = None
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    last_user = i
                    break
            if last_user is not None:
                content = messages[last_user].get("content", "")
                if not content.startswith("/no_think"):
                    messages = list(messages)  # Don't mutate caller's list
                    messages[last_user] = {
                        **messages[last_user],
                        "content": f"/no_think\n{content}",
                    }
                    kwargs["messages"] = messages

    # Force JSON output when no tools present -- prevents models from
    # mixing natural language with JSON in manual TC mode.
    # Do NOT set when tools are present -- JSON grammar conflicts with
    # function calling grammar in some backends.
    if caps.supports_json_mode and not tools:
        kwargs["response_format"] = {"type": "json_object"}

    last_exc: Exception | None = None
    for attempt in range(1, LLM_RETRIES + 1):
        try:
            return litellm.completion(**kwargs)
        except Exception as exc:
            last_exc = exc
            if not is_transient(exc) or attempt == LLM_RETRIES:
                raise
            delay = LLM_RETRY_DELAY * (2 ** (attempt - 1))
            logger.warning(
                "Transient LLM error (attempt %d/%d), retrying in %.1fs: %s",
                attempt, LLM_RETRIES, delay, str(exc)[:200],
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]
