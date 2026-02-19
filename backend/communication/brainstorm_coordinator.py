"""Brainstorming session coordinator — prevents duplicate sessions."""

from __future__ import annotations

import logging
import sqlite3
import threading
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class BrainstormingCoordinator:
    """Guard against concurrent brainstorming sessions for a project.

    The ``ListenerManager._handle_stagnation()`` handler should call
    ``start_session()`` instead of directly instantiating ``BrainstormingFlow``
    to ensure only one active session runs at a time.
    """

    def start_session(self, project_id: int, topic: str) -> int:
        """Start a new brainstorming session if none is currently active.

        Returns the ``session_id`` (new or existing).
        Uses an atomic check-and-insert to prevent duplicate active sessions.
        """

        def _atomic_get_or_create(conn: sqlite3.Connection) -> tuple[int, bool]:
            # Check for existing active session inside the same transaction
            existing = conn.execute(
                """SELECT id FROM brainstorm_sessions
                   WHERE project_id = ? AND status = 'active'
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
            if existing:
                return existing["id"], False

            cursor = conn.execute(
                """INSERT INTO brainstorm_sessions
                       (project_id, topic, status, created_at)
                   VALUES (?, ?, 'active', CURRENT_TIMESTAMP)""",
                (project_id, topic),
            )
            conn.commit()
            return cursor.lastrowid, True

        session_id, created = execute_with_retry(_atomic_get_or_create)

        if not created:
            logger.info(
                "Active brainstorming session %d already exists for project %d",
                session_id, project_id,
            )
            return session_id

        logger.info(
            "Brainstorming session %d created for project %d (topic: %s)",
            session_id, project_id, topic,
        )

        # Kick off BrainstormingFlow in a background thread
        thread = threading.Thread(
            target=self._run_flow,
            args=(project_id, session_id),
            name=f"BrainstormFlow-{session_id}",
            daemon=True,
        )
        thread.start()

        return session_id

    def get_active_session(self, project_id: int) -> dict[str, Any] | None:
        """Return the active brainstorming session for a project, if any."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                """SELECT * FROM brainstorm_sessions
                   WHERE project_id = ? AND status = 'active'
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id,),
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    def complete_session(self, session_id: int, ideas_count: int = 0) -> None:
        """Mark a session as completed."""

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                """UPDATE brainstorm_sessions
                   SET status = 'completed',
                       completed_at = CURRENT_TIMESTAMP,
                       ideas_count = ?
                   WHERE id = ?""",
                (ideas_count, session_id),
            )
            conn.commit()

        execute_with_retry(_update)
        logger.info("Brainstorming session %d completed (%d ideas)", session_id, ideas_count)

    def cancel_session(self, session_id: int) -> None:
        """Mark a session as cancelled."""

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                """UPDATE brainstorm_sessions
                   SET status = 'cancelled', completed_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (session_id,),
            )
            conn.commit()

        execute_with_retry(_update)
        logger.info("Brainstorming session %d cancelled", session_id)

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _run_flow(project_id: int, session_id: int) -> None:
        """Execute ``BrainstormingFlow`` and update the session on completion."""
        from backend.flows.brainstorming_flow import BrainstormingFlow

        try:
            flow = BrainstormingFlow()
            flow.kickoff(inputs={"project_id": project_id})
            # Mark completed — ideas_count will be updated by the flow itself
            # or we can do a best-effort count from state
            coordinator = BrainstormingCoordinator()
            coordinator.complete_session(session_id)
        except Exception:
            logger.exception(
                "BrainstormingFlow failed for session %d (project %d)",
                session_id, project_id,
            )
            coordinator = BrainstormingCoordinator()
            coordinator.cancel_session(session_id)
