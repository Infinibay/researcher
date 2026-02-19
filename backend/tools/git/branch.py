"""Tool for Git branch operations."""

import re
import sqlite3
import subprocess
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class GitBranchInput(BaseModel):
    branch_name: str = Field(..., description="Name of the branch")
    create: bool = Field(default=True, description="Create the branch if True, checkout if False")
    base_branch: str = Field(default="main", description="Base branch to create from")


class GitBranchTool(PabadaBaseTool):
    name: str = "git_branch"
    description: str = (
        "Create or checkout a Git branch. "
        "When creating, it branches from the specified base branch."
    )
    args_schema: Type[BaseModel] = GitBranchInput

    def _run(
        self, branch_name: str, create: bool = True, base_branch: str = "main"
    ) -> str:
        # Validate branch name
        if not re.match(r"^[a-zA-Z0-9._/-]+$", branch_name):
            return self._error(
                f"Invalid branch name: '{branch_name}'. "
                "Use only alphanumerics, dots, dashes, underscores, and slashes."
            )

        try:
            if create:
                # Fetch latest from base branch first
                subprocess.run(
                    ["git", "fetch", "origin", base_branch],
                    capture_output=True, text=True, timeout=30,
                )
                result = subprocess.run(
                    ["git", "checkout", "-b", branch_name, f"origin/{base_branch}"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0:
                    # Maybe branch already exists, try checkout
                    result = subprocess.run(
                        ["git", "checkout", branch_name],
                        capture_output=True, text=True, timeout=15,
                    )
                    if result.returncode != 0:
                        return self._error(f"Git error: {result.stderr.strip()}")
                    action = "checked_out"
                else:
                    action = "created"
            else:
                result = subprocess.run(
                    ["git", "checkout", branch_name],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0:
                    return self._error(f"Git error: {result.stderr.strip()}")
                action = "checked_out"
        except subprocess.TimeoutExpired:
            return self._error("Git operation timed out")
        except FileNotFoundError:
            return self._error("Git is not installed or not in PATH")

        # Register branch in DB
        project_id = self.project_id
        agent_id = self.agent_id or "unknown"

        if action == "created":
            def _register(conn: sqlite3.Connection):
                conn.execute(
                    """INSERT OR IGNORE INTO branches
                       (project_id, task_id, repo_name, branch_name, base_branch, status, created_by)
                       VALUES (?, ?, ?, ?, ?, 'active', ?)""",
                    (project_id, self.task_id, ".", branch_name, base_branch, agent_id),
                )
                conn.commit()

            try:
                execute_with_retry(_register)
            except Exception:
                pass  # Non-critical

        self._log_tool_usage(f"Branch {action}: {branch_name}")
        return self._success({
            "branch": branch_name,
            "action": action,
            "base": base_branch if action == "created" else None,
        })
