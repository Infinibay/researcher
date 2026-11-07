"""Frozen code-review admission and thread provenance; storage fixtures do not simulate native model execution."""

import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_code_candidate_state import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- register the shared storage fixture.
)
from backend.tests.runtime.test_code_candidate_state import (
    captured_result,
    closed_proof,
)
from backend.tests.runtime.test_development_state import (
    development_state as development_state,  # noqa: PLC0414 -- candidate_state dependency.
)


@pytest.fixture
def review_state(candidate_state, request):
    """Create synthetic durable author provenance; real native/namespace evidence has separate integration coverage."""
    from backend.runtime.code_reviews import CodeReviews
    from backend.runtime.peer_registry import PeerRegistry

    s, author, _binding, _copies, candidates = candidate_state
    planned, _ = candidates.plan(author)
    candidate = candidates.complete(author, captured_result(planned), closed_proof())
    if getattr(request, "param", None) == "frozen_author":
        import hashlib

        from backend.runtime.codex_session import ExecutionLimits

        s.c.store.bind_thread(author, thread_id="author-thread")
        s.c.store.reserve_input(
            author,
            workspace=json.loads(candidate["prepared_json"])["workspace"],
            catalog_hash=hashlib.sha256(b"[]").hexdigest(),
            catalog=[],
            developer_instructions="Fixture original author input.",
            model="fixture-model",
            limits=ExecutionLimits(60, 30, 1, 10, 100),
        )
    s.c.store.bind_native(author, thread_id="author-thread", turn_id="author-turn")
    s.c.conn.execute(
        "INSERT INTO runtime_peer_scopes(attempt_id,protocol_version,created_at) VALUES(?,1,?)",
        (author.attempt_id, s.c.now[0]),
    )
    s.c.conn.commit()
    registry = PeerRegistry(s.c.store)
    for kind in ("native", "business"):
        peer = registry.prepare(author, kind)
        registry.close(peer)
        if kind == "native":
            # A storage-only witnessed-bound fixture, not an actual released process.
            s.c.conn.execute(
                "UPDATE runtime_peers SET bound_at=? WHERE id=?", (s.c.now[0], peer)
            )
            s.c.conn.commit()
    if getattr(request, "param", None) in ("pending_check", "many_checks"):
        from backend.runtime.check_contracts import CheckSpec
        from backend.runtime.check_state import CodeChecks

        count = 65 if request.param == "many_checks" else 1
        for index in range(count):
            CodeChecks(s.c.store).plan(
                author, f"ci-{index}", CheckSpec(("/usr/bin/true",), "command")
            )
    s.c.store.finish(author, native_status="completed", summary="Candidate for review")
    return s, author, candidate, CodeReviews(s.c.store)


def review_request(state):
    """Select the actual complete observed subject and a distinct actor without interpreting a role name."""
    from backend.runtime.code_reviews import CodeReviewTarget

    s, author, _candidate, reviews = state
    subject = reviews.subject(101, author.attempt_id)
    return (
        replace(
            s.c.spec,
            actor_id="independent-reviewer",
            operation_key="code-review",
            context_version=author.context_version,
        ),
        CodeReviewTarget(author.attempt_id, subject["subject_sha256"]),
    )


def test_review_subject_retains_complete_original_candidate_and_closed_author(
    review_state,
):
    """The subject identifies original author/native scope, exact Git version, task requirements and check evidence."""
    _s, author, candidate, reviews = review_state
    subject = reviews.subject(101, author.attempt_id)
    assert subject["snapshot"]["candidate"]["head_sha"] == candidate["head_sha"]
    assert subject["snapshot"]["author"]["attempt_id"] == author.attempt_id
    assert subject["snapshot"]["author"]["thread_id"] == "author-thread"
    assert subject["snapshot"]["requirements"]["task"]["type"] == "code"
    assert (
        subject["snapshot"]["author_request"]["text"]
        == _s.c.store.get(101, author.run_id).prompt
    )
    assert subject["snapshot"]["author_request"]["source_kind"] == "owner_admission"
    assert subject["snapshot"]["checks"] == []
    assert (
        subject["subject_sha256"]
        == reviews.subject(101, author.attempt_id)["subject_sha256"]
    )


def test_admission_reuses_its_receipt_and_keeps_source_separate_from_review_view(
    review_state,
):
    """A review is a separate durable run and readonly candidate view, never a reset of the author's workspace."""
    s, author, candidate, reviews = review_state
    spec, target = review_request(review_state)
    run, created = reviews.admit_once(spec, target)
    assert created and run.execution_kind == "code_review"
    assert run.run_id != author.run_id
    assert reviews.admit_once(spec, target) == (run, False)
    request = reviews.request(101, run.run_id, require_current=True)
    assert request["subject_sha256"] == target.subject_sha256
    assert request["author_actor_id"] == author.actor_id
    lease = s.c.store.claim(101, run.run_id, "review-host")
    with s.c.store._transaction() as conn:
        row = s.c.store._row(conn, 101, run.run_id)
        view = reviews.execution_view(conn, row)
    assert view.workspace == candidate["workspace"]
    assert (
        view.source.workspace
        == s.c.store.workspace_binding(101, author.run_id).workspace
    )
    assert view.workspace != view.source.workspace
    assert view.subject_sha256 == target.subject_sha256
    assert lease.attempt_id != author.attempt_id


@pytest.mark.parametrize(
    "fault", ["same_actor", "wrong_subject", "other_project", "other_task"]
)
def test_review_admission_rejects_unobserved_or_related_authority(review_state, fault):
    """An actor label, foreign scope or changed hash cannot authorize an independent review."""
    from backend.runtime.contracts import RunConflict, RunNotFound

    _s, author, _candidate, reviews = review_state
    spec, target = review_request(review_state)
    if fault == "same_actor":
        spec = replace(spec, actor_id=author.actor_id)
    elif fault == "wrong_subject":
        target = replace(target, subject_sha256="e" * 64)
    elif fault == "other_project":
        spec = replace(spec, project_id=202)
    else:
        spec = replace(spec, task_id=1002)
    with pytest.raises((RunConflict, RunNotFound)):
        reviews.admit_once(spec, target)


def test_review_thread_must_differ_from_the_actual_author_thread(review_state):
    """A new run and actor do not make the author's resumed context independent."""
    from backend.runtime.contracts import RunConflict

    s, _author, _candidate, reviews = review_state
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    lease = s.c.store.claim(101, run.run_id, "review-host")
    with pytest.raises(RunConflict, match="independent"):
        s.c.store.bind_thread(lease, thread_id="author-thread")
    with pytest.raises(RunConflict, match="independent"):
        s.c.store.bind_native(lease, thread_id="author-thread", turn_id="new-turn")
    s.c.store.bind_native(lease, thread_id="review-thread", turn_id="review-turn")


def test_context_correction_invalidates_admitted_review_without_erasing_history(
    review_state,
):
    """The saved packet remains inspectable while new requirements withdraw its execution authority."""
    from backend.runtime.contracts import RunConflict

    s, author, _candidate, reviews = review_state
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    before = reviews.request(101, run.run_id)
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=author.context_version,
        operation_key="review-correction",
        statement="Preserve the old behavior.",
        source_kind="user_message",
        source_reference="owner:review",
    )
    with pytest.raises(RunConflict):
        reviews.request(101, run.run_id, require_current=True)
    assert reviews.request(101, run.run_id) == before
    assert Path(before["candidate_workspace"]).exists()


def test_subject_and_source_admission_are_immutable_in_storage(review_state):
    """A direct SQL update cannot retarget the reviewer to another version while retaining the original receipt."""
    s, _author, _candidate, reviews = review_state
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            "UPDATE runtime_code_review_requests SET subject_sha256=? WHERE run_id=?",
            ("f" * 64, run.run_id),
        )
    s.c.conn.rollback()
    assert (
        json.loads(reviews.request(101, run.run_id)["snapshot_json"])["candidate"][
            "attempt_id"
        ]
        == target.attempt_id
    )


@pytest.mark.parametrize(
    "fault",
    ["missing_thread", "native_not_bound", "unclosed_peer", "unfinished_author"],
)
def test_role_names_and_unclosed_or_unknown_origin_do_not_make_a_subject_reviewable(
    review_state, fault
):
    """Reject missing or contradictory original evidence before admitting a reviewer."""
    from backend.runtime.contracts import RunConflict

    s, author, _candidate, reviews = review_state
    if fault == "missing_thread":
        s.c.conn.execute(
            "UPDATE runtime_attempts SET thread_id=NULL WHERE id=?",
            (author.attempt_id,),
        )
    elif fault == "native_not_bound":
        s.c.conn.execute(
            "UPDATE runtime_peers SET bound_at=NULL WHERE attempt_id=? AND kind='native'",
            (author.attempt_id,),
        )
    elif fault == "unclosed_peer":
        s.c.conn.execute(
            "UPDATE runtime_peers SET state='prepared' WHERE attempt_id=? AND kind='business'",
            (author.attempt_id,),
        )
    else:
        s.c.conn.execute(
            "UPDATE runtime_runs SET status='running' WHERE id=?", (author.run_id,)
        )
    s.c.conn.commit()
    with pytest.raises(RunConflict):
        reviews.subject(101, author.attempt_id)


@pytest.fixture
def readonly_review_broker(review_state, tmp_path):
    """Give a new admitted review its own real broker/domain; author metadata remains explicitly synthetic storage data."""
    import os
    from uuid import uuid4

    from backend.runtime.execution_domain import ExecutionDomain
    from backend.runtime.peer_broker import PeerBroker
    from backend.runtime.peer_registry import AttemptPeers
    from backend.tests.runtime.authority_fixture import journal, provisioned

    s, _author, candidate, reviews = review_state
    (Path(candidate["workspace"]) / "fact.txt").write_text("candidate-200")
    (s.workspace / "fact.txt").write_text("source-137")
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    lease, peers = AttemptPeers.claim(s.c.store, 101, run.run_id, "review-host")
    relative = Path("/proc/self/cgroup").read_text().strip().split(":", 2)[2]
    parent = (Path("/sys/fs/cgroup") / relative.lstrip("/")).parent
    if not os.access(parent, os.W_OK) or not {"memory", "pids"} <= set(
        (parent / "cgroup.subtree_control").read_text().split()
    ):
        pytest.skip("Requires delegated cgroup memory/pids controllers")
    path = parent / ("researcher-review-test-" + uuid4().hex)
    path.mkdir(mode=0o700)
    root = tmp_path / "review-authority"
    root.mkdir(mode=0o700)
    authority = provisioned(root)
    try:
        with ExecutionDomain.open(path) as domain, journal(authority) as storage:
            broker = PeerBroker(storage, domain)
            try:
                yield review_state, lease, peers.registry, broker, storage
            finally:
                broker.revoke()
                for peer in peers.ids.values():
                    peers.registry.close(peer)
    finally:
        if path.exists():
            path.rmdir()


def test_admitted_review_peer_mounts_only_the_candidate_readonly(
    readonly_review_broker,
):
    """A real gated child reads candidate bytes and cannot edit them or access the original repository's host path."""
    state, lease, registry, broker, _storage = readonly_review_broker
    s, _author, candidate, _reviews = state
    peer = registry.prepare(lease, "command")
    code = (
        """from pathlib import Path
assert Path('/run/researcher-source/fact.txt').read_text()=='candidate-200'
try:Path('/run/researcher-source/fact.txt').write_text('unsafe')
except OSError:pass
else:raise AssertionError('Review source writable')
"""
        + f"assert not Path({str(s.workspace)!r}).exists()\nprint('readonly-candidate')\n"
    )
    started = broker.run_peer(registry, peer, operation_key="review-read", code=code)
    try:
        assert started.child.wait(timeout=3) == 0
        assert started.child.stdout.read() == b"readonly-candidate\n"
    finally:
        broker.revoke()
        registry.close(peer)
        started.child.close_handles()
    assert (Path(candidate["workspace"]) / "fact.txt").read_text() == "candidate-200"
    assert (s.workspace / "fact.txt").read_text() == "source-137"


def test_context_correction_between_publication_and_gate_prevents_review_payload(
    readonly_review_broker, monkeypatch
):
    """Actual pre-G binding revalidates the frozen packet instead of relying on its earlier admission."""
    from backend.runtime.contracts import RunConflict

    state, lease, registry, broker, storage = readonly_review_broker
    s, author, _candidate, _reviews = state
    bind = registry.bind

    def corrected(peer_id, identity):
        """Correct the real task after global publication while the original kernel gate is still closed."""
        s.c.store.correct_context(
            project_id=101,
            task_id=1001,
            expected_version=author.context_version,
            operation_key="review-before-g",
            statement="Preserve previous behavior.",
            source_kind="user_message",
            source_reference="owner:review-before-g",
        )
        return bind(peer_id, identity)

    monkeypatch.setattr(registry, "bind", corrected)
    peer = registry.prepare(lease, "command")
    with pytest.raises(RunConflict):
        broker.run_peer(
            registry,
            peer,
            operation_key="review-corrected",
            code="print('UNAUTHORIZED')",
        )
    broker.revoke()
    registry.close(peer)
    operations = [
        value
        for key, value in storage.load().records.items()
        if key.startswith("broker:op:")
    ]
    assert operations and all(
        value.get("gate_sent") is not True and value.get("execution_closed") is True
        for value in operations
    )


@pytest.mark.parametrize("schema_target", [40])
def test_unused_review_inverse_preserves_closed_author_and_candidate(service_setup):
    """Removing unused version40 preserves older author/candidate records without invoking current review APIs."""
    from backend.db.development_migration import restore_code_reviews
    from backend.tests.runtime.migration_fixtures import historical_candidate,historical_rows
    from backend.tools.base.db import ensure_migrations

    c=service_setup.c
    historical_candidate(c.conn)
    before=historical_rows(c.conn,'runtime_code_candidates','runtime_development_workspaces','runtime_runs','runtime_attempts')
    restore_code_reviews(c.conn)
    restore_code_reviews(c.conn)
    assert historical_rows(c.conn,*before)==before
    assert c.conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==39
    ensure_migrations(c.database,target_version=40)
    assert historical_rows(c.conn,*before)==before
    assert c.conn.execute('PRAGMA foreign_key_check').fetchall()==[]



@pytest.mark.parametrize("schema_target", [40])
def test_review_history_prevents_inverse_even_after_the_reviewer_finishes(service_setup):
    """A retained version40 request blocks removal even when its historical runs are terminal."""
    from backend.db.development_migration import restore_code_reviews
    from backend.tests.runtime.migration_fixtures import historical_review_request,historical_rows

    c=service_setup.c
    historical_review_request(c.conn)
    before=historical_rows(c.conn,'runtime_code_review_requests','runtime_code_candidates','runtime_runs','runtime_attempts')
    with pytest.raises(RuntimeError,match='rollback refused'):restore_code_reviews(c.conn)
    assert historical_rows(c.conn,*before)==before
    assert c.conn.execute('PRAGMA foreign_key_check').fetchall()==[]



@pytest.mark.parametrize("review_state", ["pending_check"], indirect=True)
def test_pending_check_remains_unknown_and_changed_evidence_invalidates_review(
    review_state,
):
    """The packet never invents success and cannot retain currentness when a late original observation changes it."""
    from backend.runtime.check_state import CodeChecks
    from backend.runtime.contracts import RunConflict

    _s, author, _candidate, reviews = review_state
    subject = reviews.subject(101, author.attempt_id)
    check = subject["snapshot"]["checks"][0]
    assert check["state"] == "preparing" and check["result"] is None
    assert all(value is None for value in check["output"].values())
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    before = reviews.request(101, run.run_id)
    CodeChecks(reviews.runs).observe_failure(
        author, check["id"], "Original work interrupted"
    )
    with pytest.raises(RunConflict, match="subject changed"):
        reviews.request(101, run.run_id, require_current=True)
    assert reviews.request(101, run.run_id) == before


@pytest.mark.parametrize("review_state", ["many_checks"], indirect=True)
def test_subject_refuses_overflow_instead_of_silently_dropping_checks(review_state):
    """All retained check records must fit the explicit subject budget; selecting a convenient subset is not allowed."""
    from backend.runtime.contracts import RunConflict

    _s, author, _candidate, reviews = review_state
    with pytest.raises(RunConflict, match="check limit"):
        reviews.subject(101, author.attempt_id)


def test_unvalidated_native_review_cannot_freeze_input_or_spend_a_dispatch_budget(
    review_state,
):
    """Readonly inspection cannot replace native Git validation; no input or dispatch budget is spent before that witness exists."""
    import hashlib

    from backend.runtime.codex_session import ExecutionLimits
    from backend.runtime.contracts import RunConflict

    s, _author, candidate, reviews = review_state
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    lease = s.c.store.claim(101, run.run_id, "review-host")
    s.c.store.bind_thread(lease, thread_id="independent-review-thread")
    before = s.c.conn.execute("SELECT * FROM runtime_project_budgets").fetchall()
    with pytest.raises(RunConflict, match="validated original candidate"):
        s.c.store.reserve_input(
            lease,
            workspace=candidate["workspace"],
            catalog_hash=hashlib.sha256(b"[]").hexdigest(),
            model="fixture-model",
            catalog=[],
            developer_instructions="Inspect the observed candidate.",
            limits=ExecutionLimits(60, 30, 1, 10, 100),
        )
    for table in ("runtime_input_snapshots", "runtime_inference_dispatches"):
        assert (
            s.c.conn.execute(
                f"SELECT count(*) FROM {table} WHERE attempt_id=?", (lease.attempt_id,)
            ).fetchone()[0]
            == 0
        )
    assert (
        s.c.conn.execute("SELECT * FROM runtime_project_budgets").fetchall() == before
    )
