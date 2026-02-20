"""Service for managing multiple git repositories per project."""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class RepositoryManager:
    """Manages git repositories: init, clone, list, archive."""

    def init_repo(
        self,
        project_id: int,
        name: str,
        local_path: str,
        remote_url: str | None = None,
        default_branch: str = "main",
    ) -> dict[str, Any]:
        """Initialize a new git repo (or clone if remote_url provided).

        Runs ``git init`` or ``git clone``, configures the repo, and
        inserts a record into the ``repositories`` table.

        When ``FORGEJO_API_URL`` is configured and no *remote_url* is given,
        a Forgejo repo is auto-created and set as the ``origin`` remote.
        """
        if remote_url:
            return self.clone_repo(project_id, name, remote_url, local_path)

        # Auto-create Forgejo repo when configured
        from backend.config.settings import settings

        clone_url: str | None = None
        if settings.FORGEJO_API_URL:
            try:
                from backend.git.forgejo_client import forgejo_client

                fg_repo = forgejo_client.create_repo(
                    name=name,
                    description="",
                    private=False,
                    owner=settings.FORGEJO_OWNER or None,
                )
                clone_url = fg_repo.get("clone_url")
                logger.info("Created Forgejo repo for '%s': %s", name, clone_url)
            except Exception:
                logger.warning("Failed to create Forgejo repo for '%s'; continuing without remote", name, exc_info=True)

        os.makedirs(local_path, exist_ok=True)

        subprocess.run(
            ["git", "init", "-b", default_branch, local_path],
            check=True,
            capture_output=True,
            text=True,
        )

        if clone_url:
            subprocess.run(
                ["git", "remote", "add", "origin", clone_url],
                cwd=local_path,
                check=True,
                capture_output=True,
                text=True,
            )

        def _insert(conn: sqlite3.Connection) -> dict[str, Any]:
            conn.execute(
                """INSERT INTO repositories
                       (project_id, name, local_path, remote_url, default_branch, status)
                   VALUES (?, ?, ?, ?, ?, 'active')""",
                (project_id, name, local_path, clone_url, default_branch),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM repositories WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
            return dict(row)

        repo = execute_with_retry(_insert)
        logger.info("Initialized repo '%s' at %s for project %d", name, local_path, project_id)
        return repo

    def clone_repo(
        self,
        project_id: int,
        name: str,
        remote_url: str,
        local_path: str,
    ) -> dict[str, Any]:
        """Clone a remote repo and register it in the DB."""
        subprocess.run(
            ["git", "clone", remote_url, local_path],
            check=True,
            capture_output=True,
            text=True,
        )

        # Detect default branch from the clone
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=local_path,
            capture_output=True,
            text=True,
        )
        default_branch = result.stdout.strip() or "main"

        def _insert(conn: sqlite3.Connection) -> dict[str, Any]:
            conn.execute(
                """INSERT INTO repositories
                       (project_id, name, local_path, remote_url, default_branch, status)
                   VALUES (?, ?, ?, ?, ?, 'active')""",
                (project_id, name, local_path, remote_url, default_branch),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM repositories WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
            return dict(row)

        repo = execute_with_retry(_insert)
        logger.info("Cloned repo '%s' from %s for project %d", name, remote_url, project_id)
        return repo

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
        """Set git user.name and user.email in a repo directory."""
        subprocess.run(
            ["git", "config", "user.name", user_name],
            cwd=local_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", user_email],
            cwd=local_path,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Configured git identity in %s", local_path)
