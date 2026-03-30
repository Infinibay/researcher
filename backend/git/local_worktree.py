"""Local git worktree manager for TUI multi-dev mode.

Simplified worktree management for the CLI/TUI — no DB tracking,
no Forgejo integration. Each developer agent gets a worktree in
.researcher/worktrees/{agent_id}/.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WORKTREE_BASE = Path(".researcher") / "worktrees"


class LocalWorktreeManager:
    """Manages git worktrees for agent isolation in TUI mode."""

    def __init__(self, repo_path: str | None = None):
        self.repo_path = repo_path or os.getcwd()
        self.worktree_base = Path(self.repo_path) / WORKTREE_BASE

    def ensure_base_dir(self) -> None:
        self.worktree_base.mkdir(parents=True, exist_ok=True)

    def create_worktree(self, agent_id: str, branch_name: str | None = None) -> str:
        """Create a worktree for an agent. Returns absolute path."""
        self.ensure_base_dir()
        worktree_path = self.worktree_base / agent_id

        if worktree_path.exists():
            return str(worktree_path.resolve())

        if branch_name is None:
            branch_name = f"agent/{agent_id}"

        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
                cwd=self.repo_path,
                capture_output=True, text=True, check=True,
            )
            logger.info("Created worktree: %s (branch: %s)", worktree_path, branch_name)
            return str(worktree_path.resolve())
        except subprocess.CalledProcessError:
            # Branch might already exist
            try:
                subprocess.run(
                    ["git", "worktree", "add", str(worktree_path), branch_name],
                    cwd=self.repo_path,
                    capture_output=True, text=True, check=True,
                )
                return str(worktree_path.resolve())
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to create worktree: {e.stderr}") from e

    def remove_worktree(self, agent_id: str, force: bool = False) -> bool:
        """Remove a worktree. Returns True if removed."""
        worktree_path = self.worktree_base / agent_id
        if not worktree_path.exists():
            return False

        try:
            cmd = ["git", "worktree", "remove"]
            if force:
                cmd.append("--force")
            cmd.append(str(worktree_path))
            subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError:
            if force:
                shutil.rmtree(worktree_path, ignore_errors=True)
                subprocess.run(
                    ["git", "worktree", "prune"],
                    cwd=self.repo_path, capture_output=True,
                )
                return True
            return False

    def get_worktree_path(self, agent_id: str) -> str | None:
        """Get path for an agent's worktree, or None."""
        p = self.worktree_base / agent_id
        return str(p.resolve()) if p.exists() else None

    def list_worktrees(self) -> list[dict[str, str]]:
        """List all agent worktrees."""
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True, text=True, check=True,
            )
        except subprocess.CalledProcessError:
            return []

        worktrees = []
        current: dict[str, str] = {}
        base_str = str(self.worktree_base.resolve())

        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                if current.get("path") and base_str in current["path"]:
                    current["agent_id"] = Path(current["path"]).name
                    worktrees.append(current)
                current = {}
            elif line.startswith("worktree "):
                current["path"] = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")

        if current.get("path") and base_str in current.get("path", ""):
            current["agent_id"] = Path(current["path"]).name
            worktrees.append(current)

        return worktrees

    def merge_worktree(
        self, agent_id: str, target_branch: str = "main", message: str | None = None,
    ) -> dict[str, Any]:
        """Merge agent branch back to target. Returns {success, message, conflicts}."""
        worktree_path = self.get_worktree_path(agent_id)
        if not worktree_path:
            return {"success": False, "message": f"No worktree for {agent_id}", "conflicts": []}

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=worktree_path, capture_output=True, text=True, check=True,
            )
            source_branch = result.stdout.strip()
        except subprocess.CalledProcessError:
            return {"success": False, "message": "Cannot determine branch", "conflicts": []}

        msg = message or f"Merge {source_branch} from {agent_id}"

        try:
            result = subprocess.run(
                ["git", "merge", "--no-ff", "-m", msg, source_branch],
                cwd=self.repo_path, capture_output=True, text=True, check=True,
            )
            return {"success": True, "message": result.stdout, "conflicts": []}
        except subprocess.CalledProcessError as e:
            conflicts = [l.strip() for l in (e.stdout or "").split("\n") if "CONFLICT" in l]
            if conflicts:
                subprocess.run(
                    ["git", "merge", "--abort"],
                    cwd=self.repo_path, capture_output=True,
                )
            return {"success": False, "message": e.stderr or e.stdout, "conflicts": conflicts}

    def cleanup_worktrees(self) -> int:
        """Remove all agent worktrees. Returns count removed."""
        count = 0
        if not self.worktree_base.exists():
            return 0
        for entry in self.worktree_base.iterdir():
            if entry.is_dir() and self.remove_worktree(entry.name, force=True):
                count += 1
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=self.repo_path, capture_output=True,
        )
        return count

    def setup_for_agents(self, agent_ids: list[str]) -> dict[str, str]:
        """Create worktrees for agents. Returns {agent_id: path}."""
        paths = {}
        for agent_id in agent_ids:
            try:
                paths[agent_id] = self.create_worktree(agent_id)
            except RuntimeError as e:
                logger.error("Worktree creation failed for %s: %s", agent_id, e)
        return paths
