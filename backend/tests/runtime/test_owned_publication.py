"""Complete host publication of controlled native author/reviewer output through real Git, broker, closure and durable owner state."""

import pytest

from backend.tests.runtime.test_development_session import (
    development_config as development_config,  # noqa: PLC0414 -- real configured owned factory fixture.
)
from backend.tests.runtime.test_owned_factory import (
    owned_config as owned_config,  # noqa: PLC0414 -- development_config dependency.
)


@pytest.mark.timeout(180)
async def test_owned_publication_runs_after_acceptance_without_another_model_turn(
    development_config,
):
    """A separate host attempt publishes the exact accepted head, keeps source files/task acceptance intact and recovers the original admission receipt."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.code_publications import (
        CodePublicationIntent,
        CodePublications,
    )
    from backend.tests.runtime.test_code_acceptance import owner_intent
    from backend.tests.runtime.test_code_review_session import proposed_native_review
    from backend.tests.runtime.test_development_workspace import fixture_git

    async with proposed_native_review(development_config) as review:
        await review.session.complete_review()
    runtime, candidate = review.coordinator, review.candidate
    runtime.store.finish(
        review.lease,
        native_status="completed",
        summary="Controlled confirmed review before explicit owner acceptance",
    )
    owner = CodeAcceptances(runtime.store)
    state = owner.state(101, candidate["run_id"])
    acceptance = owner.accept(101, candidate["run_id"], owner_intent(state))
    intent = CodePublicationIntent(
        "publish-owned-fixture",
        acceptance["operation_key"],
        candidate["attempt_id"],
        candidate["context_version"],
        state["subject_sha256"],
        state["review_sha256"],
        "refs/heads/reviewed-change",
        None,
    )
    with runtime.store._transaction() as conn:
        before = conn.execute(
            "SELECT count(*) FROM runtime_inference_dispatches"
        ).fetchone()[0]
    async with runtime:
        run = await runtime.publish_code(101, candidate["run_id"], intent)
        await runtime.wait(run.run_id)
        stored = runtime.store.get(101, run.run_id)
        assert stored.status == "accepted", (
            stored,
            CodePublications(runtime.store).request(101, run.run_id),
        )
        assert (
            await runtime.publish_code(101, candidate["run_id"], intent)
        ).run_id == run.run_id
    request = CodePublications(runtime.store).request(101, run.run_id)
    assert request["result"]["publication_performed"]
    assert request["result"]["observed"]["head_sha"] == candidate["head_sha"]
    assert (
        await fixture_git(
            development_config.s.workspace, "rev-parse", intent.target_ref
        )
    ).decode().strip() == candidate["head_sha"]
    assert (development_config.s.workspace / "fact.txt").read_text() == "137"
    assert runtime.store.context_snapshot(101, 1001)["task"]["status"] == "done"
    assert owner.state(101, candidate["run_id"])["acceptance_current"]
    with runtime.store._transaction() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM runtime_inference_dispatches"
            ).fetchone()[0]
            == before
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM runtime_peers WHERE state!='closed'"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.timeout(180)
async def test_owned_recovery_observes_commit_after_lost_response_without_repeating_transaction(
    development_config, monkeypatch
):
    """Real owned publication commits then loses its response; a fresh readonly observer recovers the marker with no second write or model turn."""
    from backend.runtime.code_acceptances import CodeAcceptances
    from backend.runtime.code_publications import (
        CodePublicationIntent,
        CodePublications,
    )
    from backend.runtime.publication_executor import OwnedPublicationGitExecutor
    from backend.tests.runtime.test_code_acceptance import owner_intent
    from backend.tests.runtime.test_code_review_session import proposed_native_review

    async with proposed_native_review(development_config) as review:
        await review.session.complete_review()
    runtime, candidate = review.coordinator, review.candidate
    runtime.store.finish(
        review.lease,
        native_status="completed",
        summary="Controlled review before lost-response recovery",
    )
    owner = CodeAcceptances(runtime.store)
    state = owner.state(101, candidate["run_id"])
    acceptance = owner.accept(101, candidate["run_id"], owner_intent(state))
    intent = CodePublicationIntent(
        "publish-lost-response",
        acceptance["operation_key"],
        candidate["attempt_id"],
        candidate["context_version"],
        state["subject_sha256"],
        state["review_sha256"],
        "refs/heads/recovered-change",
        None,
    )
    actual = OwnedPublicationGitExecutor.transact
    writes = []

    async def lost(self, command, **kwargs):
        """Deliver the actual original transaction before simulating its lost return path."""
        await actual(self, command, **kwargs)
        writes.append(kwargs["input_text"])
        raise OSError("Controlled response loss after actual Git commit")

    monkeypatch.setattr(OwnedPublicationGitExecutor, "transact", lost)
    async with runtime:
        run = await runtime.publish_code(101, candidate["run_id"], intent)
        await runtime.wait(run.run_id)
        uncertain = runtime.store.get(101, run.run_id)
        assert uncertain.status == "reconciling"
        with runtime.store._transaction() as conn:
            dispatches = conn.execute(
                "SELECT count(*) FROM runtime_inference_dispatches"
            ).fetchone()[0]
        command = {
            "project_id": 101,
            "run_id": run.run_id,
            "attempt_id": uncertain.attempt_id,
            "expected_fence": uncertain.fence,
            "operation_key": "recover-lost-response",
        }
        result = await runtime.reconcile_publication(**command)
        assert result["publication_performed"] and result["observed"]["target_current"]
        assert result["observer_attempt_id"] != uncertain.attempt_id
        assert await runtime.reconcile_publication(**command) == result
    assert len(writes) == 1
    assert runtime.store.get(101, run.run_id).status == "accepted"
    assert CodePublications(runtime.store).request(101, run.run_id)["result"] == result
    assert (development_config.s.workspace / "fact.txt").read_text() == "137"
    with runtime.store._transaction() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM runtime_inference_dispatches"
            ).fetchone()[0]
            == dispatches
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM runtime_peers WHERE state!='closed'"
            ).fetchone()[0]
            == 0
        )
