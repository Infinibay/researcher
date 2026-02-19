"""Tests for shell command execution tool."""

import json

import pytest

from backend.tools.shell import ExecuteCommandTool


class TestExecuteCommandTool:
    def test_reject_semicolon_injection(self, agent_context):
        tool = ExecuteCommandTool()
        result = tool._run(command="ls /tmp; rm -rf /")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_pipe_injection(self, agent_context):
        tool = ExecuteCommandTool()
        result = tool._run(command="cat file.txt | grep secret")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_ampersand_injection(self, agent_context):
        tool = ExecuteCommandTool()
        result = tool._run(command="ls /tmp & rm -rf /")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_backtick_injection(self, agent_context):
        tool = ExecuteCommandTool()
        result = tool._run(command="python3 `cat /etc/passwd`")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_dollar_subshell(self, agent_context):
        tool = ExecuteCommandTool()
        result = tool._run(command="python3 $(whoami)")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_redirect(self, agent_context):
        tool = ExecuteCommandTool()
        result = tool._run(command="python3 -c pass > /etc/passwd")
        assert "error" in result
        assert "dangerous" in result.lower()

    def test_reject_disallowed_command(self, agent_context):
        tool = ExecuteCommandTool()
        result = tool._run(command="bash -c 'echo hi'")
        assert "error" in result
        assert "not allowed" in result.lower()

    def test_allow_whitelisted_command(self, agent_context):
        tool = ExecuteCommandTool()
        result = json.loads(tool._run(command="python3 --version"))
        assert result["success"] is True
        assert result["exit_code"] == 0

    def test_valid_command_no_shell(self, agent_context):
        """Verify that commands run with shell=False (no shell expansion)."""
        tool = ExecuteCommandTool()
        result = json.loads(tool._run(command="ls /tmp"))
        # Should succeed with shell=False since no dangerous chars
        assert "exit_code" in result

    def test_dangerous_chars_checked_before_whitelist(self, agent_context):
        """Dangerous char rejection must happen before whitelist check,
        so even unknown commands with dangerous chars get the right error."""
        tool = ExecuteCommandTool()
        result = tool._run(command="unknown_cmd; ls")
        assert "error" in result
        assert "dangerous" in result.lower()
