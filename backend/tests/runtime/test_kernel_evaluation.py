"""Account-free evaluation fixtures exercise real native ownership and observable readiness."""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def delegated_parent():
    """Select the delegated test parent without modifying its controllers."""
    parent = (Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().split(':', 2)[2].lstrip('/')).parent
    if not os.access(parent, os.W_OK) or not {'memory', 'pids'} <= set((parent / 'cgroup.subtree_control').read_text().split()):
        pytest.skip('Requires delegated memory and pids controllers')
    return parent


def test_invalid_kernel_resources_leave_no_trial(tmp_path, native_asset):
    """Missing delegation cannot create a database or an authority as a side effect."""
    from evals.runtime.kernel_trial import prepare

    root = tmp_path / 'trial'
    with pytest.raises((OSError, ValueError)):
        prepare(root, native_asset.path, tmp_path / 'missing')
    assert not root.exists()


async def test_native_command_fixture_preserves_source_and_closes_its_domain(tmp_path, native_asset, delegated_parent):
    """Run real command RPC with no account, observe readiness, and retire original physical ownership."""
    from backend.runtime.contracts import CommandSpec
    from evals.runtime.kernel_trial import pin_peer, prepare, wait_closed, wait_empty, wait_output

    trial = prepare(tmp_path / 'trial', native_asset.path, delegated_parent)
    source = trial.workspace / 'fact.txt'
    source.write_text('137')
    async with trial.open():
        async with trial.commands() as worker:
            code = "from pathlib import Path\nprint('READY',flush=True)\nprint(Path('fact.txt').read_text(),flush=True)\ntry:Path('fact.txt').write_text('BAD')\nexcept OSError:print('READ_ONLY',flush=True)"
            handle = await worker.start(trial.lease, 'read', CommandSpec((str(Path(__import__('sys').executable).resolve()), '-I', '-S', '-c', code), '.', 5, 4096))
            await wait_output(worker, handle, b'READY')
            pinned = pin_peer(worker)
            job = await handle.wait()
            assert job.exit_code == 0 and b'137\nREAD_ONLY' in job.stdout
        try:
            await wait_closed(pinned)
            await wait_empty(trial.domain_path)
        finally:
            os.close(pinned)
        assert trial.store.get_job(101, handle.job_id).local_execution_closed
    assert trial.peers.closed() and not trial.domain_path.exists()
    assert source.read_text() == '137'
    with trial.store._transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0] == 0
    with pytest.raises(FileExistsError):
        prepare(trial.root, native_asset.path, delegated_parent)


async def test_readiness_comes_from_the_original_output_event():
    """Wait for the observed stream marker rather than assuming a command started after a sleep."""
    from evals.runtime.kernel_trial import wait_output

    changed = asyncio.Event()
    command = SimpleNamespace(stdout=bytearray(), task=None)
    worker = SimpleNamespace(_changed=changed, _commands={'original': command})
    waiting = asyncio.create_task(wait_output(worker, SimpleNamespace(job_id='original'), b'CHILD_READY'))
    await asyncio.sleep(0)
    assert not waiting.done()
    command.stdout.extend(b'CHILD_READY\n')
    changed.set()
    await waiting


async def test_completed_command_without_readiness_is_not_reported_started():
    """An exited command that never emitted the barrier must fail the scenario."""
    from evals.runtime.kernel_trial import wait_output

    done = asyncio.get_running_loop().create_future()
    done.set_result(None)
    worker = SimpleNamespace(_changed=asyncio.Event(), _commands={'original': SimpleNamespace(stdout=b'', task=done)})
    with pytest.raises(RuntimeError, match='readiness'):
        await wait_output(worker, SimpleNamespace(job_id='original'), b'CHILD_READY')
