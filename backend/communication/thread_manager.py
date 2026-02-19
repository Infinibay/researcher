"""Thread lifecycle management for conversation threads."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class ThreadManager:
    """Centralizes conversation thread creation and lifecycle operations."""

    def create_thread(
        self,
        project_id: int,
        thread_type: str,
        participants: list[str] | None = None,
        task_id: int | None = None,
    ) -> str:
        """Create a new conversation thread and return its thread_id."""
        thread_id = str(uuid.uuid4())

        def _insert(conn: sqlite3.Connection) -> str:
            conn.execute(
                """INSERT INTO conversation_threads
                       (thread_id, project_id, thread_type, task_id,
                        participants_json, created_at, last_message_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (
                    thread_id,
                    project_id,
                    thread_type,
                    task_id,
                    json.dumps(participants) if participants else "[]",
                ),
            )
            conn.commit()
            return thread_id

        return execute_with_retry(_insert)

    def get_or_create_task_thread(
        self,
        project_id: int,
        task_id: int,
        thread_type: str = "task_discussion",
    ) -> str:
        """Return the active thread for a task, creating one if none exists.

        Uses an atomic check-and-insert within the same transaction to
        prevent duplicate threads from concurrent calls.
        """
        thread_id = str(uuid.uuid4())

        def _atomic(conn: sqlite3.Connection) -> str:
            row = conn.execute(
                """SELECT thread_id FROM conversation_threads
                   WHERE project_id = ? AND task_id = ? AND thread_type = ?
                     AND status != 'archived'
                   ORDER BY created_at DESC LIMIT 1""",
                (project_id, task_id, thread_type),
            ).fetchone()
            if row:
                return row["thread_id"]

            conn.execute(
                """INSERT INTO conversation_threads
                       (thread_id, project_id, thread_type, task_id,
                        participants_json, created_at, last_message_at)
                   VALUES (?, ?, ?, ?, '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                (thread_id, project_id, thread_type, task_id),
            )
            conn.commit()
            return thread_id

        return execute_with_retry(_atomic)

    def get_active_threads(
        self,
        project_id: int,
        thread_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all active threads for a project, optionally filtered by type."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            sql = """SELECT * FROM conversation_threads
                     WHERE project_id = ? AND status != 'archived'"""
            params: list[Any] = [project_id]
            if thread_type:
                sql += " AND thread_type = ?"
                params.append(thread_type)
            sql += " ORDER BY last_message_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

    def get_task_threads(self, task_id: int) -> list[dict[str, Any]]:
        """Return all threads associated with a task."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """SELECT * FROM conversation_threads
                   WHERE task_id = ?
                   ORDER BY created_at DESC""",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

    def archive_thread(self, thread_id: str) -> None:
        """Archive a conversation thread."""

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE conversation_threads SET status = 'archived' WHERE thread_id = ?",
                (thread_id,),
            )
            conn.commit()

        execute_with_retry(_update)
        logger.info("Thread %s archived", thread_id)

    def resolve_thread(self, thread_id: str) -> None:
        """Mark a conversation thread as resolved."""

        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE conversation_threads SET status = 'resolved' WHERE thread_id = ?",
                (thread_id,),
            )
            conn.commit()

        execute_with_retry(_update)
        logger.info("Thread %s resolved", thread_id)
