"""Dependency validation for task state transitions."""

import sqlite3

from backend.tools.base.db import execute_with_retry


class DependencyValidator:
    """Validates whether a task can start based on its blocking dependencies."""

    @staticmethod
    def can_start(task_id: int) -> bool:
        """Return True if all blocking dependencies of *task_id* are done."""

        def _query(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                """SELECT COUNT(*) as cnt
                   FROM task_dependencies td
                   JOIN tasks dep ON dep.id = td.depends_on_task_id
                   WHERE td.task_id = ?
                     AND td.dependency_type = 'blocks'
                     AND dep.status NOT IN ('done', 'cancelled')""",
                (task_id,),
            ).fetchone()
            return row["cnt"] == 0

        return execute_with_retry(_query)

    @staticmethod
    def get_unmet_dependencies(task_id: int) -> list[dict]:
        """Return blocking tasks that are not yet done."""

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT dep.id, dep.title, dep.status
                   FROM task_dependencies td
                   JOIN tasks dep ON dep.id = td.depends_on_task_id
                   WHERE td.task_id = ?
                     AND td.dependency_type = 'blocks'
                     AND dep.status NOT IN ('done', 'cancelled')
                   ORDER BY dep.id""",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)
