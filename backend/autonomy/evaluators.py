"""Role-specific evaluators that score pending agent_events.

Each evaluator scores a list of pending events and picks the best one
based on role-specific priorities.  Replaces the old ``policies.py``
(which returned Decisions from DB queries) with a unified scoring model
that works over persistent events.

Import safety: uses ``backend.autonomy.db`` to avoid circular imports.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from backend.autonomy.db import execute_with_retry

logger = logging.getLogger(__name__)


@dataclass
class EvalContext:
    """Lightweight context for evaluator scoring decisions."""

    project_status: str = "unknown"
    total_tasks: int = 0
    done_tasks: int = 0
    stuck_tasks: int = 0
    in_progress_tasks: int = 0

    @staticmethod
    def build(project_id: int) -> EvalContext:
        """Build an EvalContext from DB queries."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any]:
            project = conn.execute(
                "SELECT status FROM projects WHERE id = ?", (project_id,),
            ).fetchone()

            counts = conn.execute(
                """SELECT
                     COUNT(*) as total,
                     SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                     SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                     SUM(CASE WHEN status IN ('in_progress', 'rejected')
                          AND created_at <= datetime('now', '-30 minutes')
                          THEN 1 ELSE 0 END) as stuck
                   FROM tasks WHERE project_id = ?""",
                (project_id,),
            ).fetchone()

            return {
                "project_status": project["status"] if project else "unknown",
                "total": counts["total"] or 0,
                "done": counts["done"] or 0,
                "in_progress": counts["in_progress"] or 0,
                "stuck": counts["stuck"] or 0,
            }

        data = execute_with_retry(_query)
        return EvalContext(
            project_status=data["project_status"],
            total_tasks=data["total"],
            done_tasks=data["done"],
            stuck_tasks=data["stuck"],
            in_progress_tasks=data["in_progress"],
        )


class ActionEvaluator(ABC):
    """Base class for role-specific event evaluators."""

    @abstractmethod
    def score(self, event: dict[str, Any], context: EvalContext) -> float:
        """Score 0.0-1.0 how much this event maximizes project progress."""
        ...

    def pick_best(
        self, events: list[dict[str, Any]], context: EvalContext,
    ) -> dict[str, Any] | None:
        """Score all events and return the highest-scored one.

        Returns None if no events score above 0.
        """
        if not events:
            return None

        best_event = None
        best_score = 0.0

        for event in events:
            s = self.score(event, context)
            if s > best_score:
                best_score = s
                best_event = event

        return best_event


class DeveloperEvaluator(ActionEvaluator):
    """Priorities: resume interrupted work > CI failure fix > unblocks others > new task."""

    def score(self, event: dict[str, Any], context: EvalContext) -> float:
        event_type = event.get("event_type", "")
        payload = _parse_payload(event)

        if event_type == "user_message_received":
            return 0.95

        if event_type == "message_received":
            return 0.85

        if event_type == "task_resume":
            return 0.9

        if event_type == "task_rejected":
            return 0.88

        if event_type == "task_available":
            # Base score for new tasks
            base = 0.6
            # Higher priority tasks score higher
            task_priority = payload.get("task_priority", 3)
            priority_bonus = (5 - task_priority) * 0.05  # 0-0.20
            return min(base + priority_bonus, 0.85)

        # Unknown event types get a low default
        return 0.1


class TeamLeadEvaluator(ActionEvaluator):
    """Priorities: user messages > stuck task intervention > progress eval > new planning."""

    def score(self, event: dict[str, Any], context: EvalContext) -> float:
        event_type = event.get("event_type", "")

        if event_type == "user_message_received":
            return 0.95

        if event_type == "message_received":
            return 0.85

        if event_type == "stagnation_detected":
            return 0.88

        if event_type == "all_tasks_done":
            return 0.9

        if event_type == "waiting_for_research":
            return 0.5

        if event_type == "health_check":
            # Higher score if there are stuck tasks
            if context.stuck_tasks > 0:
                return 0.8
            return 0.3

        if event_type == "evaluate_progress":
            return 0.4

        if event_type == "task_available":
            return 0.3  # Team lead doesn't usually take tasks

        return 0.1


class ResearcherEvaluator(ActionEvaluator):
    """Priorities: resume interrupted research > new research task > peer review."""

    def score(self, event: dict[str, Any], context: EvalContext) -> float:
        event_type = event.get("event_type", "")

        if event_type == "user_message_received":
            return 0.95

        if event_type == "message_received":
            return 0.85

        if event_type == "task_resume":
            return 0.9

        if event_type == "task_available":
            return 0.7

        return 0.1


class ReviewerEvaluator(ActionEvaluator):
    """Priorities: pending reviews (FIFO by wait time)."""

    def score(self, event: dict[str, Any], context: EvalContext) -> float:
        event_type = event.get("event_type", "")

        if event_type == "user_message_received":
            return 0.95

        if event_type == "message_received":
            return 0.85

        if event_type == "review_ready":
            return 0.9

        if event_type == "task_available":
            return 0.5

        return 0.1


def _parse_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Parse the payload_json field from an event dict."""
    raw = event.get("payload_json", "{}")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


# Map role names to evaluator classes
_ROLE_EVALUATORS: dict[str, type[ActionEvaluator]] = {
    "developer": DeveloperEvaluator,
    "researcher": ResearcherEvaluator,
    "team_lead": TeamLeadEvaluator,
    "project_lead": TeamLeadEvaluator,  # Same priorities as team lead
    "code_reviewer": ReviewerEvaluator,
    "research_reviewer": ReviewerEvaluator,
}


def get_evaluator_for_role(role: str) -> ActionEvaluator:
    """Return an evaluator instance for the given role."""
    cls = _ROLE_EVALUATORS.get(role, DeveloperEvaluator)
    return cls()
