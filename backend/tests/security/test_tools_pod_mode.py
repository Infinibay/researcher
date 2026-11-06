"""Tests for tool pod mode integration.

Verifies that tools correctly delegate to pod_manager.exec_in_pod
when SANDBOX_ENABLED is true (sandbox/pod mode).

These tests mock `_exec_in_pod` on each tool instance to bypass the
lazy import of pod_manager, avoiding the pre-existing circular import.
"""

import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class _MockSandboxResult:
    """Local stand-in for pod_manager.SandboxResult."""
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def _make(stdout="", stderr="", exit_code=0, timed_out=False):
    return _MockSandboxResult(
        stdout=stdout, stderr=stderr,
        exit_code=exit_code, timed_out=timed_out,
    )


@pytest.fixture(autouse=True)
def _set_agent_context():
    """Set agent context so _validate_agent_context() passes."""
    from backend.tools.base.context import set_context
    set_context(project_id=1, agent_id="dev_1_p1")








class TestExecuteCommandPodMode:
    def test_command_runs_in_pod(self):
        from backend.tools.shell.execute_command import ExecuteCommandTool
        tool = ExecuteCommandTool()

        exec_mock = MagicMock(return_value=_make(stdout="ok\n", exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = tool._run(command="echo ok")

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["stdout"] == "ok\n"
        # Verify sh -c wrapping
        cmd_arg = exec_mock.call_args[0][0]
        assert cmd_arg == ["sh", "-c", "echo ok"]

    def test_no_whitelist_in_pod_mode(self):
        """In pod mode, non-whitelisted commands should be allowed."""
        from backend.tools.shell.execute_command import ExecuteCommandTool
        tool = ExecuteCommandTool()

        exec_mock = MagicMock(return_value=_make(stdout="ok\n", exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock), \
             patch.object(tool, "_log_tool_usage"):
            result = tool._run(command="custom_binary --flag")

        parsed = json.loads(result)
        assert parsed["success"] is True


class TestCodeInterpreterPodMode:
    def test_code_runs_via_stdin(self):
        from backend.tools.shell.code_interpreter import CodeInterpreterTool
        tool = CodeInterpreterTool()

        exec_mock = MagicMock(return_value=_make(stdout="42\n", exit_code=0))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock):
            result = tool._run(code="print(42)")

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["stdout"] == "42\n"

        args, kwargs = exec_mock.call_args
        assert args[0] == ["python3", "-"]
        assert kwargs["stdin_data"] == "print(42)"


class TestGitStatusPodMode:
    def test_status_runs_in_pod(self):
        from backend.tools.git.status import GitStatusTool
        tool = GitStatusTool()

        exec_mock = MagicMock(side_effect=[
            _make(stdout=" M file.py\n?? new.txt\n", exit_code=0),
            _make(stdout="feature-branch\n", exit_code=0),
        ])

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock):
            result = tool._run()

        parsed = json.loads(result)
        assert parsed["branch"] == "feature-branch"
        assert len(parsed["modified"]) == 1
        assert len(parsed["untracked"]) == 1


class TestGitDiffPodMode:
    def test_diff_runs_in_pod(self):
        from backend.tools.git.diff import GitDiffTool
        tool = GitDiffTool()

        exec_mock = MagicMock(return_value=_make(
            stdout="diff --git a/file.py b/file.py\n", exit_code=0,
        ))

        with patch.object(tool, "_is_pod_mode", return_value=True), \
             patch.object(tool, "_exec_in_pod", exec_mock):
            result = tool._run()

        assert "diff --git" in result
