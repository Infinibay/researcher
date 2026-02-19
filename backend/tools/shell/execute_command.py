"""Tool for executing shell commands with sandboxing."""

import logging
import os
import shlex
import subprocess
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.security.container_runtime import runtime_available
from backend.security.sandbox import sandbox_executor
from backend.tools.base.base_tool import PabadaBaseTool

logger = logging.getLogger(__name__)

# Shell control operators used for chaining or redirection.
# Parentheses and $ are excluded — they appear in legitimate quoted
# arguments (e.g. `python -c "print(1)"`) and are harmless with shell=False.
DANGEROUS_CHARS = {";", "|", "&", "`", "<", ">"}


class ExecuteCommandInput(BaseModel):
    command: str = Field(..., description="Command to execute")
    timeout: int = Field(
        default=60, ge=1, le=600, description="Max execution time in seconds"
    )
    cwd: str | None = Field(
        default=None, description="Working directory for the command"
    )
    env: dict[str, str] | None = Field(
        default=None, description="Additional environment variables"
    )


class ExecuteCommandTool(PabadaBaseTool):
    name: str = "execute_command"
    description: str = (
        "Execute a shell command with sandboxing. Only whitelisted commands "
        "are allowed. Returns stdout, stderr, and exit code."
    )
    args_schema: Type[BaseModel] = ExecuteCommandInput

    def _run(
        self,
        command: str,
        timeout: int = 60,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        # Parse command into parts (always needed for shell=False execution)
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return self._error(f"Invalid command syntax: {e}")

        if not parts:
            return self._error("Empty command")

        if settings.SANDBOX_ENABLED:
            # Reject dangerous characters in the raw command string FIRST.
            # These enable shell injection (chaining, piping, subshells,
            # redirections) and must never reach the subprocess layer.
            found = [ch for ch in DANGEROUS_CHARS if ch in command]
            if found:
                return self._error(
                    f"Command rejected: contains dangerous character(s) "
                    f"{found}. Shell operators (;, |, &, `, <, >) "
                    f"are not allowed."
                )

            # Check if command is in whitelist.
            # For absolute paths, resolve and verify the real binary name
            # to prevent bypasses like /tmp/evil/ls -> malicious binary.
            cmd_path = parts[0]
            if os.path.sep in cmd_path:
                base_cmd = os.path.basename(os.path.realpath(cmd_path))
            else:
                base_cmd = cmd_path
            if base_cmd not in settings.ALLOWED_COMMANDS:
                return self._error(
                    f"Command '{base_cmd}' is not allowed. "
                    f"Allowed commands: {', '.join(sorted(settings.ALLOWED_COMMANDS))}"
                )

            # Validate cwd if provided
            if cwd:
                cwd_err = self._validate_sandbox_path(cwd)
                if cwd_err:
                    return self._error(cwd_err)

            # ── Container sandbox path ──────────────────────────────────
            if runtime_available():
                return self._run_sandboxed(parts, command, timeout, cwd, env)
            else:
                logger.warning(
                    "SANDBOX_ENABLED=True but no container runtime found; "
                    "falling back to direct subprocess execution"
                )

        # ── Direct subprocess execution (fallback / dev mode) ───────────
        return self._run_direct(parts, command, timeout, cwd, env)

    def _run_sandboxed(
        self,
        parts: list[str],
        raw_command: str,
        timeout: int,
        cwd: str | None,
        env: dict[str, str] | None,
    ) -> str:
        """Delegate execution to SandboxExecutor (container-based)."""
        agent_id = self.agent_id or "unknown"
        role = self._get_agent_role(agent_id)

        try:
            result = sandbox_executor.execute(
                command=parts,
                agent_id=agent_id,
                role=role,
                cwd=cwd,
                env=env,
                timeout=timeout,
            )
        except RuntimeError as e:
            return self._error(f"Sandbox execution failed: {e}")

        if result.timed_out:
            return self._error(f"Command timed out after {timeout}s (sandboxed)")

        self._log_tool_usage(
            f"Executed (sandbox): {raw_command[:80]} (exit={result.exit_code})"
        )

        return self._success({
            "exit_code": result.exit_code,
            "stdout": result.stdout[-10000:] if result.stdout else "",
            "stderr": result.stderr[-5000:] if result.stderr else "",
            "success": result.exit_code == 0,
        })

    def _run_direct(
        self,
        parts: list[str],
        raw_command: str,
        timeout: int,
        cwd: str | None,
        env: dict[str, str] | None,
    ) -> str:
        """Execute directly via subprocess (dev mode / fallback)."""
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        timeout = min(timeout, settings.COMMAND_TIMEOUT)

        try:
            result = subprocess.run(
                parts,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=run_env,
            )
        except subprocess.TimeoutExpired:
            return self._error(f"Command timed out after {timeout}s")
        except FileNotFoundError:
            return self._error(f"Command not found: {parts[0]}")
        except Exception as e:
            return self._error(f"Execution failed: {e}")

        self._log_tool_usage(
            f"Executed: {raw_command[:80]} (exit={result.returncode})"
        )

        return self._success({
            "exit_code": result.returncode,
            "stdout": result.stdout[-10000:] if result.stdout else "",
            "stderr": result.stderr[-5000:] if result.stderr else "",
            "success": result.returncode == 0,
        })

    @staticmethod
    def _get_agent_role(agent_id: str) -> str:
        """Look up the agent's role from the roster table."""
        import sqlite3
        from backend.tools.base.db import execute_with_retry

        role_result = {"role": "default"}

        def _query(conn: sqlite3.Connection):
            row = conn.execute(
                "SELECT role FROM roster WHERE agent_id = ?", (agent_id,)
            ).fetchone()
            if row:
                role_result["role"] = row[0]

        try:
            execute_with_retry(_query)
        except Exception:
            pass
        return role_result["role"]
