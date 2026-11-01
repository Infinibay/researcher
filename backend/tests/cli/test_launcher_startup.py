"""Exercise the actual shell entry with all external services replaced by guards."""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_launcher_refuses_uninitialized_database_before_external_work(tmp_path, kind):
    repo = Path(__file__).resolve().parents[3]
    launcher = tmp_path / "start.sh"
    shutil.copyfile(repo / "start.sh", launcher)
    database = tmp_path / "data" / "source.db"
    if kind == "empty":
        database.parent.mkdir()
        database.touch()
    tools = tmp_path / "tools"
    tools.mkdir()
    marker = tmp_path / "external-work"
    python = tools / "python3"
    python.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n')
    python.chmod(0o700)
    for name in ("docker", "podman", "podman-compose", "curl", "ollama", "npm", "uv"):
        tool = tools / name
        tool.write_text(
            "#!/bin/sh\nprintf reached > " + shlex.quote(str(marker)) + "\nexit 97\n"
        )
        tool.chmod(0o700)
    env = dict(os.environ) | {
        "INFINIBAY_DB": str(database),
        "INFINIBAY_LLM_PROVIDER": "openai",
        "INFINIBAY_EMBEDDING_PROVIDER": "default",
        "PYTHONPATH": str(repo),
        "PATH": str(tools) + os.pathsep + "/usr/bin:/bin",
    }
    result = subprocess.run(
        ["/bin/bash", str(launcher)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert not marker.exists(), (
        "Launcher reached external work before validating source state"
    )
    assert not (tmp_path / ".pids").exists()
    assert "init-db" in result.stdout + result.stderr
    if kind == "missing":
        assert not database.parent.exists()
    else:
        assert database.read_bytes() == b""
