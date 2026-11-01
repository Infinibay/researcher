"""Ken-shaped tool exercises the real owned kernel profile; published trial separate."""

import json

import pytest


def ken_peer(registry, command):
    row = registry.inspect(command)
    with registry.runs._transaction() as conn:
        _, lease = registry._lease(conn, row)
    return registry.prepare(lease, "ken")


def probe_installation(executable):
    from backend.runtime.ken_worker import KenInstallation

    executable.write_text(
        "#!"
        + str(executable.parent / "python")
        + "\n"
        + """import asyncio,json,os,socket,stat,sys
from pathlib import Path
root=Path(os.environ['KEN_PROJECT_ROOT'])
async def tick():await asyncio.sleep(0)
asyncio.run(tick())
report={'content':(root/'fact.txt').read_text(),'root':str(root),'argv':sys.argv[1:],'asyncio':True}
for label,family in [('network',socket.AF_INET),('unix',socket.AF_UNIX)]:
 try:socket.socket(family);report[label]=True
 except OSError:report[label]=False
try:(root/'fact.txt').write_text('CORRUPT');report['write']=True
except OSError:report['write']=False
report['fd_write']=False
for name in os.listdir('/proc/self/fd'):
 try:
  fd=int(name)
  if not stat.S_ISDIR(os.fstat(fd).st_mode):continue
  writer=os.open('fact.txt',os.O_WRONLY,dir_fd=fd);os.close(writer);report['fd_write']=True
 except OSError:pass
(root/'.ken/probe-note').write_text('retained')
report['credential_keys']=sorted(k for k in os.environ if k in ('OPENAI_API_KEY','RESEARCHER_TOOL_TOKEN','HF_TOKEN','CODEX_HOME'))
print(json.dumps(report))
"""
    )
    return KenInstallation.inspect(executable)


@pytest.mark.parametrize("mode", ["mcp", "prepare"])
def test_ken_profile_keeps_source_readonly_state_writable_and_asyncio_private(
    broker_setup, ken_installation, mode, monkeypatch
):
    from backend.runtime.workspaces import PEER_WORKSPACE

    s, registry, command, broker, storage, path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    installation = probe_installation(ken_installation)
    monkeypatch.setenv("OPENAI_API_KEY", "HOST_CANARY")
    peer = ken_peer(registry, command)
    result = broker.run_ken(
        registry, peer, operation_key="ken-probe", installation=installation, mode=mode
    )
    try:
        assert result.child.wait(timeout=4) == 0, result.child.stderr.read().decode()
        report = json.loads(result.child.stdout.read())
        assert report["content"] == "137" and report["root"] == str(PEER_WORKSPACE)
        assert report["asyncio"] and not report["network"] and not report["unix"]
        assert (
            not report["write"]
            and not report["fd_write"]
            and not report["credential_keys"]
        )
        assert (s.workspace / ".ken/probe-note").read_text() == "retained"
        assert (s.workspace / "fact.txt").read_text() == "137"
        operation = storage.load().records["broker:op:" + result.operation_id]
        assert (
            operation["kind"] == "ken" and operation["runtime_manifest"]["mode"] == mode
        )
        sequence = storage.load().sequence
        retry = broker.run_ken(
            registry,
            peer,
            operation_key="ken-probe",
            installation=installation,
            mode=mode,
        )
        assert (
            not retry.fresh
            and retry.child is None
            and storage.load().sequence == sequence
        )
        assert broker.close_peer(result.operation_id)["execution_closed"]
        broker.project_closed(operation_id=result.operation_id)
        assert registry.inspect(peer)["state"] == "closed" and path.exists()
    finally:
        result.child.close_handles()


def test_ken_profile_rejects_wrong_original_peer_before_reserving(
    broker_setup, ken_installation
):
    from backend.runtime.authority_journal import AuthorityConflict

    _s, registry, command, broker, storage, _path = broker_setup
    with pytest.raises(AuthorityConflict):
        broker.run_ken(
            registry,
            command,
            operation_key="wrong-kind",
            installation=probe_installation(ken_installation),
        )
    assert storage.load().records.get("broker:active") is None


def test_ken_source_fd_survives_path_replacement_after_profile_preparation(
    broker_setup, ken_installation, monkeypatch, tmp_path
):
    s, registry, command, broker, _storage, _path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    spawn = broker.domain.spawn

    def replace(*args, **kwargs):
        s.workspace.rename(tmp_path / "original-source")
        s.workspace.mkdir()
        (s.workspace / "fact.txt").write_text("OTHER")
        return spawn(*args, **kwargs)

    monkeypatch.setattr(broker.domain, "spawn", replace)
    result = broker.run_ken(
        registry,
        ken_peer(registry, command),
        operation_key="source-swap",
        installation=probe_installation(ken_installation),
    )
    try:
        assert result.child.wait(timeout=4) == 0, result.child.stderr.read().decode()
        assert json.loads(result.child.stdout.read())["content"] == "137"
        assert (
            not (s.workspace / ".ken").exists()
            and (s.workspace / "fact.txt").read_text() == "OTHER"
        )
    finally:
        result.child.close_handles()


async def test_async_ken_transport_closes_original_peer_and_keeps_sibling(
    broker_setup, ken_installation
):
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.runtime.ken_worker import KenInstallation
    from backend.tests.runtime.test_broker_rpc import code

    _s, registry, command, broker, storage, path = broker_setup
    ken_installation.write_text(
        "#!" + str(ken_installation.parent / "python") + "\n" + code()
    )
    installation = KenInstallation.inspect(ken_installation)
    peer = ken_peer(registry, command)
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.peer(registry, command, operation_key="sibling", code=code())
        ) as sibling,
    ):
        endpoint = owner.ken(
            registry, peer, operation_key="async-ken", installation=installation
        )
        async with JsonRpcClient(endpoint) as client:
            assert await client.request("echo", {"value": 137}) == {"value": 137}
        assert registry.inspect(peer)["state"] == "closed"
        assert registry.inspect(command)["state"] == "bound"
        assert (
            storage.load().records["broker:op:" + endpoint._operation][
                "runtime_manifest"
            ]["profile"]
            == "readonly-published-ken-v1"
        )
        assert await sibling.request("echo", {"value": 200}) == {"value": 200}
        assert path.exists()
    assert not path.exists()
