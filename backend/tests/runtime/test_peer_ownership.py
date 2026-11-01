"""Real Linux process trees and SQLite; no native model or credentials."""

import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest


def registry_setup(c):
    from backend.runtime.peer_registry import PeerRegistry

    c.now[0] = time.time()
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "peer-test", lease_seconds=120)
    return PeerRegistry(c.store), run, lease


def wait_until(check, process=None):
    until = time.monotonic() + 8
    while time.monotonic() < until:
        value = check()
        if value:
            return value
        if process is not None and process.poll() is not None:
            raise AssertionError("Owned test peer exited before readiness")
        time.sleep(0.01)
    raise AssertionError("Owned test peer readiness timed out")


def launch(registry, peer_id, code, *args):
    return subprocess.Popen(
        registry.command(
            peer_id, [sys.executable, "-I", "-S", "-c", code, *map(str, args)]
        ),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def cleanup(registry, peer_id, process):
    try:
        registry.close(peer_id)
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_prepared_peer_closure_prevents_late_binding_and_payload(coordination):
    from backend.runtime.contracts import RunConflict

    registry, run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    assert registry.close(peer)["reason"] == "never_released"
    process = launch(registry, peer, "print('UNEXPECTED PAYLOAD')")
    out, _err = process.communicate(timeout=8)
    assert process.returncode != 0 and b"UNEXPECTED PAYLOAD" not in out
    assert registry.inspect(peer)["state"] == "closed"
    assert coordination.store.get(101, run.run_id).status == "running"
    replacement = registry.prepare(lease, "native")
    assert replacement != peer
    assert registry.inspect(replacement)["state"] == "prepared"
    assert registry.inspect(peer)["state"] == "closed"
    with pytest.raises(RunConflict):
        registry.prepare(lease, "native")


def test_binding_gate_preserves_the_first_rpc_frame_and_records_namespace_close(
    coordination,
):
    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    process = launch(
        registry,
        peer,
        "import sys,json; print(json.dumps(json.loads(sys.stdin.readline())),flush=True)",
    )
    wire = {"id": 19, "method": "initialize", "params": {"label": "datos con ñ"}}
    out, err = process.communicate((json.dumps(wire) + "\n").encode(), timeout=10)
    assert process.returncode == 0, err.decode()
    assert json.loads(out) == wire
    record = registry.inspect(peer)
    assert record["state"] == "closed" and record["init_pid"] > 1
    assert record["init_namespace"] != record["observer_namespace"]
    assert record["reason"] in ("init_exited", "init_absent")


def test_recovery_closes_detached_children_without_touching_another_peer(
    coordination, tmp_path
):
    registry, _run, lease = registry_setup(coordination)
    target = registry.prepare(lease, "native")
    sibling = registry.prepare(lease, "business")
    started, delayed, alive = (
        tmp_path / name for name in ("started", "delayed", "alive")
    )
    code = """import os,sys,time
from pathlib import Path
if os.fork()==0:
 os.setsid()
 Path(sys.argv[1]).write_text('ready')
 time.sleep(2)
 Path(sys.argv[2]).write_text('late')
 os._exit(0)
time.sleep(20)
"""
    one = launch(registry, target, code, started, delayed)
    two = launch(
        registry,
        sibling,
        "import sys,time;from pathlib import Path;Path(sys.argv[1]).write_text('alive');time.sleep(20)",
        alive,
    )
    try:
        wait_until(started.exists, one)
        wait_until(alive.exists, two)
        record = registry.inspect(target)
        assert record["state"] == "bound"
        proof = registry.close(target)
        assert proof["state"] == "closed"
        one.communicate(timeout=5)
        assert two.poll() is None
        time.sleep(2.2)
        assert not delayed.exists(), "A detached writer survived namespace retirement"
        assert registry.inspect(sibling)["state"] == "bound"
    finally:
        cleanup(registry, target, one)
        cleanup(registry, sibling, two)


def test_identity_mismatch_never_signals_the_reused_process(coordination, tmp_path):
    from backend.runtime.peer_process import NamespaceIdentity, close_namespace

    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    marker = tmp_path / "ready"
    process = launch(
        registry,
        peer,
        "import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(20)",
        marker,
    )
    try:
        wait_until(marker.exists, process)
        identity = NamespaceIdentity.from_record(registry.inspect(peer))
        replaced = replace(identity, start_ticks=identity.start_ticks + 1)
        assert close_namespace(replaced) == "identity_replaced"
        assert process.poll() is None
    finally:
        cleanup(registry, peer, process)


def test_stop_before_binding_never_releases_payload(coordination):
    registry, run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    coordination.store.cancel(101, run.run_id)
    process = launch(registry, peer, "print('UNEXPECTED PAYLOAD')")
    out, _err = process.communicate(timeout=8)
    assert process.returncode != 0 and b"UNEXPECTED PAYLOAD" not in out
    assert registry.inspect(peer)["state"] == "closed"


def test_proc_permission_failure_is_unknown_not_absence(monkeypatch):
    from backend.runtime.peer_process import (
        NamespaceIdentity,
        PeerUncertain,
        close_namespace,
    )

    def denied(_self, *args, **kwargs):
        raise PermissionError("procfs denied")

    monkeypatch.setattr(Path, "read_text", denied)
    identity = NamespaceIdentity(os.getpid(), 1, "boot", 12, 13)
    with pytest.raises(PeerUncertain):
        close_namespace(identity)


@pytest.mark.parametrize(
    "unavailable", [FileNotFoundError, ProcessLookupError, PermissionError]
)
def test_disappearing_proc_metadata_waits_for_the_pinned_terminal_barrier(
    coordination, tmp_path, monkeypatch, unavailable
):
    from backend.runtime import peer_process

    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    ready = tmp_path / "ready"
    process = launch(
        registry,
        peer,
        "import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(.4)",
        ready,
    )
    try:
        wait_until(ready.exists, process)
        identity = peer_process.NamespaceIdentity.from_record(registry.inspect(peer))

        def disappearing(_pid):
            raise unavailable("metadata disappeared during exit")

        with monkeypatch.context() as patch:
            patch.setattr(peer_process, "_init_fields", disappearing)
            assert peer_process.close_namespace(identity, timeout=2) == "init_exited"
        process.communicate(timeout=5)
        assert process.returncode == 0
    finally:
        cleanup(registry, peer, process)


def test_denied_metadata_of_live_init_is_unknown_and_never_signaled(
    coordination, tmp_path, monkeypatch
):
    from backend.runtime import peer_process

    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    ready = tmp_path / "ready"
    process = launch(
        registry,
        peer,
        "import sys;from pathlib import Path;Path(sys.argv[1]).touch();input();print('STILL ALIVE',flush=True)",
        ready,
    )
    try:
        wait_until(ready.exists, process)
        identity = peer_process.NamespaceIdentity.from_record(registry.inspect(peer))

        def denied(_pid):
            raise PermissionError("proc namespace not observable")

        with monkeypatch.context() as patch:
            patch.setattr(peer_process, "_init_fields", denied)
            with pytest.raises(peer_process.PeerUncertain):
                peer_process.close_namespace(identity, timeout=0.02)
        out, err = process.communicate(b"continue\n", timeout=5)
        assert process.returncode == 0, err.decode()
        assert out == b"STILL ALIVE\n", "Unverified live init was signaled"
    finally:
        cleanup(registry, peer, process)


def test_namespace_is_killed_before_waiting_for_a_busy_sqlite_writer(
    coordination, tmp_path
):
    import select
    from concurrent.futures import ThreadPoolExecutor

    from backend.runtime.peer_process import _pidfd

    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    marker = tmp_path / "ready"
    process = launch(
        registry,
        peer,
        "import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(20)",
        marker,
    )
    fd = None
    try:
        wait_until(marker.exists, process)
        fd = _pidfd(registry.inspect(peer)["init_pid"])
        poller = select.poll()
        poller.register(fd, select.POLLIN | select.POLLHUP)
        coordination.conn.execute("BEGIN IMMEDIATE")
        with ThreadPoolExecutor(max_workers=1) as pool:
            closed = pool.submit(registry.close, peer)
            try:
                assert poller.poll(1000), "Local retirement waited behind the DB writer"
            finally:
                coordination.conn.rollback()
            assert closed.result(timeout=6)["state"] == "closed"
    finally:
        coordination.conn.rollback()
        if fd is not None:
            os.close(fd)
        cleanup(registry, peer, process)


def test_guard_death_leaves_recoverable_identity_without_detached_writer(
    coordination, tmp_path
):
    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    ready, delayed = tmp_path / "ready", tmp_path / "delayed"
    process = launch(
        registry,
        peer,
        """import os,sys,time
from pathlib import Path
if os.fork()==0:
 os.setsid();Path(sys.argv[1]).touch();time.sleep(2);Path(sys.argv[2]).touch();os._exit(0)
time.sleep(20)
""",
        ready,
        delayed,
    )
    try:
        wait_until(ready.exists, process)
        process.kill()
        process.communicate(timeout=5)
        assert registry.close(peer)["reason"] in ("init_exited", "init_absent")
        time.sleep(2.2)
        assert not delayed.exists()
    finally:
        cleanup(registry, peer, process)


def test_live_peer_history_survives_cascaded_project_deletion(coordination):
    import sqlite3

    from backend.runtime.peer_registry import AttemptPeers

    c = coordination
    registry, _run, lease = registry_setup(c)
    peers = AttemptPeers.prepare(c.store, lease)
    c.conn.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(sqlite3.IntegrityError, match="Close owned peers"):
        c.conn.execute("DELETE FROM projects WHERE id=101")
    c.conn.rollback()
    assert registry.inspect(peers.ids["native"])["state"] == "prepared"
    for peer in peers.ids.values():
        registry.close(peer)
    c.conn.execute("DELETE FROM projects WHERE id=101")
    c.conn.commit()
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_peers").fetchone()[0] == 0


def test_importing_the_payload_helper_does_not_read_input_or_exec():
    process = subprocess.run(
        [sys.executable, "-c", "import backend.runtime.peer_payload;print('inert')"],
        check=False,
        input=b"",
        capture_output=True,
        timeout=3,
    )
    assert process.returncode == 0 and process.stdout.strip() == b"inert"


def test_changed_kernel_is_not_assumed_to_mean_the_original_host_rebooted(monkeypatch):
    from backend.runtime import peer_process

    identity = peer_process.NamespaceIdentity(17, 100, "old-kernel", 12, 13)
    monkeypatch.setattr(peer_process, "boot_id", lambda: "another-kernel")
    with pytest.raises(peer_process.PeerUncertain, match="kernel"):
        peer_process.close_namespace(identity)


def test_recovering_a_database_copy_cannot_close_a_peer_of_the_original(
    coordination, tmp_path
):
    import sqlite3

    from backend.runtime.peer_process import PeerUncertain
    from backend.runtime.peer_registry import PeerRegistry
    from backend.runtime.sqlite_runs import SQLiteRunStore

    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    marker = tmp_path / "ready"
    process = launch(
        registry,
        peer,
        "import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(20)",
        marker,
    )
    try:
        wait_until(marker.exists, process)
        copy = tmp_path / "copied.db"
        with sqlite3.connect(copy) as target:
            coordination.conn.backup(target)
        foreign = PeerRegistry(SQLiteRunStore(copy))
        with pytest.raises(PeerUncertain, match="database"):
            foreign.close(peer)
        assert process.poll() is None
        assert registry.inspect(peer)["state"] == "bound"
    finally:
        cleanup(registry, peer, process)


def test_rejected_namespace_metadata_cannot_retire_another_peers_init(
    coordination, tmp_path
):
    registry, _run, lease = registry_setup(coordination)
    other = registry.prepare(lease, "business")
    target = registry.prepare(lease, "native")
    marker = tmp_path / "other-ready"
    sibling = launch(
        registry,
        other,
        "import sys,time;from pathlib import Path;Path(sys.argv[1]).touch();time.sleep(20)",
        marker,
    )
    process = None
    try:
        wait_until(marker.exists, sibling)
        record = registry.inspect(other)
        fake = tmp_path / "bin"
        fake.mkdir()
        info = json.dumps(
            {
                "child-pid": record["init_pid"],
                "pid-namespace": record["init_namespace"] + 1,
            }
        ).encode()
        executable = fake / "bwrap"
        executable.write_text(
            "#!"
            + sys.executable
            + "\nimport os,sys,time\nfd=int(sys.argv[sys.argv.index('--info-fd')+1])\nos.write(fd,"
            + repr(info)
            + ")\nos.close(fd)\ntime.sleep(20)\n"
        )
        executable.chmod(0o755)
        process = subprocess.Popen(
            registry.command(target, [sys.executable, "-c", "print('UNEXPECTED')"]),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            env={**os.environ, "PATH": str(fake) + os.pathsep + os.environ["PATH"]},
        )
        out, _err = process.communicate(timeout=8)
        assert process.returncode != 0 and b"UNEXPECTED" not in out
        assert sibling.poll() is None, (
            "Rejected metadata was reused as a shutdown target"
        )
    finally:
        if process is not None:
            cleanup(registry, target, process)
        cleanup(registry, other, sibling)
