"""Service wrapping the code_reviews table and optional Forgejo merge API."""

from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class PRService:
    """Manages pull/merge requests via the ``code_reviews`` table."""

    def __init__(self, branch_service=None):
        # Lazy-imported to avoid circular deps; set at module init
        self._branch_service = branch_service

    def _get_branch_service(self):
        if self._branch_service is None:
            from backend.git.branch_service import BranchService
            self._branch_service = BranchService()
        return self._branch_service

    def list_prs(
        self, project_id: int, status: str | None = None
    ) -> list[dict[str, Any]]:
        """List pull requests for a project with optional status filter."""

        def _query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            where = ["project_id = ?"]
            params: list[Any] = [project_id]

            if status is not None:
                where.append("status = ?")
                params.append(status)

            rows = conn.execute(
                f"""SELECT * FROM code_reviews
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC""",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

    def get_pr(self, pr_id: int) -> dict[str, Any] | None:
        """Get a single pull request by id."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT * FROM code_reviews WHERE id = ?", (pr_id,)
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    def get_pr_for_task(self, task_id: int) -> dict[str, Any] | None:
        """Get the pull request associated with a task."""

        def _query(conn: sqlite3.Connection) -> dict[str, Any] | None:
            row = conn.execute(
                "SELECT * FROM code_reviews WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

        return execute_with_retry(_query)

    def update_pr_status(
        self,
        pr_id: int,
        status: str,
        reviewer: str | None = None,
        comments: str | None = None,
    ) -> bool:
        """Update a PR's status, reviewer, and/or comments.

        Automatically sets ``reviewed_at`` when status is ``'approved'`` or ``'merged'``.
        """

        def _update(conn: sqlite3.Connection) -> bool:
            sets = ["status = ?"]
            params: list[Any] = [status]

            if reviewer is not None:
                sets.append("reviewer = ?")
                params.append(reviewer)
            if comments is not None:
                sets.append("comments = ?")
                params.append(comments)
            if status in ("approved", "merged"):
                sets.append("reviewed_at = CURRENT_TIMESTAMP")

            params.append(pr_id)
            cursor = conn.execute(
                f"UPDATE code_reviews SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

        updated = execute_with_retry(_update)
        if updated:
            logger.info("Updated PR %d status to '%s'", pr_id, status)
        return updated

    def merge_pr(
        self,
        pr_id: int,
        repo_path: str,
        merge_message: str | None = None,
    ) -> bool:
        """Merge a pull request.

        If ``FORGEJO_API_URL`` is set and the PR has a ``forgejo_pr_index``,
        calls the Forgejo merge API.  Otherwise performs a local
        ``git merge --no-ff``.
        Then marks the branch as merged and updates the PR status.
        """
        pr = self.get_pr(pr_id)
        if not pr:
            raise ValueError(f"PR {pr_id} not found")

        branch = pr["branch"]
        repo_name = pr["repo_name"]
        forgejo_index = pr.get("forgejo_pr_index")

        forgejo_url = os.environ.get("FORGEJO_API_URL")
        if forgejo_url and forgejo_index:
            owner_repo = self._resolve_owner_repo(pr.get("project_id"), repo_name)
            self._forgejo_merge(owner_repo, forgejo_index, merge_message)
        else:
            self._local_merge(repo_path, branch, merge_message)

        # Mark branch as merged
        bs = self._get_branch_service()
        bs.mark_branch_merged(branch, repo_name)

        # Update PR status
        self.update_pr_status(pr_id, "merged")

        logger.info("Merged PR %d (branch '%s') in repo '%s'", pr_id, branch, repo_name)
        return True

    def close_pr(self, pr_id: int) -> bool:
        """Close/abandon a pull request.

        Sets PR status to ``'changes_requested'`` and marks the branch
        as ``'abandoned'`` in the ``branches`` table.
        """
        pr = self.get_pr(pr_id)
        if not pr:
            raise ValueError(f"PR {pr_id} not found")

        self.update_pr_status(pr_id, "changes_requested")

        # Mark branch as abandoned
        def _abandon(conn: sqlite3.Connection) -> None:
            conn.execute(
                """UPDATE branches SET status = 'abandoned'
                   WHERE branch_name = ? AND repo_name = ?""",
                (pr["branch"], pr["repo_name"]),
            )
            conn.commit()

        execute_with_retry(_abandon)

        logger.info("Closed PR %d, branch '%s' marked abandoned", pr_id, pr["branch"])
        return True

    # ── Private helpers ────────────────────────────────────────────────

    @staticmethod
    def _resolve_owner_repo(project_id: int | None, repo_name: str) -> str:
        """Derive ``{owner}/{repo}`` from the repository's ``remote_url``.

        Parses both HTTPS (``https://host/owner/repo.git``) and SSH
        (``git@host:owner/repo.git``) URL formats.
        """
        if project_id is None:
            raise ValueError("Cannot resolve owner/repo without project_id")

        def _query(conn: sqlite3.Connection) -> str | None:
            row = conn.execute(
                "SELECT remote_url FROM repositories WHERE project_id = ? AND name = ?",
                (project_id, repo_name),
            ).fetchone()
            return row["remote_url"] if row else None

        remote_url = execute_with_retry(_query)
        if not remote_url:
            raise ValueError(
                f"No remote_url configured for repo '{repo_name}' in project {project_id}"
            )

        # Strip trailing .git
        url = remote_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]

        # SSH format: git@host:owner/repo
        if ":" in url and "@" in url.split(":")[0]:
            path_part = url.split(":", 1)[1]
        else:
            # HTTPS format: https://host/owner/repo
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path_part = parsed.path.lstrip("/")

        # path_part should be "owner/repo"
        parts = path_part.split("/")
        if len(parts) < 2:
            raise ValueError(f"Cannot parse owner/repo from remote_url: {remote_url}")
        return f"{parts[-2]}/{parts[-1]}"

    @staticmethod
    def _local_merge(repo_path: str, branch: str, message: str | None = None) -> None:
        """Perform a local ``git merge --no-ff``."""
        cmd = ["git", "merge", "--no-ff", branch]
        if message:
            cmd.extend(["-m", message])
        subprocess.run(
            cmd,
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )

    @staticmethod
    def _forgejo_merge(
        owner_repo: str,
        pr_index: int,
        merge_message: str | None = None,
    ) -> None:
        """Merge a PR via the Forgejo API.

        Uses ``ForgejoClient.merge_pull_request`` which calls
        ``POST /repos/{owner}/{repo}/pulls/{index}/merge``.
        """
        from backend.git.forgejo_client import forgejo_client

        forgejo_client.merge_pull_request(
            owner_repo, pr_index, merge_message=merge_message,
        )
