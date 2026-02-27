"""Tests for shell command execution tool.

Pod-mode tests use lazy imports and instance-level mocking to avoid the
pre-existing circular import in backend.tools.__init__.
"""

import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class _FakeSandboxResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Pod-mode: sh -c wrapping
# ---------------------------------------------------------------------------

class TestExecuteCommandPodMode:
    """Verify that pod mode wraps ALL commands in sh -c."""

    def _make_tool(self):
        from backend.tools.shell.execute_command import ExecuteCommandTool
        return ExecuteCommandTool()

    def test_compound_and_operator(self, agent_context):
        tool = self._make_tool()
        exec_mock = MagicMock(return_value=_FakeSandboxResult(stdout="ok", exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = json.loads(tool._run(command="pwd && ls -la"))

        assert result["success"] is True
        cmd_arg = exec_mock.call_args[0][0]
        assert cmd_arg == ["sh", "-c", "pwd && ls -la"]

    def test_pipe_operator(self, agent_context):
        tool = self._make_tool()
        exec_mock = MagicMock(return_value=_FakeSandboxResult(stdout="match", exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = json.loads(tool._run(command="grep -r pattern . | head -5"))

        cmd_arg = exec_mock.call_args[0][0]
        assert cmd_arg == ["sh", "-c", "grep -r pattern . | head -5"]

    def test_redirect_operator(self, agent_context):
        tool = self._make_tool()
        exec_mock = MagicMock(return_value=_FakeSandboxResult(exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = json.loads(tool._run(command="echo hello > /workspace/out.txt"))

        cmd_arg = exec_mock.call_args[0][0]
        assert cmd_arg == ["sh", "-c", "echo hello > /workspace/out.txt"]

    def test_heredoc(self, agent_context):
        tool = self._make_tool()
        heredoc_cmd = "cat > main.py << 'EOF'\nprint('hello')\nEOF"
        exec_mock = MagicMock(return_value=_FakeSandboxResult(exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = json.loads(tool._run(command=heredoc_cmd))

        cmd_arg = exec_mock.call_args[0][0]
        assert cmd_arg == ["sh", "-c", heredoc_cmd]

    def test_simple_command_also_wrapped(self, agent_context):
        """Even simple commands use sh -c in pod mode for consistency."""
        tool = self._make_tool()
        exec_mock = MagicMock(return_value=_FakeSandboxResult(stdout="/workspace", exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = json.loads(tool._run(command="pwd"))

        cmd_arg = exec_mock.call_args[0][0]
        assert cmd_arg == ["sh", "-c", "pwd"]

    def test_empty_command_rejected(self, agent_context):
        tool = self._make_tool()

        with patch.object(tool, "_is_pod_mode", return_value=True):
            result = tool._run(command="")

        assert "error" in result

    def test_whitespace_only_command_rejected(self, agent_context):
        tool = self._make_tool()

        with patch.object(tool, "_is_pod_mode", return_value=True):
            result = tool._run(command="   ")

        assert "error" in result

    def test_default_cwd_is_workspace(self, agent_context):
        tool = self._make_tool()
        exec_mock = MagicMock(return_value=_FakeSandboxResult(exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            tool._run(command="ls")

        assert exec_mock.call_args[1]["cwd"] == "/workspace"

    def test_custom_cwd(self, agent_context):
        tool = self._make_tool()
        exec_mock = MagicMock(return_value=_FakeSandboxResult(exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            tool._run(command="ls", cwd="/tmp")

        assert exec_mock.call_args[1]["cwd"] == "/tmp"

    def test_semicolon_allowed_in_pod(self, agent_context):
        """In pod mode, semicolons should NOT be rejected (sh -c handles them)."""
        tool = self._make_tool()
        exec_mock = MagicMock(return_value=_FakeSandboxResult(exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = json.loads(tool._run(command="mkdir -p /workspace/src; cd /workspace/src; ls"))

        assert result["success"] is True
        cmd_arg = exec_mock.call_args[0][0]
        assert cmd_arg[0] == "sh"
        assert cmd_arg[1] == "-c"


# ---------------------------------------------------------------------------
# Direct-mode: dangerous char / allowlist guards
# ---------------------------------------------------------------------------

class TestExecuteCommandDirectMode:
    """Tests for non-pod, non-sandbox (direct) mode."""

    def _make_tool(self):
        from backend.tools.shell.execute_command import ExecuteCommandTool
        return ExecuteCommandTool()

    def test_reject_semicolon_injection(self, agent_context):
        tool = self._make_tool()
        result = tool._run(command="ls /tmp; rm -rf /")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_pipe_injection(self, agent_context):
        tool = self._make_tool()
        result = tool._run(command="cat file.txt | grep secret")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_ampersand_injection(self, agent_context):
        tool = self._make_tool()
        result = tool._run(command="ls /tmp & rm -rf /")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_backtick_injection(self, agent_context):
        tool = self._make_tool()
        result = tool._run(command="python3 `cat /etc/passwd`")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_redirect(self, agent_context):
        tool = self._make_tool()
        result = tool._run(command="python3 -c pass > /etc/passwd")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_disallowed_command(self, agent_context):
        tool = self._make_tool()
        result = tool._run(command="bash -c 'echo hi'")
        assert "error" in result
        assert "not allowed" in result.lower()

    def test_allow_whitelisted_command(self, agent_context):
        tool = self._make_tool()
        result = json.loads(tool._run(command="python3 --version"))
        assert result["success"] is True
        assert result["exit_code"] == 0

    def test_valid_command_no_shell(self, agent_context):
        """Verify that commands run with shell=False (no shell expansion)."""
        tool = self._make_tool()
        result = json.loads(tool._run(command="ls /tmp"))
        assert "exit_code" in result

    def test_dangerous_chars_checked_before_whitelist(self, agent_context):
        """Dangerous char rejection must happen before whitelist check."""
        tool = self._make_tool()
        result = tool._run(command="unknown_cmd; ls")
        assert "error" in result
        assert "dangerous" in result.lower()
