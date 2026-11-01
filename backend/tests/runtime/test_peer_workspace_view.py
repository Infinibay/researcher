"""Actual gated namespaces must keep the admitted object, not re-resolve its name."""

import os
import shutil
import subprocess
import sys
import time

import pytest

from backend.runtime.workspaces import PEER_WORKSPACE
from backend.tests.runtime.test_peer_ownership import cleanup, launch


def bound_peer(setup, kind):
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.workspaces import WorkspaceRegistry

    c = setup.c
    c.now[0] = time.time()
    binding = WorkspaceRegistry(c.database, setup.root).bind(101, 11)
    run = c.store.admit(c.spec, binding=binding)
    lease, peers = AttemptPeers.claim(
        c.store, 101, run.run_id, "owner", lease_seconds=120
    )
    peer = (
        peers.ids["native"] if kind == "native" else peers.registry.prepare(lease, kind)
    )
    return peers.registry, peer


@pytest.mark.parametrize("kind", ["native", "command"])
def test_peer_rejects_replacement_before_open_without_executing_payload(
    service_setup, kind
):
    s = service_setup
    registry, peer = bound_peer(s, kind)
    retired = s.root / "retired"
    s.workspace.rename(retired)
    s.workspace.mkdir()
    marker = s.workspace / "payload-ran"
    process = launch(
        registry,
        peer,
        "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('BAD');print('SUBSTITUTE')",
        marker,
    )
    try:
        out, err = process.communicate(timeout=10)
        assert process.returncode != 0, (out, err)
        assert not marker.exists()
        assert b"SUBSTITUTE" not in out
        assert registry.inspect(peer)["state"] == "closed"
    finally:
        cleanup(registry, peer, process)


@pytest.mark.parametrize("kind", ["native", "command"])
def test_peer_mounts_opened_directory_when_name_is_replaced_before_bwrap(
    service_setup, kind
):
    s = service_setup
    (s.workspace / "identity").write_text("ADMITTED")
    registry, peer = bound_peer(s, kind)
    retired = s.root / "retired"
    binary = shutil.which("bwrap")
    assert binary
    shim_root = s.root.parent / "trusted-bwrap-test-shim"
    shim_root.mkdir()
    shim = shim_root / "bwrap"
    shim.write_text(
        "#!"
        + sys.executable
        + "\nimport os,sys\nfrom pathlib import Path\n"
        + "root=Path("
        + repr(str(s.workspace))
        + ")\n"
        + "root.rename("
        + repr(str(retired))
        + ")\nroot.mkdir()\n"
        + "(root/'identity').write_text('SUBSTITUTE')\n"
        + "os.execv("
        + repr(binary)
        + ",["
        + repr(binary)
        + ",*sys.argv[1:]])\n"
    )
    shim.chmod(0o700)
    code = (
        "from pathlib import Path;import sys;root=Path(sys.argv[1]);"
        "print((root/'identity').read_text());(root/'effect').write_text('ADMITTED_EFFECT')"
    )
    process = subprocess.Popen(
        registry.command(
            peer, [sys.executable, "-I", "-S", "-c", code, str(PEER_WORKSPACE)]
        ),
        env={"PATH": str(shim_root) + os.pathsep + os.defpath},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = process.communicate(timeout=10)
        assert process.returncode == 0, err.decode()
        assert out == b"ADMITTED\n"
        assert (retired / "effect").read_text() == "ADMITTED_EFFECT"
        assert (s.workspace / "identity").read_text() == "SUBSTITUTE"
        assert not (s.workspace / "effect").exists()
        assert registry.inspect(peer)["state"] == "closed"
    finally:
        cleanup(registry, peer, process)


@pytest.mark.parametrize("kind", ["native", "command"])
@pytest.mark.parametrize("renamed", ["source", "parent"])
def test_peer_keeps_its_view_after_gate_even_when_host_name_is_replaced(
    service_setup, kind, renamed
):
    import select

    s = service_setup
    (s.workspace / "identity").write_text("ADMITTED")
    registry, peer = bound_peer(s, kind)
    code = (
        "from pathlib import Path;import sys;root=Path(sys.argv[1]);"
        "print('READY',flush=True);sys.stdin.readline();"
        "print((root/'identity').read_text(),flush=True);"
        "(root/'effect').write_text('ADMITTED_EFFECT')"
    )
    process = launch(registry, peer, code, PEER_WORKSPACE)
    try:
        assert select.select([process.stdout], [], [], 8)[0]
        assert process.stdout.readline() == b"READY\n"
        if renamed == "parent":
            moved_parent = s.root.parent / "retired-parent"
            s.root.rename(moved_parent)
            retired = moved_parent / s.workspace.name
            s.root.mkdir()
        else:
            retired = s.root / "retired"
            s.workspace.rename(retired)
        s.workspace.mkdir()
        (s.workspace / "identity").write_text("SUBSTITUTE")
        out, err = process.communicate(b"continue\n", timeout=10)
        assert process.returncode == 0, err.decode()
        assert out == b"ADMITTED\n"
        assert (retired / "effect").read_text() == "ADMITTED_EFFECT"
        assert not (s.workspace / "effect").exists()
    finally:
        cleanup(registry, peer, process)
