"""Historical error classifiers and retired direct-model entry; no provider calls, automatic retries or fallback billing are available."""

from __future__ import annotations

import logging
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
    """Reject direct old-provider generation before client import, adaptation or retries; the native runtime owns the admitted turn."""
    from backend.runtime.lifecycle import NativeOwnerRequired

    raise NativeOwnerRequired("Legacy model calls are retired; use an explicitly admitted native runtime turn")
