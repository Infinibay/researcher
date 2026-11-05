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
