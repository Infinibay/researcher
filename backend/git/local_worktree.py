"""Retired TUI Git worktree interface; native task controls own preparation, publication and retained work.

Compatibility calls fail before filesystem or subprocess access. A target branch
argument or force flag is never substituted for exact native effect authority.
"""

from backend.runtime.legacy_git import retired_git_effect


class LocalWorktreeManager:
    """Preserve imports without reviving a second executor, unchecked checkout merge or destructive cleanup path."""

    def __init__(self, repo_path: str | None = None):
        """Accept the historical constructor without resolving paths, discovering Git or creating directories."""
        self.repo_path = repo_path

    def ensure_base_dir(self) -> None:
        """Refuse legacy workspace setup before mkdir; native allocations are recorded before filesystem work."""
        retired_git_effect('TUI workspace setup')

    def create_worktree(self, agent_id: str, branch_name: str | None = None) -> str:
        """Refuse reusing an old agent directory or branch as a new execution attempt."""
        retired_git_effect('TUI worktree creation')

    def remove_worktree(self, agent_id: str, force: bool = False) -> bool:
        """Refuse both ordinary and forced removal without pretending a failed deletion succeeded."""
        retired_git_effect('TUI worktree removal')

    def get_worktree_path(self, agent_id: str) -> str | None:
        """Refuse inferred filesystem ownership from an agent label; use scoped retained-material controls."""
        retired_git_effect('TUI worktree path discovery')

    def list_worktrees(self) -> list[dict[str, str]]:
        """Refuse the obsolete ambient Git reader instead of hiding unavailable history as an empty list."""
        retired_git_effect('TUI worktree discovery')

    def merge_worktree(self, agent_id: str, target_branch: str = 'main', message: str | None = None) -> dict:
        """Refuse unchecked merging into the current checkout; publication requires exact source, destination and receipt."""
        retired_git_effect('TUI checkout merge')

    def cleanup_worktrees(self) -> int:
        """Refuse bulk cleanup; preservation and retention decisions belong to explicit owner operations."""
        retired_git_effect('TUI worktree cleanup')

    def setup_for_agents(self, agent_ids: list[str]) -> dict[str, str]:
        """Refuse batch allocation through the removed TUI engine before any directory or process is created."""
        retired_git_effect('TUI multi-agent worktree setup')
