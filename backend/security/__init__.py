"""Security module for PABADA — container sandboxing, workspace isolation, cleanup."""

from backend.security.container_runtime import ContainerRuntime, get_runtime
from backend.security.sandbox import SandboxExecutor, SandboxResult, sandbox_executor
from backend.security.workspace_manager import WorkspaceManager, workspace_manager
from backend.security.cleanup import CleanupManager, cleanup_manager

# PodManager is imported lazily to avoid circular imports
# (cleanup → tools.base.db → tools.__init__ → agents → tools)
# Use: from backend.security.pod_manager import PodManager, pod_manager

__all__ = [
    "ContainerRuntime",
    "get_runtime",
    "SandboxExecutor",
    "SandboxResult",
    "sandbox_executor",
    "WorkspaceManager",
    "workspace_manager",
    "CleanupManager",
    "cleanup_manager",
]
