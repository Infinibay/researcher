"""Real product coordinator/API/storage/kernel; generation protocol is controlled."""

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


async def test_failed_preparation_reports_proven_closure_without_inference(owned_config, monkeypatch, caplog):
    """An actual empty kernel domain can close after preparation fails, without implying unknown inference or replaying admission."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.authority_journal import AuthorityBusy
    from backend.runtime.native_state import NativeState

    def unavailable(*args, **kwargs):
        """Fail before any peer is launched, retaining private error text only in memory."""
        try:
            raise ValueError('PRIVATE_PREPARATION_CAUSE')
        except ValueError as cause:
            raise AuthorityBusy('PRIVATE_PREPARATION_MESSAGE') from cause

    monkeypatch.setattr(NativeState, 'provision', unavailable)
    c = owned_config
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    async with runtime:
        run = await runtime.submit(c.s.c.spec, repository_id=11)
        await runtime.wait(run.run_id)
        saved = runtime.store.get(101, run.run_id)
    assert saved.status == 'failed'
    assert saved.issue['inference_started'] is False
    assert saved.issue['closure_confirmed'] is True
    assert 'preparación' in saved.issue['message']
    assert 'No se inició inferencia' in saved.issue['message']
    assert 'se comprobó el cierre' in saved.issue['message']
    assert saved.issue['next_action'] == 'inspect_saved_work'
    assert 'PRIVATE_PREPARATION' not in json.dumps(saved.issue)
    assert 'PRIVATE_PREPARATION' not in caplog.text
    assert 'backend.runtime.owned_runtime.open:' in caplog.text
    assert 'AuthorityBusy' in caplog.text and 'ValueError' in caplog.text
    with runtime.store._transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM runtime_attempts WHERE turn_id IS NOT NULL').fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM runtime_peers WHERE state!='closed'").fetchone()[0] == 0


@pytest.fixture
def owned_config(
    service_setup, ken_installation, code_host_asset, tmp_path, monkeypatch
):
    from backend.api import config
    from backend.runtime.bootstrap import initialize_authority

    relative = Path("/proc/self/cgroup").read_text().strip().split(":", 2)[2]
    parent = (Path("/sys/fs/cgroup") / relative.lstrip("/")).parent
    if not os.access(parent, os.W_OK) or not {"memory", "pids"} <= set(
        (parent / "cgroup.subtree_control").read_text().split()
    ):
        pytest.skip("Requires delegated memory/pids cgroup controllers")
    authority = tmp_path / "authority"
    authority.mkdir(mode=0o700)
    supplied = SimpleNamespace(
        **initialize_authority(
            database_dir=authority / "database", witness_dir=authority / "witness"
        )
    )
    ken_installation.write_text(
        "#!"
        + str(ken_installation.parent / "python")
        + "\n"
        + Path(__file__).with_name("fake_broker_ken.py").read_text()
    )
    binary = tmp_path / "controlled-native"
    binary.write_text(
        "#!/usr/bin/python3\n"
        + Path(__file__).with_name("fake_owned_native.py").read_text()
    )
    binary.chmod(0o755)
    tokens = tmp_path / "auth.json"
    tokens.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "fixture.header.signature",
                    "account_id": "fixture-account",
                },
            }
        )
    )
    tokens.chmod(0o600)
    models = tmp_path / "models"
    models.mkdir()
    uploads = tmp_path / "uploads"
    target = uploads / "101/uploads"
    target.mkdir(parents=True)
    attachment = target / "fixture.txt"
    attachment.write_text("Fixture base 137 units.")
    monkeypatch.setattr(config, "UPLOAD_DIR", str(uploads))
    service_setup.c.conn.execute(
        "INSERT INTO reference_files(id,project_id,file_name,file_path,file_size,file_type) VALUES(7,101,'fixture.txt',?,23,'text/plain')",
        (str(attachment),),
    )
    service_setup.c.conn.commit()
    (service_setup.workspace / "fact.txt").write_text("137")
    path = tmp_path / "runtime.json"
    settings = {
        "runtime_profile": "owned-codex-v1",
        "model": "controlled-only",
        "codex_binary": str(binary),
        "code_mode_host": code_host_asset.path,
        "token_file": str(tokens),
        "ken_command": str(ken_installation),
        "model_cache": str(models),
        "workspace_root": str(service_setup.root),
        "control_root": str(service_setup.control),
        "cgroup_parent": str(parent),
        "authority": {k: str(v) for k, v in vars(supplied).items()},
        "broker_limits": {"memory_bytes": 2 * 1024**3, "pids": 128},
        "limits": {
            "wall_seconds": 30,
            "no_progress_seconds": 10,
            "max_turns": 1,
            "max_tool_calls": 25,
            "max_observed_tokens": 1000,
        },
    }
    path.write_text(json.dumps(settings))
    monkeypatch.setenv("INFINIBAY_RUNTIME_CONFIG", str(path))
    return SimpleNamespace(
        s=service_setup,
        path=path,
        settings=settings,
        authority=supplied,
        tokens=tokens,
        parent=parent,
    )


@pytest.mark.timeout(180)
async def test_owned_memory_exhaustion_is_closed_and_explained_to_the_owner(owned_config):
    """Real cgroup exhaustion crosses broker, runtime and persisted user feedback without a second inference dispatch."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime

    c = owned_config
    c.settings["broker_limits"]["memory_bytes"] = 256 * 1024**2
    c.path.write_text(json.dumps(c.settings))
    (c.s.workspace / ".ken").mkdir(exist_ok=True)
    (c.s.workspace / ".ken/exhaust-memory").touch()
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    async with runtime:
        run = await runtime.submit(c.s.c.spec)
        await runtime.wait(run.run_id)
        saved = runtime.store.get(101, run.run_id)
        assert saved.status == "failed", saved
        assert saved.issue["code"] == "resource_exhaustion"
        assert "memoria" in saved.issue["message"]
        assert saved.issue["resource_observation"]["memory_oom_kills"] > 0
        assert c.s.c.conn.execute("SELECT count(*)FROM runtime_peers WHERE state!='closed'").fetchone()[0] == 0
        assert c.s.c.conn.execute("SELECT count(*)FROM runtime_inference_dispatches").fetchone()[0] == 1
        assert c.s.c.conn.execute("SELECT count(*)FROM tool_grants WHERE revoked_at IS NULL").fetchone()[0] == 0


@pytest.mark.parametrize("task_type", ["research", "review"])
async def test_configured_owned_product_run_persists_draft_and_analysis_receipts(
    owned_config, task_type,
):
    """Prove controlled native author delivery and durable analysis receipts through the configured product runtime."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime

    c = owned_config
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    assert type(runtime.runtime).__name__ == "OwnedCodexRuntime"
    from dataclasses import replace

    c.s.c.conn.execute("UPDATE tasks SET type=? WHERE id=1001", (task_type,))
    c.s.c.conn.commit()
    spec = replace(c.s.c.spec, context_version=runtime.store.context_snapshot(101,1001)["context_version"])
    async with runtime:
        run = await runtime.submit(spec, repository_id=11)
        await runtime.wait(run.run_id)
        view = runtime.store.get(101, run.run_id)
        assert view.status == "needs_review", (
            view,
            [
                p.read_text()
                for p in c.s.control.glob("native-state/*/home/fixture-progress.json")
            ],
        )
        delivery = runtime.store.result_state(101, run.run_id)
        assert delivery["eligible"] is True
        assert delivery["candidate"]["kind"] == "research_reports"
        assert delivery["candidate"]["reports"][0]["title"] == "Fixture inspection"
        assert delivery["acceptance"] is None
        with runtime.store._transaction() as db:
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM research_reports WHERE status='draft'"
                ).fetchone()[0]
                == 1
            )
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM findings WHERE status='provisional'"
                ).fetchone()[0]
                == 1
            )
            jobs = db.execute(
                "SELECT status,exit_code,stdout FROM runtime_jobs"
            ).fetchall()
            assert (
                len(jobs) == 1
                and jobs[0]["status"] == "exited"
                and jobs[0]["exit_code"] == 0
                and b"200" in jobs[0]["stdout"]
            )
            assert not db.execute(
                "SELECT 1 FROM runtime_peers WHERE state<>'closed'"
            ).fetchone()
            assert (
                db.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
                != "done"
            )
        assert (c.s.workspace / "fact.txt").read_text() == "137"
        if task_type == "review":
            frozen = runtime.store.input_record(101, run.run_id)
            assert "read-only code audit" in frozen["developer_instructions"]
            assert "cannot approve" in frozen["developer_instructions"]
        from backend.tests.runtime.authority_fixture import journal

        with journal(c.authority) as storage:
            records = storage.load().records
            assert records["broker:active"] is None
            grants = [
                value
                for key, value in records.items()
                if key.startswith("broker:grant:")
            ]
            assert len(grants) == 1 and grants[0]["state"] == "retired"
        assert len(list(c.s.control.glob("native-state/*/home"))) == 1


def test_owned_configuration_requires_its_actual_application_controller(owned_config):
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.live_grants import LiveGrants

    with pytest.raises(ValueError, match="application|controller"):
        configured_runtime(LiveGrants())


def test_owned_configuration_never_initializes_absent_global_authority(owned_config):
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime

    c = owned_config
    Path(c.settings["authority"]["witness"]).unlink()
    app = create_app()
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError)):
        configured_runtime(app.state.live_grants, app=app)
    assert not Path(c.settings["authority"]["witness"]).exists()


async def test_unavailable_search_leaves_an_actionable_owner_issue_without_dispatch(
    owned_config,
):
    """Explain a failed capability admission without spending or hiding a fallback."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime

    c = owned_config
    (c.s.workspace / "search-unavailable").touch()
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    async with runtime:
        run = await runtime.submit(c.s.c.spec, repository_id=11)
        await runtime.wait(run.run_id)
        view = runtime.store.get(101, run.run_id)
        assert view.issue["code"] == "native_search_unavailable"
        assert "búsqueda web" in view.issue["message"]
        assert view.issue["inference_started"] is False
        assert view.issue["next_action"] == "review_runtime_configuration"
        assert view.status == "failed"
        with runtime.store._transaction() as db:
            assert (
                db.execute(
                    "SELECT COUNT(*) FROM runtime_inference_dispatches"
                ).fetchone()[0]
                == 0
            )
            assert db.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


@pytest.mark.parametrize("stage", ["prepare", "turn"])
@pytest.mark.parametrize("action", ["stop", "correct"])
async def test_owned_stop_withdraws_startup_or_generation_and_preserves_unknown_dispatch(
    owned_config, stage, action
):
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.tests.runtime.authority_fixture import journal

    c = owned_config
    markers = c.s.workspace / ".ken"
    markers.mkdir()
    (markers / ("hold-" + stage)).write_text("hold")
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    app.state.runtime_service = runtime
    async with runtime:
        run = await runtime.submit(c.s.c.spec, repository_id=11)
        async with asyncio.timeout(5):
            while not (
                (markers / "prepare-entered").exists()
                if stage == "prepare"
                else list(c.s.control.glob("native-state/*/home/turn-entered"))
            ):
                await asyncio.sleep(0.02)
        if action == "stop":
            await runtime.stop(101, run.run_id)
        else:
            await runtime.correct(
                project_id=101,
                task_id=1001,
                expected_version=1,
                operation_key="correct-base",
                statement="Use base200; the earlier base137 is superseded.",
                source_kind="user_example",
                source_reference="owner-fixture",
            )
            assert runtime.store.context_snapshot(101, 1001)["context_version"] == 2
        await asyncio.wait_for(runtime.wait(run.run_id), 5)
        assert runtime.store.get(101, run.run_id).status == (
            "cancelled" if action == "stop" else "superseded"
        )
        with journal(c.authority) as storage:
            assert storage.load().records["broker:active"] is None
        with runtime.store._transaction() as db:
            assert not db.execute(
                "SELECT 1 FROM runtime_peers WHERE state<>'closed'"
            ).fetchone()
            assert not db.execute("SELECT 1 FROM research_reports").fetchone()
            assert db.execute(
                "SELECT COUNT(*) FROM runtime_inference_dispatches"
            ).fetchone()[0] == (stage == "turn")


async def test_owned_business_source_is_pinned_and_rejects_a_replaced_database(
    owned_config, monkeypatch, tmp_path
):
    import sqlite3

    import httpx

    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.peer_registry import AttemptPeers

    c = owned_config
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    binding = runtime.workspaces.bind(101, 11)
    run = runtime.store.admit(c.s.c.spec, binding=binding)
    lease, peers = AttemptPeers.claim(
        runtime.store, 101, run.run_id, "source-test", lease_seconds=30
    )
    token = runtime.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions={"sources.read"},
        ttl_seconds=60,
    )
    scope = runtime.research.authorize(token)
    runtime.store.bind_grant(lease, scope.grant_id)
    runtime.live_grants.activate(scope.grant_id)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
    ) as client:
        monkeypatch.setenv("INFINIBAY_DB", str(tmp_path / "wrong.db"))
        assert (
            await client.get(
                "/api/research-tools/references",
                headers={"Authorization": "Bearer " + token},
            )
        ).status_code == 200
        source = Path(runtime.store.database)
        c.s.c.conn.close()
        copied = tmp_path / "replaced.db"
        with sqlite3.connect(source) as old, sqlite3.connect(copied) as new:
            old.backup(new)
        retired = source.with_suffix(".retired")
        source.rename(retired)
        copied.rename(source)
        try:
            assert (
                await client.get(
                    "/api/research-tools/references",
                    headers={"Authorization": "Bearer " + token},
                )
            ).status_code == 401
        finally:
            source.unlink()
            retired.rename(source)
    await peers.aclose()


async def test_app_lifespan_and_owner_http_entry_use_configured_owned_factory(
    owned_config, monkeypatch
):
    from backend.api import run as api_run
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    monkeypatch.setattr(api_run, "setup_file_logging", lambda: None)
    app = create_app(
        access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters")
    )
    async with app.router.lifespan_context(app), owner_client(app) as client:
        response = await client.post(
            "/api/projects/101/tasks/1001/runs",
            json={
                "operation_key": "owner-http",
                "context_version": 1,
                "request": "Inspect the synthetic source and keep a draft.",
                "repository_id": 11,
            },
        )
        assert response.status_code == 202, response.text
        result = response.json()
        run_id = result["run_id"]
        await app.state.runtime_service.wait(run_id)
        response = await client.get("/api/projects/101/runs/" + run_id)
        assert (
            response.status_code == 200 and response.json()["status"] == "needs_review"
        ), response.text
        assert type(app.state.runtime_service.runtime).__name__ == "OwnedCodexRuntime"
