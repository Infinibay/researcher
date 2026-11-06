"""Historical PR metadata and owner navigation; competing local/remote publication is retired in favor of the native exact-candidate API."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


class PRService:
    """Read and annotate historical PR records without treating status or actor labels as native acceptance/publication authority."""

    def __init__(self, branch_service=None):
        """Keep the optional historical branch metadata service without starting Git or a remote transport."""
        # Lazy-imported to avoid circular deps; set at module init
        self._branch_service = branch_service

    def _get_branch_service(self):
        """Resolve the metadata service for explicit historical status annotations, never native publication."""
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
                    WHERE {" AND ".join(where)}
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

    def owner_entry(self, pr_id: int) -> dict:
        """Read an actual scoped navigation bridge without inventing a prior native run or issuing execution/effect authority."""
        from backend.runtime.legacy_git import pr_owner_entry

        return execute_with_retry(lambda conn: pr_owner_entry(conn, pr_id))

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

    def merge_pr(self, pr_id: int, repo_path: str, merge_message: str | None = None) -> bool:
        """Refuse retired local/remote publication; historical PR approval never substitutes for a native exact candidate and current owner acceptance."""
        pr = self.get_pr(pr_id)
        if pr is None:
            raise ValueError(f"PR {pr_id} not found")
        from backend.runtime.lifecycle import require_legacy_git_publication

        execute_with_retry(lambda conn: require_legacy_git_publication(
            conn, task_id=pr.get("task_id"), project_id=pr.get("project_id"),
            repo_name=pr["repo_name"], repo_path=repo_path,
        ))

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
        """Refuse direct old helper calls before Git; use the original accepted-candidate owner publication API."""
        from backend.runtime.legacy_git import retired_git_effect

        retired_git_effect("local PR merge")

    @staticmethod
    def _forgejo_merge(owner_repo: str, pr_index: int, merge_message: str | None = None) -> None:
        """Refuse old remote helper calls before importing a transport or reading credentials; a historical PR is not publication authority."""
        from backend.runtime.legacy_git import retired_git_effect

        retired_git_effect("remote PR merge")
