"""Tests for PodManager — persistent per-agent containers.

Note: these tests must run as part of the full test suite (not standalone)
due to the pre-existing circular import in backend.tools/__init__.py.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def mock_runtime():
    """Provide a mock ContainerRuntime."""
    runtime = MagicMock()
    runtime.is_podman = True
    runtime.is_container_running.return_value = False
    runtime.run_detached.return_value = "abc123"
    runtime.exec_command.return_value = ("output", "", 0)
    runtime.stop_container.return_value = True
    runtime.remove_container.return_value = True
    return runtime


@pytest.fixture()
def pm(mock_runtime, monkeypatch):
    """Provide a PodManager with mocked runtime and settings."""
    monkeypatch.setenv("INFINIBAY_SANDBOX_ENABLED", "true")

    from backend.security.pod_manager import PodManager
    manager = PodManager()
    with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime), \
         patch("backend.security.pod_manager.runtime_available", return_value=True):
        yield manager


class TestStartPod:
    def test_start_creates_new_pod(self, pm, mock_runtime):
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            info = pm.start_pod("dev_1_p1", "developer", "/tmp/ws")

        assert info.agent_id == "dev_1_p1"
        assert info.container_name == "infinibay-pod-dev_1_p1"
        assert info.container_id == "abc123"
        assert info.workspace_path == "/tmp/ws"
        assert info.role == "developer"
        mock_runtime.run_detached.assert_called_once()

    def test_start_is_idempotent(self, pm, mock_runtime):
        """Starting a pod twice reuses the existing one."""
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            info1 = pm.start_pod("dev_1_p1", "developer", "/tmp/ws")
            # Pod is now "running"
            mock_runtime.is_container_running.return_value = True
            info2 = pm.start_pod("dev_1_p1", "developer", "/tmp/ws")

        assert info1.container_id == info2.container_id
        # run_detached called only once
        assert mock_runtime.run_detached.call_count == 1

    def test_start_recreates_dead_pod(self, pm, mock_runtime):
        """If pod died, remove and recreate."""
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws")
            # Pod dies
            mock_runtime.is_container_running.return_value = False
            mock_runtime.run_detached.return_value = "def456"
            info = pm.start_pod("dev_1_p1", "developer", "/tmp/ws")

        assert info.container_id == "def456"
        assert mock_runtime.run_detached.call_count == 2


class TestExecInPod:
    def test_exec_returns_result(self, pm, mock_runtime):
        mock_runtime.exec_command.return_value = ("hello\n", "", 0)

        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws")
            mock_runtime.is_container_running.return_value = True
            result = pm.exec_in_pod("dev_1_p1", ["echo", "hello"])

        from backend.security.pod_manager import SandboxResult
        assert isinstance(result, SandboxResult)
        assert result.stdout == "hello\n"
        assert result.exit_code == 0
        assert not result.timed_out

    def test_exec_detects_timeout(self, pm, mock_runtime):
        mock_runtime.exec_command.return_value = ("", "Command timed out after 10s", -1)

        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws")
            mock_runtime.is_container_running.return_value = True
            result = pm.exec_in_pod("dev_1_p1", ["sleep", "999"])

        assert result.timed_out
        assert result.exit_code == -1

    def test_exec_raises_without_pod(self, pm):
        with pytest.raises(RuntimeError, match="No pod registered"):
            pm.exec_in_pod("nonexistent", ["echo", "hi"])

    def test_exec_auto_restarts_dead_pod(self, pm, mock_runtime):
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws")
            # Pod is running for start, then dies before exec
            mock_runtime.is_container_running.side_effect = [False, False, True]
            mock_runtime.run_detached.return_value = "restarted123"
            mock_runtime.exec_command.return_value = ("ok", "", 0)

            result = pm.exec_in_pod("dev_1_p1", ["echo", "ok"])

        assert result.stdout == "ok"
        # run_detached called twice (initial + restart)
        assert mock_runtime.run_detached.call_count == 2


class TestStopPod:
    def test_stop_removes_pod(self, pm, mock_runtime):
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws")
            stopped = pm.stop_pod("dev_1_p1")

        assert stopped
        mock_runtime.stop_container.assert_called_once_with("infinibay-pod-dev_1_p1")

    def test_stop_nonexistent_returns_false(self, pm):
        assert not pm.stop_pod("nonexistent")

    def test_stop_all(self, pm, mock_runtime):
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws1")
            mock_runtime.is_container_running.return_value = False
            pm.start_pod("dev_2_p1", "developer", "/tmp/ws2")

            count = pm.stop_all()

        assert count == 2
        assert pm.list_pods() == []


class TestListPods:
    def test_list_shows_active_pods(self, pm, mock_runtime):
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws1")
            mock_runtime.is_container_running.return_value = False
            pm.start_pod("dev_2_p1", "developer", "/tmp/ws2")

        pods = pm.list_pods()
        assert len(pods) == 2
        agent_ids = {p.agent_id for p in pods}
        assert agent_ids == {"dev_1_p1", "dev_2_p1"}


class TestIsPodRunning:
    def test_running_pod(self, pm, mock_runtime):
        with patch("backend.security.pod_manager.get_runtime", return_value=mock_runtime):
            pm.start_pod("dev_1_p1", "developer", "/tmp/ws")
            mock_runtime.is_container_running.return_value = True
            assert pm.is_pod_running("dev_1_p1")

    def test_not_running(self, pm):
        assert not pm.is_pod_running("nonexistent")
