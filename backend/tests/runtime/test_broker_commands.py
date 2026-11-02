"""Existing command receipts/control through original broker native ownership."""

import json
import shutil
import sys
from pathlib import Path

import pytest

from backend.runtime.contracts import CommandSpec


async def ready_development_copy(s, registry, peer, owner):
    """Prepare a real private Git copy using the low-level development policy fixture and actual broker."""
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.git_capsule import GitAsset
    from backend.tests.runtime.test_broker_git import prepare_policy_fixture
    from backend.tests.runtime.test_development_workspace import fixture_git

    lease = await prepare_policy_fixture(s, registry, peer)
    await fixture_git(s.workspace, "init", "-q")
    (s.workspace / "fact.txt").write_text("137")
    await fixture_git(s.workspace, "add", "fact.txt")
    await fixture_git(
        s.workspace,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "base",
    )
    root = s.control / "development"
    root.mkdir(mode=0o700, parents=True)
    view = await DevelopmentWorkspaces(registry.runs, root).prepare(
        lease,
        owner=owner,
        registry=registry,
        asset=GitAsset.inspect(Path(shutil.which("git"))),
    )
    return lease, view


async def test_development_native_command_writes_only_ready_private_copy(
    broker_setup, native_asset
):
    """Actual native command RPC edits the prepared copy while its original source, credentials and network stay unavailable."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.native_commands import broker_command_executor

    s, registry, peer, broker, storage, _ = broker_setup
    code = """import json,socket,subprocess
from pathlib import Path
p=Path('fact.txt');p.write_text(str(int(p.read_text())+63))
subprocess.run(['/bin/sh','-c','printf ready > shell-check.txt'],check=True)
try: socket.socket()
except PermissionError:network_denied=True
else:network_denied=False
print(json.dumps({'value':p.read_text(),'network_denied':network_denied,
 'no_credentials':not Path('/home/actor/.codex/auth.json').exists(),
 'git_preparation_allocation_hidden':not Path('/run/researcher-development').exists()}))"""
    async with AsyncPeerBroker(broker) as owner:
        lease, view = await ready_development_copy(s, registry, peer, owner)
        async with broker_command_executor(
            owner=owner,
            registry=registry,
            lease=lease,
            workspace=Path(view.workspace),
            asset=native_asset,
        ) as worker:
            handle = await worker.start(
                lease,
                "private-edit",
                CommandSpec(
                    (str(Path(sys.executable).resolve()), "-I", "-S", "-c", code),
                    ".",
                    5,
                    4096,
                ),
            )
            job = await handle.wait()
            assert job.exit_code == 0 and not job.error, job
            assert json.loads(job.stdout) == {
                "value": "200",
                "network_denied": True,
                "no_credentials": True,
                "git_preparation_allocation_hidden": True,
            }
            assert job.workspace == view.workspace
            from backend.runtime.contracts import WorkspaceChanged

            with pytest.raises(WorkspaceChanged):
                registry.runs.reserve_job(
                    lease,
                    operation_key="wrong-source-dispatch",
                    spec=CommandSpec(("/usr/bin/true",), ".", 5, 4096),
                    workspace=str(s.workspace),
                    executor_id=worker.executor_id,
                    peer_id=worker.peer_id,
                )
        operation = storage.load().records[
            "broker:op:" + worker.rpc._endpoint._operation
        ]
        assert operation["execution_binding"]["workspace"] == view.workspace
        assert (
            operation["workspace_access"] == "private-write"
            and operation["execution_closed"] is True
        )
        assert (
            operation["runtime_manifest"]["profile"]
            == "private-development-native-command-v1"
        )
        closed_job = registry.runs.get_job(101, job.job_id)
        assert closed_job.local_execution_closed and closed_job.stdout == job.stdout
        sequence = storage.load().sequence
        retry = broker.run_command(
            registry,
            worker.peer_id,
            operation_key=worker.rpc._endpoint.operation_key,
            asset=native_asset,
        )
        assert (
            not retry.fresh
            and retry.child is None
            and storage.load().sequence == sequence
        )
        assert registry.runs.workspace_binding(101, lease.run_id) == view.source
    assert (s.workspace / "fact.txt").read_text() == "137"
    assert (Path(view.workspace) / "fact.txt").read_text() == "200"
    assert (Path(view.workspace) / "shell-check.txt").read_text() == "ready"


async def test_development_diagnostics_and_ken_remain_readonly_on_the_same_copy(
    broker_setup, ken_installation
):
    """A development kind permits writes only in its native author profile, not diagnostic or Ken code."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.tests.runtime.test_broker_ken import probe_installation

    s, registry, peer, broker, storage, _ = broker_setup
    async with AsyncPeerBroker(broker) as owner:
        lease, view = await ready_development_copy(s, registry, peer, owner)
        (Path(view.workspace) / "fact.txt").write_text("200")
        diagnostic = registry.prepare(lease, "command")
        started = broker.run_peer(
            registry,
            diagnostic,
            operation_key="development-diagnostic",
            code="from pathlib import Path\np=Path('fact.txt');print(p.read_text())\ntry:p.write_text('CORRUPT')\nexcept OSError:print('readonly')",
        )
        try:
            assert started.child.wait(timeout=5) == 0
            assert started.child.stdout.read() == b"200\nreadonly\n"
        finally:
            started.child.close_handles()
        assert broker.close_peer(started.operation_id)["execution_closed"]
        broker.project_closed(operation_id=started.operation_id)
        ken = registry.prepare(lease, "ken")
        probe = broker.run_ken(
            registry,
            ken,
            operation_key="private-copy-ken",
            installation=probe_installation(ken_installation),
        )
        try:
            assert probe.child.wait(timeout=5) == 0, probe.child.stderr.read()
            report = json.loads(probe.child.stdout.read())
            assert (
                report["content"] == "200"
                and not report["write"]
                and not report["fd_write"]
            )
        finally:
            probe.child.close_handles()
        assert broker.close_peer(probe.operation_id)["execution_closed"]
        broker.project_closed(operation_id=probe.operation_id)
        assert (
            storage.load().records["broker:op:" + probe.operation_id][
                "workspace_access"
            ]
            == "read"
        )
    assert (s.workspace / "fact.txt").read_text() == "137"
    assert (Path(view.workspace) / "fact.txt").read_text() == "200"


async def test_cancelling_private_writer_closes_detached_children_and_retains_files(
    broker_setup, native_asset
):
    """Stop ends the actual writable namespace and preserves already-created private files for inspection."""
    import asyncio
    import time

    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.native_commands import broker_command_executor

    s, registry, peer, broker, storage, _ = broker_setup
    child = "from pathlib import Path;import time\np=Path('heartbeat.txt')\nwhile True:\n with p.open('a') as f:f.write('x')\n time.sleep(0.02)"
    code = (
        "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-I','-S','-c',"
        + repr(child)
        + "],start_new_session=True)\ntime.sleep(30)"
    )
    async with AsyncPeerBroker(broker) as owner:
        lease, view = await ready_development_copy(s, registry, peer, owner)
        heartbeat = Path(view.workspace) / "heartbeat.txt"
        async with broker_command_executor(
            owner=owner,
            registry=registry,
            lease=lease,
            workspace=Path(view.workspace),
            asset=native_asset,
        ) as worker:
            handle = await worker.start(
                lease,
                "private-writer",
                CommandSpec(
                    (str(Path(sys.executable).resolve()), "-I", "-S", "-c", code),
                    ".",
                    30,
                    4096,
                ),
            )
            deadline = time.monotonic() + 8
            while not heartbeat.exists():
                assert time.monotonic() < deadline, "Writer did not start"
                await asyncio.sleep(0.02)
            stopped = await handle.cancel()
            assert stopped.cancel_requested and stopped.local_execution_closed
            snapshot = heartbeat.read_bytes()
            await asyncio.sleep(0.05)
            assert snapshot and heartbeat.read_bytes() == snapshot
        operation = storage.load().records[
            "broker:op:" + worker.rpc._endpoint._operation
        ]
        assert (
            operation["execution_closed"] is True
            and operation["workspace_access"] == "private-write"
        )
    assert (
        heartbeat.read_bytes() == snapshot
        and not (s.workspace / "heartbeat.txt").exists()
    )


async def test_native_app_server_profile_uses_private_write_mount_without_a_model_turn(
    broker_setup, native_asset
):
    """The native actor profile shares the private mount policy; this probe uses only account-free command RPC."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.workspaces import PEER_WORKSPACE

    s, registry, peer, broker, storage, _ = broker_setup
    async with AsyncPeerBroker(broker) as owner:
        lease, view = await ready_development_copy(s, registry, peer, owner)
        with registry.runs._transaction() as conn:
            native_peer = conn.execute(
                "SELECT id FROM runtime_peers WHERE attempt_id=? AND kind='native' AND state='prepared'",
                (lease.attempt_id,),
            ).fetchone()[0]
        endpoint = owner.native(
            registry,
            native_peer,
            operation_key="private-native-probe",
            asset=native_asset,
        )
        async with JsonRpcClient(endpoint) as rpc:
            await rpc.request(
                "initialize",
                {
                    "clientInfo": {"name": "private-profile-probe", "version": "0.1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            await rpc.notify("initialized")
            result = await rpc.request(
                "command/exec",
                {
                    "command": [
                        str(Path(sys.executable).resolve()),
                        "-I",
                        "-S",
                        "-c",
                        "from pathlib import Path;Path('native.txt').write_text('private');print('written')",
                    ],
                    "cwd": str(PEER_WORKSPACE),
                    "sandboxPolicy": {
                        "type": "externalSandbox",
                        "networkAccess": "restricted",
                    },
                    "timeoutMs": 5000,
                    "outputBytesCap": 4096,
                },
            )
            assert result["exitCode"] == 0 and result["stdout"] == "written\n", result
        operation = storage.load().records["broker:op:" + endpoint._operation]
        assert (
            operation["kind"] == "native"
            and operation["workspace_access"] == "private-write"
        )
        assert operation["execution_closed"] is True
    assert (Path(view.workspace) / "native.txt").read_text() == "private"
    assert not (s.workspace / "native.txt").exists()


async def test_real_broker_command_uses_kernel_scope_and_original_job_receipt(
    broker_setup, native_asset
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.native_commands import broker_command_executor

    s, registry, peer, broker, storage, path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    with registry.runs._transaction() as conn:
        _row, lease = registry._lease(conn, registry._row(conn, peer))
    code = """import json,socket
from pathlib import Path
r={'answer':int(Path('fact.txt').read_text())+63}
try: socket.socket()
except PermissionError:r['network_denied']=True
try:Path('fact.txt').write_text('CORRUPT')
except OSError:r['source_readonly']=True
r['no_credentials']=not Path('/home/actor/.codex/auth.json').exists()
print(json.dumps(r))"""
    async with AsyncPeerBroker(broker) as owner:
        async with broker_command_executor(
            owner=owner,
            registry=registry,
            lease=lease,
            workspace=s.workspace,
            asset=native_asset,
        ) as worker:
            handle = await worker.start(
                lease,
                "calculate",
                CommandSpec(
                    (str(Path(sys.executable).resolve()), "-I", "-S", "-c", code),
                    ".",
                    5,
                    4096,
                ),
            )
            job = await handle.wait()
            assert job.exit_code == 0 and not job.error
            assert json.loads(job.stdout) == {
                "answer": 200,
                "network_denied": True,
                "source_readonly": True,
                "no_credentials": True,
            }
        assert path.exists() and not broker._withdrawn.is_set()
        with registry.runs._transaction() as conn:
            assert (
                conn.execute(
                    "SELECT state FROM runtime_peers WHERE id=?", (worker.peer_id,)
                ).fetchone()[0]
                == "closed"
            )
        operation = storage.load().records[
            "broker:op:" + worker.rpc._endpoint._operation
        ]
        assert operation["kind"] == "command" and operation["execution_closed"]
        assert operation["runtime_manifest"]["profile"] == "readonly-native-command-v1"
        assert (s.workspace / "fact.txt").read_text() == "137"
