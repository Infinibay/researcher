"""Real wire/subprocess integration; native sandbox behavior has separate live probes."""

import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from backend.runtime.codex_rpc import StdioRpcClient


def executor(c, workspace):
    from backend.runtime.command_jobs import OwnedCommandExecutor

    return OwnedCommandExecutor(
        StdioRpcClient(
            (
                sys.executable,
                "-u",
                str(Path(__file__).with_name("fake_command_server.py")),
            ),
            cwd=workspace,
            env={"PATH": os.defpath, "HOME": str(workspace)},
            request_timeout=2,
            close_timeout=0.1,
        ),
        journal=c.store,
        workspace=workspace,
        monitor_interval=0.02,
        cancel_grace=0.2,
    )


def claim(c):
    run = c.store.admit(c.spec)
    return c.store.claim(101, run.run_id, "worker", lease_seconds=30)


def command(c, code, **kwargs):
    return c.contracts.CommandSpec(argv=(sys.executable, "-c", code), **kwargs)


async def wait_file(path):
    async with asyncio.timeout(3):
        while not path.exists():
            await asyncio.sleep(0.01)


async def test_stream_tail_is_persisted_before_the_terminal_receipt(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    from backend.tests.runtime.command_helpers import (
        PausedOutputExecutor,
        ReplyObservedClient,
    )

    gate, received = asyncio.Event(), asyncio.Event()
    rpc = ReplyObservedClient(
        (sys.executable, "-u", str(Path(__file__).with_name("fake_command_server.py"))),
        cwd=tmp_path,
        env={"PATH": os.defpath, "HOME": str(tmp_path)},
        request_timeout=2,
        close_timeout=0.1,
        reply_received=received,
    )
    async with PausedOutputExecutor(
        rpc, journal=c.store, workspace=tmp_path, output_gate=gate
    ) as worker:
        handle = await worker.start(
            lease,
            "output-1",
            command(
                c,
                "import sys; sys.stdout.write('x'*8192+'COUNTEREVIDENCE_AT_END'); sys.stderr.write('actual stderr')",
            ),
        )
        pending = asyncio.create_task(handle.wait())
        try:
            await asyncio.wait_for(received.wait(), 2)
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(pending), 0.1)
        finally:
            gate.set()
        result = await pending
        assert result.status == "exited" and result.exit_code == 0
        assert result.stdout == b"x" * 8192 + b"COUNTEREVIDENCE_AT_END"
        assert result.stderr == b"actual stderr"
        assert c.store.get_job(101, handle.job_id) == result


async def test_retry_on_the_same_peer_never_executes_the_command_twice(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    spec = command(
        c,
        "from pathlib import Path; p=Path('effects'); p.write_text((p.read_text() if p.exists() else '')+'x')",
    )
    async with executor(c, tmp_path) as worker:
        first = await worker.start(lease, "write-once", spec)
        await first.wait()
        again = await worker.start(lease, "write-once", spec)
        assert again.job_id == first.job_id
        assert (await again.wait()).exit_code == 0
    assert (tmp_path / "effects").read_text() == "x"


async def test_an_executor_cannot_be_shared_by_another_run_or_attempt(
    coordination, tmp_path
):
    c = coordination
    first = claim(c)
    other = c.store.admit(replace(c.spec, task_id=1002, operation_key="other-request"))
    second = c.store.claim(101, other.run_id, "other-owner", lease_seconds=30)
    async with executor(c, tmp_path) as worker:
        handle = await worker.start(
            first, "first-command", command(c, "print('first')")
        )
        await handle.wait()
        with pytest.raises(c.contracts.RunConflict):
            await worker.start(second, "wrong-context", command(c, "print('second')"))


async def test_durable_stop_cancels_actual_owned_command_and_keeps_attempt_unaccepted(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with executor(c, tmp_path) as worker:
        handle = await worker.start(
            lease,
            "slow",
            command(
                c,
                "from pathlib import Path; import time; Path('started').write_text('1'); time.sleep(0.8); Path('delayed').write_text('bad')",
            ),
        )
        await wait_file(tmp_path / "started")
        await asyncio.to_thread(c.store.cancel, 101, lease.run_id)
        result = await asyncio.wait_for(handle.wait(), 2)
        assert result.status == "exited"
        assert result.exit_code != 0
        assert result.cancel_requested
        assert c.store.get(101, lease.run_id).status == "cancelling"
        await asyncio.sleep(0.85)
        assert not (tmp_path / "delayed").exists()


async def test_expired_lease_stops_owned_command_without_waiting_for_expiry_sweep(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with executor(c, tmp_path) as worker:
        handle = await worker.start(
            lease,
            "expired",
            command(
                c,
                "from pathlib import Path; import time; Path('started').write_text('1'); time.sleep(10)",
            ),
        )
        await wait_file(tmp_path / "started")
        c.now[0] = 1031
        result = await asyncio.wait_for(handle.wait(), 2)
        assert result.cancel_requested and result.exit_code != 0
        assert c.store.get(101, lease.run_id).status == "reconciling"
        c.now[0] = 1005  # A clock correction must not restore observed lost authority.
        assert c.store.attempt_active(lease) is False


async def test_output_limit_is_explicit_and_never_discards_tail_while_claiming_complete_output(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with executor(c, tmp_path) as worker:
        handle = await worker.start(
            lease,
            "too-much",
            command(
                c,
                "import sys,time; print('y'*10000,flush=True); time.sleep(5)",
                output_bytes=1024,
            ),
        )
        result = await asyncio.wait_for(handle.wait(), 2)
        assert result.output_limited
        assert len(result.stdout) == 1024
        assert result.cancel_requested


async def test_peer_loss_preserves_uncertainty_and_does_not_replay_on_reopen(
    coordination, tmp_path
):
    from backend.runtime.command_jobs import CommandNeedsReconciliation

    c = coordination
    lease = claim(c)
    spec = command(
        c,
        "from pathlib import Path; import time; p=Path('effects'); p.write_text('once'); time.sleep(10)",
    )
    async with executor(c, tmp_path) as worker:
        handle = await worker.start(lease, "lost-peer", spec)
        await wait_file(tmp_path / "effects")
        worker.rpc._process.kill()
        result = await asyncio.wait_for(handle.wait(), 2)
        assert result.status == "unknown" and result.exit_code is None
    async with executor(c, tmp_path) as replacement:
        with pytest.raises(CommandNeedsReconciliation):
            await replacement.start(lease, "lost-peer", spec)
    assert (tmp_path / "effects").read_text() == "once"


async def test_executor_close_reaps_active_commands_before_returning(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with executor(c, tmp_path) as worker:
        handle = await worker.start(
            lease,
            "closing",
            command(
                c,
                "from pathlib import Path; import time; Path('started').write_text('1'); time.sleep(0.8); Path('delayed').write_text('bad')",
            ),
        )
        await wait_file(tmp_path / "started")
    result = c.store.get_job(101, handle.job_id)
    assert result.cancel_requested
    assert result.status == "exited"
    await asyncio.sleep(0.85)
    assert not (tmp_path / "delayed").exists()


async def test_native_stop_does_not_wait_for_a_busy_sqlite_writer(
    coordination, tmp_path
):
    c = coordination
    lease = claim(c)
    async with executor(c, tmp_path) as worker:
        handle = await worker.start(
            lease,
            "sqlite-contention",
            command(
                c,
                "from pathlib import Path; import time; Path('started').write_text('1'); time.sleep(0.6); Path('delayed').write_text('bad')",
            ),
        )
        await wait_file(tmp_path / "started")
        c.conn.execute("BEGIN IMMEDIATE")
        pending = asyncio.create_task(handle.cancel())
        try:
            await asyncio.sleep(0.75)
            assert not (tmp_path / "delayed").exists()
        finally:
            c.conn.rollback()
        result = await asyncio.wait_for(pending, 2)
        assert result.cancel_requested and result.status == "exited"
        assert result.exit_code != 0
