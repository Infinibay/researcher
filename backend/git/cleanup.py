"""Read historical merged-branch records while preserving retained material; old automatic Git deletion and stale-state mutation are retired."""

import sqlite3
from typing import Any

from backend.runtime.legacy_git import retired_git_effect
from backend.tools.base.db import execute_with_retry


class BranchCleanupService:
    """Preserve the old inspection interface without granting deletion authority from branch age, status or an ambient repository path."""

    def __init__(self, branch_service=None):
        """Keep optional historical metadata access and an inert compatibility flag; construction starts no worker."""
        self._branch_service = branch_service
        self._running = False

    def _get_branch_service(self):
        """Resolve the old branch metadata reader only when explicitly requested."""
        if self._branch_service is None:
            from backend.git.branch_service import BranchService

            self._branch_service = BranchService()
        return self._branch_service

    def find_merged_branches(self, project_id: int) -> list[dict[str, Any]]:
        """Read stored merged labels; they do not prove native acceptance, reachability or permission to delete retained data."""
        def query(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            """Return the original scoped records without invoking Git or assigning a new status."""
            return [dict(row) for row in conn.execute(
                "SELECT * FROM branches WHERE project_id=? AND status='merged' ORDER BY merged_at DESC", (project_id,)
            )]
        return execute_with_retry(query)

    @staticmethod
    def delete_local_branch(branch_name: str, repo_path: str) -> bool:
        """Refuse an old direct local deletion before Git; preservation is not a claim that a branch has been imported."""
        retired_git_effect("local branch deletion")

    @staticmethod
    def delete_remote_branch(branch_name: str, repo_path: str) -> bool:
        """Refuse old remote deletion before any subprocess, transport or credential access."""
        retired_git_effect("remote branch deletion")

    def cleanup_merged_branches(self, project_id: int, repo_path: str | None = None, delete_remote: bool = True) -> int:
        """Refuse inferred merged-branch cleanup without mutating refs, status or event history."""
        retired_git_effect("merged branch cleanup")

    def cleanup_stale_branches(self, project_id: int, days_threshold: int = 30) -> int:
        """Refuse age-based automatic abandonment; a stale label does not establish that retained work is dispensable."""
        retired_git_effect("stale branch cleanup")

    def schedule_periodic_cleanup(self, interval_seconds: int = 300) -> None:
        """Refuse old autonomous cleanup before constructing a thread or setting the running flag."""
        retired_git_effect("periodic branch cleanup")

    def stop_periodic_cleanup(self) -> None:
        """Withdraw the historical flag without interpreting that assignment as proof of physical worker closure."""
        self._running = False
