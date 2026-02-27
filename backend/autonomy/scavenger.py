"""Event Scavenger — self-healing for agent event starvation.

When an agent's loop has been idle for several consecutive polls, the
scavenger scans the ``tasks`` table looking for work that *should* have
generated ``agent_events`` rows but didn't (e.g. because a DB trigger,
event listener, or EventBus handler failed silently).

It creates the missing events so the next poll picks them up immediately.

Import safety: only imports from ``backend.autonomy.db`` and
``backend.autonomy.events`` (lazy).  Never touches ``backend.tools``.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.autonomy.db import execute_with_retry

logger = logging.getLogger(__name__)

_MAX_SCAVENGE_EVENTS = 5  # cap per invocation to avoid flooding
_MAX_RETRY_COUNT = 5      # stop re-creating events for tasks that keep failing


class Scavenger:
    """Scan for orphan tasks and create missing agent_events."""

    def __init__(self, agent_id: str, project_id: int, role: str) -> None:
        self.agent_id = agent_id
        self.project_id = project_id
        self.role = role

    def scavenge(self) -> int:
        """Run role-specific scan. Returns number of events created."""
        if not self._is_project_executing():
            return 0

        # Always reap orphaned agent_runs first (role-agnostic)
        self._reap_orphaned_runs()

        # Clean up stale git worktrees (role-agnostic)
        self._cleanup_stale_worktrees()

        dispatch = {
            "developer": self._scavenge_developer,
            "researcher": self._scavenge_researcher,
            "code_reviewer": self._scavenge_code_reviewer,
            "research_reviewer": self._scavenge_research_reviewer,
            "team_lead": self._scavenge_team_lead,
        }
        handler = dispatch.get(self.role)
        if handler is None:
            return 0

        return handler()

    # -- Role-specific scanners ------------------------------------------------

    def _scavenge_developer(self) -> int:
        """Find pending/backlog code tasks + rejected tasks assigned to us."""
        dev_types = ("code", "bug_fix", "test", "integrate", "design", "documentation")
        placeholders = ",".join("?" for _ in dev_types)

        available = self._find_orphan_tasks(
            f"""SELECT t.id, t.priority FROM tasks t
                WHERE t.project_id = ?
                  AND t.status IN ('backlog', 'pending')
                  AND t.type IN ({placeholders})
                  AND t.retry_count < ?
                  AND NOT EXISTS (
                      SELECT 1 FROM agent_events ae
                      WHERE ae.project_id = t.project_id
                        AND ae.event_type = 'task_available'
                        AND ae.status IN ('pending', 'claimed', 'in_progress')
                        AND ae.payload_json LIKE '%"task_id": ' || t.id || '%'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM task_dependencies td
                      JOIN tasks dep ON dep.id = td.depends_on_task_id
                      WHERE td.task_id = t.id
                        AND td.dependency_type = 'blocks'
                        AND dep.status NOT IN ('done', 'cancelled')
                  )
                ORDER BY t.priority ASC, t.created_at ASC
                LIMIT ?""",
            (self.project_id, *dev_types, _MAX_RETRY_COUNT, _MAX_SCAVENGE_EVENTS),
        )

        rejected = self._find_orphan_tasks(
            """SELECT t.id, t.priority FROM tasks t
               WHERE t.project_id = ?
                 AND t.status = 'rejected'
                 AND t.assigned_to = ?
                 AND t.retry_count < ?
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_events ae
                     WHERE ae.project_id = t.project_id
                       AND ae.event_type = 'task_rejected'
                       AND ae.status IN ('pending', 'claimed', 'in_progress')
                       AND ae.payload_json LIKE '%"task_id": ' || t.id || '%'
                 )
               ORDER BY t.priority ASC, t.created_at ASC
               LIMIT ?""",
            (self.project_id, self.agent_id, _MAX_RETRY_COUNT, _MAX_SCAVENGE_EVENTS),
        )

        created = 0
        for task in available:
            if created >= _MAX_SCAVENGE_EVENTS:
                break
            created += self._create_event(task["id"], "task_available")

        for task in rejected:
            if created >= _MAX_SCAVENGE_EVENTS:
                break
            created += self._create_event(task["id"], "task_rejected")

        return created

    def _scavenge_researcher(self) -> int:
        """Find pending/backlog research tasks + rejected tasks assigned to us."""
        available = self._find_orphan_tasks(
            """SELECT t.id, t.priority FROM tasks t
               WHERE t.project_id = ?
                 AND t.status IN ('backlog', 'pending')
                 AND t.type = 'research'
                 AND t.retry_count < ?
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_events ae
                     WHERE ae.project_id = t.project_id
                       AND ae.event_type = 'task_available'
                       AND ae.status IN ('pending', 'claimed', 'in_progress')
                       AND ae.payload_json LIKE '%"task_id": ' || t.id || '%'
                 )
                 AND NOT EXISTS (
                     SELECT 1 FROM task_dependencies td
                     JOIN tasks dep ON dep.id = td.depends_on_task_id
                     WHERE td.task_id = t.id
                       AND td.dependency_type = 'blocks'
                       AND dep.status NOT IN ('done', 'cancelled')
                 )
               ORDER BY t.priority ASC, t.created_at ASC
               LIMIT ?""",
            (self.project_id, _MAX_RETRY_COUNT, _MAX_SCAVENGE_EVENTS),
        )

        rejected = self._find_orphan_tasks(
            """SELECT t.id, t.priority FROM tasks t
               WHERE t.project_id = ?
                 AND t.status = 'rejected'
                 AND t.assigned_to = ?
                 AND t.type = 'research'
                 AND t.retry_count < ?
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_events ae
                     WHERE ae.project_id = t.project_id
                       AND ae.event_type = 'task_rejected'
                       AND ae.status IN ('pending', 'claimed', 'in_progress')
                       AND ae.payload_json LIKE '%"task_id": ' || t.id || '%'
                 )
               ORDER BY t.priority ASC, t.created_at ASC
               LIMIT ?""",
            (self.project_id, self.agent_id, _MAX_RETRY_COUNT, _MAX_SCAVENGE_EVENTS),
        )

        created = 0
        for task in available:
            if created >= _MAX_SCAVENGE_EVENTS:
                break
            created += self._create_event(task["id"], "task_available")

        for task in rejected:
            if created >= _MAX_SCAVENGE_EVENTS:
                break
            created += self._create_event(task["id"], "task_rejected")

        return created

    def _scavenge_code_reviewer(self) -> int:
        """Find review_ready non-research tasks without active review events."""
        tasks = self._find_orphan_tasks(
            """SELECT t.id, t.priority FROM tasks t
               WHERE t.project_id = ?
                 AND t.status = 'review_ready'
                 AND t.type != 'research'
                 AND (t.reviewer IS NULL OR t.reviewer = '')
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_events ae
                     WHERE ae.project_id = t.project_id
                       AND ae.event_type = 'review_ready'
                       AND ae.status IN ('pending', 'claimed', 'in_progress')
                       AND ae.payload_json LIKE '%"task_id": ' || t.id || '%'
                 )
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_runs ar
                     WHERE ar.task_id = t.id
                       AND ar.role = 'code_reviewer'
                       AND ar.status = 'running'
                 )
               ORDER BY t.priority ASC, t.created_at ASC
               LIMIT ?""",
            (self.project_id, _MAX_SCAVENGE_EVENTS),
        )

        created = 0
        for task in tasks:
            if created >= _MAX_SCAVENGE_EVENTS:
                break
            created += self._create_event(task["id"], "review_ready")
        return created

    def _scavenge_research_reviewer(self) -> int:
        """Find review_ready research tasks without active review events."""
        tasks = self._find_orphan_tasks(
            """SELECT t.id, t.priority FROM tasks t
               WHERE t.project_id = ?
                 AND t.status = 'review_ready'
                 AND t.type = 'research'
                 AND (t.reviewer IS NULL OR t.reviewer = '')
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_events ae
                     WHERE ae.project_id = t.project_id
                       AND ae.event_type = 'review_ready'
                       AND ae.status IN ('pending', 'claimed', 'in_progress')
                       AND ae.payload_json LIKE '%"task_id": ' || t.id || '%'
                 )
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_runs ar
                     WHERE ar.task_id = t.id
                       AND ar.role = 'research_reviewer'
                       AND ar.status = 'running'
                 )
               ORDER BY t.priority ASC, t.created_at ASC
               LIMIT ?""",
            (self.project_id, _MAX_SCAVENGE_EVENTS),
        )

        created = 0
        for task in tasks:
            if created >= _MAX_SCAVENGE_EVENTS:
                break
            created += self._create_event(task["id"], "review_ready")
        return created

    def _scavenge_team_lead(self) -> int:
        """Detect stagnation: tasks stuck in_progress >30min with no recent health_check."""
        tasks = self._find_orphan_tasks(
            """SELECT t.id, t.priority FROM tasks t
               WHERE t.project_id = ?
                 AND t.status = 'in_progress'
                 AND t.assigned_to IS NOT NULL
                 AND datetime(t.created_at, '+30 minutes') < CURRENT_TIMESTAMP
                 AND NOT EXISTS (
                     SELECT 1 FROM agent_events ae
                     WHERE ae.project_id = t.project_id
                       AND ae.event_type IN ('stagnation_detected', 'health_check')
                       AND ae.status IN ('pending', 'claimed', 'in_progress')
                       AND ae.payload_json LIKE '%"task_id": ' || t.id || '%'
                 )
               ORDER BY t.created_at ASC
               LIMIT ?""",
            (self.project_id, _MAX_SCAVENGE_EVENTS),
        )

        # Only fire if 2+ tasks are stuck
        if len(tasks) < 2:
            return 0

        created = 0
        for task in tasks:
            if created >= _MAX_SCAVENGE_EVENTS:
                break
            created += self._create_event(task["id"], "stagnation_detected")
        return created

    # -- Orphaned run cleanup -------------------------------------------------

    def _reap_orphaned_runs(self) -> int:
        """Mark agent_runs as 'timeout' when they exceed the role's max execution time.

        An orphaned run is one with status='running' whose started_at is older
        than the configured timeout for the agent's role (plus a 5-minute
        buffer).  This happens when a crew process dies without calling
        complete_agent_run().

        Returns the number of runs reaped.
        """
        # Role → max execution time in seconds (mirrors settings.AGENT_TIMEOUTS)
        _DEFAULT_TIMEOUTS: dict[str, int] = {
            "researcher": 2400,
            "developer": 1200,
            "code_reviewer": 300,
            "research_reviewer": 300,
            "team_lead": 1200,
            "project_lead": 1800,
        }
        timeout_secs = _DEFAULT_TIMEOUTS.get(self.role, 1200)
        buffer_secs = 300  # 5-minute buffer
        threshold_minutes = (timeout_secs + buffer_secs) / 60.0

        def _reap(conn: sqlite3.Connection) -> int:
            rows = conn.execute(
                """SELECT id, agent_id, task_id, started_at FROM agent_runs
                   WHERE project_id = ?
                     AND status = 'running'
                     AND datetime(started_at, '+' || ? || ' minutes') < CURRENT_TIMESTAMP""",
                (self.project_id, int(threshold_minutes)),
            ).fetchall()
            if not rows:
                return 0

            ids = [r["id"] for r in rows]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"""UPDATE agent_runs
                    SET status = 'timeout',
                        ended_at = CURRENT_TIMESTAMP,
                        error_class = 'OrphanedRunReaped'
                    WHERE id IN ({placeholders})""",
                ids,
            )
            conn.commit()
            for r in rows:
                logger.warning(
                    "Scavenger: reaped orphaned agent_run id=%d "
                    "(agent=%s, task=%d, started=%s)",
                    r["id"], r["agent_id"], r["task_id"], r["started_at"],
                )
            return len(ids)

        try:
            return execute_with_retry(_reap)
        except Exception:
            logger.debug(
                "Scavenger: failed to reap orphaned runs for project %d",
                self.project_id, exc_info=True,
            )
            return 0

    # -- Stale worktree cleanup ------------------------------------------------

    def _cleanup_stale_worktrees(self) -> int:
        """Remove git worktrees for agents no longer in roster.

        Uses lazy import to avoid pulling in the full git module tree.
        Returns the number of worktrees cleaned up.
        """
        try:
            from backend.git.worktree_manager import WorktreeManager

            return WorktreeManager().cleanup_stale_worktrees(self.project_id)
        except Exception:
            logger.debug(
                "Scavenger: stale worktree cleanup failed for project %d",
                self.project_id, exc_info=True,
            )
            return 0

    # -- Helpers ---------------------------------------------------------------

    def _is_project_executing(self) -> bool:
        """Check project status without importing flow modules."""

        def _query(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                "SELECT status FROM projects WHERE id = ?",
                (self.project_id,),
            ).fetchone()
            return row is not None and row["status"] in ("executing", "planning")

        try:
            return execute_with_retry(_query)
        except Exception:
            return False

    def _find_orphan_tasks(
        self, sql: str, params: tuple[Any, ...]
    ) -> list[dict[str, Any]]:
        """Run a query and return list of dicts."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

        try:
            return execute_with_retry(_query)
        except Exception:
            logger.debug("Scavenger query failed for %s", self.agent_id, exc_info=True)
            return []

    def _create_event(self, task_id: int, event_type: str) -> int:
        """Create an agent_event via backend.autonomy.events. Returns 1 on success, 0 on failure."""
        from backend.autonomy.events import create_task_event

        ids = create_task_event(
            self.project_id,
            task_id,
            event_type,
            target_agent_id=self.agent_id,
            source="scavenger",
            extra_payload={"source_reason": "scavenger"},
        )
        if ids:
            logger.debug(
                "Scavenger: created %s event for task %d → %s",
                event_type, task_id, self.agent_id,
            )
        return len(ids)
