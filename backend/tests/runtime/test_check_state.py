"""Check reservations bind a recipe and execution view before any payload can run."""

from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_code_candidate_state import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- register the durable candidate fixture.
)
from backend.tests.runtime.test_code_candidate_state import (
    captured_result,
    closed_proof,
)
from backend.tests.runtime.test_development_state import (
    development_state as development_state,  # noqa: PLC0414 -- candidate_state dependency.
)


@pytest.fixture
def check_state(candidate_state):
    """Complete synthetic storage identity; real Git/worker execution has separate integration tests."""
    from backend.runtime.check_state import CodeChecks

    s, lease, _binding, _copies, candidates = candidate_state
    planned, _ = candidates.plan(lease)
    candidates.complete(lease, captured_result(planned), closed_proof())
    s.c.conn.execute(
        "INSERT INTO runtime_peer_scopes(attempt_id,protocol_version,created_at) VALUES(?,1,?)",
        (lease.attempt_id, s.c.now[0]),
    )
    s.c.conn.commit()
    return s, lease, CodeChecks(s.c.store)


def prepared_copy(row):
    """Make only the physical identities needed to test durable copy admission, without simulating Git verification."""
    import json

    from backend.runtime.check_workspace import PreparedCheckWorkspace
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace
    from backend.runtime.git_capsule import PrivateAllocation

    root = Path(row["allocation"])
    workspace = root / "repository"
    metadata = root / "validation-git"
    workspace.mkdir(mode=0o700, parents=True)
    metadata.mkdir(mode=0o700)
    data = json.loads(row["subject_json"])
    info = workspace.stat()
    return PreparedCheckWorkspace(
        PreparedDevelopmentWorkspace(
            data["repository_id"],
            str(workspace),
            info.st_dev,
            info.st_ino,
            data["head_sha"],
            data["tree_sha"],
        ),
        PrivateAllocation.capture(metadata),
    )


def test_check_reservation_precedes_files_and_repeated_key_cannot_change_recipe(
    check_state,
):
    """A lost response leaves the original recipe/candidate/path, not permission to execute again."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.contracts import RunConflict

    s, lease, checks = check_state
    spec = CheckSpec(("/usr/bin/true",), "command")
    row, created = checks.plan(lease, "ci-one", spec)
    assert (
        created and row["state"] == "preparing" and not Path(row["allocation"]).exists()
    )
    assert checks.plan(lease, "ci-one", spec) == (row, False)
    with pytest.raises(RunConflict):
        checks.plan(lease, "ci-one", replace(spec, argv=("/usr/bin/false",)))
    assert (
        s.c.conn.execute("SELECT count(*) FROM runtime_code_checks").fetchone()[0] == 1
    )


def test_prepared_copy_and_original_peer_are_required_before_admission(check_state):
    """Only the reserved exact copy and one original command peer can enter the running state."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.peer_registry import PeerRegistry

    s, lease, checks = check_state
    row, _ = checks.plan(lease, "ci-one", CheckSpec(("/usr/bin/true",), "command"))
    prepared = prepared_copy(row)
    ready = checks.prepared(lease, row["id"], prepared)
    assert ready["state"] == "ready"
    peer = PeerRegistry(s.c.store).prepare(lease, "command")
    running = checks.bind_peer(lease, row["id"], peer)
    assert running["state"] == "running" and running["peer_id"] == peer


def test_late_context_correction_retains_but_cannot_admit_a_check(check_state):
    """Useful preparation bytes cannot authorize CI under requirements that have already changed."""
    from backend.runtime.check_contracts import CheckSpec
    from backend.runtime.contracts import StaleAttempt

    s, lease, checks = check_state
    row, _ = checks.plan(lease, "ci-one", CheckSpec(("/usr/bin/true",), "command"))
    prepared = prepared_copy(row)
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=lease.context_version,
        operation_key="check-correction",
        statement="Preserve previous behavior.",
        source_kind="user_message",
        source_reference="owner:check",
    )
    with pytest.raises(StaleAttempt):
        checks.prepared(lease, row["id"], prepared)
    assert (
        checks.observe_failure(lease, row["id"], "Preparation interrupted")["state"]
        == "reconciling"
    )
    assert Path(prepared.view.workspace).exists()


def test_record_origin_is_immutable_before_execution(check_state):
    """A direct SQL update cannot retarget an existing recipe reservation to another candidate or allocation."""
    import sqlite3

    from backend.runtime.check_contracts import CheckSpec

    s, lease, checks = check_state
    row, _ = checks.plan(lease, "ci-one", CheckSpec(("/usr/bin/true",), "command"))
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            "UPDATE runtime_code_checks SET allocation=? WHERE id=?",
            ("/another-copy", row["id"]),
        )
    s.c.conn.rollback()


def test_never_released_peer_cannot_be_recorded_as_a_successful_check(check_state):
    """A prepared peer closed before binding is not evidence that the command actually ran."""
    import json

    from backend.runtime.check_contracts import (
        CandidateSubject,
        CheckObservation,
        CheckSpec,
    )
    from backend.runtime.contracts import RunConflict
    from backend.runtime.peer_registry import PeerRegistry

    s, lease, checks = check_state
    spec = CheckSpec(("/usr/bin/true",), "command")
    row, _ = checks.plan(lease, "not-started", spec)
    checks.prepared(lease, row["id"], prepared_copy(row))
    registry = PeerRegistry(s.c.store)
    peer = registry.prepare(lease, "command")
    checks.bind_peer(lease, row["id"], peer)
    registry.close(peer)
    observed = CheckObservation(
        CandidateSubject(**json.loads(row["subject_json"])),
        spec.sha256,
        0,
        True,
        True,
        True,
    )
    with pytest.raises(RunConflict, match="closure"):
        checks.complete(
            lease, row["id"], observed, operation_id="e" * 64, stdout=b"", stderr=b""
        )


@pytest.mark.parametrize("schema_target", [39])
def test_unused_check_inverse_preserves_older_candidate_history(service_setup):
    """Removing unused version39 preserves all older candidate and task/run values exactly."""
    from backend.db.development_migration import restore_code_checks
    from backend.tests.runtime.migration_fixtures import historical_candidate,historical_rows
    from backend.tools.base.db import ensure_migrations

    c=service_setup.c
    historical_candidate(c.conn)
    before=historical_rows(c.conn,'runtime_code_candidates','runtime_development_workspaces','runtime_runs','runtime_attempts','tasks')
    restore_code_checks(c.conn)
    restore_code_checks(c.conn)
    assert historical_rows(c.conn,*before)==before
    ensure_migrations(c.database,target_version=39)
    assert c.conn.execute('SELECT count(*) FROM runtime_code_checks').fetchone()[0]==0
    assert historical_rows(c.conn,*before)==before
    assert c.conn.execute('PRAGMA foreign_key_check').fetchall()==[]



@pytest.mark.parametrize("schema_target", [39])
def test_check_inverse_refuses_a_reserved_or_historical_check(service_setup):
    """A retained version39 check reservation is itself the blocker, independently of later schema or active actors."""
    from backend.db.development_migration import restore_code_checks
    from backend.tests.runtime.migration_fixtures import historical_candidate,historical_rows

    c=service_setup.c
    attempt=historical_candidate(c.conn)
    c.conn.execute("""INSERT INTO runtime_code_checks(id,attempt_id,run_id,project_id,task_id,context_version,
        fence,owner_id,operation_key,subject_json,spec_json,spec_sha256,allocation,state,created_at,updated_at)
        VALUES('retained-check',?,'historical-author',101,1001,1,1,'historical-owner','check','{}','{}',?,'old-check','preparing',1000,1000)""",(attempt,'d'*64))
    c.conn.commit()
    before=historical_rows(c.conn,'runtime_code_checks','runtime_code_candidates','runtime_runs','runtime_attempts')
    with pytest.raises(RuntimeError,match='rollback refused'):restore_code_checks(c.conn)
    assert historical_rows(c.conn,*before)==before
    assert c.conn.execute('PRAGMA foreign_key_check').fetchall()==[]

