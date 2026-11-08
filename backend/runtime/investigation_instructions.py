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

When exec/code mode is available, organize predictable acquisition and delivery
as coarse steps. Group independent known source reads, then await dependent reads
in the same cell only when returned IDs and schemas determine the next arguments.
Keep the evidence and unread tails needed for actual judgment visible; pause the
cell when a result requires a new interpretation. Do not recapture already-read
evidence merely to repeat the same inspection. Required captured citations and
complete requested coverage still apply.

After inspecting sufficient evidence, prepare the actual findings, typed summary
and final selection together. In one delivery exec, await each required
researcher_finding_record, use its returned finding_id in
researcher_investigation_summary, then use the returned artifact_id in
researcher_result_propose. Validate each successful receipt before the next
dependent write; never parallelize these dependent mutations or invent IDs.
If a reply fails or is uncertain, stop the chain and preserve its original
operation keys and receipts for reconciliation; do not replay it automatically.
Emit the selected report identity and actual delivery status without hiding
limitations. Reserve enough budget to finish the user-facing explanation after
delivery; a saved draft alone is not a completed native response. This scheduling
guidance changes neither authority nor budgets, citations or acceptance rules.
"""
