"""Parsing helpers for PABADA flows — review results, plans, ideas."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

logger = logging.getLogger(__name__)


def parse_review_result(
    text: str,
    approve_keyword: str = "APPROVED",
    reject_keyword: str = "REJECTED",
) -> Literal["approved", "rejected"]:
    """Parse a review result requiring the keyword at the start of the string.

    Strips leading whitespace and checks whether the response starts with
    *reject_keyword* or *approve_keyword* (using ``^KEYWORD\\b``).
    REJECTED is checked first so it always wins.  Returns ``"rejected"``
    by default when neither keyword is found, which avoids false positives
    from phrases like "NOT APPROVED".
    """
    text_upper = text.strip().upper()

    if re.match(rf"^{reject_keyword}\b", text_upper):
        return "rejected"

    if re.match(rf"^{approve_keyword}\b", text_upper):
        return "approved"

    logger.warning(
        "parse_review_result: no keyword matched, defaulting to 'rejected'. "
        "Text: %.200s",
        text,
    )
    return "rejected"


def classify_approval_response(text: str) -> Literal["approved", "rejected"]:
    """Semantically classify a free-form agent response as approved or rejected.

    Uses a regex fast-path for unambiguous responses, then falls back to
    keyword heuristics.  Defaults to "rejected" when ambiguous.
    """
    text_upper = text.strip().upper()

    # Fast-path: response starts with the keyword
    if re.match(r"^APPROVED\b", text_upper):
        return "approved"
    if re.match(r"^REJECTED\b", text_upper):
        return "rejected"

    # Broader heuristic: check for rejection indicators first (they win)
    rejection_patterns = [
        r"\bREJECTED\b",
        r"\bNOT\s+APPROV",
        r"\bDISAPPROV",
        r"\bDENI(?:ED|ES)\b",
        r"\bDECLINE[DS]?\b",
        r"\bNEEDS?\s+CHANGES?\b",
        r"\bNEEDS?\s+MODIF",
        r"\bPLEASE\s+REVISE\b",
    ]
    for pattern in rejection_patterns:
        if re.search(pattern, text_upper):
            return "rejected"

    approval_patterns = [
        r"\bAPPROVED\b",
        r"\bAPPROVE\b",
        r"\bAPPROVAL\b",
        r"\bACCEPT(?:ED|S)?\b",
        r"\bLOOKS?\s+GOOD\b",
        r"\bLGTM\b",
        r"\bPROCEED\b",
        r"\bGO\s+AHEAD\b",
        r"\bGREEN\s+LIGHT\b",
        r"\bYES\b",
    ]
    for pattern in approval_patterns:
        if re.search(pattern, text_upper):
            return "approved"

    logger.warning(
        "classify_approval_response: no keyword matched, defaulting to 'rejected'. "
        "Text: %.200s",
        text,
    )
    return "rejected"


def _normalize_title(title: str) -> str:
    """Normalize a task title for fuzzy dedup comparison.

    Lowercases, strips common prefixes (Conduct, Perform, Implement, etc.),
    removes filler words, and collapses whitespace. Two titles that normalize
    to the same string are considered duplicates.
    """
    t = title.lower().strip()
    # Strip leading action verbs that don't change the semantic meaning
    t = re.sub(
        r'^(conduct|perform|implement|create|build|design|develop|write|'
        r'research|investigate|review|analyze|study|define|establish)\s+',
        '', t,
    )
    # Remove common filler phrases
    t = re.sub(r'\b(a|an|the|on|for|of|and|with|in|to)\b', '', t)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def parse_plan_tasks(plan: str) -> list[str]:
    """Extract ordered list of task titles from plan markdown.

    Tries multiple patterns in priority order to handle different LLM formats:

    1. ``**Title**: <text>`` — canonical format from create_plan() prompt
    2. ``Title: <text>`` — plain text variant (no bold)
    3. ``### Task N: <text>`` or ``### <text>`` under a Tasks section
    4. ``- **<text>**`` — bold list items under a Tasks section
    5. ``1. **Title** - description`` — numbered bold items
    6. ``CREATE_TASK: <text>`` — tool-call-like format some LLMs produce

    Returns titles in document order, deduplicated both by exact match and
    by fuzzy normalization (stripping common action verbs and filler words).
    """
    titles: list[str] = []
    seen_exact: set[str] = set()
    seen_normalized: set[str] = set()

    def _add_title(raw: str) -> bool:
        """Add a title if it's non-empty and not a duplicate. Returns True if added."""
        title = raw.strip().strip('`').strip('*')
        if not title or len(title) < 5 or title in seen_exact:
            return False
        norm = _normalize_title(title)
        if norm in seen_normalized:
            logger.debug(
                "parse_plan_tasks: skipping near-duplicate title '%s' "
                "(normalized: '%s')",
                title, norm,
            )
            return False
        titles.append(title)
        seen_exact.add(title)
        seen_normalized.add(norm)
        return True

    # ── Pattern 1: **Title**: <text>  (canonical) ─────────────────────────
    for m in re.finditer(r'\*\*Title\*\*:\s*(.+)', plan):
        _add_title(m.group(1))
    if titles:
        return titles

    # ── Pattern 2: Title: <text>  (plain, not inside other bold fields) ───
    for m in re.finditer(r'(?m)^[-*\s]*Title:\s*(.+)', plan):
        _add_title(m.group(1))
    if titles:
        return titles

    # ── Pattern 3: ### Task [N][:.] <text>  or  ### <text> under Tasks ────
    # First try explicit "### Task N" headers
    for m in re.finditer(r'(?m)^#{2,4}\s+Task\s*\d*[.:)]*\s*(.+)', plan):
        _add_title(m.group(1))
    if titles:
        return titles

    # ── Pattern 4: Bold list items under a "Tasks" section ────────────────
    # Find sections that look like task listings
    task_section = re.search(
        r'(?mi)^#{1,4}\s+Tasks?\b.*?\n(.*?)(?=^#{1,3}\s|\Z)',
        plan,
        re.DOTALL,
    )
    if task_section:
        section_text = task_section.group(1)
        # Bold list items: - **Task title here**
        for m in re.finditer(r'(?m)^[-*]\s+\*\*(.+?)\*\*', section_text):
            _add_title(m.group(1))
        if titles:
            return titles
        # Plain list items with enough substance (>10 chars, starts with verb)
        for m in re.finditer(r'(?m)^[-*]\s+([A-Z][^.\n]{10,})', section_text):
            _add_title(m.group(1).rstrip())
        if titles:
            return titles

    # ── Pattern 5: Numbered task items like "1. **Title** - description" ──
    for m in re.finditer(r'(?m)^\d+[.)]\s+\*\*(.+?)\*\*', plan):
        _add_title(m.group(1))
    if titles:
        return titles

    # ── Pattern 6: CREATE_TASK: <text> (tool-call-like format some LLMs use) ─
    for m in re.finditer(r'(?mi)^[-*\s]*CREATE_TASK:\s*(.+)', plan):
        _add_title(m.group(1))
    if titles:
        return titles

    return titles


def parse_created_ids(llm_output: str) -> dict[str, int]:
    """Parse epic/milestone/task IDs from LLM output.

    Tries three strategies in order:
    1. JSON block with ``"title"`` and ``"id"`` fields.
    2. Markdown table rows with ``| title | id |`` columns.
    3. Lines like ``- Title (ID: 5)`` or ``Title — ID 5``.

    Returns a ``{title: id}`` dict.
    """
    result: dict[str, int] = {}

    # Strategy 1: JSON block
    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', llm_output)
    if not json_match:
        json_match = re.search(r'(\{[^{}]*"(?:epics|milestones)"[^{}]*\{[\s\S]*?\})', llm_output)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            for key in ("epics", "milestones", "tasks"):
                for item in data.get(key, []):
                    title = item.get("title", "")
                    item_id = item.get("id")
                    if title and item_id is not None:
                        result[title] = int(item_id)
            if result:
                return result
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Strategy 2: individual JSON objects ``{"title": "...", "id": N}``
    for m in re.finditer(r'"title"\s*:\s*"([^"]+)"[^}]*"id"\s*:\s*(\d+)', llm_output):
        result[m.group(1)] = int(m.group(2))
    if not result:
        for m in re.finditer(r'"id"\s*:\s*(\d+)[^}]*"title"\s*:\s*"([^"]+)"', llm_output):
            result[m.group(2)] = int(m.group(1))

    # Strategy 3: ``- Title (ID: 5)`` or ``Title — ID 5``
    if not result:
        for m in re.finditer(r'[-*]\s*(.+?)\s*\(ID:\s*(\d+)\)', llm_output):
            result[m.group(1).strip()] = int(m.group(2))

    return result


def parse_epics_milestones_from_result(result: str) -> tuple[dict[str, int], dict[str, int]]:
    """Parse epics and milestones ID maps from a Crew result string."""
    json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', result)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            epics_map: dict[str, int] = {}
            milestones_map: dict[str, int] = {}
            for item in data.get("epics", []):
                title = item.get("title", "")
                item_id = item.get("id")
                if title and item_id is not None:
                    epics_map[title] = int(item_id)
            for item in data.get("milestones", []):
                title = item.get("title", "")
                item_id = item.get("id")
                if title and item_id is not None:
                    milestones_map[title] = int(item_id)
            return epics_map, milestones_map
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning(
                "parse_epics_milestones_from_result: could not parse JSON, "
                "falling back to flat ID map"
            )

    flat = parse_created_ids(result)
    return dict(flat), dict(flat)


def parse_created_task_id(llm_output: str) -> int | None:
    """Parse a single ``CREATED_TASK_ID: N`` from LLM output.

    Returns the integer task ID or None if not found.
    """
    m = re.search(r'CREATED_TASK_ID:\s*(\d+)', llm_output)
    if m:
        return int(m.group(1))
    return None


def parse_ideas(raw_text: str) -> list[dict[str, Any]]:
    """Parse structured ideas from agent output text.

    Pass 1: Structured format — splits on ``## Idea N`` headers and extracts
    **Title**, **Description**, **Impact**, and **Feasibility** fields via regex.

    Pass 2: Legacy fallback — line-by-line heuristic for older prompt formats
    (used by consolidate_ideas, decision_phase).
    """

    # ── Pass 1: structured ``## Idea N`` blocks ──────────────────────────
    blocks = re.split(r'(?m)^##\s+Idea\s+\d+', raw_text)
    structured_ideas: list[dict[str, Any]] = []
    for block in blocks:
        if not block.strip():
            continue
        title_m = re.search(r'\*\*Title:\*\*\s*(.+)', block)
        desc_m = re.search(r'\*\*Description:\*\*\s*(.+?)(?=\n\*\*Impact:\*\*|\Z)', block, re.S)
        impact_m = re.search(r'\*\*Impact:\*\*\s*(.+?)(?=\n\*\*Feasibility:\*\*|\Z)', block, re.S)
        feas_m = re.search(r'\*\*Feasibility:\*\*\s*(.+?)(?=\Z)', block, re.S)

        title = title_m.group(1).strip() if title_m else ""
        if title:
            structured_ideas.append({
                "title": title,
                "description": desc_m.group(1).strip() if desc_m else "",
                "impact": impact_m.group(1).strip() if impact_m else "",
                "feasibility": feas_m.group(1).strip() if feas_m else "",
            })

    if structured_ideas:
        return structured_ideas

    # ── Pass 1.5: field-grouped format with **Title**: markers ────────────
    # Handles output like:
    #   - **Title**: Idea Name
    #   - **Description**: What it does
    #   - **Pros**: Benefits
    #   - **Cons**: Risks
    #   ...
    # Each **Title** marker starts a new idea; subsequent fields belong to it.
    title_positions = [m.start() for m in re.finditer(r'\*\*Title\*\*:\s*', raw_text)]
    if title_positions:
        field_ideas: list[dict[str, Any]] = []
        for idx, pos in enumerate(title_positions):
            end = title_positions[idx + 1] if idx + 1 < len(title_positions) else len(raw_text)
            block = raw_text[pos:end]

            title_m = re.search(r'\*\*Title\*\*:\s*(.+?)(?:\n|$)', block)
            title = title_m.group(1).strip().rstrip(".") if title_m else ""
            if not title:
                continue

            idea: dict[str, Any] = {"title": title, "description": ""}
            # Extract known fields
            for field, key in [
                ("Description", "description"),
                ("Pros", "pros"),
                ("Cons", "cons"),
                ("Priority", "priority"),
                ("Viability", "viability"),
                ("Impact", "impact"),
                ("Effort", "effort"),
                ("Feasibility", "feasibility"),
                ("Complementary [Ii]deas", "complementary_ideas"),
                ("Contributing [Ii]deas", "contributing_ideas"),
            ]:
                fm = re.search(
                    rf'\*\*{field}\*\*:\s*(.+?)(?=\n\s*[-*]?\s*\*\*|\Z)',
                    block, re.S,
                )
                if fm:
                    idea[key] = fm.group(1).strip()
            field_ideas.append(idea)

        if field_ideas:
            return field_ideas

    # ── Pass 2: legacy line-by-line fallback ──────────────────────────────
    ideas: list[dict[str, Any]] = []
    current_idea: dict[str, Any] | None = None

    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            if current_idea:
                ideas.append(current_idea)
                current_idea = None
            continue

        # Try numbered format: "1. Title: description" or "- Title: description"
        matched = False
        for prefix_check in [".", ")", "-", "*"]:
            stripped = line.lstrip("0123456789")
            if stripped.startswith(prefix_check):
                text = stripped[len(prefix_check):].strip()
                # Save previous idea before starting a new one
                if current_idea:
                    ideas.append(current_idea)
                if ":" in text:
                    title, _, desc = text.partition(":")
                    current_idea = {
                        "title": title.strip(),
                        "description": desc.strip(),
                    }
                else:
                    current_idea = {"title": text, "description": ""}
                matched = True
                break

        if not matched:
            # Continuation of previous idea description
            if current_idea:
                if current_idea["description"]:
                    current_idea["description"] += " " + line
                else:
                    current_idea["description"] = line

    if current_idea:
        ideas.append(current_idea)

    return ideas


def format_ideas(
    ideas: list[dict[str, Any]],
    *,
    numbered: bool = True,
    include_attribution: bool = False,
) -> str:
    """Format a list of idea dicts into a text block.

    Args:
        ideas: List of idea dicts with 'title', 'description', optionally 'proposed_by'.
        numbered: Use ``"1. Title: Desc"`` (True) or ``"- Title: Desc"`` (False).
        include_attribution: Prefix with ``[role]`` from ``proposed_by`` field.
    """
    lines: list[str] = []
    for i, idea in enumerate(ideas):
        title = idea.get("title", "Untitled")
        desc = idea.get("description", "")
        prefix = f"{i + 1}." if numbered else "-"
        if include_attribution:
            role = idea.get("proposed_by", "?")
            lines.append(f"{prefix} [{role}] {title}: {desc}")
        else:
            lines.append(f"{prefix} {title}: {desc}")
    return "\n".join(lines)
