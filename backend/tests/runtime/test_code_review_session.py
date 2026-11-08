"""Separate controlled native reviewer over a real captured candidate and owned kernel/Git/SQL boundaries."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tests.runtime.test_development_session import (
    development_attempt,
    run_development_turn,
)
from backend.tests.runtime.test_development_session import (
    development_config as development_config,  # noqa: PLC0414 -- use actual configured owned runtime.
)
from backend.tests.runtime.test_owned_factory import (
    owned_config as owned_config,  # noqa: PLC0414 -- development_config dependency.
)


@pytest.mark.timeout(60)
async def test_owned_native_review_records_exact_decision_after_closure(
    development_config,
):
    """Author and reviewer use distinct native threads; actual Git validation and quoted source bind the confirmed review without accepting the task."""
    from backend.research.models import REVIEW_PERMISSIONS
    from backend.runtime.code_reviews import CodeReviews, CodeReviewTarget
    from backend.runtime.peer_registry import AttemptPeers

    c = development_config
    async with development_attempt(c) as d:
        async with d.coordinator.runtime.open(
            workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
        ) as author_session:
            await run_development_turn(d, author_session)
            candidate = await author_session.capture_candidate()
            author_thread = author_session.thread_id
        await d.peers.aclose()
        d.coordinator.store.finish(
            d.lease,
            native_status="completed",
            summary="Actual captured candidate; awaiting review.",
        )
        reviews = CodeReviews(d.coordinator.store)
        packet = reviews.subject(101, d.lease.attempt_id)
        assert packet["snapshot"]["author_input"] is not None
        run, _created = reviews.admit_once(
            replace(
                c.s.c.spec,
                actor_id="independent-code-reviewer",
                operation_key="native-code-review",
                context_version=d.lease.context_version,
                prompt="Review the exact observed candidate against the owner's recorded request; cite actual source and state limits.",
            ),
            CodeReviewTarget(d.lease.attempt_id, packet["subject_sha256"]),
        )
        lease, peers = AttemptPeers.claim(
            d.coordinator.store,
            101,
            run.run_id,
            "review-native-fixture",
            lease_seconds=120,
        )
        token = d.coordinator.research.issue_grant(
            project_id=101,
            task_id=1001,
            agent_id=lease.actor_id,
            permissions=set(REVIEW_PERMISSIONS) - {"findings.review"},
        )
        scope = d.coordinator.research.authorize(token)
        d.coordinator.store.bind_grant(lease, scope.grant_id)
        live = d.coordinator.runtime.live_grants
        live.activate(scope.grant_id)
        try:
            async with d.coordinator.runtime.open(
                workspace=c.s.workspace, tool_token=token, peer_owner=peers
            ) as session:
                assert session.thread_id != author_thread
                assert Path(session.execution_workspace) == Path(candidate["workspace"])
                names = {tool["name"] for tool in session.catalog}
                assert {
                    "ken_read",
                    "researcher_code_review_subject",
                    "researcher_code_review_file",
                    "researcher_code_review_propose",
                } <= names
                assert (
                    not {
                        "researcher_finding_record",
                        "researcher_report_write",
                        "researcher_review_decide",
                        "researcher_wiki_write",
                        "researcher_result_propose",
                    }
                    & names
                )
                d.coordinator.store.bind_thread(lease, thread_id=session.thread_id)
                frozen = d.coordinator.store.reserve_input(
                    lease,
                    workspace=str(session.execution_workspace),
                    catalog_hash=session.catalog_hash,
                    model=session.model,
                    developer_instructions=session.developer_instructions,
                    catalog=session.catalog,
                    limits=d.coordinator.limits,
                )
                assert (
                    json.loads(frozen.input_text)["execution"]["kind"] == "code_review"
                )

                async def started(thread_id, turn_id):
                    """Bind the actual controlled protocol IDs through the production independent-thread guard."""
                    d.coordinator.store.bind_native(
                        lease, thread_id=thread_id, turn_id=turn_id
                    )

                result = await session.run(frozen.input_text, on_started=started)
                assert result.status == "completed"
                review = await session.complete_review()
                assert review["state"] == "confirmed"
                assert json.loads(review["proposal_json"])["verdict"] == "supported"
                assert (
                    json.loads(review["result_json"])["candidate"]["head_sha"]
                    == candidate["head_sha"]
                )
                assert await session.complete_review() == review
                assert (Path(candidate["workspace"]) / "fact.txt").read_text() == "200"
                assert (c.s.workspace / "fact.txt").read_text() == "137"
            await peers.aclose()

            d.coordinator.store.finish(
                lease, native_status="completed", summary=result.text
            )
            assert d.coordinator.store.get(101, run.run_id).status == "needs_review"
            assert (
                d.coordinator.store.context_snapshot(101, 1001)["task"]["status"]
                != "done"
            )
        finally:
            live.withdraw(scope.grant_id)
            d.coordinator.research.revoke_grant(scope.grant_id)
            await peers.aclose()


@asynccontextmanager
async def proposed_native_review(c):
    """Run actual author capture and controlled independent reviewer once, yielding its unconfirmed original proposal."""
    from backend.research.models import CODE_REVIEW_PERMISSIONS
    from backend.runtime.code_review_records import CodeReviewRecords
    from backend.runtime.code_reviews import CodeReviews, CodeReviewTarget
    from backend.runtime.peer_registry import AttemptPeers

    async with development_attempt(c) as d:
        async with d.coordinator.runtime.open(
            workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
        ) as session:
            await run_development_turn(d, session)
            candidate = await session.capture_candidate()
        await d.peers.aclose()
        d.coordinator.store.finish(
            d.lease,
            native_status="completed",
            summary="Actual candidate for controlled review",
        )
        packet = CodeReviews(d.coordinator.store).subject(101, d.lease.attempt_id)
        spec = replace(
            c.s.c.spec,
            actor_id="reviewer-failure-fixture",
            operation_key="review-failure",
            context_version=d.lease.context_version,
            prompt="Inspect the observed candidate and propose an attributed review.",
        )
        run, _ = CodeReviews(d.coordinator.store).admit_once(
            spec, CodeReviewTarget(d.lease.attempt_id, packet["subject_sha256"])
        )
        lease, peers = AttemptPeers.claim(
            d.coordinator.store,
            101,
            run.run_id,
            "review-failure-host",
            lease_seconds=120,
        )
        token = d.coordinator.research.issue_grant(
            project_id=101,
            task_id=1001,
            agent_id=lease.actor_id,
            permissions=set(CODE_REVIEW_PERMISSIONS),
        )
        scope = d.coordinator.research.authorize(token)
        d.coordinator.store.bind_grant(lease, scope.grant_id)
        live = d.coordinator.runtime.live_grants
        live.activate(scope.grant_id)
        try:
            async with d.coordinator.runtime.open(
                workspace=c.s.workspace, tool_token=token, peer_owner=peers
            ) as reviewer:
                d.coordinator.store.bind_thread(lease, thread_id=reviewer.thread_id)
                frozen = d.coordinator.store.reserve_input(
                    lease,
                    workspace=str(reviewer.execution_workspace),
                    catalog_hash=reviewer.catalog_hash,
                    model=reviewer.model,
                    developer_instructions=reviewer.developer_instructions,
                    catalog=reviewer.catalog,
                    limits=d.coordinator.limits,
                )

                async def started(thread_id, turn_id):
                    """Bind actual original native IDs before any review proposal can commit."""
                    d.coordinator.store.bind_native(
                        lease, thread_id=thread_id, turn_id=turn_id
                    )

                result = await reviewer.run(frozen.input_text, on_started=started)
                assert result.status == "completed"
                yield SimpleNamespace(
                    c=c,
                    coordinator=d.coordinator,
                    session=reviewer,
                    lease=lease,
                    candidate=candidate,
                    records=CodeReviewRecords(d.coordinator.store),
                )
        finally:
            live.withdraw(scope.grant_id)
            d.coordinator.research.revoke_grant(scope.grant_id)
            await peers.aclose()


@pytest.mark.parametrize("change", ["context", "source"])
@pytest.mark.timeout(60)
async def test_changed_review_cannot_confirm_and_retains_original_proposal(
    development_config, change
):
    """Actual model completion cannot bless corrected requirements or a modified candidate; useful old assertions remain historical."""
    from backend.runtime.contracts import RunConflict

    async with proposed_native_review(development_config) as review:
        if change == "context":
            review.coordinator.store.correct_context(
                project_id=101,
                task_id=1001,
                expected_version=review.lease.context_version,
                operation_key="review-context-change",
                statement="Preserve the original behavior.",
                source_kind="user_message",
                source_reference="owner:changed-review",
            )
        else:
            (Path(review.candidate["workspace"]) / "fact.txt").write_text("999")
        with pytest.raises(RunConflict):
            await review.session.complete_review()
        row = review.records.get(101, review.lease.attempt_id)
        assert (
            row["state"] == "reconciling"
            and row["proposal_json"] is not None
            and row["result_json"] is None
        )
        assert (review.c.s.workspace / "fact.txt").read_text() == "137"


@pytest.mark.timeout(60)
async def test_stop_during_review_confirmation_closes_original_owner_and_joins_work(
    development_config, monkeypatch
):
    """Stop cannot return while a confirmation task can later create a confirmed result under the original domain."""
    from backend.runtime import code_review_controller

    async with proposed_native_review(development_config) as review:
        entered = asyncio.Event()
        never = asyncio.Event()

        async def held(*_args, **_kwargs):
            """Hold only the post-review validation; preparation already completed under actual owned Git."""
            entered.set()
            await never.wait()

        monkeypatch.setattr(code_review_controller, "validate_review_candidate", held)
        confirming = asyncio.create_task(review.session.complete_review())
        await asyncio.wait_for(entered.wait(), 10)
        await asyncio.wait_for(review.session.cancel(), 5)
        await asyncio.wait_for(asyncio.gather(confirming, return_exceptions=True), 5)
        row = review.records.get(101, review.lease.attempt_id)
        assert (
            row["state"] == "reconciling"
            and row["result_json"] is None
            and row["proposal_json"] is not None
        )
        grant = review.session._owner.broker.journal.load().records[
            review.session._owner.broker._grant_key
        ]
        assert grant["state"] == "retired" and grant["domain_removed"]


@pytest.mark.parametrize("changed,rejected", [(False, False), (True, False), (False, True)])
@pytest.mark.timeout(60)
async def test_coordinator_schedules_native_review_and_does_not_finish_unconfirmed_work(
    development_config, monkeypatch, changed, rejected
):
    """Actual owned review preserves rejection or uncertain confirmation without automatic rework, another dispatch or task acceptance."""
    from backend.runtime.code_review_records import CodeReviewRecords
    from backend.runtime.code_reviews import CodeReviews, CodeReviewTarget

    c = development_config
    async with development_attempt(c) as d:
        async with d.coordinator.runtime.open(
            workspace=c.s.workspace, tool_token=d.token, peer_owner=d.peers
        ) as author:
            await run_development_turn(d, author)
            candidate = await author.capture_candidate()
        await d.peers.aclose()
        d.coordinator.store.finish(
            d.lease,
            native_status="completed",
            summary="Actual source candidate for product review",
        )
        packet = CodeReviews(d.coordinator.store).subject(101, d.lease.attempt_id)
        original = CodeReviewRecords.confirm

        def confirm(records, *args, **kwargs):
            """Change actual quoted bytes after post-review Git, so final citation validation must still reject them."""
            if changed:
                (Path(candidate["workspace"]) / "fact.txt").write_text("999")
            return original(records, *args, **kwargs)

        monkeypatch.setattr(CodeReviewRecords, "confirm", confirm)
        async with d.coordinator:
            run = await d.coordinator.review_code(
                replace(
                    c.s.c.spec,
                    actor_id="product-code-reviewer",
                    operation_key="product-code-review",
                    context_version=d.lease.context_version,
                    prompt="Review this exact candidate and state the observed evidence and limits." + (" Controlled test: request changes." if rejected else ""),
                ),
                CodeReviewTarget(d.lease.attempt_id, packet["subject_sha256"]),
            )
            await d.coordinator.wait(run.run_id)
            view = d.coordinator.store.get(101, run.run_id)
            with d.coordinator.store._transaction() as conn:
                row = conn.execute(
                    "SELECT * FROM runtime_code_review_records WHERE run_id=?",
                    (run.run_id,),
                ).fetchone()
            if changed:
                assert (
                    view.status == "failed"
                    and row["state"] == "reconciling"
                    and row["result_json"] is None
                )
                assert view.issue["code"] == "code_review_unconfirmed"
            else:
                assert view.status == "needs_review" and row["state"] == "confirmed"
            assert row["proposal_json"] is not None
            assert (
                d.coordinator.store.context_snapshot(101, 1001)["task"]["status"]
                != "done"
            )
            assert (c.s.workspace / "fact.txt").read_text() == "137"
            from backend.tests.runtime.test_code_acceptance import choose_fixture_check_policy
            choose_fixture_check_policy(d.coordinator.store)
            owner_state = d.coordinator.store.code_result_state(101, d.run.run_id)
            if rejected:
                assert json.loads(row["proposal_json"])["verdict"] == "needs_revision"
                assert not owner_state["eligible"] and owner_state["acceptance"] is None
                # Exercise the actual dispatcher rather than waiting for silence.
                for _ in range(3):
                    await d.coordinator.dispatch_planned_work()
                assert c.s.c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 2
                assert c.s.c.conn.execute("SELECT count(*) FROM runtime_inference_dispatches").fetchone()[0] == 2
                assert not d.coordinator._workers
                assert c.s.c.conn.execute("SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL").fetchone()[0] == 0
            elif changed:
                assert not owner_state["eligible"] and owner_state["acceptance"] is None
            else:
                assert (
                    owner_state["eligible"] and owner_state["requires_acknowledgement"]
                )
                receipt = d.coordinator.store.accept_code(
                    101,
                    d.run.run_id,
                    operation_key="explicit-owner-code-acceptance",
                    attempt_id=d.lease.attempt_id,
                    context_version=d.lease.context_version,
                    subject_sha256=owner_state["subject_sha256"],
                    review_sha256=owner_state["review_sha256"],
                    check_policy_revision=owner_state["project_check_policy"]["revision"],
                    acknowledge_limits=True,
                    note="Owner accepts this exact controlled candidate with its displayed limitations.",
                )
                assert receipt["task_accepted"] and not receipt["publication_performed"]
                assert d.coordinator.store.code_result_state(101, d.run.run_id)[
                    "acceptance_current"
                ]
