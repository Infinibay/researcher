"""Service for branch lifecycle management."""

from __future__ import annotations

import logging
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from typing import Any

from backend.flows.helpers import set_task_branch
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class BranchService:
    """Manages git branches: creation, listing, status transitions."""

    def generate_branch_name(self, task_id: int, task_title: str) -> str:
        """Generate a branch name from a task id and title.

        Returns ``task-{id}-{slug}`` where *slug* is the title lowercased,
        spaces replaced with ``-``, non-alphanumeric characters stripped,
        and truncated to 40 characters.
        """
        slug = task_title.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        slug = slug[:40].rstrip("-")
        return f"task-{task_id}-{slug}"

    @staticmethod
    def _get_task_row(task_id: int) -> dict[str, Any] | None:
        """Look up task id, title, and project_id from DB."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT id, title, project_id FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    def create_branch_for_task(
        self,
        task_id: int,
        repo_path: str,
        base_branch: str = "main",
        repo_name: str = "default",
        project_id: int | None = None,
        created_by: str = "developer",
    ) -> str:
        """Create a git branch for a task and register it in the DB.

        1. Looks up the task title to generate a branch name.
        2. Runs ``git branch <name> <base>`` (does NOT checkout).
        3. Inserts into the ``branches`` table.
        4. Updates ``tasks.branch_name`` via :func:`set_task_branch`.
        """
        task = self._get_task_row(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if project_id is None:
            project_id = task["project_id"]

        branch_name = self.generate_branch_name(task_id, task["title"])

        # Create branch without switching HEAD (safe for concurrent use)
        subprocess.run(
            ["git", "branch", branch_name, base_branch],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

        # Register branch in DB
        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO branches
                       (project_id, task_id, repo_name, branch_name,
                        base_branch, status, created_by)
                   VALUES (?, ?, ?, ?, ?, 'active', ?)""",
                (project_id, task_id, repo_name, branch_name, base_branch, created_by),
            )
            conn.commit()

        execute_with_retry(_insert)

        # Update task record
        set_task_branch(task_id, branch_name)

        logger.info(
            "Created branch '%s' for task %d in repo '%s'",
            branch_name, task_id, repo_name,
        )
        return branch_name

    def list_branches(
        self,
        project_id: int,
        repo_name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List branches for a project with optional filters."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            where = ["project_id = ?"]
            params: list[Any] = [project_id]

            if repo_name is not None:
                where.append("repo_name = ?")
                params.append(repo_name)
            if status is not None:
                where.append("status = ?")
                params.append(status)

            rows = conn.execute(
                f"""SELECT * FROM branches
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC""",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

    def get_branch_for_task(self, task_id: int) -> dict[str, Any] | None:
        """Look up the branch associated with a task."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT * FROM branches WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    def mark_branch_merged(
        self,
        branch_name: str,
        repo_name: str,
        merged_at: str | None = None,
    ) -> bool:
        """Mark a branch as merged in the DB."""
        if merged_at is None:
            merged_at = datetime.now(timezone.utc).isoformat()

        def _update(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                """UPDATE branches
                   SET status = 'merged', merged_at = ?
                   WHERE branch_name = ? AND repo_name = ?""",
                (merged_at, branch_name, repo_name),
            )
            conn.commit()
            return cursor.rowcount > 0

        updated = execute_with_retry(_update)
        if updated:
            logger.info("Marked branch '%s' as merged in repo '%s'", branch_name, repo_name)
        return updated

    def mark_branch_stale(self, branch_name: str, repo_name: str) -> bool:
        """Mark a branch as stale in the DB."""

        def _update(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                """UPDATE branches
                   SET status = 'stale'
                   WHERE branch_name = ? AND repo_name = ?""",
                (branch_name, repo_name),
            )
            conn.commit()
            return cursor.rowcount > 0

        updated = execute_with_retry(_update)
        if updated:
            logger.info("Marked branch '%s' as stale in repo '%s'", branch_name, repo_name)
        return updated

    def find_stale_branches(
        self, project_id: int, days_threshold: int = 30
    ) -> list[dict[str, Any]]:
        """Find active branches with no commits in the last *days_threshold* days."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """SELECT * FROM branches
                   WHERE project_id = ?
                     AND status = 'active'
                     AND last_commit_at < datetime('now', ? || ' days')""",
                (project_id, f"-{days_threshold}"),
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)
