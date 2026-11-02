"""Durable code candidates retain exact original attempt/context and never authorize capture replay."""

import hashlib
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_development_state import (
    development_state as development_state,  # noqa: PLC0414 -- register the shared state fixture.
)


@pytest.fixture
def candidate_state(development_state):
    """Prepare physical synthetic identities; Git bytes are verified separately by the real capture tests."""
    from backend.runtime.candidate_state import CodeCandidates
    from backend.runtime.development_workspace import PreparedDevelopmentWorkspace

    s, lease, binding, copies = development_state
    planned, _ = copies.plan(lease)
    author = Path(planned["allocation"]) / "repository"
    author.mkdir(mode=0o700, parents=True)
    info = author.stat()
    copies.complete(
        lease,
        PreparedDevelopmentWorkspace(
            11, str(author), info.st_dev, info.st_ino, "a" * 40, "b" * 40
        ),
    )
    return s, lease, binding, copies, CodeCandidates(s.c.store)


def captured_result(planned):
    """Construct a host-result value for storage contract tests without pretending to execute Git."""
    from backend.runtime.code_candidate import CapturedCodeCandidate

    snapshot = Path(planned["allocation"]) / "repository"
    snapshot.mkdir(mode=0o700, parents=True)
    info = snapshot.stat()
    diff = b"diff fixture\n"
    return CapturedCodeCandidate(
        11,
        "a" * 40,
        "c" * 40,
        "d" * 40,
        str(snapshot),
        info.st_dev,
        info.st_ino,
        diff,
        hashlib.sha256(diff).hexdigest(),
    )


def closed_proof():
    """Represent the trusted controller's closed-operation observations for one original domain."""
    return {
        "grant_id": "f" * 64,
        "operations": [{"operation_id": "e" * 64, "execution_closed": True}],
    }


def test_candidate_plan_persists_original_scope_before_creating_files(candidate_state):
    """A reserved path and origin survive a crash without granting a second capture or adopting old files."""
    s, lease, binding, _copies, candidates = candidate_state
    planned, created = candidates.plan(lease)
    assert created and planned["state"] == "capturing"
    assert (
        planned["context_version"] == lease.context_version
        and planned["repository_id"] == binding.repository_id
    )
    assert planned["attempt_id"] == lease.attempt_id and planned["base_sha"] == "a" * 40
    assert not Path(planned["allocation"]).exists()
    assert json.loads(planned["source_json"])["workspace"] == binding.workspace
    again, created = candidates.plan(lease)
    assert not created and again == planned
    assert (
        s.c.conn.execute("SELECT count(*) FROM runtime_code_candidates").fetchone()[0]
        == 1
    )


def test_candidate_completion_is_exact_immutable_and_survives_store_reopen(
    candidate_state,
):
    """Only a complete host observation becomes ready; its commit/diff remain inspectable independently of live authority."""
    from backend.runtime.candidate_state import CodeCandidates
    from backend.runtime.sqlite_runs import SQLiteRunStore

    s, lease, _binding, _copies, candidates = candidate_state
    planned, _ = candidates.plan(lease)
    result = captured_result(planned)
    ready = candidates.complete(lease, result, closed_proof())
    assert ready["state"] == "ready" and ready["head_sha"] == result.head_sha
    assert (
        bytes(ready["diff"]) == result.diff
        and ready["diff_sha256"] == result.diff_sha256
    )
    assert candidates.complete(lease, result, closed_proof()) == ready
    reopened = CodeCandidates(SQLiteRunStore(s.c.database, clock=lambda: s.c.now[0]))
    assert reopened.inspect(101, lease.run_id) == ready
    assert s.c.store.get(101, lease.run_id).status == "running"
    assert s.c.store.context_snapshot(101, 1001)["task"]["status"] != "done"
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            "UPDATE runtime_code_candidates SET head_sha=? WHERE attempt_id=?",
            ("e" * 40, lease.attempt_id),
        )
    s.c.conn.rollback()


@pytest.mark.parametrize(
    "wrong", ["repository", "base", "directory", "diff_hash", "head", "closure"]
)
def test_wrong_candidate_cannot_be_bound_to_the_attempt(candidate_state, wrong):
    """A host result cannot silently switch the repository, parent, allocation, content digest or closure proof."""
    from backend.runtime.contracts import RunConflict

    _s, lease, _binding, _copies, candidates = candidate_state
    planned, _ = candidates.plan(lease)
    result = captured_result(planned)
    proof = closed_proof()
    if wrong == "repository":
        result = replace(result, repository_id=22)
    elif wrong == "base":
        result = replace(result, base_sha="e" * 40)
    elif wrong == "directory":
        result = replace(result, workspace=str(Path(result.workspace).parent))
    elif wrong == "diff_hash":
        result = replace(result, diff_sha256="e" * 64)
    elif wrong == "head":
        result = replace(result, head_sha="branch-name")
    else:
        proof["operations"][0]["execution_closed"] = False
    with pytest.raises(RunConflict):
        candidates.complete(lease, result, proof)
    assert candidates.inspect(lease.project_id, lease.run_id)["state"] == "capturing"


def test_context_correction_blocks_ready_but_retains_the_original_failure(
    candidate_state,
):
    """A former owner can record its interrupted capture without validating it under corrected requirements."""
    from backend.runtime.contracts import RunConflict, StaleAttempt

    s, lease, _binding, _copies, candidates = candidate_state
    planned, _ = candidates.plan(lease)
    result = captured_result(planned)
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=lease.context_version,
        operation_key="correct-candidate",
        statement="Preserve the original behavior.",
        source_kind="user_message",
        source_reference="owner:correction",
    )
    with pytest.raises(StaleAttempt):
        candidates.complete(lease, result, closed_proof())
    retained = candidates.observe_failure(
        lease, "Capture interrupted after context changed"
    )
    assert retained["state"] == "reconciling" and Path(result.workspace).exists()
    with pytest.raises(StaleAttempt):
        candidates.plan(lease)
    with pytest.raises(RunConflict, match="original owner"):
        candidates.observe_failure(
            replace(lease, owner_id="another-owner"), "Cannot adopt"
        )


def test_candidate_scope_is_immutable_even_before_completion(candidate_state):
    """SQLite protects reserved origin/path identity before any filesystem or Git side effect starts."""
    s, lease, _binding, _copies, candidates = candidate_state
    candidates.plan(lease)
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            "UPDATE runtime_code_candidates SET context_version=context_version+1 WHERE attempt_id=?",
            (lease.attempt_id,),
        )
    s.c.conn.rollback()


def test_normal_startup_installs_candidate_storage_and_unused_inverse_is_repeatable(
    coordination,
):
    """The packaged migration runs normally, and removing unused storage does not discard task rows."""
    from backend.db.development_migration import (
        restore_code_acceptances,
        restore_code_candidates,
        restore_code_checks,
        restore_code_reviews,
        restore_native_code_reviews,
    )
    from backend.tools.base.db import ensure_migrations

    c = coordination
    assert (
        c.conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 42
    )
    restore_code_acceptances(c.conn)
    restore_native_code_reviews(c.conn)
    restore_code_reviews(c.conn)
    restore_code_checks(c.conn)
    restore_code_candidates(c.conn)
    restore_code_candidates(c.conn)
    assert c.conn.execute("SELECT count(*) FROM tasks").fetchone()[0] == 3
    ensure_migrations(c.database)
    assert (
        c.conn.execute("SELECT count(*) FROM runtime_code_candidates").fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("proof", [{}, {"grant_id": "f" * 64, "operations": []}])
def test_sql_ready_row_requires_a_domain_and_nonempty_closure_proof(
    candidate_state, proof
):
    """Direct SQL cannot turn missing domain/operation evidence into a complete ready record."""
    s, lease, _binding, _copies, candidates = candidate_state
    planned, _ = candidates.plan(lease)
    result = captured_result(planned)
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            """UPDATE runtime_code_candidates SET state='ready',workspace=?,device=?,inode=?,head_sha=?,tree_sha=?,diff=?,diff_sha256=?,writer_proof_json=? WHERE attempt_id=?""",
            (
                result.workspace,
                result.device,
                result.inode,
                result.head_sha,
                result.tree_sha,
                result.diff,
                result.diff_sha256,
                json.dumps(proof),
                lease.attempt_id,
            ),
        )
    s.c.conn.rollback()


def test_candidate_inverse_refuses_retained_history(candidate_state):
    """A reserved or interrupted capture is execution evidence, even before a commit is available."""
    from backend.db.development_migration import (
        restore_code_candidates,
    )

    s, lease, _binding, _copies, candidates = candidate_state
    planned, _ = candidates.plan(lease)
    with pytest.raises(RuntimeError, match="rollback refused"):
        restore_code_candidates(s.c.conn)
    assert candidates.inspect(lease.project_id, lease.run_id) == planned


def test_owner_reads_of_preparing_code_return_explicit_unavailability(candidate_state):
    """A normal in-progress capture must not become an HTTP500 or a fabricated empty diff."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.contracts import RunConflict

    s, lease, _binding, _copies, candidates = candidate_state
    candidates.plan(lease)
    owner = CodeAcceptances(s.c.store)
    with pytest.raises(RunConflict):
        owner.state(lease.project_id, lease.run_id)
    with pytest.raises(RunConflict):
        owner.diff(lease.project_id, lease.run_id)
