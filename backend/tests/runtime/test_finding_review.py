"""Real finding review subjects, author origin and independent-attempt authority."""

from dataclasses import replace

import pytest


@pytest.fixture
def authored_finding(coordination):
    """Commit a finding/report through a real bound original author attempt."""
    from backend.research.models import (
        EvidenceReference,
        FindingDraft,
        ReportDraft,
        SourceDraft,
    )

    c = coordination
    run = c.store.admit(c.spec)
    lease = c.store.claim(101, run.run_id, "author-host")
    c.store.bind_native(lease, thread_id="author-thread", turn_id="author-turn")
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions={
            "sources.capture",
            "sources.read",
            "findings.write",
            "reports.write",
        },
    )
    grant = c.research.authorize(token)
    c.store.bind_grant(lease, grant.grant_id)
    scope = c.research.authorize(token)
    source = c.research.capture_source(
        scope,
        "author-source",
        SourceDraft(
            "web",
            "https://example.org/fact",
            "Observed data",
            "The sample contains 137 units.",
        ),
        intent={},
    )
    finding = c.research.record_finding(
        scope,
        "author-finding",
        FindingDraft(
            topic="Sample size",
            content="The recorded sample contains 137 units.",
            evidence=(EvidenceReference(source["source_id"], "137 units"),),
        ),
    )
    report = c.research.write_report(
        scope,
        "author-report",
        ReportDraft(
            title="Sample report",
            content="The recorded sample contains 137 units.",
            finding_ids=(finding["finding_id"],),
        ),
    )
    c.store.finish(lease, native_status="completed", summary="A draft for review.")
    return c, lease, finding["finding_id"], source["source_id"], report["artifact_id"]


def test_review_subject_binds_exact_origin_finding_sources_and_reports(
    authored_finding,
):
    """A changed dependency cannot silently retain a previous review identity."""
    from backend.knowledge.reviews import finding_subject

    c, author, fid, _sid, rid = authored_finding
    subject = finding_subject(c.conn, 101, fid)
    assert subject["reviewable"] is True
    assert subject["snapshot"]["author"]["attempt_id"] == author.attempt_id
    assert subject["snapshot"]["author"]["run_id"] == author.run_id
    assert (
        subject["snapshot"]["finding"]["content"]
        == "The recorded sample contains 137 units."
    )
    assert subject["snapshot"]["evidence"][0]["quote"] == "137 units"
    assert subject["snapshot"]["reports"][0]["id"] == rid
    assert "content" not in subject["snapshot"]["evidence"][0]["source"]
    before = subject["subject_sha256"]
    c.conn.execute("UPDATE findings SET content='A changed claim' WHERE id=?", (fid,))
    c.conn.commit()
    assert finding_subject(c.conn, 101, fid)["subject_sha256"] != before


def test_review_subject_does_not_infer_native_authorship_for_legacy_rows(coordination):
    """An active flag and reviewer-looking author name prove no original attempt."""
    from backend.knowledge.reviews import finding_subject

    c = coordination
    c.conn.execute(
        "INSERT INTO findings(project_id,task_id,topic,content,agent_id,status) VALUES(101,1001,'Legacy','Claim','reviewer','active')"
    )
    fid = c.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.conn.commit()
    subject = finding_subject(c.conn, 101, fid)
    assert subject["reviewable"] is False
    assert subject["snapshot"]["author"] is None
    assert subject["reason"] == "author_origin_unknown"


def test_review_subject_rejects_corrupt_captured_source(authored_finding):
    """A retained source id/hash cannot disguise changed saved bytes."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import InvalidEvidence

    c, _, fid, sid, _ = authored_finding
    c.conn.execute(
        "UPDATE research_sources SET content='Unrecorded change' WHERE id=?", (sid,)
    )
    c.conn.commit()
    with pytest.raises(InvalidEvidence, match="hash"):
        finding_subject(c.conn, 101, fid)


def test_review_subject_ignores_derived_embedding_cache(authored_finding):
    """Retrieval cache bytes cannot masquerade as claim or review version changes."""
    from backend.knowledge.reviews import finding_subject

    c, _, fid, _, _ = authored_finding
    before = finding_subject(c.conn, 101, fid)["subject_sha256"]
    c.conn.execute(
        "UPDATE findings SET embedding=? WHERE id=?", (b"derived-vector", fid)
    )
    c.conn.commit()
    assert finding_subject(c.conn, 101, fid)["subject_sha256"] == before


def test_review_migration_is_atomic_repeatable_and_preserves_original_claim(
    authored_finding,
):
    """Review tables must not promote or rewrite pre-existing evidence."""
    from backend.tools.base.db import ensure_migrations

    c, _, fid, _, _ = authored_finding
    ensure_migrations(c.database)
    ensure_migrations(c.database)
    tables = {
        r[0]
        for r in c.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"finding_review_requests", "finding_review_decisions"} <= tables
    assert (
        c.conn.execute("SELECT status FROM findings WHERE id=?", (fid,)).fetchone()[0]
        == "provisional"
    )
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=34"
        ).fetchone()[0]
        == 1
    )
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_review_admission_is_distinct_frozen_and_idempotent(authored_finding):
    """Admit the review alongside its closed author proposal, without accepting it."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import ReviewTarget

    c, author, fid, _, _ = authored_finding
    subject = finding_subject(c.conn, 101, fid)
    target = ReviewTarget(fid, subject["subject_sha256"])
    spec = replace(
        c.spec,
        actor_id="reviewer",
        operation_key="review-request",
        prompt="Review the exact saved claim.",
    )
    run, fresh = c.store.admit_once(spec, review=target)
    assert fresh and run.run_id != author.run_id
    assert run.review["finding_id"] == fid
    assert run.review["subject_sha256"] == target.subject_sha256
    assert c.store.get(101, author.run_id).status == "needs_review"
    replay, fresh = c.store.admit_once(spec, review=target)
    assert not fresh and replay.run_id == run.run_id
    assert (
        c.conn.execute("SELECT COUNT(*) FROM finding_review_requests").fetchone()[0]
        == 1
    )
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )


@pytest.mark.parametrize(
    "fault", ["same_actor", "changed_subject", "unrelated_active_run"]
)
def test_review_admission_rejects_missing_independence_or_subject_authority(
    authored_finding, fault
):
    """Neither a role name nor a new operation key bypasses review admission."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import ReviewTarget
    from backend.runtime.contracts import RunConflict

    c, author, fid, _, _ = authored_finding
    target = ReviewTarget(fid, finding_subject(c.conn, 101, fid)["subject_sha256"])
    spec = replace(
        c.spec,
        actor_id="reviewer",
        operation_key="review-fault",
        prompt="Review this claim.",
    )
    if fault == "same_actor":
        spec = replace(spec, actor_id=author.actor_id)
    elif fault == "changed_subject":
        c.conn.execute(
            "UPDATE findings SET content='Different claim' WHERE id=?", (fid,)
        )
        c.conn.commit()
    else:
        c.store.cancel(101, author.run_id)
        c.store.admit(replace(c.spec, operation_key="other-work"))
        target = ReviewTarget(fid, finding_subject(c.conn, 101, fid)["subject_sha256"])
    with pytest.raises(RunConflict):
        c.store.admit_once(spec, review=target)
    assert (
        c.conn.execute("SELECT COUNT(*) FROM finding_review_requests").fetchone()[0]
        == 0
    )


@pytest.fixture
def admitted_review(authored_finding):
    """Bind a distinct review grant to the immutable owner-admitted subject."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import REVIEW_PERMISSIONS, ReviewTarget

    c, author, fid, sid, rid = authored_finding
    target = ReviewTarget(fid, finding_subject(c.conn, 101, fid)["subject_sha256"])
    spec = replace(
        c.spec,
        actor_id="reviewer",
        operation_key="review-request",
        prompt="Review the exact saved claim.",
    )
    run = c.store.admit(spec, review=target)
    lease = c.store.claim(101, run.run_id, "review-host")
    c.store.bind_native(lease, thread_id="review-thread", turn_id="review-turn")
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions=set(REVIEW_PERMISSIONS),
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    return c, author, lease, c.research.authorize(token), fid, sid, rid, target


def decision(source_id):
    """Specify a limited documentary check rather than a scientific certification."""
    from backend.research.models import EvidenceReference, ReviewCheck, ReviewDecision

    return ReviewDecision(
        "supported",
        "The captured text supports this sample count.",
        (
            ReviewCheck(
                "claim_support",
                "supported",
                "The saved source explicitly contains the count.",
            ),
        ),
        (EvidenceReference(source_id, "137 units"),),
        ("The underlying measurement was not independently repeated.",),
    )


def test_review_decision_retains_real_attempt_and_does_not_accept_work(admitted_review):
    """Only the bound reviewer records a version-specific assertion and receipt."""
    c, author, lease, scope, fid, sid, rid, target = admitted_review
    result = c.research.record_review(scope, "review-decision", decision(sid))
    assert result["verdict"] == "supported"
    assert result["subject_sha256"] == target.subject_sha256
    assert c.research.record_review(scope, "review-decision", decision(sid)) == result
    row = c.conn.execute("SELECT * FROM finding_review_decisions").fetchone()
    assert row["reviewer_attempt_id"] == lease.attempt_id != author.attempt_id
    assert row["reviewer_actor_id"] == lease.actor_id != author.actor_id
    assert c.conn.execute(
        "SELECT status,confidence FROM findings WHERE id=?", (fid,)
    ).fetchone()[:] == ("provisional", None)
    assert (
        c.conn.execute(
            "SELECT status FROM research_reports WHERE artifact_id=?", (rid,)
        ).fetchone()[0]
        == "draft"
    )
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )


@pytest.mark.parametrize(
    "fault", ["stale_claim", "revoked", "context", "foreign_quote", "second_decision"]
)
def test_review_decision_rejects_stale_or_unadmitted_effects(admitted_review, fault):
    """A saved role name does not authorize a new, stale or foreign decision."""
    from backend.research.models import (
        EvidenceReference,
        InvalidEvidence,
        OperationConflict,
        ResearchForbidden,
        ResearchNotFound,
    )

    c, _, _lease, scope, fid, sid, _, _ = admitted_review
    draft = decision(sid)
    if fault == "stale_claim":
        c.conn.execute("UPDATE findings SET content='A new claim' WHERE id=?", (fid,))
        c.conn.commit()
    elif fault == "revoked":
        c.research.revoke_grant(scope.grant_id)
    elif fault == "context":
        c.store.correct_context(
            project_id=101,
            task_id=1001,
            expected_version=1,
            operation_key="correct-review",
            statement="Review the revised scope.",
            source_kind="user_message",
            source_reference="message-42",
        )
    elif fault == "foreign_quote":
        draft = replace(
            draft, evidence=(EvidenceReference(99999, "Not an admitted source"),)
        )
    else:
        c.research.record_review(scope, "first-decision", draft)
    with pytest.raises(
        (ResearchForbidden, OperationConflict, InvalidEvidence, ResearchNotFound)
    ):
        c.research.record_review(scope, "other-decision", draft)
    assert c.conn.execute("SELECT COUNT(*) FROM finding_review_decisions").fetchone()[
        0
    ] == (1 if fault == "second_decision" else 0)


async def test_review_service_uses_restricted_grant_and_frozen_subject(
    authored_finding, service_setup
):
    """The real coordinator selects review authority from the stored request."""
    import json

    from backend.knowledge.reviews import finding_subject
    from backend.research.models import REVIEW_PERMISSIONS, ReviewTarget
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )

    (
        c,
        _,
        fid,
        sid,
        _,
    ) = authored_finding
    target = ReviewTarget(fid, finding_subject(c.conn, 101, fid)["subject_sha256"])

    class ControlledReview(ControlledInference):
        """Replace only generation; admission, grants, input and decisions remain real."""

        async def run(self, prompt, *, on_started, on_event):
            """Inspect received authority and commit one requested documentary decision."""
            result = await super().run(prompt, on_started=on_started, on_event=on_event)
            assert self.scope.permissions == REVIEW_PERMISSIONS
            assert (
                json.loads(prompt)["review"]["subject_sha256"] == target.subject_sha256
            )
            c.research.record_review(
                self.scope, "service-review-decision", decision(sid)
            )
            return result

    native = ControlledReview(service_setup)
    native.release.set()
    service = coordinator(service_setup, native)
    spec = replace(
        c.spec,
        actor_id="reviewer",
        operation_key="review-service",
        prompt="Review the saved count.",
    )
    async with service:
        run = await service.submit(spec, repository_id=11, review=target)
        await service.wait(run.run_id)
        view = c.store.get(101, run.run_id)
        assert view.status == "needs_review"
        assert view.review["decision_id"] is not None
        assert len(native.prompts) == 1
        replay = await service.submit(spec, repository_id=11, review=target)
        assert replay.run_id == run.run_id and len(native.prompts) == 1


async def test_review_host_catalog_is_readonly_except_decision_and_question(
    admitted_review,
):
    """Real HTTP mediation exposes the bound decision tool and rejects author tools."""
    import json
    from dataclasses import asdict

    import httpx

    from backend.api.main import create_app
    from backend.api.research_dependencies import ResearchContext, get_research_context
    from backend.runtime.business_mediation import REVIEW_NAMES
    from backend.runtime.host_business import host_business

    c, _, _, scope, _, sid, _, _ = admitted_review
    app = create_app()
    app.dependency_overrides[get_research_context] = lambda: ResearchContext(
        c.research, scope, None
    )
    async with host_business(
        api_url="http://127.0.0.1",
        token="controlled-review-token-for-http",
        transport=httpx.ASGITransport(app=app),
        active=lambda: True,
        withdraw=lambda: None,
        names=REVIEW_NAMES,
    ) as peer:
        names = {tool.name for tool in (await peer.list_tools()).tools}
        assert (
            "researcher_review_decide" in names and "researcher_review_subject" in names
        )
        assert (
            not {
                "researcher_capture_web",
                "researcher_finding_record",
                "researcher_report_write",
                "researcher_wiki_write",
            }
            & names
        )
        subject = await peer.call_tool(
            "researcher_review_subject", {"max_chars": 20000}
        )
        assert not subject.isError
        assert (
            json.loads(subject.content[0].text)["author_attempt_id"]
            != json.loads(subject.content[0].text)["reviewer_attempt_id"]
        )
        rejected = await peer.call_tool(
            "researcher_finding_record", {"topic": "Must not write"}
        )
        assert rejected.isError
        result = await peer.call_tool(
            "researcher_review_decide",
            json.loads(
                json.dumps({"operation_key": "http-review", **asdict(decision(sid))})
            ),
        )
        assert not result.isError, result
        assert json.loads(result.content[0].text)["verdict"] == "supported"
    assert (
        c.conn.execute("SELECT COUNT(*) FROM finding_review_decisions").fetchone()[0]
        == 1
    )


from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414 -- pytest fixture registration


async def test_owned_review_session_records_bound_decision_without_author_mutators(
    authored_finding, owned_config
):
    """Exercise real owned startup/Ken/catalog/HTTP/closure with generation controlled."""
    import json

    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import ReviewTarget

    c, author, fid, _, _ = authored_finding
    target = ReviewTarget(fid, finding_subject(c.conn, 101, fid)["subject_sha256"])
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    async with runtime:
        run = await runtime.submit(
            replace(
                c.spec,
                actor_id="reviewer",
                operation_key="owned-review",
                prompt="Review the exact saved sample count.",
            ),
            repository_id=11,
            review=target,
        )
        await runtime.wait(run.run_id)
        view = runtime.store.get(101, run.run_id)
        assert view.status == "needs_review", view
        assert view.review["decision_id"] is not None
        assert (
            view.attempt_id != author.attempt_id and view.thread_id != "author-thread"
        )
        rows = c.conn.execute("SELECT * FROM finding_review_decisions").fetchall()
        assert len(rows) == 1 and rows[0]["reviewer_attempt_id"] == view.attempt_id
        thread = json.loads(
            next(
                owned_config.s.control.glob("native-state/*/home/fixture-thread.json")
            ).read_text()
        )
        names = {tool["name"] for tool in thread["catalog"]}
        assert "researcher_review_decide" in names
        assert (
            not {
                "researcher_finding_record",
                "researcher_capture_web",
                "researcher_report_write",
            }
            & names
        )
        assert all(
            r[0] == "closed" for r in c.conn.execute("SELECT state FROM runtime_peers")
        )


async def test_owner_can_inspect_and_admit_exact_review_with_csrf(
    authored_finding, service_setup
):
    """Owner scope and a concrete observed version precede actual review dispatch."""
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_runtime_service import (
        ControlledInference,
        coordinator,
    )

    (
        c,
        _,
        fid,
        sid,
        _,
    ) = authored_finding

    class Review(ControlledInference):
        """Supply only generation while owner and tool authority stay real."""

        async def run(self, prompt, *, on_started, on_event):
            """Commit the limited requested review under its actual bound grant."""
            result = await super().run(prompt, on_started=on_started, on_event=on_event)
            c.research.record_review(self.scope, "owner-api-decision", decision(sid))
            return result

    native = Review(service_setup)
    native.release.set()
    runtime = coordinator(service_setup, native)
    app = create_app(
        access=LocalAccess(pairing_key="review-owner-fixture-with-32-characters")
    )
    app.state.runtime_service = runtime
    path = f"/api/projects/101/findings/{fid}/review-state"
    async with (
        runtime,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client,
    ):
        paired = await client.post(
            "/api/session",
            json={"code": "review-owner-fixture-with-32-characters"},
            headers={"X-Researcher-Client": "web"},
        )
        assert paired.status_code == 200
        state = await client.get(path)
        assert state.status_code == 200, state.text
        observed = state.json()
        assert observed["reviewable"] and observed["context_version"] == 1
        body = {
            "operation_key": "owner-review",
            "context_version": 1,
            "finding_id": fid,
            "subject_sha256": observed["subject_sha256"],
            "repository_id": 11,
        }
        admission = "/api/projects/101/tasks/1001/finding-reviews"
        assert (await client.post(admission, json=body)).status_code == 403
        client.headers["X-Researcher-CSRF"] = paired.json()["csrf_token"]
        response = await client.post(admission, json=body)
        assert response.status_code == 202, response.text
        await runtime.wait(response.json()["run_id"])
        replay = await client.post(admission, json=body)
        assert (
            replay.status_code == 202
            and replay.json()["run_id"] == response.json()["run_id"]
        )
        assert len(native.prompts) == 1
        final = (await client.get(path)).json()
        assert len(final["reviews"]["items"]) == 1
        item = final["reviews"]["items"][0]
        assert item["subject_current"] and item["verdict"] == "supported"
        detail = await client.get(
            f"/api/projects/101/finding-reviews/{item['request_id']}"
        )
        assert detail.status_code == 200
        assert detail.json()["decision"]["limitations"] == [
            "The underlying measurement was not independently repeated."
        ]
        assert detail.json()["scientific_confidence"] is None


@pytest.mark.parametrize("change", ["report_status", "author_proposal_status"])
def test_administrative_acceptance_does_not_change_reviewed_scientific_subject(
    authored_finding, change
):
    """Accepting unchanged work must not fabricate a new scientific claim version."""
    from backend.knowledge.reviews import finding_subject

    c, author, fid, _, rid = authored_finding
    before = finding_subject(c.conn, 101, fid)["subject_sha256"]
    if change == "report_status":
        c.conn.execute(
            "UPDATE research_reports SET status='accepted' WHERE artifact_id=?", (rid,)
        )
    else:
        c.conn.execute(
            "UPDATE runtime_runs SET status='accepted' WHERE id=?", (author.run_id,)
        )
    c.conn.commit()
    assert finding_subject(c.conn, 101, fid)["subject_sha256"] == before


def test_review_subject_refuses_to_drop_an_orphaned_citation(authored_finding):
    """A broken saved-source join is an integrity failure, not an empty review scope."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import InvalidEvidence

    (
        c,
        _,
        fid,
        sid,
        _,
    ) = authored_finding
    c.conn.execute("PRAGMA foreign_keys=OFF")
    c.conn.execute("DELETE FROM research_sources WHERE id=?", (sid,))
    c.conn.commit()
    try:
        with pytest.raises(InvalidEvidence):
            finding_subject(c.conn, 101, fid)
    finally:
        c.conn.execute("PRAGMA foreign_keys=ON")


@pytest.mark.parametrize("binder", ["bind_thread", "bind_native"])
def test_reviewer_cannot_reuse_the_authors_native_thread(authored_finding, binder):
    """A new actor label and attempt cannot turn the author's context into independence."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.models import ReviewTarget
    from backend.runtime.contracts import RunConflict

    (
        c,
        _,
        fid,
        _,
        _,
    ) = authored_finding
    target = ReviewTarget(fid, finding_subject(c.conn, 101, fid)["subject_sha256"])
    run = c.store.admit(
        replace(c.spec, actor_id="reviewer", operation_key="thread-fault"),
        review=target,
    )
    lease = c.store.claim(101, run.run_id, "review-host")
    args = {"thread_id": "author-thread"}
    if binder == "bind_native":
        args["turn_id"] = "different-turn"
    with pytest.raises(RunConflict, match="independent"):
        getattr(c.store, binder)(lease, **args)
    assert c.store.get(101, run.run_id).thread_id is None
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_inference_dispatches").fetchone()[
            0
        ]
        == 0
    )


def test_review_schema_can_rollback_without_losing_original_work(authored_finding):
    """An unused additive review schema can be removed and upgraded without id loss."""
    from backend.db.review_migration import restore_review_schema
    from backend.tools.base.db import ensure_migrations

    c, author, fid, sid, rid = authored_finding
    original = tuple(
        c.conn.execute(
            "SELECT id,topic,content,status FROM findings WHERE id=?", (fid,)
        ).fetchone()
    )
    from backend.db.development_migration import (
        restore_code_candidates,
        restore_development_kinds,
        restore_development_workspaces,
    )
    from backend.db.result_migration import restore_result_schema

    restore_code_candidates(c.conn)
    restore_development_workspaces(c.conn)
    restore_development_kinds(c.conn)
    restore_result_schema(c.conn)
    restore_review_schema(c.conn)
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=34"
        ).fetchone()[0]
        == 0
    )
    assert "execution_kind" not in {
        r[1] for r in c.conn.execute("PRAGMA table_info(runtime_runs)")
    }
    assert (
        tuple(
            c.conn.execute(
                "SELECT id,topic,content,status FROM findings WHERE id=?", (fid,)
            ).fetchone()
        )
        == original
    )
    assert (
        c.conn.execute("SELECT id FROM research_sources WHERE id=?", (sid,)).fetchone()[
            0
        ]
        == sid
    )
    assert (
        c.conn.execute(
            "SELECT artifact_id FROM research_reports WHERE artifact_id=?", (rid,)
        ).fetchone()[0]
        == rid
    )
    ensure_migrations(c.database)
    assert c.store.get(101, author.run_id).status == "needs_review"
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_review_schema_rollback_refuses_new_admissions(admitted_review):
    """A downgrade cannot erase a request merely because no decision exists yet."""
    from backend.db.review_migration import restore_review_schema

    c, _, lease, _, _, _, _, _ = admitted_review
    with pytest.raises(RuntimeError, match="review"):
        restore_review_schema(c.conn)
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM finding_review_requests WHERE run_id=?",
            (lease.run_id,),
        ).fetchone()[0]
        == 1
    )
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version=34"
        ).fetchone()[0]
        == 1
    )


def test_review_evidence_owner_window_checks_saved_and_expected_hash(authored_finding):
    """The existing owner source viewer must not show changed bytes as reviewed evidence."""
    from backend.runtime.contracts import RunConflict
    from backend.runtime.views import OwnerRuntimeView

    (
        c,
        _,
        _,
        sid,
        _,
    ) = authored_finding
    view = OwnerRuntimeView(c.database)
    source = view.source(101, sid)
    assert "137 units" in source["content"]
    with pytest.raises(RunConflict, match="version|hash"):
        view.source(101, sid, expected_sha256="0" * 64)
    c.conn.execute(
        "UPDATE research_sources SET content='Changed bytes' WHERE id=?", (sid,)
    )
    c.conn.commit()
    with pytest.raises(RunConflict, match="hash"):
        view.source(101, sid)


@pytest.mark.parametrize("change", ["metadata", "content"])
def test_additional_review_evidence_is_version_bound(admitted_review, change):
    """Counterevidence outside the author's citations remains a real review dependency."""
    import hashlib

    from backend.research.models import EvidenceReference, SourceDraft

    c, _, lease, scope, _, _, _, _ = admitted_review
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="another-researcher",
        permissions={"sources.capture"},
    )
    other = c.research.authorize(token)
    extra = c.research.capture_source(
        other,
        "additional-evidence",
        SourceDraft(
            "web",
            "https://example.org/independent",
            "Independent data",
            "Another source reports 137 units.",
        ),
        intent={},
    )
    c.research.record_review(
        scope,
        "review-additional",
        replace(
            decision(extra["source_id"]),
            evidence=(EvidenceReference(extra["source_id"], "137 units"),),
        ),
    )
    request_id = c.conn.execute(
        "SELECT id FROM finding_review_requests WHERE run_id=?", (lease.run_id,)
    ).fetchone()[0]
    assert c.store.finding_review_detail(101, request_id)["subject_current"] is True
    if change == "metadata":
        c.conn.execute(
            "UPDATE research_sources SET locator='https://different.example/replacement' WHERE id=?",
            (extra["source_id"],),
        )
    else:
        content = "A replacement source with different observations."
        c.conn.execute(
            "UPDATE research_sources SET content=?,sha256=? WHERE id=?",
            (content, hashlib.sha256(content.encode()).hexdigest(), extra["source_id"]),
        )
    c.conn.commit()
    detail = c.store.finding_review_detail(101, request_id)
    assert detail["subject_current"] is False
    assert detail["currentness_reason"] == "review_evidence_changed"


def test_review_citations_retain_source_dependencies_and_frozen_provenance(
    admitted_review,
):
    """A committed countercitation cannot lose its source or original provenance."""
    import sqlite3

    from backend.research.models import SourceDraft

    c, _, lease, scope, _, _, _, _ = admitted_review
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="another-researcher",
        permissions={"sources.capture"},
    )
    extra = c.research.capture_source(
        c.research.authorize(token),
        "retained-counterevidence",
        SourceDraft(
            "web",
            "https://example.org/independent",
            "Independent data",
            "The record contains 137 units.",
        ),
        intent={},
    )
    sid = extra["source_id"]
    c.research.record_review(scope, "retain-citation", decision(sid))
    request_id = c.conn.execute(
        "SELECT id FROM finding_review_requests WHERE run_id=?", (lease.run_id,)
    ).fetchone()[0]
    source = c.store.finding_review_detail(101, request_id)["decision"][
        "verified_evidence"
    ][0]["source"]
    assert source["locator"] == "https://example.org/independent"
    assert (
        c.conn.execute(
            "SELECT COUNT(*) FROM finding_sources WHERE source_id=?", (sid,)
        ).fetchone()[0]
        == 0
    )
    c.conn.execute("PRAGMA foreign_keys=ON")
    assert c.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        c.conn.execute("DELETE FROM research_sources WHERE id=?", (sid,))
    c.conn.rollback()
    assert (
        c.conn.execute("SELECT COUNT(*) FROM finding_review_evidence").fetchone()[0]
        == 1
    )


@pytest.mark.parametrize("change", ["content", "topic", "citation"])
def test_changed_claim_cannot_keep_its_original_native_authorship(
    authored_finding, change
):
    """A retained id/agent label is weaker than evidence of who wrote this version."""
    from backend.knowledge.reviews import finding_subject

    c, _, fid, sid, _ = authored_finding
    assert finding_subject(c.conn, 101, fid)["reviewable"]
    if change == "citation":
        c.conn.execute(
            "UPDATE finding_sources SET quote='sample' WHERE finding_id=? AND source_id=?",
            (fid, sid),
        )
    else:
        c.conn.execute(
            f"UPDATE findings SET {change}='A changed claim version' WHERE id=?", (fid,)
        )
    c.conn.commit()
    subject = finding_subject(c.conn, 101, fid)
    assert subject["snapshot"]["author"] is None
    assert (
        subject["reviewable"] is False and subject["reason"] == "author_origin_unknown"
    )


def test_old_native_writer_intent_is_verified_without_guessing_authorship(
    authored_finding,
):
    """Historical effects can prove an unchanged draft, never an edited replacement."""
    import json

    from backend.knowledge.reviews import finding_subject

    c, author, fid, _, _ = authored_finding
    row = c.conn.execute(
        "SELECT result_json FROM tool_operations WHERE operation_key='author-finding'"
    ).fetchone()
    original = json.loads(row[0])
    original.pop("finding_version_sha256", None)
    original.pop("finding_version_schema", None)
    c.conn.execute(
        "UPDATE tool_operations SET result_json=? WHERE operation_key='author-finding'",
        (json.dumps(original),),
    )
    c.conn.commit()
    subject = finding_subject(c.conn, 101, fid)
    assert (
        subject["reviewable"]
        and subject["snapshot"]["author"]["attempt_id"] == author.attempt_id
    )
    assert subject["snapshot"]["author"]["version_proof"] == "historical_writer_intent"
    c.conn.execute("UPDATE findings SET content='A later assertion' WHERE id=?", (fid,))
    c.conn.commit()
    assert finding_subject(c.conn, 101, fid)["snapshot"]["author"] is None


def test_author_can_read_actual_review_feedback_without_review_authority(
    admitted_review,
):
    """Recorded review presence is truthful, while currentness and permission stay separate."""
    import json

    c, _, _, scope, fid, sid, _, _ = admitted_review
    result = c.research.record_review(scope, "feedback-decision", decision(sid))
    token = c.research.issue_grant(
        project_id=101, task_id=1001, agent_id="reader", permissions={"findings.read"}
    )
    reader = c.research.authorize(token)
    items = c.research.list_findings(reader)["items"]
    assert items[0]["review_status"] == "independent_decision_recorded"
    assert items[0]["review"]["currentness"] == "not_checked"
    history = c.research.read_reviews(reader, fid)
    request_id = history["reviews"]["items"][0]["request_id"]
    assert history["read_kind"] == "history"
    detail = c.research.read_reviews(
        reader, fid, request_id=request_id, max_chars=20000
    )
    assert (
        detail["subject_current"] is True
        and detail["decision_id"] == result["decision_id"]
    )
    assert json.loads(detail["content"])["limitations"] == [
        "The underlying measurement was not independently repeated."
    ]
    old_subject = c.research.read_reviews(
        reader, fid, request_id=request_id, part="subject", max_chars=20000
    )
    assert (
        json.loads(old_subject["content"])["finding"]["content"]
        == "The recorded sample contains 137 units."
    )


def test_old_review_stays_inspectable_when_current_capture_is_corrupt(admitted_review):
    """A source integrity failure must not erase the historical decision or invent currentness."""
    c, _, lease, scope, _, sid, _, _ = admitted_review
    c.research.record_review(scope, "historical-decision", decision(sid))
    request_id = c.conn.execute(
        "SELECT id FROM finding_review_requests WHERE run_id=?", (lease.run_id,)
    ).fetchone()[0]
    c.conn.execute(
        "UPDATE research_sources SET content='Corrupt bytes' WHERE id=?", (sid,)
    )
    c.conn.commit()
    detail = c.store.finding_review_detail(101, request_id)
    assert detail["decision"]["verdict"] == "supported"
    assert detail["subject_current"] is None
    assert detail["currentness_reason"] == "review_subject_unavailable"


def test_retained_reader_gets_actual_feedback_without_review_write_authority(
    admitted_review,
):
    """Legacy read scope can inspect decisions and frozen subjects, but cannot retarget a foreign project."""
    import json

    from backend.tools.base.context import set_context
    from backend.tools.knowledge.read_finding_reviews import ReadFindingReviewsTool

    c, _, _, scope, fid, sid, _, _ = admitted_review
    receipt = c.research.record_review(scope, "legacy-feedback-decision", decision(sid))
    set_context(project_id=101, task_id=1001, agent_id="legacy-feedback-reader")
    try:
        tool = ReadFindingReviewsTool()
        history = json.loads(tool._run(finding_id=fid))
        assert history["read_kind"] == "history"
        rid = history["reviews"]["items"][0]["request_id"]
        detail = json.loads(tool._run(finding_id=fid, request_id=rid, max_chars=20000))
        assert detail["subject_current"] is True
        assert (
            json.loads(detail["content"])["verdict"]
            == receipt["verdict"]
            == "supported"
        )
        assert detail["scientific_confidence"] is None
        frozen = json.loads(
            tool._run(finding_id=fid, request_id=rid, part="subject", max_chars=20000)
        )
        assert json.loads(frozen["content"])["finding"]["id"] == fid
        c.conn.execute(
            "UPDATE research_sources SET title='Changed source metadata' WHERE id=?",
            (sid,),
        )
        c.conn.commit()
        stale = json.loads(tool._run(finding_id=fid, request_id=rid, max_chars=20000))
        assert stale["subject_current"] is False
        set_context(project_id=202, task_id=2002, agent_id="foreign-feedback-reader")
        assert "error" in json.loads(tool._run(finding_id=fid, request_id=rid))
    finally:
        set_context(project_id=None, task_id=None, agent_id=None, agent_run_id=None)
