"""Atomic planning delivery preserves explanation, identity and independent owner authority."""

import json

import pytest

from backend.planning.store import ProjectPlans
from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_project_planning import draft, planning_state

EXPLANATION = "Primero investigamos el comportamiento; después aplicamos el cambio respaldado. Puedes corregir la premisa sobre el repositorio."


def close_peers(peers):
    """Close synthetic storage-test witnesses; this helper makes no physical process claim."""
    for peer in peers.ids.values():
        peers.registry.close(peer)


def test_delivery_fences_tools_and_retains_original_receipt_after_lost_response(service_setup):
    """A committed explanation and graph survive reconnection without another write or new execution permission."""
    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    before = s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0]
    receipt = plans.deliver(lease, "delivery-a", draft(), EXPLANATION)
    assert plans.state(101, run.run_id)["proposal"]["delivery"]["explanation"] == EXPLANATION
    assert s.c.store.get(101, run.run_id).status == "cancelling"
    assert not plans.state(101, run.run_id)["eligible"]
    with pytest.raises(RunConflict):
        plans.material(lease)
    assert ProjectPlans(s.c.store).deliver(lease, "delivery-a", draft(), EXPLANATION) == receipt
    for key, explanation in [("other", EXPLANATION), ("delivery-a", "Changed explanation")]:
        with pytest.raises(RunConflict):
            plans.deliver(lease, key, draft(), explanation)
    with pytest.raises(RunConflict):
        plans.finish_delivery(lease, native_status="interrupted")
    close_peers(peers)
    result = plans.finish_delivery(lease, native_status="interrupted")
    assert result.status == "needs_review"
    assert plans.state(101, run.run_id)["eligible"]
    native = json.loads(s.c.conn.execute("SELECT native_result_json FROM runtime_attempts WHERE id=?", (lease.attempt_id,)).fetchone()[0])
    assert native["native_status"] == "interrupted"
    assert native["summary"] == EXPLANATION
    assert s.c.conn.execute("SELECT count(*)FROM tasks").fetchone()[0] == before
    accepted = plans.accept(101, run.run_id, operation_key="owner-a", proposal_sha256=receipt["proposal_sha256"], context_version=lease.context_version)
    assert len(accepted["tasks"]) == 2
    assert accepted["execution_started"] is False


@pytest.mark.parametrize("explanation", ["", "  ", "é" * 12001])
def test_invalid_explanation_never_partially_saves_a_plan(service_setup, explanation):
    """Invalid human delivery must roll back both the proposal and closure intent."""
    s, run, lease, _ = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    with pytest.raises(ValueError):
        plans.deliver(lease, "bad-explanation", draft(), explanation)
    assert plans.state(101, run.run_id)["proposal"] is None
    assert s.c.store.get(101, run.run_id).status == "running"


@pytest.mark.parametrize("reason", ["stop", "context", "failed", "unknown"])
def test_artifact_survives_without_eligibility_when_delivery_cannot_be_confirmed(service_setup, reason):
    """Saved text cannot override owner withdrawal, changed inputs or missing native termination."""
    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    plans.deliver(lease, "retained", draft(), EXPLANATION)
    close_peers(peers)
    if reason == "stop":
        s.c.store.cancel(101, run.run_id)
    elif reason == "context":
        s.c.conn.execute("UPDATE tasks SET description='Different task' WHERE id=1001")
        s.c.conn.commit()
    status = "failed" if reason == "failed" else None if reason == "unknown" else "interrupted"
    with pytest.raises(RunConflict):
        plans.finish_delivery(lease, native_status=status)
    state = plans.state(101, run.run_id)
    assert not state["eligible"]
    assert state["proposal"]["delivery"]["explanation"] == EXPLANATION
    assert state["acceptance"] is None


def test_legacy_proposal_does_not_become_a_typed_delivery(service_setup):
    """Old draft records still require their original native completion contract."""
    s, run, lease, peers = planning_state(service_setup)
    plans = ProjectPlans(s.c.store)
    plans.propose(lease, "old-draft", draft())
    close_peers(peers)
    assert plans.finish_delivery(lease, native_status="interrupted") is None
    assert "delivery" not in plans.state(101, run.run_id)["proposal"]
    assert not plans.state(101, run.run_id)["eligible"]


async def test_native_delivery_closes_without_returning_a_tool_reply_or_requesting_another_turn(tmp_path):
    """Host delivery interrupts the pending tool request yet keeps the actual native terminal status."""
    from backend.runtime.contracts import DeliveryReady
    from backend.tests.runtime.test_codex_session import requests, session

    async def delivered(_request):
        """Stand in for the already committed host operation, without fabricating native observations."""
        raise DeliveryReady()

    async with session(tmp_path, no_progress_seconds=1) as native:
        result = await native.run("budget-host", on_request=delivered)
    frames = requests(tmp_path)
    assert result.status == "interrupted"
    assert result.observed_tokens == 80
    assert sum(frame.get("method") == "turn/start" for frame in frames) == 1
    assert sum(frame.get("method") == "turn/interrupt" for frame in frames) == 1
    assert not any(frame.get("id") == "budget-1" and "result" in frame for frame in frames)


def test_closure_intent_failure_rolls_back_plan_and_explanation(service_setup):
    """A write failure between proposal insertion and fencing must leave neither half committed."""
    import sqlite3

    s, run, lease, _ = planning_state(service_setup)
    s.c.conn.execute("CREATE TRIGGER reject_delivery BEFORE UPDATE OF status ON runtime_runs WHEN NEW.status='cancelling' BEGIN SELECT RAISE(ABORT,'simulated write failure'); END")
    s.c.conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="simulated write failure"):
        ProjectPlans(s.c.store).deliver(lease, "atomic", draft(), EXPLANATION)
    assert ProjectPlans(s.c.store).state(101, run.run_id)["proposal"] is None
    assert s.c.store.get(101, run.run_id).status == "running"


def test_stop_before_delivery_prevents_any_artifact_commit(service_setup):
    """A queued final call cannot save new work after Stop has already withdrawn authority."""
    s, run, lease, _ = planning_state(service_setup)
    s.c.store.cancel(101, run.run_id)
    with pytest.raises(RunConflict):
        ProjectPlans(s.c.store).deliver(lease, "too-late", draft(), EXPLANATION)
    assert ProjectPlans(s.c.store).state(101, run.run_id)["proposal"] is None


async def test_atomic_delivery_keeps_the_configured_human_output_limit(tmp_path):
    """Moving the final answer into a tool must not bypass a smaller configured answer-byte fuse."""
    from backend.runtime.contracts import DeliveryReady
    from backend.runtime.codex_session import ExecutionLimitExceeded
    from backend.tests.runtime.test_codex_session import session

    async def delivered(_request):
        """Report a host-measured final explanation exceeding this test's explicit output bound."""
        raise DeliveryReady(101)

    async with session(tmp_path, max_answer_bytes=100) as native:
        with pytest.raises(ExecutionLimitExceeded) as stopped:
            await native.run("budget-host", on_request=delivered)
    assert stopped.value.kind == "output"
