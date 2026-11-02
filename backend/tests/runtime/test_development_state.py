"""Private development preparations have durable original identity and no automatic destructive retry."""

import json
import sqlite3
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from backend.db.migrations import apply_sql_resource


@pytest.fixture
def development_state(service_setup):
    """Prepare real source registration and lease without enabling a public developer API."""
    from backend.runtime.development_state import DevelopmentWorkspaces
    from backend.runtime.workspaces import WorkspaceRegistry

    s = service_setup
    for filename in ("development_schema.sql", "development_workspace_schema.sql"):
        apply_sql_resource(
            s.c.conn, Path(__file__).resolve().parents[2] / "db" / filename
        )
    s.c.conn.execute("UPDATE tasks SET type='code' WHERE id=1001")
    s.c.conn.commit()
    version = s.c.store.context_snapshot(101, 1001)["context_version"]
    binding = WorkspaceRegistry(s.c.database, s.root).bind(101, 11)
    run = s.c.store.admit(replace(s.c.spec, context_version=version), binding=binding)
    s.c.conn.execute(
        "UPDATE runtime_runs SET execution_kind='development' WHERE id=?", (run.run_id,)
    )
    s.c.conn.commit()
    lease = s.c.store.claim(101, run.run_id, "owner")
    root = s.control / "development"
    root.mkdir(mode=0o700, parents=True)
    return s, lease, binding, DevelopmentWorkspaces(s.c.store, root)


def test_plan_is_durable_before_copy_and_does_not_reallocate_or_adopt_existing_work(
    development_state,
):
    """A crash before clone leaves a real scope record; repeat planning returns data without permission to reset."""
    s, lease, binding, store = development_state
    first, created = store.plan(lease)
    assert created is True and first["state"] == "preparing"
    assert json.loads(first["source_json"]) == asdict(binding)
    assert Path(first["allocation"]).name == lease.attempt_id
    assert not Path(first["allocation"]).exists()
    again, created = store.plan(lease)
    assert created is False and again == first
    assert (
        s.c.conn.execute(
            "SELECT count(*) FROM runtime_development_workspaces"
        ).fetchone()[0]
        == 1
    )


def test_ready_copy_preserves_source_and_has_an_explicit_execution_view(
    development_state,
):
    """Only the pinned child of the planned allocation can become the native execution view."""
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace

    s, lease, binding, store = development_state
    planned, _ = store.plan(lease)
    copy = Path(planned["allocation"]) / "repository"
    copy.mkdir(mode=0o700, parents=True)
    info = copy.stat()
    prepared = PreparedDevelopmentWorkspace(
        11, str(copy), info.st_dev, info.st_ino, "a" * 40, "b" * 40
    )
    ready = store.complete(lease, prepared)
    assert ready["state"] == "ready"
    view = store.view(lease.project_id, lease.attempt_id)
    assert view.source == binding and view.workspace == str(copy)
    assert view.workspace != binding.workspace and view.base_sha == "a" * 40
    assert store.complete(lease, prepared) == ready
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            "UPDATE runtime_development_workspaces SET workspace='changed' WHERE attempt_id=?",
            (lease.attempt_id,),
        )
    s.c.conn.rollback()
    s.c.conn.execute(
        "UPDATE runtime_development_workspaces SET state='reconciling' WHERE attempt_id=?",
        (lease.attempt_id,),
    )
    s.c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            "UPDATE runtime_development_workspaces SET workspace='changed' WHERE attempt_id=?",
            (lease.attempt_id,),
        )
    s.c.conn.rollback()


@pytest.mark.parametrize("missing", ["device", "inode", "base_sha", "base_tree_sha"])
def test_ready_record_requires_complete_identity_in_storage(development_state, missing):
    """SQLite NULL semantics cannot turn incomplete preparation evidence into a ready copy."""
    s, lease, _, store = development_state
    planned, _ = store.plan(lease)
    values = dict(
        workspace=str(Path(planned["allocation"]) / "repository"),
        device=53,
        inode=123,
        base_sha="a" * 40,
        base_tree_sha="b" * 40,
    )
    values[missing] = None
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            """UPDATE runtime_development_workspaces SET state='ready',workspace=?,device=?,inode=?,base_sha=?,base_tree_sha=? WHERE attempt_id=?""",
            (*values.values(), lease.attempt_id),
        )
    s.c.conn.rollback()


def test_context_correction_blocks_late_ready_result_and_preserves_preparation_evidence(
    development_state,
):
    """A useful old copy is retained but cannot authorize writes under a corrected task context."""
    from backend.runtime.contracts import StaleAttempt
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace

    s, lease, _, store = development_state
    planned, _ = store.plan(lease)
    copy = Path(planned["allocation"]) / "repository"
    copy.mkdir(mode=0o700, parents=True)
    (copy / "useful.py").write_text("VALUE = 137\n")
    info = copy.stat()
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=lease.context_version,
        operation_key="correction",
        statement="Use a second source before completing.",
        source_kind="user_message",
        source_reference="owner-correction:correction",
    )
    with pytest.raises(StaleAttempt):
        store.complete(
            lease,
            PreparedDevelopmentWorkspace(
                11, str(copy), info.st_dev, info.st_ino, "a" * 40, "b" * 40
            ),
        )
    store.observe_failure(lease, "Context changed during preparation")
    assert store.inspect(101, lease.run_id)["state"] == "reconciling"
    assert (copy / "useful.py").read_text() == "VALUE = 137\n"


def test_development_peer_never_falls_back_to_original_source(development_state):
    """Preparing a native peer does not make the source checkout its implicit execution directory."""
    from backend.runtime.contracts import RunConflict, RunNotFound
    from backend.runtime.peer_registry import PeerRegistry

    s, lease, source, _ = development_state
    registry = PeerRegistry(s.c.store)
    peer = registry.prepare(lease, "native")
    with pytest.raises((RunConflict, RunNotFound)):
        registry.workspace_binding(peer)
    assert registry.source_binding(peer) == source


def test_ready_peer_admission_separates_source_and_execution_view(development_state):
    """All author peers share the ready copy while their global concession keeps the original source."""
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace
    from backend.runtime.peer_registry import PeerRegistry

    s, lease, source, store = development_state
    planned, _ = store.plan(lease)
    copy = Path(planned["allocation"]) / "repository"
    copy.mkdir(mode=0o700, parents=True)
    info = copy.stat()
    store.complete(
        lease,
        PreparedDevelopmentWorkspace(
            11, str(copy), info.st_dev, info.st_ino, "a" * 40, "b" * 40
        ),
    )
    registry = PeerRegistry(s.c.store)
    peer = registry.prepare(lease, "native")
    admission = registry.admission(peer)
    assert admission["source_binding"] == source
    assert admission["binding"].workspace == str(copy)
    assert admission["binding"] == registry.workspace_binding(peer)
    assert registry.admission(peer, source_only=True)["binding"] == source
