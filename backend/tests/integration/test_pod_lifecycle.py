"""Integration tests for pod lifecycle.

These tests require a container runtime (podman/docker) and are
skipped when running in CI without one.

Run explicitly with: pytest -m integration backend/tests/integration/test_pod_lifecycle.py
"""

import subprocess

import pytest


def _sandbox_image_available():
    """Check runtime AND sandbox image exist without triggering __init__ import chain."""
    try:
        from backend.security.container_runtime import runtime_available
        if not runtime_available():
            return False
        # Also check that the sandbox image is built
        result = subprocess.run(
            ["podman", "image", "exists", "pabada-sandbox:latest"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (ImportError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _sandbox_image_available(),
    reason="No container runtime or sandbox image available",
)


@pytest.mark.integration
class TestPodLifecycle:
    """End-to-end pod lifecycle tests (requires container runtime)."""

    def test_start_exec_stop(self, tmp_path):
        """Start a pod, exec a command, stop it."""
        from backend.security.pod_manager import PodManager

        pm = PodManager()
        workspace = str(tmp_path)

        # Write a test file in workspace
        (tmp_path / "hello.txt").write_text("hello from host")

        try:
            info = pm.start_pod(
                agent_id="test_dev_1",
                role="developer",
                workspace_path=workspace,
            )
            assert info.container_name == "pabada-pod-test_dev_1"

            # Exec a command
            result = pm.exec_in_pod(
                "test_dev_1",
                ["cat", "/workspace/hello.txt"],
            )
            assert result.exit_code == 0
            assert "hello from host" in result.stdout

            # Check pod is running
            assert pm.is_pod_running("test_dev_1")

            # List pods
            pods = pm.list_pods()
            assert any(p.agent_id == "test_dev_1" for p in pods)

        finally:
            pm.stop_pod("test_dev_1")

        assert not pm.is_pod_running("test_dev_1")

    def test_idempotent_start(self, tmp_path):
        """Starting a pod twice returns the same pod."""
        from backend.security.pod_manager import PodManager

        pm = PodManager()
        workspace = str(tmp_path)

        try:
            info1 = pm.start_pod("test_dev_2", "developer", workspace)
            info2 = pm.start_pod("test_dev_2", "developer", workspace)
            assert info1.container_id == info2.container_id
        finally:
            pm.stop_pod("test_dev_2")

    def test_exec_with_stdin(self, tmp_path):
        """Exec with stdin data works."""
        from backend.security.pod_manager import PodManager

        pm = PodManager()

        try:
            pm.start_pod("test_dev_3", "developer", str(tmp_path))
            result = pm.exec_in_pod(
                "test_dev_3",
                ["python3", "-c", "import sys; print(sys.stdin.read().upper())"],
                stdin_data="hello",
            )
            assert result.exit_code == 0
            assert "HELLO" in result.stdout
        finally:
            pm.stop_pod("test_dev_3")
