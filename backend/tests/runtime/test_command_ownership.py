"""Command result, physical lifetime and owner recovery are independent facts."""

import asyncio

import pytest


def test_command_peer_requires_registered_attempt_scope(coordination):
    from backend.runtime.peer_registry import PeerRegistry

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "old-owner")
    with pytest.raises(c.contracts.RunConflict, match="scope"):
        PeerRegistry(c.store).prepare(lease, "command")


def test_registered_attempt_cannot_reserve_an_unowned_command(coordination):
    from backend.runtime.peer_registry import AttemptPeers

    c = coordination
    run = c.store.admit(c.spec)
    lease, _ = AttemptPeers.claim(c.store, 101, run.run_id, "owner")
    with pytest.raises(c.contracts.RunConflict, match="peer"):
        c.store.reserve_job(
            lease,
            operation_key="unowned",
            spec=c.contracts.CommandSpec(("/bin/echo", "bad")),
            workspace="/fixture",
            executor_id="unowned",
        )
    assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0


async def test_lost_command_peer_can_be_closed_and_recovered_without_inventing_a_result(
    coordination, tmp_path
):
    from backend.runtime.recovery import RunRecovery
    from backend.tests.runtime.test_command_executor import (
        claim,
        command,
        executor,
        wait_file,
    )

    c = coordination
    lease = claim(c)
    async with executor(c, tmp_path, lease) as worker:
        handle = await worker.start(
            lease,
            "lost",
            command(
                c,
                "from pathlib import Path; import time; Path('once').write_text('one'); time.sleep(10)",
            ),
        )
        await wait_file(tmp_path / "once")
        worker.rpc._process.kill()
        job = await asyncio.wait_for(handle.wait(), 5)
        assert job.status == "unknown" and job.exit_code is None
        assert job.peer_id and job.local_execution_closed
    before = c.store.get(101, lease.run_id)
    recovery = RunRecovery(c.store)
    details = recovery.inspection(101, lease.run_id)
    assert details["unknown_jobs"] == 1 and details["can_reconcile"]
    assert details["jobs"][0]["local_execution_closed"]
    result = recovery.reconcile(
        project_id=101,
        run_id=lease.run_id,
        attempt_id=lease.attempt_id,
        expected_fence=before.fence,
        operation_key="close-lost-command",
    )
    assert (
        result["status"] == "failed"
        and not result["task_accepted"]
        and not result["inference_started"]
    )
    assert c.store.get_job(101, handle.job_id).exit_code is None
    assert (tmp_path / "once").read_text() == "one"


@pytest.mark.parametrize("failure", ["expired", "database_busy"])
async def test_a_completed_command_does_not_certify_its_detached_child_closed(
    coordination, tmp_path, failure
):
    from backend.tests.runtime.test_command_executor import (
        claim,
        command,
        executor,
    )

    c = coordination
    lease = claim(c)
    child = "from pathlib import Path; import time; Path('child-started').write_text('1'); time.sleep(2); Path('delayed-child').write_text('bad')"
    parent = (
        "import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,'-c',"
        + repr(child)
        + "],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);\nwhile not Path('child-started').exists(): time.sleep(.01)"
    )
    async with executor(c, tmp_path, lease) as worker:
        job = await (await worker.start(lease, "background", command(c, parent))).wait()
        assert job.exit_code == 0 and not job.local_execution_closed
        if failure == "expired":
            c.now[0] = lease.expires_at + 1
        else:
            c.conn.execute("BEGIN IMMEDIATE")
            try:
                await asyncio.sleep(2.2)
                assert not (tmp_path / "delayed-child").exists(), (
                    "Owner supervision waited behind the database writer"
                )
            finally:
                c.conn.rollback()
        async with asyncio.timeout(3):
            while not c.store.get_job(101, job.job_id).local_execution_closed:
                await asyncio.sleep(0.02)
    await asyncio.sleep(2.1)
    assert not (tmp_path / "delayed-child").exists()
    assert c.store.get_job(101, job.job_id).exit_code == 0


async def test_bound_command_peer_cannot_be_borrowed_by_another_attempt(
    coordination, tmp_path
):
    from dataclasses import replace

    from backend.runtime.peer_registry import AttemptPeers
    from backend.tests.runtime.test_command_executor import claim, command, executor

    c = coordination
    lease = claim(c)
    other = c.store.admit(replace(c.spec, task_id=1002, operation_key="another-task"))
    other_lease, _ = AttemptPeers.claim(
        c.store, 101, other.run_id, "another-owner", lease_seconds=120
    )
    async with executor(c, tmp_path, lease) as worker:
        with pytest.raises(c.contracts.RunConflict, match="peer"):
            c.store.reserve_job(
                other_lease,
                operation_key="borrow-peer",
                spec=command(c, "print('wrong')"),
                workspace=str(tmp_path),
                executor_id="borrowed",
                peer_id=worker.peer_id,
            )
        assert c.conn.execute("SELECT COUNT(*) FROM runtime_jobs").fetchone()[0] == 0
        job = await (
            await worker.start(lease, "original", command(c, "print('original')"))
        ).wait()
        assert job.stdout == b"original\n" and job.exit_code == 0
