"""Native factory policy through a real stdio child, with an explicit business port."""

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def native_factory_setup(tmp_path, monkeypatch):
    from backend.runtime import native_inference
    from backend.runtime.business_mediation import BUSINESS_NAMES

    binary = tmp_path / "codex"
    helper = Path(__file__).with_name("fake_production_codex.py")
    binary.write_text(
        "#!"
        + sys.executable
        + '\nimport os,sys\nos.execv(sys.executable,[sys.executable,"-u",'
        + repr(str(helper))
        + ",*sys.argv[1:]])\n"
    )
    binary.chmod(0o755)
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / "config.toml").write_text('[mcp_servers.legacy]\ncommand="/bin/false"\n')
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    @asynccontextmanager
    async def business(**kwargs):
        assert kwargs["token"] == "HOST_ONLY_GRANT"

        class Peer:
            async def list_tools(self):
                return SimpleNamespace(
                    tools=[
                        SimpleNamespace(
                            name=name,
                            description=name,
                            inputSchema={"type": "object", "properties": {}},
                        )
                        for name in sorted(BUSINESS_NAMES)
                    ]
                )

        yield Peer()

    monkeypatch.setattr(native_inference, "business_peer", business)
    return SimpleNamespace(
        module=native_inference,
        binary=binary,
        managed=managed,
        workspace=workspace,
        control=tmp_path / "control",
        tmp=tmp_path,
    )


def factory(setup):
    return setup.module.CodexRuntime(
        codex_binary=setup.binary,
        managed_home=setup.managed,
        control_root=setup.control,
        ken_command=setup.tmp / "ken",
        model_cache=setup.tmp / "models",
        business_script=setup.tmp / "business.py",
        uv_binary=Path("/usr/bin/true"),
        uv_cache=setup.tmp / "uv-cache",
        api_url="http://127.0.0.1:8000",
        model="test-model",
    )


async def test_factory_passes_current_directory_identity_to_required_ken_worker(
    native_factory_setup,
):
    c = native_factory_setup
    info = c.workspace.stat()
    async with factory(c).open(
        workspace=c.workspace, tool_token="HOST_ONLY_GRANT"
    ) as session:
        config = await session.native.rpc.request(
            "config/read", {"cwd": str(c.workspace), "includeLayers": False}
        )
        args = config["config"]["mcp_servers"]["researcher_ken"]["args"]
        assert args[args.index("--expected-device") + 1] == str(info.st_dev)
        assert args[args.index("--expected-inode") + 1] == str(info.st_ino)


async def test_factory_rejects_replaced_admitted_workspace_before_starting_peers(
    native_factory_setup, coordination
):
    import time

    from backend.runtime.contracts import WorkspaceChanged
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.workspaces import WorkspaceRegistry

    c = native_factory_setup
    coordination.now[0] = time.time()
    coordination.conn.execute(
        "INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'source',?)",
        (str(c.workspace),),
    )
    coordination.conn.commit()
    binding = WorkspaceRegistry(coordination.database, c.tmp).bind(101, 11)
    run = coordination.store.admit(coordination.spec, binding=binding)
    _lease, peers = AttemptPeers.claim(
        coordination.store, 101, run.run_id, "owner", lease_seconds=120
    )
    c.workspace.rename(c.tmp / "old-admitted-source")
    c.workspace.mkdir()
    try:
        with pytest.raises(WorkspaceChanged):
            async with factory(c).open(
                workspace=c.workspace, tool_token="HOST_ONLY_GRANT", peer_owner=peers
            ):
                pass
        assert not (c.managed / "requests.jsonl").exists()
        assert not (c.workspace / ".ken").exists()
    finally:
        await peers.aclose()


async def test_registered_factory_uses_the_stable_peer_source_view(
    native_factory_setup, coordination
):
    import time

    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.workspaces import PEER_WORKSPACE, WorkspaceRegistry

    c = native_factory_setup
    coordination.now[0] = time.time()
    coordination.conn.execute(
        "INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'source',?)",
        (str(c.workspace),),
    )
    coordination.conn.commit()
    binding = WorkspaceRegistry(coordination.database, c.tmp).bind(101, 11)
    run = coordination.store.admit(coordination.spec, binding=binding)
    _lease, peers = AttemptPeers.claim(
        coordination.store, 101, run.run_id, "owner", lease_seconds=120
    )
    try:
        async with factory(c).open(
            workspace=c.workspace, tool_token="HOST_ONLY_GRANT", peer_owner=peers
        ) as session:
            assert session.native.workspace == PEER_WORKSPACE
            config = (
                await session.native.rpc.request(
                    "config/read", {"cwd": str(PEER_WORKSPACE), "includeLayers": False}
                )
            )["config"]
            assert config["permissions"]["researcher_inference"]["workspace_roots"] == {
                str(PEER_WORKSPACE): True
            }
            args = config["mcp_servers"]["researcher_ken"]["args"]
            assert args[args.index("--workspace") + 1] == str(PEER_WORKSPACE)
        assert coordination.store.workspace_binding(101, run.run_id) == binding
        records = [
            json.loads(line)
            for line in (c.managed / "requests.jsonl").read_text().splitlines()
        ]
        thread = next(row for row in records if row.get("method") == "thread/start")
        assert thread["params"]["cwd"] == str(PEER_WORKSPACE)
    finally:
        await peers.aclose()


@pytest.mark.parametrize("field", ["ken_command", "model_cache"])
async def test_logical_view_cannot_hide_trusted_ken_assets_inside_host_source(
    native_factory_setup, field
):
    from dataclasses import replace

    c = native_factory_setup
    runtime = replace(factory(c), **{field: c.workspace / field})
    with pytest.raises(ValueError):
        async with runtime.open(workspace=c.workspace, tool_token="HOST_ONLY_GRANT"):
            pass
    assert not (c.managed / "requests.jsonl").exists()


async def test_model_peer_keeps_managed_auth_but_never_business_or_api_key_env(
    native_factory_setup, monkeypatch
):
    c = native_factory_setup
    monkeypatch.setenv("OPENAI_API_KEY", "MUST_NOT_REACH_NATIVE")
    monkeypatch.setenv("RESEARCHER_TOOL_TOKEN", "MUST_NOT_REACH_NATIVE")
    async with factory(c).open(
        workspace=c.workspace, tool_token="HOST_ONLY_GRANT"
    ) as session:
        assert session.thread_id == "factory-thread"
        sent_instructions = session.developer_instructions
        sent_catalog = session.catalog
    records = [
        json.loads(line)
        for line in (c.managed / "requests.jsonl").read_text().splitlines()
    ]
    keys = next(row["environment_keys"] for row in records if "environment_keys" in row)
    assert "CODEX_HOME" in keys
    assert "OPENAI_API_KEY" not in keys
    assert "RESEARCHER_TOOL_TOKEN" not in keys
    started = next(row for row in records if row.get("method") == "thread/start")
    assert started["params"]["permissions"] == "researcher_inference"
    assert started["params"]["developerInstructions"] == sent_instructions
    assert started["params"]["dynamicTools"] == sent_catalog
    from backend.runtime.business_mediation import BUSINESS_NAMES

    assert {
        tool["name"] for tool in started["params"]["dynamicTools"]
    } == BUSINESS_NAMES
    assert len(started["params"]["dynamicTools"]) == len(BUSINESS_NAMES)
    assert "HOST_ONLY_GRANT" not in json.dumps(records)
    assert not any(row.get("method") == "turn/start" for row in records)
    assert not list(c.control.glob("native-inference-*"))


async def test_native_factory_registers_namespace_init_before_protocol_start(
    native_factory_setup, coordination
):
    import time

    from backend.runtime.peer_registry import AttemptPeers

    c = native_factory_setup
    coordination.now[0] = time.time()
    run = coordination.store.admit(coordination.spec)
    lease = coordination.store.claim(
        101, run.run_id, "factory-owner", lease_seconds=120
    )
    peers = AttemptPeers.prepare(coordination.store, lease)
    try:
        async with factory(c).open(
            workspace=c.workspace, tool_token="HOST_ONLY_GRANT", peer_owner=peers
        ) as session:
            assert session.thread_id == "factory-thread"
            assert session.native.rpc.process_group_signals is False
            record = peers.registry.inspect(peers.ids["native"])
            assert record["state"] == "bound"
            assert record["init_namespace"] != record["observer_namespace"]
        records = [
            json.loads(line)
            for line in (c.managed / "requests.jsonl").read_text().splitlines()
        ]
        assert not any(row.get("method") == "turn/start" for row in records)
    finally:
        await peers.aclose()
    assert peers.closed()


async def test_registered_session_dispatches_python_with_combined_frozen_catalog(
    native_factory_setup, coordination, monkeypatch
):
    import time

    from backend.runtime.peer_registry import AttemptPeers
    from backend.tests.runtime.test_analysis_tools import content, envelope, terminal
    from backend.tests.runtime.test_command_executor import executor

    c = native_factory_setup
    coordination.now[0] = time.time()
    run = coordination.store.admit(coordination.spec)
    lease, peers = AttemptPeers.claim(
        coordination.store, 101, run.run_id, "owner", lease_seconds=120
    )

    def command_factory(**kwargs):
        # Replace only the native executable boundary; retain actual guards,
        # SQLite admission/receipts and real subprocess output/cancellation.
        assert kwargs["workspace_access"] == "read"
        assert kwargs["lease"] == lease and kwargs["workspace"] == c.workspace
        return executor(coordination, c.workspace, lease)

    monkeypatch.setattr(c.module, "command_executor", command_factory, raising=False)
    try:
        async with factory(c).open(
            workspace=c.workspace, tool_token="HOST_ONLY_GRANT", peer_owner=peers
        ) as session:
            names = {tool["name"] for tool in session.catalog}
            assert "researcher_python" in names and "researcher_command_cancel" in names
            from backend.runtime.business_mediation import BUSINESS_NAMES

            assert names == BUSINESS_NAMES | {
                "researcher_python",
                "researcher_command_start",
                "researcher_command_read",
                "researcher_command_cancel",
            }
            first_hash = session.catalog_hash
            started = content(
                await session._request(
                    {
                        "method": "item/tool/call",
                        "params": envelope(
                            "researcher_python",
                            operation_key="through-session",
                            code="print(6 * 7)",
                        ),
                    }
                )
            )
            result = await terminal(session.business, started["job_id"])
            assert (
                result["stdout"]["text"] == "42\n" and result["local_execution_closed"]
            )
            assert session.catalog_hash == first_hash
            invalid = await session._request(
                {"method": "item/tool/call", "params": {"tool": []}}
            )
            assert not invalid["success"]
        rows = [
            json.loads(line)
            for line in (c.managed / "requests.jsonl").read_text().splitlines()
        ]
        sent = next(
            row["params"]["dynamicTools"]
            for row in rows
            if row.get("method") == "thread/start"
        )
        assert {tool["name"] for tool in sent} == names
        assert "HOST_ONLY_GRANT" not in json.dumps(sent)
    finally:
        await peers.aclose()
    assert peers.closed()


async def test_unsafe_effective_configuration_is_refused_before_thread_or_turn(
    native_factory_setup,
):
    c = native_factory_setup
    (c.workspace / "unsafe-effective-config").touch()
    with pytest.raises(RuntimeError, match="configuration"):
        async with factory(c).open(workspace=c.workspace, tool_token="HOST_ONLY_GRANT"):
            pass
    records = [
        json.loads(line)
        for line in (c.managed / "requests.jsonl").read_text().splitlines()
    ]
    assert not any(
        row.get("method", "").startswith(("thread/", "turn/")) for row in records
    )


async def test_native_factory_refuses_api_key_mode_without_a_turn(native_factory_setup):
    from backend.runtime.codex_session import SubscriptionRequired

    c = native_factory_setup
    (c.managed / "api-key-account").touch()
    with pytest.raises(SubscriptionRequired):
        async with factory(c).open(workspace=c.workspace, tool_token="HOST_ONLY_GRANT"):
            pass
    records = [
        json.loads(line)
        for line in (c.managed / "requests.jsonl").read_text().splitlines()
    ]
    assert not any(
        row.get("method", "").startswith(("thread/", "turn/")) for row in records
    )


async def test_required_native_code_host_cannot_be_disabled_by_effective_config(
    native_factory_setup,
):
    c = native_factory_setup
    (c.workspace / "disabled-code-host").touch()
    with pytest.raises(RuntimeError, match="required_features"):
        async with factory(c).open(workspace=c.workspace, tool_token="HOST_ONLY_GRANT"):
            pass


async def test_native_configuration_accepts_equivalent_builtin_defaults(
    native_factory_setup,
):
    c = native_factory_setup
    (c.workspace / "normalized-defaults").touch()
    async with factory(c).open(
        workspace=c.workspace, tool_token="HOST_ONLY_GRANT"
    ) as session:
        assert session.thread_id == "factory-thread"


async def test_native_configuration_refuses_custom_auth_endpoint(native_factory_setup):
    c = native_factory_setup
    (c.workspace / "untrusted-auth-endpoint").touch()
    with pytest.raises(RuntimeError, match="auth_endpoint"):
        async with factory(c).open(workspace=c.workspace, tool_token="HOST_ONLY_GRANT"):
            pass


async def test_native_configuration_refuses_credential_bearing_shell_environment(
    native_factory_setup,
):
    c = native_factory_setup
    (c.workspace / "unsafe-shell-env").touch()
    with pytest.raises(RuntimeError, match="shell_environment"):
        async with factory(c).open(workspace=c.workspace, tool_token="HOST_ONLY_GRANT"):
            pass


async def test_native_resume_requires_a_recorded_catalog_before_process_start(
    native_factory_setup,
):
    c = native_factory_setup
    with pytest.raises(RuntimeError, match="catalog"):
        async with factory(c).open(
            workspace=c.workspace,
            tool_token="HOST_ONLY_GRANT",
            resume_thread_id="factory-thread",
        ):
            pass
    assert not (c.managed / "requests.jsonl").exists()


async def test_native_resume_reuses_only_matching_workspace_and_catalog(
    native_factory_setup,
):
    c = native_factory_setup
    async with factory(c).open(
        workspace=c.workspace, tool_token="HOST_ONLY_GRANT"
    ) as first:
        digest = first.catalog_hash
    async with factory(c).open(
        workspace=c.workspace,
        tool_token="HOST_ONLY_GRANT",
        resume_thread_id="factory-thread",
        expected_catalog_hash=digest,
    ) as restored:
        assert restored.thread_id == "factory-thread"
    records = [
        json.loads(line)
        for line in (c.managed / "requests.jsonl").read_text().splitlines()
    ]
    assert sum(row.get("method") == "thread/start" for row in records) == 1
    resume = next(row for row in records if row.get("method") == "thread/resume")
    assert "dynamicTools" not in resume["params"]
    assert not any(row.get("method") == "turn/start" for row in records)


async def test_native_resume_refuses_another_workspaces_thread(native_factory_setup):
    c = native_factory_setup
    async with factory(c).open(
        workspace=c.workspace, tool_token="HOST_ONLY_GRANT"
    ) as first:
        digest = first.catalog_hash
    other = c.tmp / "beta"
    other.mkdir()
    with pytest.raises(RuntimeError, match="workspace"):
        async with factory(c).open(
            workspace=other,
            tool_token="HOST_ONLY_GRANT",
            resume_thread_id="factory-thread",
            expected_catalog_hash=digest,
        ):
            pass
    records = [
        json.loads(line)
        for line in (c.managed / "requests.jsonl").read_text().splitlines()
    ]
    assert not any(row.get("method") == "thread/resume" for row in records)
