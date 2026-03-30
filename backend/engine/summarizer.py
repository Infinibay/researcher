"""Smart Context Summarizer - Generates compact summaries from action history."""

import re
from collections import defaultdict

from .loop_models import ActionRecord, LoopState


MAX_SUMMARY_TOKENS = 200


class SmartContextSummarizer:
    """Generates condensed context summaries from agent action history.

    Analyzes action records to identify:
    - Modified files and their patterns
    - Error patterns and resolutions
    - Technical decisions made
    - Pending/unfinished work
    """

    def __init__(self, max_tokens: int = MAX_SUMMARY_TOKENS):
        self.max_tokens = max_tokens

    def generate_summary(self, state: LoopState) -> str:
        """Generate a compact summary of the current loop state."""
        if not state.history or not state.plan:
            return ""

        summaries = self._analyze_actions(state.history)
        decisions = self._extract_decisions(state.history)
        errors = self._extract_errors(state.history)
        pending = self._extract_pending(state.plan, state.history)

        return self._format_summary(
            summaries=summaries,
            decisions=decisions,
            errors=errors,
            pending=pending,
            max_tokens=self.max_tokens,
        )

    def _analyze_actions(self, history: list[ActionRecord]) -> dict:
        """Group actions by file and detect patterns."""
        files_modified: dict[str, list[str]] = defaultdict(list)
        file_sequences: list[list[str]] = []
        current_sequence: list[str] = []

        file_patterns = [
            r"(?:Read|wrote|Wrote|edit|Edit|edited|EDITED)\s+([\w/._-]+)",
            r"(?:Read|wrote|Wrote|edit|Edit|edited|EDITED)\s+`+([\w/._-]+)`+",
        ]

        for record in history:
            file_path = None
            for pattern in file_patterns:
                match = re.search(pattern, record.summary, re.IGNORECASE)
                if match:
                    file_path = match.group(1)
                    break

            if file_path:
                files_modified[file_path].append(record.summary)

                if current_sequence and current_sequence[-1] == file_path:
                    current_sequence.append(file_path)
                else:
                    if len(current_sequence) > 1:
                        file_sequences.append(current_sequence)
                    current_sequence = [file_path]

        if len(current_sequence) > 1:
            file_sequences.append(current_sequence)

        return {
            "files_modified": dict(files_modified),
            "frequently_edited": self._get_most_edited(files_modified, top=5),
            "consecutive_edits": file_sequences,
        }

    def _get_most_edited(self, files: dict, top: int = 5) -> list[tuple]:
        sorted_files = sorted(files.items(), key=lambda x: len(x[1]), reverse=True)
        return sorted_files[:top]

    def _extract_decisions(self, history: list[ActionRecord]) -> list[str]:
        decision_patterns = [
            r"(using|chose|decided to|switching to)\s+([\w_]+)",
            r"(replaced|changed|updated)\s+([\w_]+)\s+to\s+([\w_]+)",
            r"(added|removed)\s+(import|package|dependency)\s+([\w_]+)",
            r"(fixed|resolved|addressed)\s+(issue|bug|problem|error):?\s*([\w\s]+)",
        ]

        decisions: list[str] = []
        for record in history:
            for pattern in decision_patterns:
                matches = re.findall(pattern, record.summary, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        decision = " ".join(filter(None, match))
                    else:
                        decision = match
                    if decision and len(decision) < 100:
                        decisions.append(decision)

        return list(set(decisions))[-10:]

    def _extract_errors(self, history: list[ActionRecord]) -> list[str]:
        error_keywords = ["error", "failed", "exception", "traceback", "not found"]
        resolution_keywords = ["fixed", "resolved", "solved", "handled", "workaround"]

        errors: list[str] = []
        for i, record in enumerate(history):
            record_lower = record.summary.lower()

            has_error = any(kw in record_lower for kw in error_keywords)
            has_resolution = any(kw in record_lower for kw in resolution_keywords)

            if has_error and i > 0:
                prev_summary = history[i - 1].summary if i > 0 else ""
                if has_resolution or any(kw in prev_summary.lower() for kw in resolution_keywords):
                    error_summary = f"Resolved: {record.summary}"
                    if prev_summary:
                        error_summary += f" (after: {prev_summary[:50]})"
                    errors.append(error_summary)
            elif has_error:
                errors.append(f"Error detected: {record.summary}")

        return errors[-5:]

    def _extract_pending(self, plan, history: list[ActionRecord]) -> list[str]:
        pending_steps: list[str] = []
        for step in plan.steps:
            if step.status in ["pending", "active"]:
                pending_steps.append(step.description)
        return pending_steps[:3]

    def _format_summary(
        self,
        summaries: dict,
        decisions: list[str],
        errors: list[str],
        pending: list[str],
        max_tokens: int = MAX_SUMMARY_TOKENS,
    ) -> str:
        lines: list[str] = []
        token_count = 0

        if summaries.get("frequently_edited"):
            lines.append("MODIFIED FILES:")
            for file_path, count in summaries["frequently_edited"]:
                line = f"  - {file_path} ({count} edits)"
                if token_count + len(line) < max_tokens:
                    lines.append(line)
                    token_count += len(line)

        if decisions:
            lines.append("\nTECHNICAL DECISIONS:")
            for decision in decisions:
                line = f"  - {decision}"
                if token_count + len(line) < max_tokens:
                    lines.append(line)
                    token_count += len(line)

        if errors:
            lines.append("\nERROR PATTERNS:")
            for error in errors:
                line = f"  ! {error}"
                if token_count + len(line) < max_tokens:
                    lines.append(line)
                    token_count += len(line)

        if pending:
            lines.append("\nPENDING WORK:")
            for item in pending:
                line = f"  [ ] {item}"
                if token_count + len(line) < max_tokens:
                    lines.append(line)
                    token_count += len(line)

        return "\n".join(lines)[:max_tokens]
