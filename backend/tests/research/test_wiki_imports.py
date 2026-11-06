"""Fresh imports expose package cycles that an already initialized API can conceal."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_knowledge_entry_points_import_independently_without_incidental_engine_order():
    """Native wiki and its package entry load no framework memory, model stack or retired catalog."""
    root = Path(__file__).resolve().parents[3]
    dependencies = Path(pytest.__file__).resolve().parent.parent
    probe = """
import sys
sys.path[:0]=sys.argv[1:3]
import pytest_socket
pytest_socket.disable_socket(allow_unix_socket=True)
from backend.knowledge.wiki import WikiStore
import backend.knowledge
assert 'crewai' not in sys.modules and 'litellm' not in sys.modules
assert not hasattr(backend.knowledge,'KnowledgeService')
assert not hasattr(backend.knowledge,'WikiKnowledgeSource')
"""
    env = {
        key: value
        for key, value in os.environ.items()
        if "API_KEY" not in key
        and key not in ("INFINIBAY_RUNTIME_CONFIG", "INFINIBAY_RETRIEVAL_ASSET_DIR")
    }
    env.update(CREWAI_TELEMETRY_DISABLED="true", OTEL_SDK_DISABLED="true")
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", probe, str(root), str(dependencies)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
