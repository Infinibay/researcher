"""Service for managing multiple git repositories per project."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.runtime.contracts import RunConflict
from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)




class RepositoryManager:
    """Read and archive historical registrations; all source mutations require explicit administrative ownership."""

    def init_repo(
        self,
        project_id: int,
        name: str,
        local_path: str,
        remote_url: str | None = None,
        default_branch: str = "main",
        description: str = "",
    ) -> dict[str, Any]:
        """Reject retired setup before filesystem, Git, remote, credential or registration effects; use an original explicit administrative source operation."""
        raise RunConflict("Source operations require the explicit owner source-operations API; legacy setup cannot initialize, clone, configure credentials or publish.")

    def clone_repo(
        self,
        project_id: int,
        name: str,
        remote_url: str,
        local_path: str,
    ) -> dict[str, Any]:
        """Reject retired setup before filesystem, Git, remote, credential or registration effects; use an original explicit administrative source operation."""
        raise RunConflict("Source operations require the explicit owner source-operations API; legacy setup cannot initialize, clone, configure credentials or publish.")

    def list_repos(self, project_id: int) -> list[dict[str, Any]]:
        """List active repositories for a project."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """SELECT * FROM repositories
                   WHERE project_id = ? AND status = 'active'
                   ORDER BY name""",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

    def get_repo(self, project_id: int, name: str) -> dict[str, Any] | None:
        """Look up a single repository by project and name."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT * FROM repositories WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    def archive_repo(self, project_id: int, name: str) -> bool:
        """Soft-delete a repository by setting status to 'archived'."""

        def _update(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "UPDATE repositories SET status = 'archived' WHERE project_id = ? AND name = ?",
                (project_id, name),
            )
            conn.commit()
            return cursor.rowcount > 0

        archived = execute_with_retry(_update)
        if archived:
            logger.info("Archived repo '%s' for project %d", name, project_id)
        return archived

    def configure_git(self, local_path: str, user_name: str, user_email: str) -> None:
        """Reject retired setup before filesystem, Git, remote, credential or registration effects; use an original explicit administrative source operation."""
        raise RunConflict("Source operations require the explicit owner source-operations API; legacy setup cannot initialize, clone, configure credentials or publish.")

    @staticmethod
    def _configure_forgejo_auth(local_path: str, token: str) -> None:
        """Reject retired setup before filesystem, Git, remote, credential or registration effects; use an original explicit administrative source operation."""
        raise RunConflict("Source operations require the explicit owner source-operations API; legacy setup cannot initialize, clone, configure credentials or publish.")
