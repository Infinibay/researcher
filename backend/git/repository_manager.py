"""Service for managing multiple git repositories per project."""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
from typing import Any
from urllib.parse import urlparse

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


def _forgejo_clone_url(api_url: str, owner: str, repo_name: str) -> str:
    """Build a clone URL that uses the same host/port as FORGEJO_API_URL.

    Forgejo's API returns ``clone_url`` relative to its own ``ROOT_URL``
    (often ``localhost``), which may differ from the address the user
    configured in ``FORGEJO_API_URL``.  This helper derives the correct
    external URL from the API base.
    """
    parsed = urlparse(api_url)  # e.g. http://192.168.0.199:3000/api/v1
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/{owner}/{repo_name}.git"


class RepositoryManager:
    """Manages git repositories: init, clone, list, archive."""

    def init_repo(
        self,
        project_id: int,
        name: str,
        local_path: str,
        remote_url: str | None = None,
        default_branch: str = "main",
        description: str = "",
    ) -> dict[str, Any]:
        """Initialize a new git repo (or clone if remote_url provided).

        Idempotent — safe to call multiple times. If a repo already exists
        in the DB, returns it. Handles pre-existing Forgejo repos, local
        directories, and git remotes gracefully.

        When ``FORGEJO_API_URL`` is configured and no *remote_url* is given,
        a Forgejo repo is auto-created and set as the ``origin`` remote.
        """
        if remote_url:
            return self.clone_repo(project_id, name, remote_url, local_path)

        # Check if repo already exists in DB — return it directly
        existing = self.get_repo(project_id, name)
        if existing and existing.get("status") == "active":
            logger.info("Repo '%s' already exists in DB for project %d, returning existing", name, project_id)
            existing["has_remote"] = existing.get("remote_url") is not None
            return existing

        from backend.config.settings import settings

        # ── Step 1: Ensure Forgejo repo exists ──────────────────────────
        clone_url: str | None = None
        if settings.FORGEJO_API_URL:
            try:
                from backend.git.forgejo_client import forgejo_client

                forgejo_client.create_repo(
                    name=name,
                    description=description,
                    private=False,
                    owner=settings.FORGEJO_OWNER or None,
                )
                owner = settings.FORGEJO_OWNER or "infinibay"
                clone_url = _forgejo_clone_url(settings.FORGEJO_API_URL, owner, name)
                logger.info("Forgejo repo ready for '%s': %s", name, clone_url)
            except Exception:
                logger.error(
                    "Failed to create Forgejo repo for '%s' — aborting repo init. "
                    "Forgejo is configured (FORGEJO_API_URL=%s) so a remote is required.",
                    name, settings.FORGEJO_API_URL, exc_info=True,
                )
                raise

        # ── Step 2: Initialize local git repo ───────────────────────────
        os.makedirs(local_path, exist_ok=True)

        is_existing_repo = os.path.isdir(os.path.join(local_path, ".git"))
        if not is_existing_repo:
            subprocess.run(
                ["git", "init", "-b", default_branch, local_path],
                check=True,
                capture_output=True,
                text=True,
            )
            self.configure_git(local_path, "INFINIBAY", "infinibay@localhost")
            gitkeep = os.path.join(local_path, ".gitkeep")
            with open(gitkeep, "w") as f:
                pass
            subprocess.run(
                ["git", "add", ".gitkeep"],
                cwd=local_path, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=local_path, check=True, capture_output=True, text=True,
            )
        else:
            logger.info("Local git repo already exists at %s, reusing it", local_path)
            self.configure_git(local_path, "INFINIBAY", "infinibay@localhost")

        # ── Step 3: Configure remote and push ───────────────────────────
        if clone_url:
            # Check if origin remote already exists
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=local_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # No origin remote — add it
                subprocess.run(
                    ["git", "remote", "add", "origin", clone_url],
                    cwd=local_path, check=True, capture_output=True, text=True,
                )
            elif result.stdout.strip() != clone_url:
                # Origin exists but points to wrong URL — update it
                subprocess.run(
                    ["git", "remote", "set-url", "origin", clone_url],
                    cwd=local_path, check=True, capture_output=True, text=True,
                )

            self._configure_forgejo_auth(local_path, settings.FORGEJO_TOKEN)

            # Push initial commit (force because auto_init creates a
            # separate initial commit on Forgejo)
            push_result = subprocess.run(
                ["git", "push", "--force", "-u", "origin", default_branch],
                cwd=local_path,
                capture_output=True,
                text=True,
            )
            if push_result.returncode != 0:
                logger.error(
                    "git push failed for '%s': %s",
                    name, push_result.stderr.strip(),
                )
                raise subprocess.CalledProcessError(
                    push_result.returncode,
                    push_result.args,
                    output=push_result.stdout,
                    stderr=push_result.stderr,
                )
            logger.info("Pushed initial commit to origin/%s for '%s'", default_branch, name)

        # ── Step 4: Upsert DB record ────────────────────────────────────
        def _upsert(conn: sqlite3.Connection) -> dict[str, Any]:
            conn.execute(
                """INSERT INTO repositories
                       (project_id, name, local_path, remote_url, default_branch, status)
                   VALUES (?, ?, ?, ?, ?, 'active')
                   ON CONFLICT(project_id, name) DO UPDATE SET
                       local_path = excluded.local_path,
                       remote_url = excluded.remote_url,
                       default_branch = excluded.default_branch,
                       status = 'active'""",
                (project_id, name, local_path, clone_url, default_branch),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM repositories WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
            return dict(row)

        repo = execute_with_retry(_upsert)
        repo["has_remote"] = clone_url is not None
        logger.info("Initialized repo '%s' at %s for project %d (has_remote=%s)", name, local_path, project_id, repo["has_remote"])
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

    @staticmethod
    def _configure_forgejo_auth(local_path: str, token: str) -> None:
        """Store Forgejo token as an HTTP extra header in the repo's git config.

        This allows ``git push`` / ``git fetch`` to authenticate without
        embedding credentials in the remote URL.
        """
        if not token:
            return
        subprocess.run(
            [
                "git", "config", "--local",
                "http.extraHeader",
                f"Authorization: token {token}",
            ],
            cwd=local_path,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Configured Forgejo token auth in %s", local_path)
