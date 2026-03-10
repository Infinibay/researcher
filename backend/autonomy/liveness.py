"""Dead-agent detection and task recovery.

Provides functions to determine if an agent is truly alive and working,
and to recover tasks/events from dead agents.

An agent is considered DEAD when:
- Its loop thread is not alive (process-level check), OR
- Its last_poll_at in agent_loop_state is older than DEAD_AGENT_TIMEOUT

An agent is considered ALIVE when:
- Its loop thread is actively polling, OR
- It has polled recently (within DEAD_AGENT_TIMEOUT)

This module is used by:
- The watchdog (periodic background check)
- Graceful shutdown (to save state properly)
- Stagnation handler (to decide whether to reset tasks)
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.autonomy.db import execute_with_retry
from backend.config.settings import settings

logger = logging.getLogger(__name__)


def is_agent_dead(agent_id: str) -> bool:
    """Check if an agent's loop is dead based on last_poll_at.

    Returns True if the agent hasn't polled within DEAD_AGENT_TIMEOUT seconds.
    """
    timeout = settings.AGENT_LOOP_DEAD_AGENT_TIMEOUT

    def _check(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT last_poll_at,
                      (julianday('now') - julianday(last_poll_at)) * 86400 AS seconds_since_poll
               FROM agent_loop_state
               WHERE agent_id = ?""",
            (agent_id,),
        ).fetchone()
        if not row or row["last_poll_at"] is None:
            return True  # no loop state at all → dead
        return row["seconds_since_poll"] > timeout

    try:
        return execute_with_retry(_check)
    except Exception:
        return False  # can't determine → assume alive (conservative)


def is_agent_alive_for_task(agent_id: str, task_id: int) -> bool:
    """Check if an agent is alive AND actively working on a specific task.

    Returns True if:
    - Agent has polled recently (within DEAD_AGENT_TIMEOUT), AND
    - Agent has an in_progress event for this task
    """
    if is_agent_dead(agent_id):
        return False

    def _check(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM agent_events
               WHERE agent_id = ?
                 AND status = 'in_progress'
                 AND payload_json LIKE ?""",
            (agent_id, f'%"task_id": {task_id}%'),
        ).fetchone()
        return row["cnt"] > 0 if row else False

    try:
        return execute_with_retry(_check)
    except Exception:
        return True  # can't determine → assume alive (conservative)


def find_dead_agent_tasks(project_id: int) -> list[dict[str, Any]]:
    """Find in_progress tasks whose assigned agent is dead.

    Returns list of {task_id, task_title, agent_id, seconds_since_poll}.
    """
    timeout = settings.AGENT_LOOP_DEAD_AGENT_TIMEOUT

    def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = conn.execute(
            """SELECT t.id AS task_id, t.title AS task_title,
                      t.assigned_to AS agent_id,
                      ls.last_poll_at,
                      (julianday('now') - julianday(ls.last_poll_at)) * 86400 AS seconds_since_poll
               FROM tasks t
               LEFT JOIN agent_loop_state ls ON t.assigned_to = ls.agent_id
               WHERE t.project_id = ?
                 AND t.status = 'in_progress'
                 AND t.assigned_to IS NOT NULL
                 AND (
                     ls.last_poll_at IS NULL
                     OR (julianday('now') - julianday(ls.last_poll_at)) * 86400 > ?
                 )""",
            (project_id, timeout),
        ).fetchall()
        return [dict(r) for r in rows]

    try:
        return execute_with_retry(_query)
    except Exception:
        logger.debug("find_dead_agent_tasks failed", exc_info=True)
        return []


def recover_dead_agent_task(task_id: int, agent_id: str, reason: str = "dead_agent") -> bool:
    """Reset a task from in_progress → pending and fail its in_progress events.

    Returns True if the task was reset.
    """

    def _recover(conn: sqlite3.Connection) -> bool:
        # Only reset if still in_progress and assigned to this agent
        cursor = conn.execute(
            """UPDATE tasks SET status = 'pending', assigned_to = NULL
               WHERE id = ? AND status = 'in_progress' AND assigned_to = ?""",
            (task_id, agent_id),
        )
        if cursor.rowcount == 0:
            return False

        # Fail any in_progress events for this agent+task
        conn.execute(
            """UPDATE agent_events
               SET status = 'failed',
                   error_message = ?,
                   completed_at = CURRENT_TIMESTAMP
               WHERE agent_id = ?
                 AND status IN ('in_progress', 'claimed')
                 AND payload_json LIKE ?""",
            (f"recovered: {reason}", agent_id, f'%"task_id": {task_id}%'),
        )

        # Clear loop state
        conn.execute(
            """UPDATE agent_loop_state
               SET status = 'idle', current_event_id = NULL
               WHERE agent_id = ?""",
            (agent_id,),
        )

        conn.commit()
        return True

    try:
        recovered = execute_with_retry(_recover)
        if recovered:
            logger.info(
                "Recovered task %d from dead agent %s (reason: %s)",
                task_id, agent_id, reason,
            )
        return recovered
    except Exception:
        logger.warning(
            "Failed to recover task %d from agent %s",
            task_id, agent_id, exc_info=True,
        )
        return False


def recover_all_dead_agent_tasks(project_id: int, reason: str = "dead_agent") -> int:
    """Find and recover all tasks stuck on dead agents for a project.

    Returns the number of tasks recovered.
    """
    dead_tasks = find_dead_agent_tasks(project_id)
    recovered = 0
    for dt in dead_tasks:
        if recover_dead_agent_task(dt["task_id"], dt["agent_id"], reason):
            recovered += 1
    return recovered
