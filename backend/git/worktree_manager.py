"""Per-agent git worktree management.

Gives each agent its own isolated working copy via ``git worktree``.
Worktrees share the ``.git`` object store but each has its own checkout,
branch, and staging area — lightweight and native to git.

Import safety: only imports from ``backend.tools.base.db`` (not from
``backend.tools``).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Manage per-agent git worktrees for concurrent development."""

    def ensure_worktree(
        self,
        project_id: int,
        agent_id: str,
        repo_local_path: str,
        base_branch: str = "main",
    ) -> str:
        """Return (or create) an isolated worktree for *agent_id*.

        Idempotent: if an active worktree already exists for this
        agent+project in the DB AND the directory exists on disk, just
        return its path.

        The worktree is created at ``{repo_local_path}/.worktrees/{agent_id}``.
        Forgejo auth config (``http.extraHeader``) is copied from the main
        repo so push/fetch works.

        Returns the absolute worktree path.
        """
        # 1. Check DB for an existing active worktree
        existing = self._get_active_worktree(agent_id, project_id)
        if existing and os.path.isdir(existing["worktree_path"]):
            logger.debug(
                "Reusing existing worktree for %s at %s",
                agent_id, existing["worktree_path"],
            )
            return existing["worktree_path"]

        # If the DB row exists but the directory is gone, clean up the stale record
        if existing:
            self._mark_removed(agent_id, project_id)

        # 2. Resolve repo_id from repositories table
        repo_id = self._get_repo_id(project_id, repo_local_path)
        if repo_id is None:
            raise ValueError(
                f"No repository found for project {project_id} "
                f"at path {repo_local_path}"
            )

        # 3. Create the worktree on disk
        worktree_path = os.path.join(repo_local_path, ".worktrees", agent_id)
        os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

        # Remove stale directory if it exists but isn't a valid worktree
        if os.path.exists(worktree_path):
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", worktree_path],
                    cwd=repo_local_path,
                    capture_output=True,
                    text=True,
                )
            except Exception:
                pass

        # Prune stale worktree refs before adding
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repo_local_path,
            capture_output=True,
            text=True,
        )

        # Use --detach because the base branch is typically already checked
        # out in the main repo (or another worktree).  Agents create their
        # own feature branches from this starting point anyway.
        subprocess.run(
            ["git", "worktree", "add", "--detach", worktree_path, base_branch],
            cwd=repo_local_path,
            check=True,
            capture_output=True,
            text=True,
        )

        # 4. Copy Forgejo auth config from main repo
        self._copy_auth_config(repo_local_path, worktree_path)

        # 5. Copy git identity config from main repo
        self._copy_git_identity(repo_local_path, worktree_path)

        # 6. Record in DB
        def _insert(conn: sqlite3.Connection) -> None:
            conn.execute(
                """INSERT INTO agent_worktrees
                       (project_id, repo_id, agent_id, worktree_path, branch_name, status)
                   VALUES (?, ?, ?, ?, ?, 'active')
                   ON CONFLICT(agent_id, project_id) DO UPDATE SET
                       worktree_path = excluded.worktree_path,
                       branch_name = excluded.branch_name,
                       status = 'active',
                       cleaned_up_at = NULL""",
                (project_id, repo_id, agent_id, worktree_path, base_branch),
            )
            conn.commit()

        execute_with_retry(_insert)
        logger.info(
            "Created worktree for %s at %s (base: %s)",
            agent_id, worktree_path, base_branch,
        )
        return worktree_path

    def remove_worktree(self, agent_id: str, project_id: int) -> bool:
        """Remove the worktree for *agent_id* and mark it in the DB.

        Returns True if a worktree was found and removed.
        """
        existing = self._get_active_worktree(agent_id, project_id)
        if not existing:
            return False

        worktree_path = existing["worktree_path"]

        # Find the main repo path (parent of .worktrees/)
        repo_local_path = self._repo_path_from_worktree(worktree_path)

        if repo_local_path and os.path.isdir(repo_local_path):
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", worktree_path],
                    cwd=repo_local_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except Exception:
                logger.warning(
                    "Failed to git-remove worktree %s, attempting manual cleanup",
                    worktree_path, exc_info=True,
                )
                # Fall back to manual removal
                import shutil
                try:
                    if os.path.isdir(worktree_path):
                        shutil.rmtree(worktree_path)
                except Exception:
                    logger.warning(
                        "Manual cleanup also failed for %s", worktree_path,
                        exc_info=True,
                    )

        self._mark_removed(agent_id, project_id)
        logger.info("Removed worktree for %s at %s", agent_id, worktree_path)
        return True

    def cleanup_stale_worktrees(self, project_id: int) -> int:
        """Remove worktrees for agents no longer in roster or with missing dirs.

        Also runs ``git worktree prune`` on each repo to clean stale refs.
        Returns the count of worktrees removed.
        """
        stale = self._find_stale_worktrees(project_id)
        removed = 0

        for row in stale:
            agent_id = row["agent_id"]
            worktree_path = row["worktree_path"]
            repo_local_path = self._repo_path_from_worktree(worktree_path)

            if repo_local_path and os.path.isdir(repo_local_path):
                try:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", worktree_path],
                        cwd=repo_local_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except Exception:
                    logger.debug(
                        "git worktree remove failed for %s", worktree_path,
                        exc_info=True,
                    )

            self._mark_removed(agent_id, project_id)
            removed += 1
            logger.info(
                "Cleaned up stale worktree for %s at %s", agent_id, worktree_path,
            )

        # Run git worktree prune on all active repos for this project
        self._prune_repos(project_id)

        return removed

    # -- Internal helpers ------------------------------------------------------

    @staticmethod
    def _get_active_worktree(
        agent_id: str, project_id: int
    ) -> dict[str, Any] | None:
        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                """SELECT * FROM agent_worktrees
                   WHERE agent_id = ? AND project_id = ? AND status = 'active'""",
                (agent_id, project_id),
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    @staticmethod
    def _mark_removed(agent_id: str, project_id: int) -> None:
        def _update(conn: sqlite3.Connection) -> None:
            conn.execute(
                """UPDATE agent_worktrees
                   SET status = 'removed', cleaned_up_at = CURRENT_TIMESTAMP
                   WHERE agent_id = ? AND project_id = ?""",
                (agent_id, project_id),
            )
            conn.commit()

        execute_with_retry(_update)

    @staticmethod
    def _get_repo_id(project_id: int, local_path: str) -> int | None:
        def _query(conn: sqlite3.Connection) -> int | None:
            row = conn.execute(
                """SELECT id FROM repositories
                   WHERE project_id = ? AND local_path = ? AND status = 'active'""",
                (project_id, local_path),
            ).fetchone()
            return row["id"] if row else None

        return execute_with_retry(_query)

    @staticmethod
    def _repo_path_from_worktree(worktree_path: str) -> str | None:
        """Derive the main repo path from a worktree path.

        Worktrees are at ``{repo_local_path}/.worktrees/{agent_id}``.
        """
        parts = worktree_path.rsplit("/.worktrees/", 1)
        if len(parts) == 2:
            return parts[0]
        return None

    @staticmethod
    def _copy_auth_config(repo_local_path: str, worktree_path: str) -> None:
        """Copy Forgejo token auth from main repo to worktree."""
        try:
            result = subprocess.run(
                ["git", "config", "--local", "--get", "http.extraHeader"],
                cwd=repo_local_path,
                capture_output=True,
                text=True,
            )
            header = result.stdout.strip()
            if header:
                subprocess.run(
                    ["git", "config", "--local", "http.extraHeader", header],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True,
                )
        except Exception:
            logger.debug(
                "Could not copy auth config to worktree %s", worktree_path,
                exc_info=True,
            )

    @staticmethod
    def _copy_git_identity(repo_local_path: str, worktree_path: str) -> None:
        """Copy git user.name / user.email from main repo to worktree."""
        for key in ("user.name", "user.email"):
            try:
                result = subprocess.run(
                    ["git", "config", "--local", "--get", key],
                    cwd=repo_local_path,
                    capture_output=True,
                    text=True,
                )
                value = result.stdout.strip()
                if value:
                    subprocess.run(
                        ["git", "config", key, value],
                        cwd=worktree_path,
                        capture_output=True,
                        text=True,
                    )
            except Exception:
                pass

    @staticmethod
    def _find_stale_worktrees(project_id: int) -> list[dict[str, Any]]:
        """Find active worktrees whose agent is no longer in roster or dir is missing."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """SELECT aw.agent_id, aw.worktree_path
                   FROM agent_worktrees aw
                   WHERE aw.project_id = ?
                     AND aw.status = 'active'
                     AND (
                         NOT EXISTS (
                             SELECT 1 FROM roster r
                             WHERE r.agent_id = aw.agent_id
                               AND r.status IN ('active', 'idle')
                         )
                     )""",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            stale = execute_with_retry(_query)
        except Exception:
            return []

        # Also include worktrees whose directory no longer exists
        def _query_existing(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = conn.execute(
                """SELECT aw.agent_id, aw.worktree_path
                   FROM agent_worktrees aw
                   WHERE aw.project_id = ?
                     AND aw.status = 'active'""",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            all_active = execute_with_retry(_query_existing)
        except Exception:
            all_active = []

        stale_ids = {r["agent_id"] for r in stale}
        for row in all_active:
            if row["agent_id"] not in stale_ids and not os.path.isdir(row["worktree_path"]):
                stale.append(row)
                stale_ids.add(row["agent_id"])

        return stale

    @staticmethod
    def _prune_repos(project_id: int) -> None:
        """Run ``git worktree prune`` on all active repos for a project."""

        def _query(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                """SELECT local_path FROM repositories
                   WHERE project_id = ? AND status = 'active'""",
                (project_id,),
            ).fetchall()
            return [r["local_path"] for r in rows]

        try:
            paths = execute_with_retry(_query)
        except Exception:
            return

        for path in paths:
            if os.path.isdir(path):
                try:
                    subprocess.run(
                        ["git", "worktree", "prune"],
                        cwd=path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except Exception:
                    pass
