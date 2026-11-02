"""Native review persistence and exact evidence; Git/native closure witnesses are explicitly synthetic in storage tests."""

from dataclasses import replace
from pathlib import Path

import pytest

from backend.tests.runtime.test_code_candidate_state import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- review_state dependency.
)
from backend.tests.runtime.test_code_candidate_state import closed_proof
from backend.tests.runtime.test_code_review_state import review_request
from backend.tests.runtime.test_code_review_state import review_state as review_state  # noqa: PLC0414 -- original author storage fixture.
from backend.tests.runtime.test_development_state import (
    development_state as development_state,  # noqa: PLC0414 -- candidate_state dependency.
)


@pytest.fixture
def review_records(review_state):
    """Admit an actual separate run over synthetic capture identity and original frozen input; no model generation is simulated here."""
    from backend.runtime.code_review_files import CodeReviewFiles
    from backend.runtime.code_review_git import ReviewGitWitness
    from backend.runtime.code_review_records import CodeReviewRecords

    s, _author, candidate, reviews = review_state
    (Path(candidate["workspace"]) / "sample.py").write_text("VALUE = 200\n")
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    lease = s.c.store.claim(101, run.run_id, "review-record-fixture")
    with s.c.store._transaction() as conn:
        view = reviews.execution_view(conn, s.c.store._row(conn, 101, run.run_id))
    observed = ReviewGitWitness(
        **{
            key: candidate[key]
            for key in ("base_sha", "head_sha", "tree_sha", "diff_sha256")
        }
    )
    return (
        s,
        lease,
        target,
        CodeReviewRecords(s.c.store),
        CodeReviewFiles(view),
        observed,
    )


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_native_review_reserves_once_and_cannot_validate_another_candidate(
    review_records,
):
    """Durable preparing state precedes effects, and mismatched Git never makes that scope ready."""
    from backend.runtime.contracts import RunConflict

    _s, lease, _target, records, _files, witness = review_records
    row, created = records.reserve(lease)
    assert created and row["state"] == "preparing"
    assert records.reserve(lease) == (row, False)
    with pytest.raises(RunConflict):
        records.preflight(lease, replace(witness, head_sha="e" * 40), closed_proof())
    assert records.get(101, lease.attempt_id)["state"] == "preparing"
    assert records.preflight(lease, witness, closed_proof())["state"] == "ready"


def test_native_review_refuses_unknown_original_input(review_records):
    """Storage-only provenance must not silently become enough context for native review generation."""
    from backend.runtime.contracts import RunConflict

    _s, lease, _target, records, _files, _witness = review_records
    with pytest.raises(RunConflict, match="exact saved input"):
        records.reserve(lease)


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_attributed_proposal_requires_independent_turn_and_actual_quoted_bytes(
    review_records,
):
    """Wrong citations never commit; repeated receipt cannot create another proposal or authority to accept a task."""
    from backend.research.models import InvalidEvidence, ReviewCheck
    from backend.runtime.code_review_models import (
        CodeReviewDecision,
        CodeReviewReference,
    )
    from backend.runtime.contracts import RunConflict

    s, lease, target, records, files, witness = review_records
    records.reserve(lease)
    records.preflight(lease, witness, closed_proof())
    source = files.read("sample.py")
    reference = CodeReviewReference(
        "file", "sample.py", source["sha256"], 1, "VALUE = 200"
    )
    decision = CodeReviewDecision(
        "supported",
        "Observed requested value.",
        (ReviewCheck("value", "supported", "Actual source contains200."),),
        (reference,),
        ("Source inspection; no test execution claimed.",),
    )
    with pytest.raises(RunConflict, match="independent native turn"):
        records.propose(lease, "decision", target.subject_sha256, decision)
    s.c.store.bind_native(
        lease, thread_id="record-review-thread", turn_id="record-review-turn"
    )
    with pytest.raises(InvalidEvidence):
        records.propose(
            lease,
            "decision",
            target.subject_sha256,
            replace(decision, references=(replace(reference, quote="VALUE = 137"),)),
        )
    result = records.propose(lease, "decision", target.subject_sha256, decision)
    assert result["state"] == "proposed"
    assert records.propose(lease, "decision", target.subject_sha256, decision) == result
    with pytest.raises(RunConflict):
        records.propose(lease, "another-key", target.subject_sha256, decision)
    assert s.c.store.context_snapshot(101, 1001)["task"]["status"] != "done"


def propose_fixture(records_fixture):
    """Create one attributed synthetic-host proposal with real quoted file bytes for terminal-state tests."""
    from backend.research.models import ReviewCheck
    from backend.runtime.code_review_models import (
        CodeReviewDecision,
        CodeReviewReference,
    )

    s, lease, target, records, files, witness = records_fixture
    records.reserve(lease)
    records.preflight(lease, witness, closed_proof())
    s.c.store.bind_native(
        lease, thread_id="record-review-thread", turn_id="record-review-turn"
    )
    source = files.read("sample.py")
    decision = CodeReviewDecision(
        "supported",
        "Observed actual value200.",
        (ReviewCheck("value", "supported", "Exact source contains200."),),
        (CodeReviewReference("file", "sample.py", source["sha256"], 1, "VALUE = 200"),),
        ("Synthetic storage witness; no model or actual Git closure claimed.",),
    )
    records.propose(lease, "decision", target.subject_sha256, decision)
    return s, lease, records, witness


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_confirmation_needs_same_owner_and_closed_native_then_is_immutable(
    review_records,
):
    """A proposal remains unconfirmed without closure; a confirmed historical record cannot become another decision."""
    import sqlite3

    from backend.runtime.contracts import RunConflict
    from backend.runtime.peer_registry import PeerRegistry

    s, lease, records, witness = propose_fixture(review_records)
    with pytest.raises(RunConflict, match="physical closure"):
        records.confirm(lease, witness, closed_proof())
    s.c.conn.execute(
        "INSERT INTO runtime_peer_scopes(attempt_id,protocol_version,created_at) VALUES(?,1,?)",
        (lease.attempt_id, s.c.now[0]),
    )
    s.c.conn.commit()
    registry = PeerRegistry(s.c.store)
    for kind in ("native", "business"):
        peer = registry.prepare(lease, kind)
        registry.close(peer)
        if kind == "native":
            s.c.conn.execute(
                "UPDATE runtime_peers SET bound_at=? WHERE id=?", (s.c.now[0], peer)
            )
            s.c.conn.commit()
    with pytest.raises(RunConflict, match="physical owner"):
        records.confirm(lease, witness, {**closed_proof(), "grant_id": "d" * 64})
    confirmed = records.confirm(lease, witness, closed_proof())
    assert confirmed["state"] == "confirmed" and confirmed["result_json"] is not None
    with pytest.raises(sqlite3.IntegrityError):
        s.c.conn.execute(
            "UPDATE runtime_code_review_records SET issue='retargeted' WHERE attempt_id=?",
            (lease.attempt_id,),
        )
    s.c.conn.rollback()
    assert records.get(101, lease.attempt_id) == confirmed
    assert s.c.store.context_snapshot(101, 1001)["task"]["status"] != "done"


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_byte_changed_quote_is_rejected_even_if_git_witness_names_still_match(
    review_records,
):
    """Equivalent line-ending conversions cannot silently relabel exact byte evidence quoted in the proposal."""
    from backend.research.models import InvalidEvidence

    _s, lease, records, witness = propose_fixture(review_records)
    candidate = records.candidate(lease)
    (Path(candidate.workspace) / "sample.py").write_bytes(b"VALUE = 200\r\n")
    with pytest.raises(InvalidEvidence):
        records.confirm(lease, witness, closed_proof())
    assert records.get(101, lease.attempt_id)["state"] == "proposed"


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_mutating_research_grant_cannot_attach_to_a_code_reviewer(review_records):
    """Host grant mistakes cannot let a reviewer acquire author write capabilities through the business API."""
    from backend.research.models import DEVELOPMENT_PERMISSIONS, ResearchForbidden

    s, lease, _target, _records, _files, _witness = review_records
    token = s.c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions=set(DEVELOPMENT_PERMISSIONS),
    )
    scope = s.c.research.authorize(token)
    s.c.store.bind_grant(lease, scope.grant_id)
    with pytest.raises(ResearchForbidden, match="mutation permissions"):
        s.c.research.authorize(token)


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
async def test_code_review_tools_only_expose_bounded_reads_and_proposal(review_records):
    """Undeclared capabilities, source traversal and extra arguments cannot mutate a reserved native review."""
    from backend.runtime.code_review_tools import CodeReviewTools
    from backend.runtime.owned_runtime import _settled

    _s, lease, _target, records, _files, witness = review_records
    records.reserve(lease)
    records.preflight(lease, witness, closed_proof())
    tools = CodeReviewTools(records, lease, active=lambda: True, settled=_settled)
    assert {row["name"] for row in tools.catalog} == {
        "researcher_code_review_subject",
        "researcher_code_review_file",
        "researcher_code_review_propose",
    }
    material = await tools.call(
        {
            "tool": "researcher_code_review_subject",
            "arguments": {"section": "author_input", "max_chars": 8},
        }
    )
    assert material["success"]
    for params in (
        {"tool": [], "arguments": {}},
        {"tool": "researcher_code_review_confirm", "arguments": {}},
        {"tool": "researcher_code_review_file", "arguments": {"path": "../outside"}},
        {"tool": "researcher_code_review_subject", "arguments": {"publish": True}},
    ):
        assert not (await tools.call(params))["success"]
    await tools.aclose()
    assert not (
        await tools.call({"tool": "researcher_code_review_subject", "arguments": {}})
    )["success"]
    assert records.get(101, lease.attempt_id)["state"] == "ready"


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
async def test_review_tool_scope_drains_original_host_work_before_closing(
    review_records, monkeypatch
):
    """Cancellation of an uncertain callback cannot release its SQL/filesystem lifetime while the underlying work remains alive."""
    import asyncio
    from threading import Event

    from backend.runtime.code_review_tools import CodeReviewTools
    from backend.runtime.owned_runtime import _settled

    _s, lease, _target, records, _files, witness = review_records
    records.reserve(lease)
    records.preflight(lease, witness, closed_proof())
    entered, released = Event(), Event()
    material = records.material

    def held(*args, **kwargs):
        """Hold actual original host work until its scope's draining behavior has been observed."""
        entered.set()
        assert released.wait(5)
        return material(*args, **kwargs)

    monkeypatch.setattr(records, "material", held)
    tools = CodeReviewTools(records, lease, active=lambda: True, settled=_settled)
    call = asyncio.create_task(
        tools.call({"tool": "researcher_code_review_subject", "arguments": {}})
    )
    assert await asyncio.to_thread(entered.wait, 2)
    call.cancel()
    closed = asyncio.create_task(tools.aclose())
    await asyncio.sleep(0)
    assert not closed.done()
    released.set()
    await asyncio.gather(call, return_exceptions=True)
    await asyncio.wait_for(closed, 2)


def test_unused_native_review_inverse_preserves_existing_packet(review_state):
    """Removing unused native-stage storage must retain an older completed review request and its frozen author context."""
    from backend.db.development_migration import (
        restore_code_acceptances,
        restore_native_code_reviews,
    )
    from backend.tools.base.db import ensure_migrations

    s, _author, _candidate, reviews = review_state
    spec, target = review_request(review_state)
    run, _ = reviews.admit_once(spec, target)
    lease = s.c.store.claim(101, run.run_id, "old-review-fixture")
    s.c.store.bind_native(
        lease, thread_id="old-review-thread", turn_id="old-review-turn"
    )
    s.c.store.finish(
        lease, native_status="completed", summary="Synthetic completed storage request"
    )
    before = reviews.request(101, run.run_id)
    restore_code_acceptances(s.c.conn)
    restore_native_code_reviews(s.c.conn)
    restore_code_acceptances(s.c.conn)
    restore_native_code_reviews(s.c.conn)
    assert reviews.request(101, run.run_id) == before
    ensure_migrations(s.c.database)
    assert (
        s.c.conn.execute("SELECT count(*) FROM runtime_code_review_records").fetchone()[
            0
        ]
        == 0
    )


@pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)
def test_retained_native_reservation_blocks_inverse_even_after_failure(review_records):
    """An attempt that failed before any model call still retains its non-replayable reservation and evidence."""
    from backend.db.development_migration import (
        restore_code_acceptances,
        restore_native_code_reviews,
    )

    s, lease, _target, records, _files, _witness = review_records
    row, _ = records.reserve(lease)
    s.c.store.finish(
        lease,
        native_status="failed",
        summary="Synthetic failure before native preparation",
    )
    with pytest.raises(RuntimeError, match="rollback refused"):
        restore_code_acceptances(s.c.conn)
        restore_native_code_reviews(s.c.conn)
    assert records.get(101, lease.attempt_id) == row
