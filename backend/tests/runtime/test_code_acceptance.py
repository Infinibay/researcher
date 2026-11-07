"""Explicit owner decisions over synthetic stored review witnesses; actual process closure has separate integration coverage."""

from dataclasses import replace

import pytest

from backend.tests.runtime.test_code_candidate_state import closed_proof
from backend.tests.runtime.test_code_review_records import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- register original storage fixture.
)
from backend.tests.runtime.test_code_review_records import (
    development_state as development_state,  # noqa: PLC0414 -- register original storage fixture.
)
from backend.tests.runtime.test_code_review_records import (
    review_records as review_records,  # noqa: PLC0414 -- register original storage fixture.
)
from backend.tests.runtime.test_code_review_records import (
    review_state as review_state,  # noqa: PLC0414 -- register original storage fixture.
)

pytestmark = pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)


@pytest.fixture
def code_result(review_records, request):
    """Close an attributed reviewer over synthetic Git/owner witnesses, with verdict selected before immutable persistence."""
    result = finish_owner_review(review_records, getattr(request, "param", "supported"))
    choose_fixture_check_policy(result[0].c.store)
    return result


def choose_fixture_check_policy(store):
    """Explicitly authorize missing tests in acceptance fixtures; production migrations make no such choice."""
    from backend.runtime.project_check_policy import ProjectCheckPolicies

    policies = ProjectCheckPolicies(store)
    if policies.state(101)['revision'] == 0:
        policies.update(101, operation_key='fixture-check-policy', expected_revision=0, mode='allow_missing')


def finish_owner_review(review_records, verdict="supported"):
    """Complete one distinct storage-only review using original state transitions and explicitly synthetic physical witnesses."""
    from backend.research.models import ReviewCheck
    from backend.runtime.code_review_models import (
        CodeReviewDecision,
        CodeReviewReference,
    )
    from backend.runtime.peer_registry import PeerRegistry

    s, lease, target, records, files, witness = review_records
    records.reserve(lease)
    records.preflight(lease, witness, closed_proof())
    s.c.store.bind_native(
        lease,
        thread_id="owner-review-" + lease.attempt_id,
        turn_id="owner-turn-" + lease.attempt_id,
    )
    source = files.read("sample.py")
    records.propose(
        lease,
        "owner-review-proposal-" + lease.run_id,
        target.subject_sha256,
        CodeReviewDecision(
            "supported" if verdict == "unconfirmed" else verdict,
            "Observed value in source; storage-only fixture.",
            (ReviewCheck("value", "supported", "Source quotes actual200."),),
            (
                CodeReviewReference(
                    "file", "sample.py", source["sha256"], 1, "VALUE = 200"
                ),
            ),
            (
                "Synthetic closure/Git witnesses; no test suite or model inference claimed.",
            ),
        ),
    )
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
    if verdict != "unconfirmed":
        records.confirm(lease, witness, closed_proof())
    s.c.store.finish(
        lease,
        native_status="completed",
        summary="Stored independent review; owner has not accepted.",
    )
    candidate = s.c.conn.execute(
        "SELECT * FROM runtime_code_candidates WHERE attempt_id=?", (target.attempt_id,)
    ).fetchone()
    return s, lease, dict(candidate)


def owner_intent(state, **changes):
    """Prepare one exact neutral owner observation; retries preserve every field."""
    from backend.runtime.code_acceptance_policy import CodeAcceptanceIntent

    return CodeAcceptanceIntent(
        **{
            "operation_key": "owner-accept-code",
            "attempt_id": state["candidate"]["attempt_id"],
            "context_version": state["candidate"]["context_version"],
            "subject_sha256": state["subject_sha256"],
            "review_sha256": state["review_sha256"],
            "acknowledge_limits": True,
            "note": "Accept this exact fixture with displayed limits.",
            "check_policy_revision": state["project_check_policy"]["revision"],
            **changes,
        }
    )


def test_owner_acceptance_is_version_bound_atomic_idempotent_and_separate_from_publication(
    code_result,
):
    """Finishing author/reviewer leaves task incomplete; only observed explicit owner acceptance closes it and records one durable event."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.contracts import RunConflict

    s, reviewer, candidate = code_result
    store = CodeAcceptances(s.c.store)
    state = store.state(101, candidate["run_id"])
    assert state["eligible"] and state["requires_acknowledgement"]
    assert state["checks"]["limitations"][0]["code"] == "checks_absent"
    with pytest.raises(RunConflict):
        store.accept(
            101, candidate["run_id"], owner_intent(state, acknowledge_limits=False)
        )
    intent = owner_intent(state)
    receipt = store.accept(101, candidate["run_id"], intent)
    assert (
        receipt["publication_performed"] is False and receipt["task_accepted"] is True
    )
    assert store.accept(101, candidate["run_id"], intent) == receipt
    assert store.state(101, candidate["run_id"])["acceptance_current"] is True
    assert s.c.store.get(101, reviewer.run_id).status == "accepted"
    assert (
        s.c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "done"
    )
    assert (
        s.c.conn.execute("SELECT count(*) FROM runtime_code_acceptances").fetchone()[0]
        == 1
    )
    with pytest.raises(RunConflict):
        store.accept(101, candidate["run_id"], replace(intent, note="Changed intent"))


@pytest.mark.parametrize(
    "code_result", ["needs_revision", "inconclusive", "unconfirmed"], indirect=True
)
def test_owner_acknowledgement_cannot_override_rejected_or_unconfirmed_review(
    code_result,
):
    """A fluent native completion and a checkbox cannot turn concerns or missing confirmation into approval."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.contracts import RunConflict

    s, _reviewer, candidate = code_result
    store = CodeAcceptances(s.c.store)
    state = store.state(101, candidate["run_id"])
    assert not state["eligible"]
    with pytest.raises(RunConflict):
        store.accept(101, candidate["run_id"], owner_intent(state))


def test_correction_reopens_accepted_code_without_rewriting_its_original_receipt(
    code_result,
):
    """An old retry returns history, while changed owner requirements lose present-day acceptance."""
    from backend.runtime.code_acceptances import CodeAcceptances

    s, _reviewer, candidate = code_result
    store = CodeAcceptances(s.c.store)
    state = store.state(101, candidate["run_id"])
    intent = owner_intent(state)
    receipt = store.accept(101, candidate["run_id"], intent)
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=candidate["context_version"],
        operation_key="owner-new-requirement",
        statement="Use201instead.",
        source_kind="user_example",
        source_reference="owner-message",
    )
    assert store.accept(101, candidate["run_id"], intent) == receipt
    current = store.state(101, candidate["run_id"])
    assert current["acceptance"] == receipt and current["acceptance_current"] is False
    assert current["checks"]["limitations"] == []
    assert any(item["code"] == "checks_unverifiable" for item in current["blockers"])
    assert (
        s.c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "pending"
    )


def test_code_acceptance_never_leaks_or_mutates_a_different_project(code_result):
    """Receipt keys and internal candidate IDs cannot select another project's result."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.contracts import RunNotFound

    s, _reviewer, candidate = code_result
    store = CodeAcceptances(s.c.store)
    state = store.state(101, candidate["run_id"])
    with pytest.raises(RunNotFound):
        store.state(202, candidate["run_id"])
    with pytest.raises(RunNotFound):
        store.accept(202, candidate["run_id"], owner_intent(state))


async def test_owner_http_code_acceptance_requires_pairing_csrf_and_exact_observation(
    code_result,
):
    """Actual owner HTTP preserves authorization, bounded historical diff and one idempotent explicit acceptance."""
    from dataclasses import asdict

    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.runtime.code_acceptances import CodeAcceptances

    s, _reviewer, candidate = code_result
    state = CodeAcceptances(s.c.store).state(101, candidate["run_id"])
    app = create_app(
        access=LocalAccess(pairing_key="code-owner-fixture-long-enough-code")
    )
    root = f"/api/projects/101/runs/{candidate['run_id']}/code-result"
    body = asdict(owner_intent(state))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        assert (await client.get(root)).status_code == 401
        assert (
            await client.post(
                root + "/accept",
                json=body,
                headers={"Authorization": "Bearer tool-token"},
            )
        ).status_code == 401
        paired = await client.post(
            "/api/session",
            json={"code": "code-owner-fixture-long-enough-code"},
            headers={"X-Researcher-Client": "web"},
        )
        assert paired.status_code == 200
        assert (await client.post(root + "/accept", json=body)).status_code == 403
        observed = await client.get(root)
        assert (
            observed.status_code == 200
            and observed.headers["cache-control"] == "no-store"
        )
        assert (await client.get(root.replace("/101/", "/202/"))).status_code == 404
        diff = await client.get(root + "/diff", params={"max_chars": 2})
        assert (
            diff.status_code == 200
            and len(diff.json()["content"]) == 2
            and not diff.json()["complete_file"]
        )
        headers = {"X-Researcher-CSRF": paired.json()["csrf_token"]}
        assert (
            await client.post(
                root + "/accept",
                json={**body, "actor_source": "agent"},
                headers=headers,
            )
        ).status_code == 422
        assert (
            await client.post(
                root + "/accept",
                json={**body, "subject_sha256": "e" * 64},
                headers=headers,
            )
        ).status_code == 409
        accepted = await client.post(root + "/accept", json=body, headers=headers)
        assert accepted.status_code == 200, accepted.text
        assert (
            await client.post(root + "/accept", json=body, headers=headers)
        ).json() == accepted.json()
        assert (await client.get(root)).json()["acceptance_current"] is True


def test_metadata_change_reopens_code_and_direct_sql_cannot_invent_acceptance(
    code_result,
):
    """The SQL boundary rejects old completion helpers and reopens accepted code when task inputs change."""
    import sqlite3

    from backend.runtime.code_acceptances import CodeAcceptances

    s, _reviewer, candidate = code_result
    with pytest.raises(sqlite3.IntegrityError, match="explicit owner acceptance"):
        s.c.conn.execute("UPDATE tasks SET status='done' WHERE id=1001")
    s.c.conn.rollback()
    store = CodeAcceptances(s.c.store)
    state = store.state(101, candidate["run_id"])
    receipt = store.accept(101, candidate["run_id"], owner_intent(state))
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        s.c.conn.execute("UPDATE runtime_code_acceptances SET receipt_json='{}'")
    s.c.conn.rollback()
    s.c.conn.execute(
        "UPDATE tasks SET description='An additional owner requirement' WHERE id=1001"
    )
    s.c.conn.commit()
    assert (
        s.c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "pending"
    )
    current = store.state(101, candidate["run_id"])
    assert current["acceptance"] == receipt and not current["acceptance_current"]


def test_code_acceptance_rolls_back_all_changes_when_its_event_cannot_commit(
    code_result, monkeypatch
):
    """A lost event write must not leave task completion, reviewer retirement or an apparent receipt."""
    from backend.runtime.code_acceptances import CodeAcceptances

    s, reviewer, candidate = code_result
    store = CodeAcceptances(s.c.store)
    state = store.state(101, candidate["run_id"])

    def fail_event(*args, **kwargs):
        """Reproduce a durable event failure inside the same transaction after state writes."""
        raise RuntimeError("Fixture event write failed")

    monkeypatch.setattr(s.c.store, "_event", fail_event)
    with pytest.raises(RuntimeError, match="event write"):
        store.accept(101, candidate["run_id"], owner_intent(state))
    assert (
        s.c.conn.execute("SELECT count(*) FROM runtime_code_acceptances").fetchone()[0]
        == 0
    )
    assert s.c.store.get(101, reviewer.run_id).status == "needs_review"
    assert (
        s.c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        != "done"
    )


def test_owner_read_of_accepted_code_never_reopens_native_review_admission(code_result):
    """Readonly accepted-author reconstruction is explicit and cannot weaken the default native review precondition."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.contracts import RunConflict

    s, _reviewer, candidate = code_result
    store = CodeAcceptances(s.c.store)
    state = store.state(101, candidate["run_id"])
    store.accept(101, candidate["run_id"], owner_intent(state))
    assert store.state(101, candidate["run_id"])["acceptance_current"]
    with pytest.raises(RunConflict, match="closed original author"):
        store.reviews.subject(101, candidate["attempt_id"])


def followup_owner_review(s, older, candidate, operation_key="another-review"):
    """Close the previous storage-only review request and produce another independent attributed judgment of the same subject."""
    from backend.runtime.code_review_files import CodeReviewFiles
    from backend.runtime.code_review_git import ReviewGitWitness
    from backend.runtime.code_review_records import CodeReviewRecords
    from backend.runtime.code_reviews import CodeReviews, CodeReviewTarget

    s.c.store.cancel(101, older.run_id)
    reviews = CodeReviews(s.c.store)
    packet = reviews.subject(101, candidate["attempt_id"])
    target = CodeReviewTarget(candidate["attempt_id"], packet["subject_sha256"])
    run, _ = reviews.admit_once(
        replace(
            s.c.spec,
            actor_id="another-code-reviewer",
            operation_key=operation_key,
            context_version=candidate["context_version"],
        ),
        target,
    )
    lease = s.c.store.claim(101, run.run_id, "another-review-owner")
    with s.c.store._transaction() as conn:
        view = reviews.execution_view(conn, s.c.store._row(conn, 101, run.run_id))
    witness = ReviewGitWitness(
        **{
            key: candidate[key]
            for key in ("base_sha", "head_sha", "tree_sha", "diff_sha256")
        }
    )
    finish_owner_review(
        (s, lease, target, CodeReviewRecords(s.c.store), CodeReviewFiles(view), witness)
    )
    return lease


@pytest.mark.parametrize("code_result", ["needs_revision"], indirect=True)
def test_later_supported_review_cannot_hide_an_earlier_current_rejection(code_result):
    """Cancelling an old review run and asking another reviewer must not erase an unresolved objection about the exact same code."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.contracts import RunConflict

    s, older, candidate = code_result
    followup_owner_review(s, older, candidate)
    owner = CodeAcceptances(s.c.store)
    state = owner.state(101, candidate["run_id"])
    assert not state["eligible"]
    assert any(
        item["run_id"] == older.run_id and item["verdict"] == "needs_revision"
        for item in state["review_issues"]
    )
    with pytest.raises(RunConflict):
        owner.accept(101, candidate["run_id"], owner_intent(state))


@pytest.mark.parametrize("code_result", ["inconclusive"], indirect=True)
def test_prior_inconclusive_review_remains_visible_without_becoming_a_rejection(
    code_result,
):
    """New supported evidence may resolve missing inspection, but the owner still sees and acknowledges earlier limits."""
    from backend.runtime.code_acceptances import CodeAcceptances

    s, older, candidate = code_result
    followup_owner_review(s, older, candidate)
    owner = CodeAcceptances(s.c.store)
    state = owner.state(101, candidate["run_id"])
    assert state["eligible"] and state["requires_acknowledgement"]
    assert state["review_issues"][0]["verdict"] == "inconclusive"
    assert state["review_issues"][0]["blocking"] is False
    receipt = owner.accept(101, candidate["run_id"], owner_intent(state))
    assert receipt["review_issues"] == state["review_issues"]
    assert owner.state(101, candidate["run_id"])["acceptance_current"]


def test_review_history_overflow_is_explicit_and_cannot_silently_authorize_acceptance(
    code_result,
):
    """The complete bounded history gate permits64 prior reviews and rejects65 without hiding a tail."""
    from backend.runtime.code_acceptances import CodeAcceptances

    s, latest, candidate = code_result
    owner = CodeAcceptances(s.c.store)
    for index in range(65):
        latest = followup_owner_review(
            s, latest, candidate, "history-review-" + str(index)
        )
        if index == 63:
            assert owner.state(101, candidate["run_id"])["eligible"]
    state = owner.state(101, candidate["run_id"])
    assert not state["eligible"]
    assert any(
        item["code"] == "review_history_over_limit" for item in state["blockers"]
    )
