"""Tool for Git push operations (async-capable)."""

import asyncio
import subprocess
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool


class GitPushInput(BaseModel):
    branch: str | None = Field(
        default=None, description="Branch to push. If None, pushes current branch."
    )
    force: bool = Field(default=False, description="Force push (use with caution)")


class GitPushTool(PabadaBaseTool):
    name: str = "git_push"
    description: str = (
        "Push commits to the remote repository. "
        "Pushes the current branch by default."
    )
    args_schema: Type[BaseModel] = GitPushInput

    def _run(self, branch: str | None = None, force: bool = False) -> str:
        try:
            # Get current branch if not specified
            if branch is None:
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    return self._error("Failed to determine current branch")
                branch = result.stdout.strip()

            cmd = ["git", "push", "-u", "origin", branch]
            if force:
                cmd.insert(2, "--force")

            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=settings.GIT_PUSH_TIMEOUT,
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                if "rejected" in stderr:
                    return self._error(
                        f"Push rejected (remote has new commits). "
                        f"Pull first or use force=True. Details: {stderr}"
                    )
                return self._error(f"Push failed: {stderr}")

        except subprocess.TimeoutExpired:
            return self._error(
                f"Push timed out after {settings.GIT_PUSH_TIMEOUT}s"
            )
        except FileNotFoundError:
            return self._error("Git is not installed or not in PATH")

        self._log_tool_usage(f"Pushed {branch} to origin")
        return self._success({
            "branch": branch,
            "remote": "origin",
            "forced": force,
        })

    async def _arun(self, branch: str | None = None, force: bool = False) -> str:
        """Async push using asyncio subprocess."""
        try:
            if branch is None:
                proc = await asyncio.create_subprocess_exec(
                    "git", "rev-parse", "--abbrev-ref", "HEAD",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                if proc.returncode != 0:
                    return self._error("Failed to determine current branch")
                branch = stdout.decode().strip()

            cmd = ["git", "push", "-u", "origin", branch]
            if force:
                cmd.insert(2, "--force")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=settings.GIT_PUSH_TIMEOUT
            )

            if proc.returncode != 0:
                err = stderr.decode().strip()
                return self._error(f"Push failed: {err}")

        except asyncio.TimeoutError:
            return self._error(f"Push timed out after {settings.GIT_PUSH_TIMEOUT}s")

        self._log_tool_usage(f"Pushed {branch} to origin (async)")
        return self._success({"branch": branch, "remote": "origin", "forced": force})
