"""Git preparation runs through the real gated broker, with only its allocation writable."""

import shutil
from pathlib import Path

import pytest

from backend.tests.runtime.test_development_workspace import fixture_git


async def test_real_broker_prepares_copy_and_closes_every_git_peer(broker_setup):
    """Prove exact source/copy isolation and global/source closure through the actual resource owner."""
    from backend.runtime.broker_git import OwnedGitExecutor
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.development_workspace import prepare_workspace
    from backend.runtime.git_capsule import GitAsset

    s, registry, peer, broker, storage, domain_path = broker_setup
    await fixture_git(s.workspace, "init", "-q")
    (s.workspace / "value.py").write_text(
        '"""Synthetic owned development fixture."""\nVALUE = 137\n'
    )
    await fixture_git(s.workspace, "add", "value.py")
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
    with registry.runs._transaction() as conn:
        _row, lease = registry._lease(conn, registry._row(conn, peer))
    # Low-level schema/policy fixture; full product admission is intentionally not inferred.
    s.c.conn.execute(
        "UPDATE runtime_runs SET execution_kind='development' WHERE id=?",
        (lease.run_id,),
    )
    s.c.conn.commit()
    allocation = s.control / "development" / lease.attempt_id
    allocation.parent.mkdir(mode=0o700, parents=True)
    asset = GitAsset.inspect(Path(shutil.which("git")))
    async with AsyncPeerBroker(broker) as owner:
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=s.workspace,
            allocation=allocation,
            asset=asset,
        )
        prepared = await prepare_workspace(
            registry.source_binding(peer), allocation, executor=executor
        )
        assert (Path(prepared.workspace) / "value.py").read_bytes() == (
            s.workspace / "value.py"
        ).read_bytes()
        assert (
            prepared.base_sha
            == (await fixture_git(s.workspace, "rev-parse", "HEAD")).decode().strip()
        )
        assert executor.operations
        for operation_id in executor.operations:
            operation = storage.load().records["broker:op:" + operation_id]
            assert operation["execution_closed"] is True
            assert operation["exit_code"] == 0
            assert (
                operation["runtime_manifest"]["profile"] == "owned-git-preparation-v1"
            )
        assert domain_path.exists() and not broker._withdrawn.is_set()

    assert (s.workspace / "value.py").read_text().endswith("VALUE = 137\n")


async def prepare_policy_fixture(s, registry, peer):
    """Select the low-level development kind without claiming public developer admission is enabled."""
    with registry.runs._transaction() as conn:
        _row, lease = registry._lease(conn, registry._row(conn, peer))
    s.c.conn.execute(
        "UPDATE runtime_runs SET execution_kind='development' WHERE id=?",
        (lease.run_id,),
    )
    s.c.conn.commit()
    return lease


async def test_durable_preparation_keeps_one_global_source_and_exposes_only_ready_copy(
    broker_setup,
):
    """A real Git preparation and later analysis share ownership without confusing source and execution paths."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.git_capsule import GitAsset

    s, registry, peer, broker, storage, _ = broker_setup
    lease = await prepare_policy_fixture(s, registry, peer)
    await fixture_git(s.workspace, "init", "-q")
    (s.workspace / "value.py").write_text("VALUE = 137\n")
    await fixture_git(s.workspace, "add", "value.py")
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
    state = DevelopmentWorkspaces(s.c.store, root)
    async with AsyncPeerBroker(broker) as owner:
        view = await state.prepare(
            lease,
            owner=owner,
            registry=registry,
            asset=GitAsset.inspect(Path(shutil.which("git"))),
        )
        assert state.inspect(101, lease.run_id)["state"] == "ready"
        assert view.source == registry.source_binding(peer)
        (Path(view.workspace) / "value.py").write_text("VALUE = 200\n")
        following = registry.prepare(lease, "command")
        started = broker.run_peer(
            registry,
            following,
            operation_key="read-prepared-copy",
            code="from pathlib import Path;print(Path('value.py').read_text())",
        )
        assert started.child.wait(timeout=8) == 0
        out = started.child.stdout.read()
        started.child.close_handles()
        assert b"VALUE = 200" in out
        operation = storage.load().records["broker:op:" + started.operation_id]
        assert operation["execution_binding"]["workspace"] == view.workspace
        grant = storage.load().records[broker._grant_key]
        assert grant["workspace_binding"]["workspace"] == str(s.workspace)
        before = set(storage.load().records)
        from backend.runtime.contracts import RunConflict

        with pytest.raises(RunConflict, match="already exists"):
            await state.prepare(
                lease,
                owner=owner,
                registry=registry,
                asset=GitAsset.inspect(Path(shutil.which("git"))),
            )
        assert set(storage.load().records) == before
    assert (s.workspace / "value.py").read_text() == "VALUE = 137\n"


async def test_context_change_after_real_clone_retains_copy_without_admitting_it(
    broker_setup, monkeypatch
):
    """Late preparation cannot cross a corrected context; its useful files and closure evidence survive."""
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.contracts import StaleAttempt
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.git_capsule import GitAsset

    s, registry, peer, broker, storage, _ = broker_setup
    lease = await prepare_policy_fixture(s, registry, peer)
    await fixture_git(s.workspace, "init", "-q")
    (s.workspace / "value.py").write_text("VALUE = 137\n")
    await fixture_git(s.workspace, "add", "value.py")
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
    state = DevelopmentWorkspaces(s.c.store, root)
    complete = state.complete

    def correct_before_complete(lease, prepared):
        """Model the owner correcting requirements after the physical clone has already finished."""
        s.c.store.correct_context(
            project_id=101,
            task_id=1001,
            expected_version=lease.context_version,
            operation_key="new-context",
            statement="Preserve the original interface.",
            source_kind="user_message",
            source_reference="owner-correction:new-context",
        )
        return complete(lease, prepared)

    monkeypatch.setattr(state, "complete", correct_before_complete)
    async with AsyncPeerBroker(broker) as owner:
        with pytest.raises(StaleAttempt):
            await state.prepare(
                lease,
                owner=owner,
                registry=registry,
                asset=GitAsset.inspect(Path(shutil.which("git"))),
            )
        record = state.inspect(101, lease.run_id)
        assert record["state"] == "reconciling" and record["workspace"] is None
        assert (
            Path(record["allocation"]) / "repository/value.py"
        ).read_text() == "VALUE = 137\n"
        operations = [
            value
            for key, value in storage.load().records.items()
            if key.startswith("broker:op:")
        ]
        assert operations and all(op["execution_closed"] is True for op in operations)
    assert (s.workspace / "value.py").read_text() == "VALUE = 137\n"


async def test_git_broker_keeps_original_source_readonly(broker_setup):
    """Even an admitted Git writer can mutate only the private allocation, never its registered source."""
    from backend.runtime.broker_git import OwnedGitExecutor
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.development_workspace import git_environment
    from backend.runtime.git_capsule import GitAsset
    from backend.runtime.workspaces import PEER_WORKSPACE

    s, registry, peer, broker, storage, _ = broker_setup
    await fixture_git(s.workspace, "init", "-q")
    lease = await prepare_policy_fixture(s, registry, peer)
    allocation = s.control / "private-copy"
    allocation.parent.mkdir(mode=0o700, parents=True)
    asset = GitAsset.inspect(Path(shutil.which("git")))
    async with AsyncPeerBroker(broker) as owner:
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=s.workspace,
            allocation=allocation,
            asset=asset,
        )
        result = await executor.run(
            (asset.path, "config", "--local", "fixture.mustNotWrite", "bad"),
            cwd=PEER_WORKSPACE,
            env=git_environment(Path("/home/actor")),
            timeout=10,
        )
        assert (
            result.exit_code != 0
            and result.local_execution_closed
            and result.output_complete
        )
        assert "mustNotWrite" not in (s.workspace / ".git/config").read_text()
        assert (
            storage.load().records["broker:op:" + executor.operations[0]][
                "execution_closed"
            ]
            is True
        )


async def test_changed_source_registration_between_reservation_and_gate_cannot_launch_git(
    broker_setup, monkeypatch
):
    """Owner changes during gated startup must be checked again before a Git payload can execute."""
    from backend.runtime.broker_git import OwnedGitExecutor
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.contracts import WorkspaceChanged
    from backend.runtime.development_workspace import git_environment
    from backend.runtime.git_capsule import GitAsset
    from backend.runtime.workspaces import PEER_WORKSPACE

    s, registry, peer, broker, storage, _ = broker_setup
    lease = await prepare_policy_fixture(s, registry, peer)
    asset = GitAsset.inspect(Path(shutil.which("git")))
    original = registry.bind

    def redirect_before_gate(peer_id, identity):
        """Model an explicit repository-registration edit after the process exists but before its gate opens."""
        with registry.runs._transaction(write=True) as conn:
            conn.execute(
                "UPDATE repositories SET local_path=? WHERE id=11",
                (str(s.workspace.parent / "changed"),),
            )
        return original(peer_id, identity)

    monkeypatch.setattr(registry, "bind", redirect_before_gate)
    async with AsyncPeerBroker(broker) as owner:
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=s.workspace,
            allocation=s.control / "unallocated",
            asset=asset,
        )
        with pytest.raises(WorkspaceChanged):
            await executor.run(
                (asset.path, "--version"),
                cwd=PEER_WORKSPACE,
                env=git_environment(Path("/home/actor")),
                timeout=10,
            )
        assert not executor.receipts
    operations = [
        value
        for key, value in storage.load().records.items()
        if key.startswith("broker:op:")
    ]
    assert len(operations) == 1
    assert (
        operations[0]["gate_sent"] is False
        and operations[0]["execution_closed"] is True
    )


async def test_cancelling_git_waits_for_actual_peer_closure(broker_setup):
    """A cancelled preparation cannot report success while its Git/shell child remains capable of acting."""
    import asyncio

    import pytest

    from backend.runtime.broker_git import OwnedGitExecutor
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.development_workspace import git_environment
    from backend.runtime.git_capsule import PEER_ALLOCATION, GitAsset

    s, registry, peer, broker, storage, _ = broker_setup
    await fixture_git(s.workspace, "init", "-q")
    lease = await prepare_policy_fixture(s, registry, peer)
    allocation = s.control / "cancelled-copy"
    allocation.mkdir(mode=0o700, parents=True)
    asset = GitAsset.inspect(Path(shutil.which("git")))
    async with AsyncPeerBroker(broker) as owner:
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=s.workspace,
            allocation=allocation,
            asset=asset,
        )
        command = (
            asset.path,
            "-c",
            f"alias.wait=!touch {PEER_ALLOCATION}/started; sleep 30",
            "wait",
        )
        task = asyncio.create_task(
            executor.run(
                command,
                cwd=PEER_ALLOCATION,
                env=git_environment(Path("/home/actor")),
                timeout=20,
            )
        )
        try:
            async with asyncio.timeout(5):
                while not (allocation / "started").exists():
                    if task.done():
                        await task
                    await asyncio.sleep(0.02)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            operation = storage.load().records["broker:op:" + executor.operations[0]]
            assert operation["execution_closed"] is True
            assert registry.inspect(operation["peer_id"])["state"] == "closed"
            assert not executor.receipts
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


async def test_real_broker_captures_candidate_in_its_original_private_allocation(
    broker_setup,
):
    """Actual Git gates pin a separate complete candidate while every peer retains original source ownership."""
    from backend.runtime.broker_git import OwnedGitExecutor
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.code_candidate import capture_candidate
    from backend.runtime.development_workspace import prepare_workspace
    from backend.runtime.git_capsule import GitAsset

    s, registry, peer, broker, storage, _domain_path = broker_setup
    await fixture_git(s.workspace, "init", "-q")
    (s.workspace / "value.py").write_text(
        '"""Original owned candidate fixture."""\nVALUE = 137\n'
    )
    await fixture_git(s.workspace, "add", "value.py")
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
    with registry.runs._transaction() as conn:
        _row, lease = registry._lease(conn, registry._row(conn, peer))
    s.c.conn.execute(
        "UPDATE runtime_runs SET execution_kind='development' WHERE id=?",
        (lease.run_id,),
    )
    s.c.conn.commit()
    allocation = s.control / "development" / lease.attempt_id
    allocation.parent.mkdir(mode=0o700, parents=True)
    binding = registry.source_binding(peer)
    async with AsyncPeerBroker(broker) as owner:
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=s.workspace,
            allocation=allocation,
            asset=GitAsset.inspect(Path(shutil.which("git"))),
        )
        prepared = await prepare_workspace(binding, allocation, executor=executor)
        author = Path(prepared.workspace)
        (author / "value.py").write_text(
            '"""Edited owned candidate fixture."""\nVALUE = 200\n'
        )
        (author / "new.py").write_text('"""New private source."""\nVALUE = 200\n')
        first_capture_operation = len(executor.operations)
        captured = await capture_candidate(
            binding, prepared, allocation / "candidate", executor=executor
        )
        assert (Path(captured.workspace) / "new.py").read_bytes() == (
            author / "new.py"
        ).read_bytes()
        assert b"VALUE = 200" in captured.diff and b"new.py" in captured.diff
        assert len(executor.operations) > first_capture_operation
        for operation_id in executor.operations:
            operation = storage.load().records["broker:op:" + operation_id]
            assert operation["execution_closed"] and operation["exit_code"] == 0
            assert operation["execution_binding"]["workspace"] == str(s.workspace)
            assert operation["runtime_manifest"]["launch"][
                "allocation"
            ] is None or operation["runtime_manifest"]["launch"]["allocation"][
                "path"
            ] == str(allocation)
        assert "137" in (s.workspace / "value.py").read_text()
        assert await fixture_git(s.workspace, "status", "--porcelain") == b""
    assert storage.load().records[broker._grant_key]["state"] == "retired"
