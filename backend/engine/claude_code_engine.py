"""Claude Code CLI-based agent execution engine.

Runs Claude Code inside sandbox pods to execute agent tasks.  The agent's
system prompt is written to a temporary file inside the pod, then Claude
Code is invoked with ``--append-system-prompt`` pointing at that file.

Requires:
- ``PABADA_SANDBOX_ENABLED=true``
- Claude Code installed in the sandbox image
- Valid credentials copied into the pod (handled by PodManager)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.engine.base import AgentEngine, AgentKilledError

logger = logging.getLogger(__name__)


# No per-role timeouts — local models are too slow for hard limits.


class ClaudeCodeEngine(AgentEngine):
    """Executes agent tasks by running Claude Code CLI inside pods."""

    def execute(
        self,
        agent: Any,
        task_prompt: tuple[str, str],
        *,
        verbose: bool = True,
        guardrail: Any | None = None,
        guardrail_max_retries: int = 5,
        output_pydantic: type | None = None,
        task_tools: list | None = None,
        event_id: int | None = None,
        resume_state: dict | None = None,
    ) -> str:
        from backend.config.settings import settings
        from backend.security.pod_manager import pod_manager

        description, expected_output = task_prompt

        # Build the user prompt that Claude Code will receive
        user_prompt = self._build_user_prompt(description, expected_output)

        # Build system prompt from the agent's backstory
        system_prompt = agent.backstory

        # Resolve pod environment variables
        pod_env = self._build_pod_env(agent, settings)

        # Write system prompt to a temp file inside the pod
        write_cmd = [
            "sh", "-c",
            f"cat > /tmp/pabada_system.txt << 'PABADA_SYSTEM_EOF'\n{system_prompt}\nPABADA_SYSTEM_EOF",
        ]
        try:
            pod_manager.exec_in_pod(
                agent.agent_id, write_cmd, cwd="/workspace",
                env=pod_env, timeout=30,
            )
        except Exception:
            logger.warning(
                "Failed to write system prompt to pod for %s, using inline",
                agent.agent_id, exc_info=True,
            )

        # Build the claude command
        claude_cmd = self._build_claude_command(user_prompt, settings)

        # Execute Claude Code in the pod (no timeout — local models need time)
        logger.info(
            "ClaudeCodeEngine: executing task for agent %s (role=%s)",
            agent.agent_id, agent.role,
        )
        result = pod_manager.exec_in_pod(
            agent.agent_id,
            claude_cmd,
            cwd=pod_manager.get_workdir(agent.agent_id),
            env=pod_env,
        )

        if result.exit_code != 0:
            # Fatal exit codes — process was killed (shutdown or OOM)
            if result.exit_code in (137, 139, -9):
                logger.warning(
                    "Claude Code killed (exit code %d) for agent %s",
                    result.exit_code, agent.agent_id,
                )
                raise AgentKilledError(
                    f"Claude Code was killed (exit code {result.exit_code}) "
                    f"for agent {agent.agent_id}"
                )
            logger.error(
                "Claude Code exited with code %d for agent %s: %s",
                result.exit_code, agent.agent_id,
                result.stderr[:500] if result.stderr else "(no stderr)",
            )

        # Parse the result
        output = self._parse_output(result.stdout)

        # Apply guardrail if provided
        if guardrail is not None:
            output = self._apply_guardrail(
                agent, task_prompt, output, guardrail,
                guardrail_max_retries, pod_env, settings,
            )

        return output

    def _build_user_prompt(self, description: str, expected_output: str) -> str:
        """Build the user prompt from task description and expected output."""
        return f"{description}\n\n## Expected Output\n{expected_output}"

    def _build_pod_env(self, agent: Any, settings: Any) -> dict[str, str]:
        """Build environment variables to inject into the pod."""
        from backend.security.container_runtime import get_runtime

        runtime = get_runtime(settings.SANDBOX_CONTAINER_RUNTIME)

        env = {
            "PABADA_API_URL": f"http://{runtime.host_dns}:8000",
            "PABADA_PROJECT_ID": str(agent.project_id),
            "PABADA_AGENT_ID": agent.agent_id,
        }

        # Get task_id from context if available
        from backend.tools.base.context import get_context_for_agent
        ctx = get_context_for_agent(agent.agent_id)
        if ctx and ctx.task_id:
            env["PABADA_TASK_ID"] = str(ctx.task_id)

        # Forgejo credentials for git operations (create-pr, push, etc.)
        if settings.FORGEJO_API_URL:
            env["FORGEJO_API_URL"] = settings.FORGEJO_API_URL
        if settings.FORGEJO_TOKEN:
            env["FORGEJO_TOKEN"] = settings.FORGEJO_TOKEN
        if settings.FORGEJO_OWNER:
            env["FORGEJO_OWNER"] = settings.FORGEJO_OWNER
        # FORGEJO_REPO is per-project: "project-{id}"
        env["FORGEJO_REPO"] = f"project-{agent.project_id}"

        return env

    def _build_claude_command(self, user_prompt: str, settings: Any) -> list[str]:
        """Build the claude CLI command.

        Uses ``sh -c`` wrapper so that ``$(cat ...)`` expands correctly
        inside the pod shell.
        """
        # Escape single quotes in the user prompt for shell embedding
        escaped_prompt = user_prompt.replace("'", "'\\''")
        allowed_tools = ",".join([
            "Read", "Write", "Edit", "Bash", "Glob", "Grep",
            "WebSearch", "WebFetch",
            "mcp__plugin_context7_context7__resolve-library-id",
            "mcp__plugin_context7_context7__get-library-docs",
            "mcp__pabada__task-get",
            "mcp__pabada__task-list",
            "mcp__pabada__task-create",
            "mcp__pabada__task-update-status",
            "mcp__pabada__task-take",
            "mcp__pabada__task-add-comment",
            "mcp__pabada__task-set-dependencies",
            "mcp__pabada__task-approve",
            "mcp__pabada__task-reject",
            "mcp__pabada__epic-create",
            "mcp__pabada__milestone-create",
            "mcp__pabada__chat-send",
            "mcp__pabada__chat-read",
            "mcp__pabada__chat-ask-team-lead",
            "mcp__pabada__chat-ask-project-lead",
            "mcp__pabada__finding-record",
            "mcp__pabada__finding-read",
            "mcp__pabada__finding-validate",
            "mcp__pabada__finding-reject",
            "mcp__pabada__wiki-read",
            "mcp__pabada__wiki-write",
            "mcp__pabada__query-database",
            "mcp__pabada__create-pr",
            "mcp__pabada__session-save",
            "mcp__pabada__session-load",
        ])
        cmd = (
            f"claude -p '{escaped_prompt}' "
            f"--append-system-prompt \"$(cat /tmp/pabada_system.txt)\" "
            f"--allowedTools '{allowed_tools}' "
            f"--output-format json "
            f"--model {settings.CLAUDE_CODE_MODEL}"
        )
        return ["sh", "-c", cmd]

    def _parse_output(self, stdout: str) -> str:
        """Parse Claude Code JSON output to extract the result text."""
        if not stdout.strip():
            return ""

        try:
            data = json.loads(stdout)
            # Claude Code JSON output format: {"result": "...", ...}
            if isinstance(data, dict):
                return data.get("result", data.get("content", stdout))
            elif isinstance(data, list):
                # Array of content blocks
                texts = []
                for block in data:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            texts.append(block.get("text", ""))
                        elif block.get("type") == "result":
                            texts.append(block.get("result", ""))
                return "\n".join(texts) if texts else stdout
        except json.JSONDecodeError:
            pass

        # Fall back to raw stdout
        return stdout.strip()

    def _apply_guardrail(
        self,
        agent: Any,
        task_prompt: tuple[str, str],
        output: str,
        guardrail: Any,
        max_retries: int,
        pod_env: dict[str, str],
        settings: Any,
    ) -> str:
        """Apply guardrail validation with retry loop."""
        from backend.security.pod_manager import pod_manager

        for attempt in range(max_retries):
            try:
                validation = guardrail(output)
                if validation is True or (isinstance(validation, tuple) and validation[0] is True):
                    return output
                # Guardrail returned feedback
                if isinstance(validation, tuple):
                    feedback = validation[1]
                else:
                    feedback = str(validation)
            except Exception as exc:
                feedback = f"Guardrail error: {exc}"

            if attempt >= max_retries - 1:
                logger.warning(
                    "Guardrail failed after %d attempts for agent %s, "
                    "returning last output",
                    max_retries, agent.agent_id,
                )
                return output

            # Retry with feedback
            logger.info(
                "Guardrail rejected output (attempt %d/%d) for agent %s: %s",
                attempt + 1, max_retries, agent.agent_id, str(feedback)[:200],
            )
            retry_prompt = (
                f"Your previous output was rejected by validation. "
                f"Feedback: {feedback}\n\n"
                f"Please fix your output and try again.\n\n"
                f"Original task:\n{task_prompt[0]}\n\n"
                f"Expected output:\n{task_prompt[1]}"
            )
            retry_cmd = self._build_claude_command(retry_prompt, settings)
            try:
                result = pod_manager.exec_in_pod(
                    agent.agent_id, retry_cmd,
                    cwd=pod_manager.get_workdir(agent.agent_id),
                    env=pod_env,
                )
            except RuntimeError as exc:
                logger.warning(
                    "Guardrail retry failed (pod unavailable) for agent %s: %s",
                    agent.agent_id, exc,
                )
                return output
            if result.exit_code in (137, 139, -9):
                raise AgentKilledError(
                    f"Claude Code was killed (exit code {result.exit_code}) "
                    f"for agent {agent.agent_id}"
                )
            output = self._parse_output(result.stdout)

        return output
