"""Reproduce completed native command retirement without another model admission."""

import asyncio
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('delay', [0, 4])
async def test_completed_command_remains_closeable_after_owner_reads(broker_setup, native_asset, delay):
    """Preserve a completed calculation while its original broker closes the idle namespace."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.contracts import CommandSpec
    from backend.runtime.native_commands import broker_command_executor

    setup, registry, peer, broker, storage, _ = broker_setup
    with registry.runs._transaction() as connection:
        _row, lease = registry._lease(connection, registry._row(connection, peer))
    async with AsyncPeerBroker(broker) as owner:
        async with broker_command_executor(owner=owner, registry=registry, lease=lease,
                                           workspace=setup.workspace, asset=native_asset) as worker:
            handle = await worker.start(lease, 'completed-host-probe', CommandSpec(
                (str(Path(sys.executable).resolve()), '-I', '-S', '-c', 'print(137 + 63)'), '.', 5, 4096))
            job = await handle.wait()
            assert job.exit_code == 0 and job.stdout == b'200\n'
            await asyncio.sleep(delay)
        saved = registry.runs.get_job(101, job.job_id)
        assert saved.local_execution_closed and saved.stdout == b'200\n'


async def test_closing_endpoint_input_delivers_eof_to_original_peer(broker_setup):
    """Let stdin-driven peers finish without retaining another writable pipe handle."""
    from backend.runtime.broker_stdio import AsyncPeerBroker

    _setup, registry, peer, broker, _storage, _path = broker_setup
    async with AsyncPeerBroker(broker) as owner:
        endpoint = owner.peer(
            registry, peer, operation_key='host-input-eof',
            code='import sys; print(len(sys.stdin.buffer.read()), flush=True)',
        )
        await endpoint.open(limit=4096)
        endpoint.stdin.close()
        async with asyncio.timeout(3):
            assert await endpoint.stdout.read() == b'0\n'
        await endpoint.aclose(timeout=3)
