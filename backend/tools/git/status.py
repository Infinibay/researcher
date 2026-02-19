"""Tool for viewing Git status."""

import subprocess
from typing import Type

from pydantic import BaseModel

from backend.tools.base.base_tool import PabadaBaseTool


class GitStatusInput(BaseModel):
    pass


class GitStatusTool(PabadaBaseTool):
    name: str = "git_status"
    description: str = (
        "Show the current Git status including modified, staged, and untracked files."
    )
    args_schema: Type[BaseModel] = GitStatusInput

    def _run(self) -> str:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                return self._error(f"Git status failed: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            return self._error("Git status timed out")
        except FileNotFoundError:
            return self._error("Git is not installed or not in PATH")

        raw = result.stdout.rstrip("\n")
        lines = raw.split("\n") if raw else []

        staged = []
        modified = []
        untracked = []

        for line in lines:
            if len(line) < 3:
                continue
            index_status = line[0]
            worktree_status = line[1]
            file_path = line[3:]

            if index_status in ("A", "M", "D", "R", "C"):
                staged.append({"status": index_status, "file": file_path})
            if worktree_status in ("M", "D"):
                modified.append({"status": worktree_status, "file": file_path})
            if index_status == "?" and worktree_status == "?":
                untracked.append(file_path)

        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

        return self._success({
            "branch": branch,
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "clean": len(lines) == 0,
        })
