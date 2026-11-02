"""Controlled development generation through actual factory, input, business, Ken and kernel boundaries."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414 -- register the shared pytest fixture without shadowing it.


@pytest.fixture
def development_config(request):
    """Use controlled native transport with a versioned code task and isolated real source registration."""
    c = request.getfixturevalue("owned_config")
    c.s.c.conn.execute("UPDATE tasks SET type='code' WHERE id=1001")
    c.s.c.conn.commit()
    return c


@asynccontextmanager
async def development_attempt(c, *, permissions=None):
    """Create one typed internal attempt; retain real factory ownership and revoke every test grant on exit."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.research.models import DEVELOPMENT_PERMISSIONS
    from backend.runtime.peer_registry import AttemptPeers
    from backend.tests.runtime.test_development_workspace import fixture_git

    await fixture_git(c.s.workspace, "init", "-q")
    await fixture_git(c.s.workspace, "add", "fact.txt")
    await fixture_git(
        c.s.workspace,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "base",
    )
    app = create_app()
    coordinator = configured_runtime(app.state.live_grants, app=app)
    version = coordinator.store.context_snapshot(101, 1001)["context_version"]
    binding = coordinator.workspaces.bind(101, 11)
    spec = replace(
        c.s.c.spec,
        context_version=version,
        prompt="Change fact.txt from 137 to 200 in this attempt's private copy, read it with Ken and report actual checks.",
    )
    run = coordinator.store.admit(spec, binding=binding)
    assert run.execution_kind == "development"
    lease, peers = AttemptPeers.claim(
        coordinator.store, 101, run.run_id, "development-fixture", lease_seconds=120
    )
    token = coordinator.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions=set(
            DEVELOPMENT_PERMISSIONS if permissions is None else permissions
        ),
    )
    scope = coordinator.research.authorize(token)
    coordinator.store.bind_grant(lease, scope.grant_id)
    app.state.live_grants.activate(scope.grant_id)
    try:
        yield SimpleNamespace(
            coordinator=coordinator,
            run=run,
            lease=lease,
            peers=peers,
            token=token,
            binding=binding,
        )
    finally:
        app.state.live_grants.withdraw(scope.grant_id)
        coordinator.research.revoke_grant(scope.grant_id)
        await peers.aclose()


async def test_development_factory_prepares_private_session_and_freezes_exact_input(
    development_config,
):
    """A typed internal development turn edits only its copy, uses the same Ken view and leaves no accepted task."""
    c = development_config
    async with development_attempt(c) as d:
        coordinator, lease, peers = d.coordinator, d.lease, d.peers
        async with coordinator.runtime.open(
            workspace=c.s.workspace,
            tool_token=d.token,
            peer_owner=peers,
            limits=coordinator.limits,
        ) as session:
            workspace = Path(session.execution_workspace)
            assert workspace != c.s.workspace
            tools = {tool["name"]: tool for tool in session.catalog}
            assert "researcher_result_propose" not in tools and "ken_read" in tools
            assert "private" in tools["researcher_command_start"]["description"].lower()
            assert (
                "read-only"
                not in tools["researcher_command_start"]["description"].lower()
            )
            coordinator.store.bind_thread(lease, thread_id=session.thread_id)
            frozen = coordinator.store.reserve_input(
                lease,
                workspace=str(workspace),
                catalog_hash=session.catalog_hash,
                model=session.model,
                developer_instructions=session.developer_instructions,
                catalog=session.catalog,
                limits=coordinator.limits,
            )
            payload = json.loads(frozen.input_text)
            from backend.tests.runtime.test_development_workspace import fixture_git

            assert payload["execution"]["kind"] == "development"
            assert (
                payload["execution"]["base_sha"]
                == (await fixture_git(c.s.workspace, "rev-parse", "HEAD"))
                .decode()
                .strip()
            )
            assert payload["scope"]["attempt_id"] == lease.attempt_id
            assert str(workspace) not in frozen.input_text

            async def on_started(thread_id, turn_id):
                """Use the coordinator's actual native identity write when controlled generation starts."""
                await asyncio.to_thread(
                    coordinator.store.bind_native,
                    lease,
                    thread_id=thread_id,
                    turn_id=turn_id,
                )

            result = await session.run(frozen.input_text, on_started=on_started)
            assert result.status == "completed"
            assert (workspace / "fact.txt").read_text() == "200"
            assert (c.s.workspace / "fact.txt").read_text() == "137"
        assert coordinator.runtime.consume_closure(lease) is True
        await peers.aclose()
        assert all(row["state"] == "closed" for row in peers._rows())
        assert coordinator.store.workspace_binding(101, d.run.run_id) == d.binding
        coordinator.store.settle_inference(
            lease, observed_tokens=result.observed_tokens, native_status=result.status
        )
        coordinator.store.finish(
            lease, native_status=result.status, summary=result.text
        )
        assert coordinator.store.get(101, d.run.run_id).status == "needs_review"
        assert coordinator.store.context_snapshot(101, 1001)["task"]["status"] != "done"


async def test_research_grant_cannot_open_a_development_session(development_config):
    """A research role is not silently promoted into writable development despite sharing some business tools."""
    from backend.research.models import RESEARCH_PERMISSIONS

    c = development_config
    async with development_attempt(c, permissions=RESEARCH_PERMISSIONS) as d:
        with pytest.raises(ValueError, match="Business capabilities differ"):
            async with d.coordinator.runtime.open(
                workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
            ):
                pytest.fail("A research grant opened a writable session")
        assert not (c.s.control / "development").exists()
        assert not d.coordinator.store.input_record(101, d.run.run_id)["available"]


async def test_context_correction_after_preparation_prevents_model_dispatch(
    development_config,
):
    """A prepared private copy survives correction but its old lease cannot reserve a new model turn."""
    from backend.runtime.contracts import StaleAttempt

    c = development_config
    async with development_attempt(c) as d:
        async with d.coordinator.runtime.open(
            workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
        ) as session:
            workspace = Path(session.execution_workspace)
            d.coordinator.store.correct_context(
                project_id=101,
                task_id=1001,
                expected_version=d.lease.context_version,
                operation_key="before-model",
                statement="Preserve the original file format.",
                source_kind="user_message",
                source_reference="owner-correction:before-model",
            )
            with pytest.raises(StaleAttempt):
                d.coordinator.store.reserve_input(
                    d.lease,
                    workspace=str(workspace),
                    catalog_hash=session.catalog_hash,
                    model=session.model,
                    developer_instructions=session.developer_instructions,
                    catalog=session.catalog,
                    limits=d.coordinator.limits,
                )
            assert not d.coordinator.store.input_record(101, d.run.run_id)["available"]
        assert d.coordinator.runtime.consume_closure(d.lease) is True
        assert (workspace / "fact.txt").read_text() == "137"
        assert (c.s.workspace / "fact.txt").read_text() == "137"


async def call_development_tool(session, name, arguments):
    """Exercise the native request boundary, including required Ken readiness, without a model turn."""
    return await session._session._request(
        {"method": "item/tool/call", "params": {"tool": name, "arguments": arguments}}
    )


def ken_preparations(session):
    """Count witnessed complete-preparation attempts in this original broker only."""
    return [
        row
        for key, row in session._owner.broker.journal.load().records.items()
        if key.startswith("broker:op:")
        and row.get("runtime_manifest", {}).get("mode") == "prepare"
    ]


async def test_unchanged_code_and_metadata_do_not_reprepare_ken(development_config):
    """Source consistency is content-based; ordinary reads and Ken metadata writes keep the same index revision."""
    c = development_config
    async with development_attempt(c) as d, d.coordinator.runtime.open(
        workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
    ) as session:
        assert len(ken_preparations(session)) == 1
        for _ in range(2):
            response = await call_development_tool(
                session, "ken_read", {"path": "fact.txt"}
            )
            assert response["success"]
        (Path(session.execution_workspace) / ".ken/cache-note").write_text(
            "metadata only"
        )
        response = await call_development_tool(
            session, "ken_read", {"path": "fact.txt"}
        )
        assert response["success"] and len(ken_preparations(session)) == 1


async def test_active_writer_blocks_query_and_uncertain_cancel_requires_reconciliation(
    development_config,
):
    """Cancellation closes the writer; an absent terminal receipt fences the attempt and prevents reindexing."""
    c = development_config
    async with (
        development_attempt(c) as d,
        d.coordinator.runtime.open(
            workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
        ) as session,
    ):
        response = await call_development_tool(
            session,
            "researcher_python",
            {
                "operation_key": "writer",
                "code": "from pathlib import Path;import time;Path('writer-entered').write_text('started');time.sleep(30)",
                "timeout_seconds": 30.0,
            },
        )
        job = json.loads(response["contentItems"][0]["text"])["job_id"]
        marker = Path(session.execution_workspace) / "writer-entered"
        for _ in range(100):
            if marker.exists():
                break
            await asyncio.sleep(0.02)
        assert marker.exists()
        blocked = await call_development_tool(
            session, "ken_read", {"path": "fact.txt"}
        )
        assert (
            not blocked["success"]
            and "writer" in blocked["contentItems"][0]["text"]
        )
        cancelled = await call_development_tool(
            session, "researcher_command_cancel", {"job_id": job}
        )
        # This controlled native transport blocks inside subprocess.run and
        # cannot acknowledge termination. Physical closure must not be
        # promoted to a known exit code or permission to continue effects.
        assert not cancelled["success"]
        assert "durable receipt" in cancelled["contentItems"][0]["text"]
        receipt = d.coordinator.store.get_job(101, job)
        assert receipt.cancel_requested and receipt.local_execution_closed
        assert receipt.status == "unknown" and receipt.exit_code is None
        assert d.coordinator.store.get(101, d.run.run_id).status == "reconciling"
        assert not d.coordinator.store.attempt_active(d.lease)
        assert len(ken_preparations(session)) == 1
        ready = await call_development_tool(
            session, "ken_read", {"path": "fact.txt"}
        )
        assert not ready["success"] and len(ken_preparations(session)) == 1
        assert marker.exists()
        assert not (c.s.workspace / "writer-entered").exists()


async def test_stop_during_reindex_closes_original_owner_without_reopening_ken(
    development_config,
):
    """A hung preparation remains under the global Stop path while the SDK owner drains its own contexts."""
    c = development_config
    async with development_attempt(c) as d:
        async with d.coordinator.runtime.open(
            workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
        ) as session:
            workspace = Path(session.execution_workspace)
            (workspace / "fact.txt").write_text("200")
            (workspace / ".ken/hold-prepare").write_text("hold")
            query = asyncio.create_task(
                call_development_tool(session, "ken_read", {"path": "fact.txt"})
            )
            for _ in range(200):
                if (workspace / ".ken/prepare-entered").exists():
                    break
                await asyncio.sleep(0.02)
            assert (workspace / ".ken/prepare-entered").exists()
            await asyncio.wait_for(session.cancel(), 5)
            await asyncio.gather(query, return_exceptions=True)
            preparations = ken_preparations(session)
            assert len(preparations) == 2 and all(
                row["execution_closed"] for row in preparations
            )
        assert d.coordinator.runtime.consume_closure(d.lease)
        assert (c.s.workspace / "fact.txt").read_text() == "137"
