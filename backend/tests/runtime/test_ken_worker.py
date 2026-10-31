"""Our OS boundary, exercised with a synthetic Ken-shaped tool installation.

Published Ken itself is checked separately by the explicit security probe.
"""

import json
import socket
import subprocess
import sys
import venv

import pytest


@pytest.fixture
def ken_installation(tmp_path):
    tool = tmp_path / "tool"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(tool)
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    packages = tool / "lib" / version / "site-packages"
    metadata = packages / "ken_rank-0.18.0.dist-info"
    metadata.mkdir(parents=True)
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: ken-rank\nVersion: 0.18.0\n"
    )
    package = packages / "ken"
    package.mkdir()
    (package / "__init__.py").write_text("")
    executable = tool / "bin/ken"
    executable.write_text(
        "#!"
        + str(tool / "bin/python")
        + "\n"
        + """
import json, os, socket, sys
from pathlib import Path
root=Path(sys.argv[2])
result={"inside":(root/"source.py").read_text(),"credentials_present":[key for key in os.environ if key in {"OPENAI_API_KEY","RESEARCHER_TOOL_TOKEN","HF_TOKEN","CODEX_HOME"}]}
try: result["outside"]=(root/"escape.py").read_text()
except OSError: result["outside"]="denied"
try: (root/"source.py").write_text("unwanted")
except OSError: result["source_write"]="denied"
(root/".ken/worker-note").write_text("retained")
try: socket.create_connection(("127.0.0.1",int((root/".ken/fixture-port").read_text())),timeout=.1); result["network"]="available"
except OSError: result["network"]="unavailable"
result["leaked_handle_reads"]=[]
for fd in range(3,128):
    try: result["leaked_handle_reads"].append(Path(f"/proc/self/fd/{fd}/../owner.key").read_text())
    except OSError: pass
result["home"]=os.environ["HOME"]
print(json.dumps(result))
"""
    )
    executable.chmod(0o755)
    return executable


@pytest.mark.allow_hosts(["127.0.0.1"])
def test_ken_worker_mounts_only_selected_source_and_own_state(
    ken_installation, tmp_path, monkeypatch
):
    from backend.runtime.ken_worker import KenInstallation, worker_process

    workspace = tmp_path / "alpha"
    workspace.mkdir()
    (workspace / "source.py").write_text("ALPHA_ONLY")
    outside = tmp_path / "owner.key"
    outside.write_text("FAKE_CONTROL_SECRET")
    (workspace / "escape.py").symlink_to(outside)
    installation = KenInstallation.inspect(ken_installation)
    monkeypatch.setenv("OPENAI_API_KEY", "FAKE_KEY")
    monkeypatch.setenv("RESEARCHER_TOOL_TOKEN", "FAKE_GRANT")
    monkeypatch.setenv("HF_TOKEN", "FAKE_HF_SECRET")
    monkeypatch.setenv("CODEX_HOME", "/fake-managed-login")
    (workspace / ".ken").mkdir()
    with (
        socket.socket() as listener,
        worker_process(installation, workspace=workspace) as launch,
    ):
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        (workspace / ".ken/fixture-port").write_text(str(listener.getsockname()[1]))
        result = subprocess.run(
            launch.command,
            env=launch.env,
            pass_fds=launch.pass_fds,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["inside"] == "ALPHA_ONLY"
    assert output["outside"] == "denied"
    assert output["source_write"] == "denied"
    assert output["credentials_present"] == []
    assert output["network"] == "unavailable"
    assert output["leaked_handle_reads"] == []
    assert (workspace / "source.py").read_text() == "ALPHA_ONLY"
    assert (workspace / ".ken/worker-note").read_text() == "retained"
    assert "FAKE_CONTROL_SECRET" not in result.stdout


def test_ken_state_symlink_never_becomes_a_foreign_writable_mount(
    ken_installation, tmp_path
):
    from backend.runtime.ken_worker import KenInstallation, worker_process

    workspace = tmp_path / "alpha"
    workspace.mkdir()
    beta = tmp_path / "beta"
    beta.mkdir()
    (workspace / ".ken").symlink_to(beta, target_is_directory=True)
    with (
        pytest.raises(ValueError, match="state|symlink"),
        worker_process(
            KenInstallation.inspect(ken_installation), workspace=workspace, mode="mcp"
        ),
    ):
        pass
    assert list(beta.iterdir()) == []


def test_untrusted_workspace_cannot_contain_the_tool_installation(
    ken_installation, tmp_path
):
    from backend.runtime.ken_worker import KenInstallation, worker_process

    with (
        pytest.raises(ValueError, match="installation"),
        worker_process(
            KenInstallation.inspect(ken_installation), workspace=tmp_path, mode="mcp"
        ),
    ):
        pass


def test_ken_installation_rejects_wrong_version_before_worker_start(ken_installation):
    from backend.runtime.ken_worker import KenInstallation

    metadata = next(
        ken_installation.parent.parent.glob(
            "lib/python*/site-packages/*.dist-info/METADATA"
        )
    )
    metadata.write_text("Metadata-Version: 2.1\nName: ken-rank\nVersion: 0.17.0\n")
    with pytest.raises(ValueError, match="0.18.0"):
        KenInstallation.inspect(ken_installation)


def test_swapping_state_after_admission_cannot_mount_the_foreign_directory(
    ken_installation, tmp_path
):
    from backend.runtime.ken_worker import KenInstallation, worker_process

    workspace = tmp_path / "alpha"
    workspace.mkdir()
    (workspace / "source.py").write_text("ALPHA_ONLY")
    beta = tmp_path / "beta"
    beta.mkdir()
    (beta / "sentinel").write_text("BETA_ONLY")
    with worker_process(
        KenInstallation.inspect(ken_installation), workspace=workspace
    ) as launch:
        (workspace / ".ken/fixture-port").write_text("1")
        (workspace / ".ken").rename(workspace / ".ken-before-swap")
        (workspace / ".ken").symlink_to(beta, target_is_directory=True)
        result = subprocess.run(
            launch.command,
            env=launch.env,
            pass_fds=launch.pass_fds,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    assert {p.name: p.read_text() for p in beta.iterdir()} == {"sentinel": "BETA_ONLY"}
    if result.returncode == 0:
        assert (workspace / ".ken-before-swap/worker-note").read_text() == "retained"
        assert json.loads(result.stdout)["leaked_handle_reads"] == []


@pytest.mark.parametrize("corrupted", [False, True])
def test_only_pinned_public_model_bytes_are_mounted(
    ken_installation, tmp_path, corrupted
):
    import hashlib
    from dataclasses import replace

    from backend.runtime.ken_worker import KenInstallation, worker_process

    workspace = tmp_path / "alpha"
    workspace.mkdir()
    (workspace / "source.py").write_text("ALPHA_ONLY")
    (workspace / ".ken").mkdir()
    (workspace / ".ken/fixture-port").write_text("1")
    cache = tmp_path / "public-cache"
    cache.mkdir()
    (cache / "token").write_text("FAKE_HF_TOKEN")
    revision = "1" * 40
    file = cache / "models--owner--public" / "snapshots" / revision / "model.bin"
    file.parent.mkdir(parents=True)
    expected = b"REGISTERED_PUBLIC_BYTES"
    file.write_bytes(b"X" * len(expected) if corrupted else expected)
    assets = {
        "model_id": "owner/public",
        "revision": revision,
        "artifacts": {
            "model.bin": {
                "bytes": len(expected),
                "sha256": hashlib.sha256(expected).hexdigest(),
            }
        },
    }
    installation = replace(KenInstallation.inspect(ken_installation), assets=(assets,))
    if corrupted:
        with (
            pytest.raises(ValueError, match="artifact"),
            worker_process(installation, workspace=workspace, model_cache=cache),
        ):
            pass
        return
    executable = ken_installation
    executable.write_text(
        executable.read_text()
        + """
from pathlib import Path
assert Path("/opt/researcher-ken-models/hub/models--owner--public/snapshots/"+"1"*40+"/model.bin").read_bytes()==b"REGISTERED_PUBLIC_BYTES"
assert not Path("/opt/researcher-ken-models/hub/token").exists()
"""
    )
    with worker_process(installation, workspace=workspace, model_cache=cache) as launch:
        result = subprocess.run(
            launch.command,
            env=launch.env,
            pass_fds=launch.pass_fds,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr
