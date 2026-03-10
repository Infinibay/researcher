"""Periodic cleanup of merged and stale git branches."""

from __future__ import annotations

import logging
import sqlite3
import subprocess
import threading
from typing import Any

from backend.flows.helpers import log_flow_event
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class BranchCleanupService:
    """Cleans up merged and stale branches from git and the database."""

    def __init__(self, branch_service=None):
        self._branch_service = branch_service
        self._running = False

    def _get_branch_service(self):
        if self._branch_service is None:
            from backend.git.branch_service import BranchService
            self._branch_service = BranchService()
        return self._branch_service

    def find_merged_branches(self, project_id: int) -> list[dict[str, Any]]:
        """Return all branches with status ``'merged'`` for a project."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """SELECT * FROM branches
                   WHERE project_id = ? AND status = 'merged'
                   ORDER BY merged_at DESC""",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

    @staticmethod
    def delete_local_branch(branch_name: str, repo_path: str) -> bool:
        """Safely delete a local branch with ``git branch -d``."""
        try:
            subprocess.run(
                ["git", "branch", "-d", branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(
                "Failed to delete local branch '%s': %s", branch_name, e.stderr
            )
            return False

    @staticmethod
    def delete_remote_branch(branch_name: str, repo_path: str) -> bool:
        """Delete a remote branch with ``git push origin --delete``."""
        try:
            subprocess.run(
                ["git", "push", "origin", "--delete", branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(
                "Failed to delete remote branch '%s': %s", branch_name, e.stderr
            )
            return False

    @staticmethod
    def _resolve_repo_path(repo_name: str, project_id: int) -> str | None:
        """Look up the local_path for a repo from the repositories table."""

        def _query(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                """SELECT local_path FROM repositories
                   WHERE project_id = ? AND name = ? AND status = 'active'""",
                (project_id, repo_name),
            ).fetchone()
            return row["local_path"] if row else None

        return execute_with_retry(_query)

    def cleanup_merged_branches(
        self,
        project_id: int,
        repo_path: str | None = None,
        delete_remote: bool = True,
    ) -> int:
        """Delete all merged branches (local + optionally remote).

        Each branch's repo path is resolved individually by joining
        ``branches.repo_name`` to ``repositories.local_path``.  The
        *repo_path* parameter is used as a fallback when a repository
        record cannot be found.

        Returns the number of branches cleaned up.
        """
        merged = self.find_merged_branches(project_id)
        cleaned = 0

        for branch in merged:
            name = branch["branch_name"]

            # Resolve path per branch from repositories table
            path = self._resolve_repo_path(branch["repo_name"], project_id)
            if path is None:
                path = repo_path
            if path is None:
                logger.warning(
                    "Cannot resolve repo path for branch '%s' (repo '%s') — skipping",
                    name, branch["repo_name"],
                )
                continue

            local_ok = self.delete_local_branch(name, path)

            remote_ok = True
            if delete_remote:
                remote_ok = self.delete_remote_branch(name, path)

            if local_ok or remote_ok:
                cleaned += 1
                log_flow_event(
                    project_id=project_id,
                    event_type="branch_cleanup",
                    event_source="cleanup_service",
                    entity_type="branch",
                    entity_id=branch["id"],
                    event_data={
                        "branch_name": name,
                        "local_deleted": local_ok,
                        "remote_deleted": remote_ok if delete_remote else None,
                    },
                )

        if cleaned:
            logger.info(
                "Cleaned up %d merged branch(es) for project %d", cleaned, project_id
            )
        return cleaned

    def cleanup_stale_branches(
        self, project_id: int, days_threshold: int = 30
    ) -> int:
        """Find stale branches and mark them abandoned in the DB.

        Does **not** delete branches from git — logs a warning for
        manual review instead.  Returns the count of branches marked.
        """
        bs = self._get_branch_service()
        stale = bs.find_stale_branches(project_id, days_threshold)
        marked = 0

        for branch in stale:
            def _mark(conn: sqlite3.Connection, bid=branch["id"]) -> None:
                conn.execute(
                    "UPDATE branches SET status = 'abandoned' WHERE id = ?", (bid,)
                )
                conn.commit()

            execute_with_retry(_mark)
            marked += 1
            logger.warning(
                "Stale branch '%s' in repo '%s' marked abandoned — review manually",
                branch["branch_name"],
                branch["repo_name"],
            )

        return marked

    # ── Periodic scheduling ────────────────────────────────────────────

    def schedule_periodic_cleanup(self, interval_seconds: int = 300) -> None:
        """Start a daemon thread that runs merged-branch cleanup periodically."""
        if self._running:
            return

        self._running = True

        def _loop():
            while self._running:
                try:
                    # Cleanup across all projects with merged branches
                    def _projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
                        rows = conn.execute(
                            """SELECT DISTINCT project_id
                               FROM branches WHERE status = 'merged'"""
                        ).fetchall()
                        return [dict(r) for r in rows]

                    projects = execute_with_retry(_projects)
                    for proj in projects:
                        # Each branch resolves its own repo path internally
                        self.cleanup_merged_branches(proj["project_id"])
                except Exception:
                    logger.warning("Periodic branch cleanup failed", exc_info=True)

                event = threading.Event()
                event.wait(timeout=interval_seconds)

        t = threading.Thread(target=_loop, daemon=True, name="infinibay-branch-cleanup")
        t.start()
        logger.info("Periodic branch cleanup started (interval=%ds)", interval_seconds)

    def stop_periodic_cleanup(self) -> None:
        self._running = False
