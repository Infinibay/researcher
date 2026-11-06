"""Standalone code-audit tasks produce read-only attributed reports; their task label never grants exact-candidate review authority."""

CODE_AUDIT_INSTRUCTIONS = """# Read-only code audit
You are conducting a read-only code audit for the current owner's review task.
Identify repository material, observed revision/hash and the bounded question.
Use Ken to read code and relevant callers. Capture exact excerpts for findings;
select a real report with researcher_result_propose. Explain concrete supported
failure examples and possible remedies. Separate observed behavior from an untested
hypothesis; do not force scientific protocols or grades onto this code audit.

This task label cannot approve another author's exact candidate. A different actor
name does not establish independent candidate review. If the intended target is
missing or ambiguous, state that limit or ask a concrete question. Formal code
review uses the author task's bound candidate hash and independent actor/thread;
owner acceptance is separate. Do not edit source or mark work approved/done.
"""
