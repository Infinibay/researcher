"""Git service layer — repository, branch, PR, worktree, and cleanup management."""

from backend.git.branch_service import BranchService
from backend.git.cleanup import BranchCleanupService
from backend.git.forgejo_client import ForgejoClient, forgejo_client
from backend.git.pr_service import PRService
from backend.git.repository_manager import RepositoryManager
from backend.git.worktree_manager import WorktreeManager

__all__ = [
    "RepositoryManager",
    "BranchService",
    "PRService",
    "BranchCleanupService",
    "WorktreeManager",
    "ForgejoClient",
    "repository_manager",
    "branch_service",
    "pr_service",
    "cleanup_service",
    "worktree_manager",
    "forgejo_client",
]

# Module-level singletons
repository_manager = RepositoryManager()
branch_service = BranchService()
pr_service = PRService(branch_service=branch_service)
cleanup_service = BranchCleanupService(branch_service=branch_service)
worktree_manager = WorktreeManager()
