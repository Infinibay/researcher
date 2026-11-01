"""Existing command receipts/control through original broker native ownership."""

import json
import sys
from pathlib import Path

from backend.runtime.contracts import CommandSpec


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
