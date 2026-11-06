"""Native Git capsules must import in an isolated host without initializing the web service graph."""

import subprocess
import sys
from pathlib import Path


def test_native_broker_import_uses_only_its_isolated_dependencies():
    """A fresh -I -S process imports the actual broker without ambient packages or constructing legacy API services."""
    root = str(Path(__file__).resolve().parents[3])
    code = (
        f'import sys; sys.path.insert(0, {root!r}); '
        'from backend.runtime.peer_broker import PeerBroker; '
        'assert "backend.git.branch_service" not in sys.modules; '
        'assert "backend.config.settings" not in sys.modules; '
        'assert "pydantic" not in sys.modules'
    )
    result = subprocess.run([sys.executable, '-I', '-S', '-c', code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_existing_service_exports_keep_the_original_singletons():
    """The API uses the shared service instances rather than same-named imported Python modules."""
    from backend.api.routes import git as routes
    from backend.git import services

    for name in ('repository_manager', 'branch_service', 'pr_service', 'cleanup_service'):
        assert getattr(routes, name) is getattr(services, name)
    assert isinstance(routes.branch_service, services.BranchService)
    assert isinstance(routes.pr_service, services.PRService)
