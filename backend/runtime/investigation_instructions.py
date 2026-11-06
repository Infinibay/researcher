"""Exploratory investigation behavior uses explicit scope, grouped evidence and correction opportunities without a host-owned LLM loop."""

INVESTIGATION_INSTRUCTIONS = """# Exploratory investigation
Define a bounded question and scope from the actual request and criteria. Gather,
organize and summarize information; do not force hypothesis testing, PICO, ACH or
GRADE onto an exploratory task. Read Ken for code. Capture selected sources before
citing them, record exact excerpts and group observations by area. No evidence for
an area means unresolved, not a negative result or an invented finding.

Use researcher_investigation_summary to persist the actual question, scope, areas
with finding IDs, conclusion, limits and proposed next steps. Unresolved areas may
have empty finding lists; the complete report still needs real cited findings.
Explain insufficient evidence rather than launching automatic rescue/review loops.
The host renders this structured summary without a second synthesis model. Select
actual final typed reports with researcher_result_propose; scratch output is not
implicitly delivered. Neither delivery nor a summary grants scientific certainty,
accepts a task, publishes work or authorizes another agent.
"""
