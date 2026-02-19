"""Tool for Git commit operations."""

import sqlite3
import subprocess
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class GitCommitInput(BaseModel):
    message: str = Field(..., description="Commit message")
    files: list[str] | None = Field(
        default=None,
        description="Specific files to stage. If None, stages all changes (git add -A).",
    )


class GitCommitTool(PabadaBaseTool):
    name: str = "git_commit"
    description: str = (
        "Stage and commit changes to Git. "
        "Optionally specify files to stage, otherwise stages all changes."
    )
    args_schema: Type[BaseModel] = GitCommitInput

    def _run(self, message: str, files: list[str] | None = None) -> str:
        try:
            # Check if there are changes to commit
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=15,
            )
            if not status.stdout.strip():
                return self._error("No changes to commit")

            # Stage files
            if files:
                for f in files:
                    result = subprocess.run(
                        ["git", "add", f],
                        capture_output=True, text=True, timeout=15,
                    )
                    if result.returncode != 0:
                        return self._error(f"Failed to stage {f}: {result.stderr.strip()}")
            else:
                result = subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0:
                    return self._error(f"Failed to stage changes: {result.stderr.strip()}")

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return self._error(f"Commit failed: {result.stderr.strip()}")

            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else None

            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            branch_name = branch_result.stdout.strip() if branch_result.returncode == 0 else None

            # Update branch record in DB
            if branch_name and commit_hash:
                def _update_branch(conn: sqlite3.Connection):
                    conn.execute(
                        """UPDATE branches
                           SET last_commit_hash = ?, last_commit_at = CURRENT_TIMESTAMP
                           WHERE branch_name = ? AND status = 'active'""",
                        (commit_hash, branch_name),
                    )
                    conn.commit()

                try:
                    execute_with_retry(_update_branch)
                except Exception:
                    pass

        except subprocess.TimeoutExpired:
            return self._error("Git operation timed out")
        except FileNotFoundError:
            return self._error("Git is not installed or not in PATH")

        self._log_tool_usage(f"Committed: {message[:80]}")
        return self._success({
            "commit_hash": commit_hash,
            "branch": branch_name,
            "message": message,
        })
