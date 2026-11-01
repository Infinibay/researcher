"""Protocol integration, not a provisioned production actor domain or broker.

The test host publishes a real gated namespace globally before the local bind/G,
then a separate process closes it using that journal after the project DB is lost.
"""

import asyncio
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from backend.runtime.peer_guard import _info
from backend.runtime.peer_process import NamespaceIdentity, close_namespace
from backend.tests.runtime.authority_fixture import journal, provisioned
from backend.tests.runtime.test_authority_journal_crash import command
from backend.tests.runtime.test_peer_ownership import registry_setup


@pytest.mark.parametrize("lose_monitor", [False, True])
async def test_original_namespace_closes_from_global_identity_after_project_db_loss(
    coordination, tmp_path, lose_monitor
):
    authority_root = tmp_path / "global-authority"
    authority_root.mkdir(mode=0o700)
    c = provisioned(authority_root)
    registry, _run, lease = registry_setup(coordination)
    peer = registry.prepare(lease, "native")
    started, permit, late, heartbeat = (
        tmp_path / name for name in ("started", "permit-late", "late", "heartbeat")
    )
    code = """import os,sys,time
from pathlib import Path
if os.fork()==0:
 os.setsid()
 Path(sys.argv[1]).touch()
 deadline=time.monotonic()+30
 while not Path(sys.argv[2]).exists() and time.monotonic()<deadline:
  Path(sys.argv[4]).write_text(str(time.monotonic_ns()))
  time.sleep(.01)
 if Path(sys.argv[2]).exists():Path(sys.argv[3]).write_text('escaped')
 os._exit(0)
time.sleep(40)
"""
    read_fd, write_fd = os.pipe()
    process = identity = recoverer = None
    try:
        options = [] if lose_monitor else ["--die-with-parent"]
        process = await asyncio.create_subprocess_exec(
            shutil.which("bwrap"),
            "--unshare-pid",
            *options,
            "--bind",
            "/",
            "/",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--info-fd",
            str(write_fd),
            "--",
            sys.executable,
            "-I",
            "-S",
            str(Path(__file__).parents[2] / "runtime/peer_payload.py"),
            sys.executable,
            "-I",
            "-S",
            "-c",
            code,
            str(started),
            str(permit),
            str(late),
            str(heartbeat),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            pass_fds=(write_fd,),
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        )
        os.close(write_fd)
        write_fd = None
        info_fd, read_fd = read_fd, None
        info = await _info(info_fd)
        async with asyncio.timeout(3):
            while identity is None:
                try:
                    identity = NamespaceIdentity.capture(
                        info["child-pid"], expected_parent=process.pid
                    )
                except (OSError, RuntimeError):
                    await asyncio.sleep(0.01)
        with journal(c) as j:
            j.commit(
                j.load(),
                transition_id="publish-peer",
                puts={
                    "peer:owned": {
                        **asdict(identity),
                        "state": "bound",
                        "local_peer_id": peer,
                    }
                },
            )
        # This is the actual local bind; its G has not yet been sent.
        registry.bind(peer, identity)
        process.stdin.write(b"G")
        await process.stdin.drain()
        async with asyncio.timeout(3):
            while not started.exists() or not heartbeat.exists():
                await asyncio.sleep(0.01)
        coordination.conn.close()
        source = Path(coordination.database)
        source.unlink()
        for suffix in ("-wal", "-shm"):
            Path(str(source) + suffix).unlink(missing_ok=True)
        if lose_monitor:
            process.kill()
            # asyncio.wait() also waits for inherited pipes to close. Observe
            # the exact monitor's exit without waiting out its live children.
            async with asyncio.timeout(2):
                while process.returncode is None:
                    await asyncio.sleep(0.01)
        before = heartbeat.stat().st_mtime_ns
        async with asyncio.timeout(2):
            while heartbeat.stat().st_mtime_ns == before:
                await asyncio.sleep(0.01)
        # The detached writer is still alive immediately before recovery; this
        # proof must not pass because a wait for pipe EOF let it expire first.
        recoverer = await asyncio.create_subprocess_exec(
            *command(c, "--phase", "recover-peer"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        )
        async with asyncio.timeout(8):
            out, err = await recoverer.communicate()
        assert recoverer.returncode == 0, err.decode()
        assert json.loads(out)["outcome"] == "closed"
        assert not source.exists(), (
            "Recovery must not recreate or consult the lost project DB"
        )
        with journal(c) as j:
            state = j.load()
            assert (
                state.sequence == 2 and state.records["peer:owned"]["state"] == "closed"
            )
        permit.touch()
        await asyncio.sleep(0.15)
        assert not late.exists(), (
            "Detached child survived the registered namespace barrier"
        )
        await asyncio.wait_for(process.wait(), 3)
    finally:
        if recoverer is not None and recoverer.returncode is None:
            recoverer.kill()
            await recoverer.wait()
        if identity is not None:
            close_namespace(identity)
        if process is not None:
            if process.stdin is not None:
                process.stdin.close()
            if process.returncode is None:
                process.kill()
            await process.communicate()
        for fd in (read_fd, write_fd):
            if fd is not None:
                os.close(fd)
