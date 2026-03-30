"""ReAct trace detection and cleanup utilities.

CrewAI's agent executor sometimes returns raw ReAct thinking traces
instead of a proper final answer.  This happens when the ReAct loop
is interrupted (max_iter reached, tool-not-found, Qwen3 stopword
conflict, etc.).  These helpers detect and clean such traces.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_REACT_ACTION_RE = re.compile(
    r'(?m)^Action\s*:\s*.+\nAction\s+Input\s*:\s*\{',
)
_REACT_THOUGHT_PREFIX_RE = re.compile(
    r'^Thought\s*:\s*',
)


def _is_incomplete_react_trace(text: str) -> bool:
    """Return True if *text* looks like a raw ReAct trace, not a decision.

    Indicators:
    - Starts with ``Thought:`` AND contains an ``Action: ... Action Input:``
      block (the agent was mid-loop, not giving a final answer).
    - Does NOT contain any of the expected decision prefixes.
    """
    if not text:
        return False
    upper = text.upper()
    # If it starts with a valid prefix, it's a real decision.
    if any(upper.startswith(p) for p in (
        "NEW_TICKETS", "BRAINSTORM_NEEDED", "PROJECT_COMPLETE",
    )):
        return False
    return bool(
        _REACT_THOUGHT_PREFIX_RE.match(text) and _REACT_ACTION_RE.search(text)
    )


def _strip_react_trace(text: str) -> str:
    """Try to extract a usable decision from a potentially messy LLM response.

    Some models wrap the answer in ``Thought: ...`` preamble or append
    ``Action:`` blocks after the decision.  This function:
    1. Looks for a known decision prefix anywhere in the text.
    2. If found, returns from that prefix onward (trimming leading noise).
    3. Otherwise returns the text unchanged.
    """
    if not text:
        return text
    upper = text.upper()
    for prefix in ("NEW_TICKETS", "BRAINSTORM_NEEDED", "PROJECT_COMPLETE"):
        idx = upper.find(prefix)
        if idx != -1:
            extracted = text[idx:].strip()
            if extracted != text:
                logger.info(
                    "Stripped %d chars of preamble before '%s' prefix",
                    idx, prefix,
                )
            return extracted
    return text
