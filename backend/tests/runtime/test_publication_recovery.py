"""Host publication recovery uses fresh readonly authority over closed original effects, with storage provenance explicitly synthetic here."""

import pytest

from backend.tests.runtime.test_code_publications import (
    candidate_state as candidate_state,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_code_publications import code_result as code_result  # noqa: PLC0414 -- register original fixture dependency.
from backend.tests.runtime.test_code_publications import (
    development_state as development_state,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_code_publications import (
    publication_request as publication_request,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_code_publications import (
    review_records as review_records,  # noqa: PLC0414 -- register original fixture dependency.
)
from backend.tests.runtime.test_code_publications import review_state as review_state  # noqa: PLC0414 -- register original fixture dependency.

pytestmark = pytest.mark.parametrize("review_state", ["frozen_author"], indirect=True)


def original_closed(publication_request):
    """Create storage-only command closure and an explicitly synthetic host proof; actual journal checks have separate integration coverage."""
    from backend.runtime.peer_registry import AttemptPeers

    s, candidate, publications, intent = publication_request
    run, _ = publications.admit_once(101, candidate["run_id"], intent)
    lease, peers = AttemptPeers.claim(s.c.store, 101, run.run_id, "original-host")
    peer = peers.registry.prepare(lease, "command")
    peers.registry.close(peer)
    publications.interrupted(lease, physically_closed=True, reason="LostResponse")
    return (
        s,
        candidate,
        publications,
        lease,
        {
            "attempt_id": lease.attempt_id,
            "fence": lease.fence,
            "database_identity": peers.registry._database_identity(),
            "execution_closed": True,
            "grant_ids": ["synthetic-original-grant"],
        },
    )


def test_recovery_has_new_readonly_attempt_after_context_change_and_same_receipt(
    publication_request,
):
    """A historical effect can be observed after correction without inference, candidate access or reuse of the original writer lease."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        PublicationRefObservation,
    )
    from backend.runtime.publication_recovery import PublicationRecovery

    s, _candidate, publications, original, proof = original_closed(publication_request)
    s.c.store.correct_context(
        project_id=101,
        task_id=1001,
        expected_version=original.context_version,
        operation_key="correct-before-observation",
        statement="Different requirement",
        source_kind="user_message",
        source_reference="owner",
    )
    recovery = PublicationRecovery(s.c.store)
    command = {
        "project_id": 101,
        "run_id": original.run_id,
        "attempt_id": original.attempt_id,
        "expected_fence": s.c.store.get(101, original.run_id).fence,
        "operation_key": "observe-original",
    }
    lease, peers = recovery.begin(**command, proof=proof, owner_id="readonly-host")
    assert lease.attempt_id != original.attempt_id and lease.fence > original.fence
    assert s.c.store.heartbeat(lease).attempt_id == lease.attempt_id
    peer = peers.registry.prepare(lease, "command")
    admission = peers.registry.admission(peer)
    assert admission["publication_observation"] is True
    with pytest.raises(RunConflict):
        peers.registry.prepare(lease, "native")
    peers.registry.close(peer)
    ref = PublicationRefIntent(original.run_id, "refs/heads/reviewed-change", None)
    view = publications.request(101, original.run_id)["view"]
    observed = PublicationRefObservation(
        "published",
        False,
        "d" * 40,
        view["head_sha"],
        view["head_sha"],
        ref.receipt_ref,
    )
    result = recovery.complete(
        lease, observed, {"domain_closed": True, "grant_id": "synthetic-observer"}
    )
    assert result["publication_performed"] and result["completed_after_withdrawal"]
    assert result["observed"]["observed_target_sha"] == "d" * 40
    assert s.c.store.get(101, original.run_id).status == "superseded"
    assert recovery.receipt(**command) == result
    assert publications.request(101, original.run_id)["result"] == result
    assert s.c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_observation_cannot_begin_without_exact_original_closed_proof(
    publication_request,
):
    """A boolean or another attempt's host proof cannot promote uncertain work into readonly recovery."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.publication_recovery import PublicationRecovery

    s, _candidate, _publications, original, proof = original_closed(publication_request)
    command = {
        "project_id": 101,
        "run_id": original.run_id,
        "attempt_id": original.attempt_id,
        "expected_fence": original.fence,
        "operation_key": "invalid-observation",
    }
    for changed in (
        {**proof, "execution_closed": False},
        {**proof, "attempt_id": "another-attempt"},
        {**proof, "database_identity": "0" * 64},
    ):
        with pytest.raises(RunConflict):
            PublicationRecovery(s.c.store).begin(
                **command, proof=changed, owner_id="observer"
            )


@pytest.mark.parametrize(
    "state,target,marker", [("not_applied", None, None), ("uncertain", "d" * 40, None)]
)
def test_readonly_result_distinguishes_no_effect_from_uncertainty(
    publication_request, state, target, marker
):
    """Only a conclusive observation becomes a final publication result; uncertainty retains a separate recovery receipt without authorizing another write."""
    from backend.runtime.publication_git import (
        PublicationRefIntent,
        PublicationRefObservation,
    )
    from backend.runtime.publication_recovery import PublicationRecovery

    s, _candidate, publications, original, proof = original_closed(publication_request)
    recovery = PublicationRecovery(s.c.store)
    command = {
        "project_id": 101,
        "run_id": original.run_id,
        "attempt_id": original.attempt_id,
        "expected_fence": original.fence,
        "operation_key": "observe-state",
    }
    lease, peers = recovery.begin(**command, proof=proof, owner_id="readonly-host")
    peer = peers.registry.prepare(lease, "command")
    peers.registry.close(peer)
    view = publications.request(101, original.run_id)["view"]
    ref = PublicationRefIntent(original.run_id, "refs/heads/reviewed-change", None)
    observed = PublicationRefObservation(
        state, False, target, marker, view["head_sha"], ref.receipt_ref
    )
    result = recovery.complete(
        lease, observed, {"domain_closed": True, "grant_id": "synthetic-observer"}
    )
    assert not result["publication_performed"] and result["observed"]["state"] == state
    assert (publications.request(101, original.run_id)["result"] is None) == (
        state == "uncertain"
    )
    assert s.c.store.get(101, original.run_id).status == (
        "reconciling" if state == "uncertain" else "failed"
    )
    assert recovery.receipt(**command) == result


def test_local_closed_namespace_without_global_grant_is_not_original_domain_proof(
    publication_request, monkeypatch
):
    """A local namespace closure cannot replace missing original global cgroup provenance for a previously bound command."""
    from contextlib import contextmanager
    from types import SimpleNamespace

    from backend.runtime import publication_closure
    from backend.runtime.contracts import RunConflict

    s, _candidate, _publications, original, _proof = original_closed(
        publication_request
    )
    s.c.conn.execute(
        "UPDATE runtime_peers SET init_pid=123,start_ticks=1 WHERE attempt_id=?",
        (original.attempt_id,),
    )
    s.c.conn.commit()

    @contextmanager
    def missing_journal(**_kwargs):
        """Supply an explicitly synthetic valid-empty journal view to exercise the missing original-grant branch."""
        yield SimpleNamespace(load=lambda: SimpleNamespace(records={}))

    monkeypatch.setattr(
        publication_closure, "WitnessedAuthorityJournal", missing_journal
    )
    with pytest.raises(RunConflict, match="global"):
        publication_closure.close_original_publication(
            {}, s.c.store, 101, original.run_id, original.attempt_id
        )
