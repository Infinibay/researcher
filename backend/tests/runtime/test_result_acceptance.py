"""Research results require explicit delivery, immutable versions and a distinct owner decision."""

import pytest


def make_active_result(c, task_id=1001):
    """Write real scoped report/evidence under one live independently admitted author attempt."""
    from dataclasses import replace

    from backend.research.models import (
        RESEARCH_PERMISSIONS,
        EvidenceReference,
        FindingDraft,
        ReportDraft,
        SourceDraft,
    )

    run = c.store.admit(
        replace(c.spec, task_id=task_id, operation_key=f"request-{task_id}")
    )
    lease = c.store.claim(101, run.run_id, "author-host")
    c.store.bind_native(lease, thread_id="author-thread", turn_id="author-turn")
    token = c.research.issue_grant(
        project_id=101,
        task_id=task_id,
        agent_id=lease.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    c.store.bind_grant(lease, c.research.authorize(token).grant_id)
    scope = c.research.authorize(token)
    sid = c.research.capture_source(
        scope,
        "source",
        SourceDraft(
            "attachment", "synthetic:sample", "Sample", "The sample contains 137 units."
        ),
        intent={},
    )["source_id"]
    fid = c.research.record_finding(
        scope,
        "finding",
        FindingDraft(
            "Sample count",
            "The sample contains 137 units.",
            (EvidenceReference(sid, "137 units"),),
        ),
    )["finding_id"]
    report = c.research.write_report(
        scope,
        "report",
        ReportDraft(
            title="Sample report",
            content="The sample contains 137 units.",
            finding_ids=(fid,),
        ),
    )["artifact_id"]
    return c, lease, scope, fid, sid, report


@pytest.fixture
def active_result(coordination, request):
    """Provide one real live author and its evidence-backed draft."""
    if getattr(request, "param", "research") == "review":
        from dataclasses import replace

        coordination.conn.execute("UPDATE tasks SET type='review' WHERE id=1001")
        coordination.conn.commit()
        coordination.spec = replace(coordination.spec, context_version=coordination.store.context_snapshot(101,1001)["context_version"])
    return make_active_result(coordination)


def test_result_proposal_selects_actual_deliverables_and_never_completes_task(
    active_result,
):
    """A typed selection is independent of scratch writes, model completion text and scientific validation."""
    from backend.research.models import ReportDraft, ResultDraft

    c, lease, scope, fid, _, report = active_result
    scratch = c.research.write_report(
        scope,
        "scratch",
        ReportDraft(
            title="Scratch draft", content="Exploratory note.", finding_ids=(fid,)
        ),
    )["artifact_id"]
    draft = ResultDraft(
        (report,), "An exact documentary count.", ("The measurement was not repeated.",)
    )
    first = c.research.propose_result(scope, "deliver", draft)
    assert c.research.propose_result(scope, "deliver", draft) == first
    state = c.store.result_state(101, lease.run_id)
    assert state["candidate"]["candidate_id"] == first["candidate_id"]
    assert [item["artifact_id"] for item in state["candidate"]["reports"]] == [report]
    assert scratch not in [
        item["artifact_id"] for item in state["candidate"]["reports"]
    ]
    assert state["eligible"] is False and state["reason"] == "author_not_closed"
    c.store.finish(
        lease, native_status="completed", summary="VALIDATED. All work is done."
    )
    current = c.store.result_state(101, lease.run_id)
    assert current["eligible"] is True and current["candidate_current"] is True
    assert current["acceptance"] is None
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )
    assert c.conn.execute(
        "SELECT status,confidence FROM findings WHERE id=?", (fid,)
    ).fetchone()[:] == ("provisional", None)
    assert (
        c.conn.execute(
            "SELECT status FROM research_reports WHERE artifact_id=?", (report,)
        ).fetchone()[0]
        == "draft"
    )


def test_completed_turn_without_delivery_does_not_invent_a_candidate(active_result):
    """Written scratch reports and persuasive prose alone do not prove a selected final result."""
    c, lease, _, _, _, _ = active_result
    c.store.finish(
        lease,
        native_status="completed",
        summary="Everything is completed and approved.",
    )
    state = c.store.result_state(101, lease.run_id)
    assert state["candidate"] is None and state["eligible"] is False
    assert state["reason"] == "no_explicit_delivery"
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )


@pytest.fixture
def delivered_result(active_result):
    """Finish an explicit versioned delivery without making an owner decision."""
    from backend.research.models import ResultDraft

    c, lease, scope, _, _, report = active_result
    c.research.propose_result(
        scope,
        "deliver",
        ResultDraft(
            (report,),
            "A documentary result.",
            ("The underlying measurement was not repeated.",),
        ),
    )
    c.store.finish(
        lease, native_status="completed", summary="The selected report is ready."
    )
    return (*active_result, c.store.result_state(101, lease.run_id))


def accept(
    c,
    lease,
    state,
    *,
    key="owner-accept",
    ack=True,
    note="Accepted as a documentary result.",
):
    """Send exactly the observed candidate/context/review identity to the trusted owner use case."""
    return c.store.accept_result(
        101,
        lease.run_id,
        operation_key=key,
        candidate_id=state["candidate"]["candidate_id"],
        candidate_sha256=state["candidate"]["candidate_sha256"],
        context_version=lease.context_version,
        review_sha256=state["review_sha256"],
        acknowledge_limits=ack,
        note=note,
    )


def make_accepted_result(c):
    """Complete a real synthetic native research task through delivery, closure and an explicit owner decision."""
    from backend.research.models import ResultDraft

    _, lease, scope, _, _, report = make_active_result(c)
    c.research.propose_result(
        scope,
        "deliver",
        ResultDraft(
            (report,), "A documentary result.", ("The measurement was not repeated.",)
        ),
    )
    c.store.finish(
        lease, native_status="completed", summary="Selected report delivered."
    )
    accept(c, lease, c.store.result_state(101, lease.run_id))
    return c, lease


@pytest.mark.parametrize("active_result", ["research", "review"], indirect=True)
def test_owner_acceptance_is_distinct_idempotent_and_does_not_publish(delivered_result):
    """An explicit owner action completes one version, without promoting claims or report publication."""
    from backend.research.models import OperationConflict

    c, lease, _, fid, _, report, state = delivered_result
    receipt = accept(c, lease, state)
    assert receipt["actor_source"] == "paired_owner_action"
    assert receipt["task_accepted"] is True and receipt["scientific_confidence"] is None
    assert accept(c, lease, state) == receipt
    with pytest.raises(OperationConflict):
        accept(c, lease, state, note="Different owner intent.")
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] == "done"
    )
    assert c.store.get(101, lease.run_id).status == "accepted"
    assert c.conn.execute(
        "SELECT status,confidence FROM findings WHERE id=?", (fid,)
    ).fetchone()[:] == ("provisional", None)
    assert (
        c.conn.execute(
            "SELECT status FROM research_reports WHERE artifact_id=?", (report,)
        ).fetchone()[0]
        == "draft"
    )
    current = c.store.result_state(101, lease.run_id)
    assert current["acceptance"]["acceptance_id"] == receipt["acceptance_id"]
    assert current["acceptance_current"] is True


def test_missing_independent_review_requires_explicit_owner_acknowledgement(
    delivered_result,
):
    """No recorded reviewer is not converted into implied scientific or human verification."""
    from backend.research.models import OperationConflict

    c, lease, _, _, _, _, state = delivered_result
    assert state["requires_acknowledgement"] is True
    assert state["review_issues"][0]["reason"] == "no_independent_review"
    with pytest.raises(OperationConflict):
        accept(c, lease, state, ack=False)
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )


@pytest.mark.parametrize("change", ["report", "source", "context"])
def test_changed_delivery_cannot_be_accepted_by_reusing_old_observation(
    delivered_result, change
):
    """The owner cannot accidentally accept a different report/source/context with an old button."""
    import hashlib

    from backend.research.models import OperationConflict

    c, lease, _, _, sid, rid, state = delivered_result
    if change == "report":
        body = "# Sample report\n\nDifferent count."
        c.conn.execute("UPDATE artifacts SET content=? WHERE id=?", (body, rid))
        c.conn.execute(
            "UPDATE research_reports SET content_sha256=? WHERE artifact_id=?",
            (hashlib.sha256(body.encode()).hexdigest(), rid),
        )
    elif change == "source":
        body = "The sample contains 137 units. New source version."
        c.conn.execute(
            "UPDATE research_sources SET content=?,sha256=? WHERE id=?",
            (body, hashlib.sha256(body.encode()).hexdigest(), sid),
        )
    else:
        c.conn.execute("UPDATE task_contexts SET version=version+1 WHERE task_id=1001")
    c.conn.commit()
    current = c.store.result_state(101, lease.run_id)
    assert current["eligible"] is False
    with pytest.raises(OperationConflict):
        accept(c, lease, state)
    assert (
        c.conn.execute("SELECT count(*) FROM runtime_result_acceptances").fetchone()[0]
        == 0
    )
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "in_progress"
    )


def test_owner_operation_keys_are_scoped_to_the_task(delivered_result):
    """Different tasks can recover their own owner receipt using the same local action key."""
    from backend.research.models import ResultDraft

    c, first, _, _, _, _, state = delivered_result
    original = accept(c, first, state)
    _, second, scope, _, _, report = make_active_result(c, 1002)
    c.research.propose_result(
        scope, "deliver", ResultDraft((report,), "Second result.", ("Not repeated.",))
    )
    c.store.finish(second, native_status="completed", summary="Ready.")
    second_state = c.store.result_state(101, second.run_id)
    other = accept(c, second, second_state)
    assert (
        other["task_id"] == 1002 and other["acceptance_id"] != original["acceptance_id"]
    )
    assert accept(c, first, state) == original


def test_retry_after_context_change_returns_history_without_recompleting_task(
    delivered_result,
):
    """A lost-response retry recovers its old decision, not authority over a corrected task."""
    c, lease, _, _, _, _, state = delivered_result
    original = accept(c, lease, state)
    c.conn.execute("UPDATE task_contexts SET version=version+1 WHERE task_id=1001")
    c.conn.execute("UPDATE tasks SET status='pending',completed_at=NULL WHERE id=1001")
    c.conn.commit()
    assert accept(c, lease, state) == original
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "pending"
    )
    assert c.store.result_state(101, lease.run_id)["acceptance_current"] is False


def test_complete_source_bytes_are_bounded_before_delivery(active_result):
    """Large mutated legacy evidence cannot disappear behind a small metadata-only candidate."""
    import hashlib

    from backend.research.models import ResultDraft, SourceTooLarge

    c, _, scope, _, sid, report = active_result
    body = "137 units " + "é" * (1024**2 + 1)
    c.conn.execute(
        "UPDATE research_sources SET content=?,sha256=? WHERE id=?",
        (body, hashlib.sha256(body.encode()).hexdigest(), sid),
    )
    c.conn.commit()
    with pytest.raises(SourceTooLarge):
        c.research.propose_result(
            scope,
            "deliver",
            ResultDraft((report,), "Bounded result.", ("Not repeated.",)),
        )
    assert (
        c.conn.execute("SELECT COUNT(*) FROM runtime_result_proposals").fetchone()[0]
        == 0
    )


def test_delivery_freezes_complete_evidence_and_latest_explicit_selection(
    active_result,
):
    """Old receipt replay cannot replace the current explicitly delivered immutable candidate."""
    import json
    import sqlite3

    from backend.research.models import ResultDraft

    c, lease, scope, _, sid, report = active_result
    first_draft = ResultDraft((report,), "First summary.", ("Not repeated.",))
    first = c.research.propose_result(scope, "first", first_draft)
    second = c.research.propose_result(
        scope,
        "second",
        ResultDraft((report,), "Corrected summary.", ("Not repeated.",)),
    )
    assert c.research.propose_result(scope, "first", first_draft) == first
    assert (
        c.store.result_state(101, lease.run_id)["candidate"]["candidate_id"]
        == second["candidate_id"]
    )
    frozen = json.loads(
        c.conn.execute(
            "SELECT snapshot_json FROM runtime_result_proposals WHERE id=?",
            (first["candidate_id"],),
        ).fetchone()[0]
    )
    assert frozen["sources"][0]["source"]["content"] == "The sample contains 137 units."
    assert frozen["sources"][0]["source"]["id"] == sid
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        c.conn.execute(
            "UPDATE runtime_result_proposals SET subject_sha256='changed' WHERE id=?",
            (first["candidate_id"],),
        )
    c.conn.rollback()


async def test_author_delivery_tool_crosses_actual_catalog_http_and_bound_grant(
    coordination,
):
    """The new author capability uses the real transport and is absent from reviewer catalogs."""
    import json
    import time

    import httpx

    from backend.api.main import create_app
    from backend.research.models import RESEARCH_PERMISSIONS
    from backend.runtime.business_definitions import definitions
    from backend.runtime.business_mediation import REVIEW_NAMES, BusinessTools
    from backend.runtime.host_business import host_business

    c = coordination
    c.now[0] = time.time()
    _, lease, _, _, _, report = make_active_result(c)
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    app = create_app()
    app.state.live_grants.activate(scope.grant_id)
    assert "researcher_result_propose" not in {
        item.name for item in definitions(None, names=REVIEW_NAMES)
    }
    async with host_business(
        api_url="http://127.0.0.1",
        token=token,
        withdraw=lambda: app.state.live_grants.withdraw(scope.grant_id),
        transport=httpx.ASGITransport(app=app),
    ) as peer:
        facade = await BusinessTools.connect(peer)
        assert "researcher_result_propose" in {item["name"] for item in facade.catalog}
        arguments = {
            "operation_key": "native-deliver",
            "report_ids": [report],
            "summary": "A documentary result.",
            "limitations": ["Measurement not repeated."],
        }
        response = await facade.call(
            {"tool": "researcher_result_propose", "arguments": arguments}
        )
        assert response["success"], response
        receipt = json.loads(response["contentItems"][0]["text"])
        again = await facade.call(
            {"tool": "researcher_result_propose", "arguments": arguments}
        )
        assert json.loads(again["contentItems"][0]["text"]) == receipt
        assert receipt["task_accepted"] is False and receipt["report_ids"] == [report]


async def test_owner_api_scopes_frozen_delivery_and_requires_owner_csrf(
    delivered_result,
):
    """A frozen report remains inspectable after drift; tool bearers cannot accept on the owner's behalf."""
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    c, lease, _, _, _, report, state = delivered_result
    app = create_app(
        access=LocalAccess(pairing_key="result-owner-fixture-long-enough-code")
    )
    root = f"/api/projects/101/runs/{lease.run_id}/result"
    body = {
        "operation_key": "owner-ui",
        "candidate_id": state["candidate"]["candidate_id"],
        "candidate_sha256": state["candidate"]["candidate_sha256"],
        "context_version": 1,
        "review_sha256": state["review_sha256"],
        "acknowledge_limits": True,
        "note": "Accept documentary result.",
    }
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
        session = await client.post(
            "/api/session",
            json={"code": "result-owner-fixture-long-enough-code"},
            headers={"X-Researcher-Client": "web"},
        )
        assert session.status_code == 200, session.text
        assert (await client.post(root + "/accept", json=body)).status_code == 403
        response = await client.get(root)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert (await client.get(root.replace("/101/", "/202/"))).status_code == 404
        path = root + f"/candidates/{body['candidate_id']}/reports/{report}"
        first = await client.get(path, params={"max_chars": 10})
        assert first.status_code == 200, first.text
        assert first.json()["next_offset"] == 10
        c.conn.execute(
            "UPDATE artifacts SET content='Changed after delivery' WHERE id=?",
            (report,),
        )
        c.conn.commit()
        frozen = await client.get(path)
        assert (
            frozen.json()["content"]
            == "# Sample report\n\nThe sample contains 137 units."
        )
        assert frozen.json()["candidate_sha256"] == body["candidate_sha256"]
        refused = await client.post(
            root + "/accept",
            json=body,
            headers={"X-Researcher-CSRF": session.json()["csrf_token"]},
        )
        assert refused.status_code == 409, refused.text


def test_managed_task_cannot_be_completed_by_legacy_sql(delivered_result):
    """Legacy helpers cannot skip the explicit owner action even if a model emits VALIDATED."""
    import sqlite3

    c, lease, _, _, _, _, state = delivered_result
    with pytest.raises(sqlite3.IntegrityError, match="owner acceptance"):
        c.conn.execute("UPDATE tasks SET status='done' WHERE id=1001")
    c.conn.rollback()
    assert accept(c, lease, state)["task_accepted"] is True


def test_changing_accepted_inputs_reopens_task_and_preserves_original_decision(
    delivered_result,
):
    """New task requirements cannot inherit completion from the previous accepted version."""
    c, lease, _, _, _, _, state = delivered_result
    receipt = accept(c, lease, state)
    c.conn.execute(
        "UPDATE tasks SET description='Also compare another source.' WHERE id=1001"
    )
    c.conn.commit()
    assert c.conn.execute(
        "SELECT status,completed_at FROM tasks WHERE id=1001"
    ).fetchone()[:] == ("pending", None)
    c.conn.execute("INSERT INTO tasks_fts(tasks_fts,rank) VALUES('integrity-check',1)")
    assert (
        c.conn.execute(
            "SELECT rowid FROM tasks_fts WHERE tasks_fts MATCH 'independent'"
        ).fetchall()
        == []
    )
    assert (
        c.conn.execute(
            "SELECT rowid FROM tasks_fts WHERE tasks_fts MATCH 'compare'"
        ).fetchone()[0]
        == 1001
    )
    c.conn.commit()
    current = c.store.result_state(101, lease.run_id)
    assert current["acceptance"] == receipt and current["acceptance_current"] is False
    assert accept(c, lease, state) == receipt
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "pending"
    )


def test_owner_correction_reopens_accepted_task_once_without_repeating_work(
    delivered_result,
):
    """A correction advances shared context and preserves the historic owner decision on retry."""
    c, lease, _, _, _, _, state = delivered_result
    receipt = accept(c, lease, state)
    command = {
        "project_id": 101,
        "task_id": 1001,
        "expected_version": 1,
        "operation_key": "owner-revision",
        "statement": "Compare an independent source before the next delivery.",
        "source_kind": "user_message",
        "source_reference": "owner-correction:owner-revision",
    }
    assert c.store.correct_context(**command) == 2
    assert c.store.correct_context(**command) == 2
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
        == "pending"
    )
    assert c.store.get(101, lease.run_id).status == "accepted"
    assert c.store.result_state(101, lease.run_id)["acceptance"] == receipt


@pytest.mark.parametrize("status", ["active", "superseded"])
def test_legacy_flags_cannot_promote_or_reject_managed_findings(active_result, status):
    """Structured review assertions must not be bypassed by old mutable validation flags."""
    import sqlite3

    c, _, _, fid, _, _ = active_result
    with pytest.raises(sqlite3.IntegrityError, match="versioned review"):
        c.conn.execute("UPDATE findings SET status=? WHERE id=?", (status, fid))
    c.conn.rollback()
    assert (
        c.conn.execute("SELECT status FROM findings WHERE id=?", (fid,)).fetchone()[0]
        == "provisional"
    )


