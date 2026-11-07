"""Retired per-agent Git worktree mutation interface.

Native development owns a fresh private allocation per attempt. Historical
checkout data and database rows remain available to explicit owner inspection;
no old helper may reset a branch, copy host credentials or infer safe deletion.
"""

from backend.runtime.legacy_git import retired_git_effect


class WorktreeManager:
    """Keep import compatibility while rejecting obsolete database-backed worktree effects before any IO."""

    def ensure_worktree(self, project_id: int, agent_id: str, repo_local_path: str, base_branch: str = 'main') -> str:
        """Refuse per-agent reuse/reset; native preparation admits an independent allocation for each exact attempt."""
        retired_git_effect('per-agent worktree creation or reuse')

    def remove_worktree(self, agent_id: str, project_id: int) -> bool:
        """Refuse force removal and false removed-state updates; retained dirty/untracked files remain untouched."""
        retired_git_effect('per-agent worktree removal')

    def cleanup_stale_worktrees(self, project_id: int) -> int:
        """Refuse age/roster-based disposal and pruning; missing actors do not establish that their work is dispensable."""
        retired_git_effect('stale worktree cleanup')
