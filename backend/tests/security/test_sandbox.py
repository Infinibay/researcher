"""Tests for SandboxExecutor in backend/security/sandbox.py."""

from unittest.mock import MagicMock, patch

import pytest

from backend.security.resource_limits import ResourceLimits
from backend.security.sandbox import SandboxExecutor, SandboxResult


@pytest.fixture()
def mock_runtime():
    runtime = MagicMock()
    runtime.run_ephemeral.return_value = ("output", "", 0)
    return runtime


@pytest.fixture()
def mock_ws_manager():
    ws = MagicMock()
    ws.get_workspace.return_value = "/tmp/ws"
    return ws


class TestExecute:
    @patch("backend.security.sandbox.runtime_available", return_value=True)
    @patch("backend.security.sandbox.get_runtime")
    @patch("backend.security.sandbox.get_limits_for_role")
    def test_execute_calls_runtime_run_ephemeral(
        self, mock_limits, mock_get_rt, mock_rt_avail, mock_runtime, mock_ws_manager
    ):
        limits = ResourceLimits(memory="2g", cpus=2.0, pids_limit=256, timeout=300)
        mock_limits.return_value = limits
        mock_get_rt.return_value = mock_runtime

        executor = SandboxExecutor(ws_manager=mock_ws_manager)
        result = executor.execute(
            command=["python", "test.py"],
            agent_id="dev-1",
            role="developer",
        )

        mock_runtime.run_ephemeral.assert_called_once()
        call_kwargs = mock_runtime.run_ephemeral.call_args
        assert call_kwargs.kwargs["command"] == ["python", "test.py"]
        assert call_kwargs.kwargs["memory"] == "2g"
        assert call_kwargs.kwargs["cpus"] == 2.0

    @patch("backend.security.sandbox.runtime_available", return_value=False)
    def test_execute_raises_when_no_runtime(self, mock_rt_avail, mock_ws_manager):
        executor = SandboxExecutor(ws_manager=mock_ws_manager)

        with pytest.raises(RuntimeError, match="No container runtime available"):
            executor.execute(command=["echo", "hi"], agent_id="dev-1")

    @patch("backend.security.sandbox.runtime_available", return_value=True)
    @patch("backend.security.sandbox.get_runtime")
    @patch("backend.security.sandbox.get_limits_for_role")
    def test_execute_returns_sandbox_result(
        self, mock_limits, mock_get_rt, mock_rt_avail, mock_runtime, mock_ws_manager
    ):
        mock_limits.return_value = ResourceLimits(memory="1g", cpus=1.0, pids_limit=128, timeout=120)
        mock_get_rt.return_value = mock_runtime
        mock_runtime.run_ephemeral.return_value = ("output", "", 0)

        executor = SandboxExecutor(ws_manager=mock_ws_manager)
        result = executor.execute(command=["echo", "hi"], agent_id="dev-1")

        assert isinstance(result, SandboxResult)
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.timed_out is False

    @patch("backend.security.sandbox.runtime_available", return_value=True)
    @patch("backend.security.sandbox.get_runtime")
    @patch("backend.security.sandbox.get_limits_for_role")
    def test_timed_out_detection(
        self, mock_limits, mock_get_rt, mock_rt_avail, mock_runtime, mock_ws_manager
    ):
        mock_limits.return_value = ResourceLimits(memory="1g", cpus=1.0, pids_limit=128, timeout=120)
        mock_get_rt.return_value = mock_runtime
        mock_runtime.run_ephemeral.return_value = ("", "timed out", -1)

        executor = SandboxExecutor(ws_manager=mock_ws_manager)
        result = executor.execute(command=["sleep", "999"], agent_id="dev-1")

        assert result.timed_out is True
        assert result.exit_code == -1

    @patch("backend.security.sandbox.runtime_available", return_value=True)
    @patch("backend.security.sandbox.get_runtime")
    @patch("backend.security.sandbox.get_limits_for_role")
    def test_timeout_capped_by_role_limits(
        self, mock_limits, mock_get_rt, mock_rt_avail, mock_runtime, mock_ws_manager
    ):
        mock_limits.return_value = ResourceLimits(memory="1g", cpus=1.0, pids_limit=128, timeout=30)
        mock_get_rt.return_value = mock_runtime

        executor = SandboxExecutor(ws_manager=mock_ws_manager)
        executor.execute(command=["echo", "hi"], agent_id="dev-1", timeout=120)

        call_kwargs = mock_runtime.run_ephemeral.call_args.kwargs
        assert call_kwargs["timeout"] == 30  # Capped by role limit

    @patch("backend.security.sandbox.runtime_available", return_value=True)
    @patch("backend.security.sandbox.get_runtime")
    @patch("backend.security.sandbox.get_limits_for_role")
    def test_workspace_path_used_in_volume(
        self, mock_limits, mock_get_rt, mock_rt_avail, mock_runtime, mock_ws_manager
    ):
        mock_limits.return_value = ResourceLimits(memory="1g", cpus=1.0, pids_limit=128, timeout=120)
        mock_get_rt.return_value = mock_runtime
        mock_ws_manager.get_workspace.return_value = "/tmp/ws"

        executor = SandboxExecutor(ws_manager=mock_ws_manager)
        executor.execute(command=["ls"], agent_id="dev-1")

        call_kwargs = mock_runtime.run_ephemeral.call_args.kwargs
        assert any("/tmp/ws:/workspace" in v for v in call_kwargs["volumes"])
