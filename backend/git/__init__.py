"""Git service layer — repository, branch, PR, and cleanup management."""

from backend.git.branch_service import BranchService
from backend.git.cleanup import BranchCleanupService
from backend.git.forgejo_client import ForgejoClient, forgejo_client
from backend.git.pr_service import PRService
from backend.git.repository_manager import RepositoryManager

__all__ = [
    "RepositoryManager",
    "BranchService",
    "PRService",
    "BranchCleanupService",
    "ForgejoClient",
    "repository_manager",
    "branch_service",
    "pr_service",
    "cleanup_service",
    "forgejo_client",
]

# Module-level singletons
repository_manager = RepositoryManager()
branch_service = BranchService()
pr_service = PRService(branch_service=branch_service)
cleanup_service = BranchCleanupService(branch_service=branch_service)
