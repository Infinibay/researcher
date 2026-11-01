"""Real journal/cgroup/namespace/gate integration; not production enrollment."""

import json
import os
import select
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest


def test_global_publication_and_local_bind_precede_real_payload(
    broker_setup, monkeypatch
):
    s, registry, peer, broker, storage, _path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    original = registry.bind
    observed = []

    def bind(peer_id, identity):
        records = storage.load().records
        matches = [
            v
            for k, v in records.items()
            if k.startswith("broker:op:") and v["peer_id"] == peer
        ]
        assert (
            len(matches) == 1
            and matches[0]["namespace"]["init_pid"] == identity.init_pid
        )
        assert matches[0]["state"] == "published"
        assert registry.inspect(peer)["state"] == "prepared"
        observed.append("globally-published")
        return original(peer_id, identity)

    monkeypatch.setattr(registry, "bind", bind)
    started = broker.run_peer(
        registry,
        peer,
        operation_key="calculation",
        code="from pathlib import Path;print(int(Path('/run/researcher-source/fact.txt').read_text())+63)",
    )
    try:
        assert started.fresh and started.child.wait(timeout=3) == 0
        assert started.child.stdout.read() == b"200\n"
        assert observed == ["globally-published"]
        assert registry.inspect(peer)["state"] == "bound"
    finally:
        started.child.close_handles()


def test_retry_returns_receipt_without_releasing_another_gate(broker_setup):
    from backend.runtime.authority_journal import AuthorityConflict

    _s, registry, peer, broker, storage, _path = broker_setup
    first = broker.run_peer(
        registry, peer, operation_key="once", code="print('one execution')"
    )
    try:
        assert first.child.wait(timeout=3) == 0
        assert first.child.stdout.read() == b"one execution\n"
        before = storage.load().sequence
        retry = broker.run_peer(
            registry, peer, operation_key="once", code="print('one execution')"
        )
        assert (
            not retry.fresh
            and retry.child is None
            and retry.operation_id == first.operation_id
        )
        assert storage.load().sequence == before
        with pytest.raises(AuthorityConflict):
            broker.run_peer(
                registry, peer, operation_key="once", code="print('different intent')"
            )
    finally:
        first.child.close_handles()


def test_revocation_stops_namespace_before_slow_local_bind_and_never_sends_g(
    broker_setup, monkeypatch
):
    from backend.runtime.authority_journal import AuthorityConflict

    _s, registry, peer, broker, storage, path = broker_setup
    original = registry.bind
    entered = Event()
    release = Event()

    def blocked_bind(*args):
        entered.set()
        assert release.wait(4)
        return original(*args)

    monkeypatch.setattr(registry, "bind", blocked_bind)
    with ThreadPoolExecutor(2) as pool:
        start = pool.submit(
            broker.run_peer,
            registry,
            peer,
            operation_key="blocked",
            code="print('MUST NOT RUN')",
        )
        stop = None
        try:
            assert entered.wait(3)
            stop = pool.submit(broker.revoke)
            deadline = time.monotonic() + 2
            while path.exists():
                assert time.monotonic() < deadline, (
                    "Physical closure waited behind local SQL/bind"
                )
                time.sleep(0.01)
            release.set()
            with pytest.raises(AuthorityConflict):
                start.result(timeout=3)
            assert stop.result(timeout=3)["state"] == "retired"
            operations = [
                v
                for k, v in storage.load().records.items()
                if k.startswith("broker:op:")
            ]
            assert len(operations) == 1 and operations[0]["gate_sent"] is False
        finally:
            release.set()
            if stop is not None:
                stop.result(timeout=3)


def test_analysis_profile_cannot_reach_controller_files_sockets_or_write_source(
    broker_setup,
):
    s, registry, peer, broker, _storage, _path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    (s.workspace / "controller-link").symlink_to("/sys/fs/cgroup")
    code = """import json,os,socket,stat
from pathlib import Path
result={}
result['cgroup_hidden']=not Path('/sys/fs/cgroup/cgroup.procs').exists()
result['host_pid_root_hidden']=not Path('/proc/1/root/sys/fs/cgroup/cgroup.procs').exists()
result['source_link_hidden']=not Path('/run/researcher-source/controller-link/cgroup.procs').exists()
result['session_bus_hidden']=not Path('/run/user').exists()
try:socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
except PermissionError:result['unix_socket_denied']=True
try:Path('/run/researcher-source/fact.txt').write_text('changed')
except OSError:result['source_readonly']=True
result['source_fd_write_blocked']=True
for entry in list(Path('/proc/self/fd').iterdir()):
 try:
  number=int(entry.name)
  if not stat.S_ISDIR(os.fstat(number).st_mode):continue
  writer=os.open('fact.txt',os.O_WRONLY,dir_fd=number)
 except OSError:continue
 else:
  os.write(writer,b'CORRUPT')
  os.close(writer)
  result['source_fd_write_blocked']=False
print(json.dumps(result))
"""
    started = broker.run_peer(registry, peer, operation_key="boundaries", code=code)
    try:
        assert started.child.wait(timeout=3) == 0, started.child.stderr.read().decode()
        result = json.loads(started.child.stdout.read())
        assert result == dict.fromkeys(
            (
                "cgroup_hidden",
                "host_pid_root_hidden",
                "source_link_hidden",
                "session_bus_hidden",
                "unix_socket_denied",
                "source_readonly",
                "source_fd_write_blocked",
            ),
            True,
        )
        assert (s.workspace / "fact.txt").read_text() == "137"
    finally:
        started.child.close_handles()


def test_global_sql_contention_cannot_delay_physical_revocation(broker_setup):
    import sqlite3

    from backend.runtime.authority_journal import AuthorityBusy

    _s, registry, peer, broker, storage, path = broker_setup
    started = broker.run_peer(
        registry,
        peer,
        operation_key="busy",
        code="import time;print('LIVE',flush=True);time.sleep(30)",
    )
    assert started.child.stdout.readline() == b"LIVE\n"
    with sqlite3.connect(storage._paths["database"]) as writer:
        writer.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(AuthorityBusy):
                broker.revoke()
            assert not path.exists(), "Physical closure waited behind global SQL"
        finally:
            writer.rollback()
    assert broker.revoke()["state"] == "retired"


def test_lost_release_seal_preserves_observed_gate_send_in_retirement(
    broker_setup, monkeypatch
):
    _s, registry, peer, broker, storage, _path = broker_setup
    original = broker._update

    def lost(operation_id, **changes):
        if changes["state"] == "released":
            raise OSError("synthetic lost post-G seal")
        return original(operation_id, **changes)

    monkeypatch.setattr(broker, "_update", lost)
    with pytest.raises(OSError):
        broker.run_peer(
            registry,
            peer,
            operation_key="lost-g-ack",
            code="print('may have executed')",
        )
    broker.revoke()
    operations = [
        v for k, v in storage.load().records.items() if k.startswith("broker:op:")
    ]
    assert operations[0]["gate_sent"] is True, (
        "A lost receipt was reported as no dispatch"
    )


def test_recovery_cannot_adopt_a_live_broker(broker_setup):
    from backend.runtime.authority_journal import AuthorityConflict
    from backend.runtime.peer_broker import PeerBroker

    _s, registry, peer, broker, storage, _path = broker_setup
    started = broker.run_peer(
        registry,
        peer,
        operation_key="live-owner",
        code="print('READY',flush=True);input();print('STILL LIVE',flush=True)",
    )
    try:
        assert started.child.stdout.readline() == b"READY\n"
        with pytest.raises(AuthorityConflict):
            PeerBroker.recover(storage, broker.grant_id)
        started.child.stdin.write(b"continue\n")
        assert started.child.stdout.readline() == b"STILL LIVE\n"
    finally:
        try:
            started.child.wait(timeout=3)
        finally:
            started.child.close_handles()


@pytest.mark.parametrize("phase", ["before-global", "before-local", "after-g"])
def test_separate_recovery_after_broker_crash_and_project_db_loss(broker_setup, phase):
    s, _registry, peer, _broker, storage, path = broker_setup
    script = Path(__file__).with_name("fake_peer_broker.py")
    command = [sys.executable, "-I", "-S", str(script)]
    for key in ("database", "witness", "mutex"):
        command += ["--" + key, str(storage._paths[key])]
    command += ["--authority-id", storage.authority_id]
    process = subprocess.Popen(
        [
            *command,
            "--domain",
            str(path),
            "--source",
            str(s.c.database),
            "--peer",
            peer,
            "--phase",
            phase,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": os.defpath, "LANG": "C.UTF-8"},
    )
    try:
        assert select.select([process.stdout], [], [], 5)[0]
        line = process.stdout.readline()
        assert line, process.stderr.read().decode()
        metadata = json.loads(line)
        s.c.conn.close()
        source = Path(s.c.database)
        source.unlink()
        process.stdin.write(b"crash\n")
        process.stdin.flush()
        process.communicate(timeout=5)

        assert process.returncode == -signal.SIGKILL
        recovered = subprocess.run(
            [*command, "--recover", metadata["grant_id"]],
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
            capture_output=True,
            check=False,
            timeout=8,
        )
        assert recovered.returncode == 0, recovered.stderr.decode()
        assert json.loads(recovered.stdout)["state"] == "retired"
        assert not path.exists() and not source.exists()
        records = storage.load().records
        operations = [v for k, v in records.items() if k.startswith("broker:op:")]
        assert len(operations) == 1 and operations[0]["state"] == "closed"
        assert operations[0]["gate_sent"] is (False if phase != "after-g" else None)
        assert records["broker:active"] is None
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_analysis_profile_denies_raw_namespace_and_alt_abi_controls(broker_setup):
    _s, registry, peer, broker, _storage, _path = broker_setup
    code = """import ctypes,errno,json,subprocess,sys
lib=ctypes.CDLL(None,use_errno=True)
def error(number,*args):
 ctypes.set_errno(0)
 result=lib.syscall(number,*args)
 return ctypes.get_errno() if result==-1 else 0
child=subprocess.run([sys.executable,'-I','-S','-c',"import socket;socket.socket()"],capture_output=True)
print(json.dumps({'unshare':error(272,0),'clone3':error(435,0,0),'x32_socket':error(0x40000000+41,1,1,0),'descendant':b'PermissionError' in child.stderr,'child_rc':child.returncode}))
"""
    started = broker.run_peer(registry, peer, operation_key="raw-controls", code=code)
    try:
        assert started.child.wait(timeout=3) == 0, started.child.stderr.read().decode()
        result = json.loads(started.child.stdout.read())
        assert result == {
            "unshare": 1,
            "clone3": 38,
            "x32_socket": 1,
            "descendant": True,
            "child_rc": 1,
        }
    finally:
        started.child.close_handles()


def test_closing_client_transport_does_not_close_broker_supervision(broker_setup):
    _s, registry, peer, broker, _storage, _path = broker_setup
    started = broker.run_peer(
        registry,
        peer,
        operation_key="transport-close",
        code="import time;print('READY',flush=True);time.sleep(30)",
    )
    owner = broker._children[started.operation_id]
    assert started.child.stdout.readline() == b"READY\n"
    try:
        started.child.close_handles()
        assert broker.revoke()["state"] == "retired"
    finally:
        # Before the fix a client could close the owner's pidfd. Reap only this
        # exact owned child so the RED fixture does not leak a zombie.
        try:
            _, status = os.waitpid(owner.pid, 0)
        except ChildProcessError:
            pass
        else:
            owner._status = os.waitstatus_to_exitcode(status)
