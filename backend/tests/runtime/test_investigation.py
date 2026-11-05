"""Exploratory scope/area summaries reuse actual native report/result evidence; peer witnesses in storage tests are synthetic."""

import json
from dataclasses import replace

import pytest

from backend.research.models import (
    RESEARCH_PERMISSIONS,
    EvidenceReference,
    FindingDraft,
    ReportDraft,
    ResultDraft,
    SourceDraft,
)
from backend.runtime.peer_registry import AttemptPeers


def investigation_state(coordination):
    """Create one actual bound author and captured evidence under an explicitly admitted exploratory task."""
    c = coordination
    c.conn.execute(
        "UPDATE tasks SET type='investigation',status='pending' WHERE id=1001"
    )
    c.conn.commit()
    run = c.store.admit(
        replace(
            c.spec,
            context_version=c.store.context_snapshot(101, 1001)["context_version"],
            prompt="Explore what the recorded sample count establishes.",
        )
    )
    lease, peers = AttemptPeers.claim(
        c.store, 101, run.run_id, "fixture-investigation-owner"
    )
    c.store.bind_native(
        lease, thread_id="exploratory-author", turn_id="exploratory-turn"
    )
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    source = c.research.capture_source(
        scope,
        "observed-source",
        SourceDraft(
            "attachment", "fixture:sample", "Sample", "The sample contains 137 units."
        ),
        intent={},
    )["source_id"]
    finding = c.research.record_finding(
        scope,
        "observed-finding",
        FindingDraft(
            "Count",
            "The source reports 137 units.",
            (EvidenceReference(source, "137 units"),),
        ),
    )["finding_id"]
    return c, run, lease, peers, scope, finding


def summary_packet(finding):
    """Describe one supported documentary observation and an unresolved area without fabricating another finding."""
    return {
        "title": "Exploratory count review",
        "question": "What count is recorded, and what remains unknown?",
        "scope_includes": ["Read the supplied count."],
        "scope_excludes": ["Repeat the measurement."],
        "areas": [
            {
                "title": "Recorded count",
                "observations": "The supplied source reports 137 units.",
                "finding_ids": [finding],
            },
            {
                "title": "Measurement method",
                "observations": "No measurement protocol was supplied.",
                "finding_ids": [],
            },
        ],
        "conclusion": "The document records 137 units; its measurement was not repeated.",
        "limitations": ["Documentary inspection only."],
        "next_steps": ["Obtain the measurement protocol if needed."],
    }


def test_typed_investigation_summary_is_idempotent_deliverable_and_owner_accepted(
    coordination,
):
    """One structured summary preserves scope, grouped evidence and unknowns in report/result snapshots; only the existing owner decision completes the task."""
    from backend.research.investigation import InvestigationSummary
    from backend.tests.runtime.test_result_acceptance import accept

    c, run, lease, peers, scope, finding = investigation_state(coordination)
    draft = InvestigationSummary.model_validate(summary_packet(finding))
    receipt = c.research.write_investigation_summary(
        scope, "exploration-summary", draft
    )
    assert (
        c.research.write_investigation_summary(scope, "exploration-summary", draft)
        == receipt
    )
    report = c.research.read_report(scope, receipt["artifact_id"])
    assert report["report_type"] == "summary" and "137 units" in report["content"]
    assert (
        c.conn.execute(
            "SELECT count(*)FROM research_investigation_summaries"
        ).fetchone()[0]
        == 1
    )
    c.research.propose_result(
        scope,
        "deliver-exploration",
        ResultDraft(
            (receipt["artifact_id"],),
            "Recorded count with an explicit unknown method.",
            ("Documentary inspection only.",),
        ),
    )
    for peer in peers.ids.values():
        peers.registry.close(peer)
    c.store.finish(
        lease,
        native_status="completed",
        summary="A scoped summary is ready for inspection.",
    )
    state = c.store.result_state(101, run.run_id)
    assert state["eligible"], state
    snapshot = json.loads(
        c.conn.execute(
            "SELECT snapshot_json FROM runtime_result_proposals WHERE run_id=?",
            (run.run_id,),
        ).fetchone()[0]
    )
    selected = snapshot["reports"][0]
    assert selected["investigation"]["question"] == draft.question
    assert selected["investigation"]["areas"][1]["finding_ids"] == []
    assert snapshot["scientific_confidence"] is None
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] != "done"
    )
    accepted = accept(c, lease, state)
    assert accepted["run_id"] == run.run_id
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] == "done"
    )


def test_generic_report_cannot_bypass_exploratory_summary_contract(coordination):
    """An investigation cannot masquerade as a typed scoped result by selecting an ordinary free-text report."""
    from backend.research.models import ResearchInputError

    c, _run, _lease, _peers, scope, finding = investigation_state(coordination)
    report = c.research.write_report(
        scope,
        "scratch-summary",
        ReportDraft("Scratch", "The source reports 137 units.", (finding,), "summary"),
    )
    with pytest.raises(ResearchInputError, match="investigation|exploratory|typed"):
        c.research.propose_result(
            scope,
            "bypass-summary",
            ResultDraft(
                (report["artifact_id"],), "A free-text summary.", ("Only documentary.",)
            ),
        )


def test_legacy_investigation_entry_and_event_handoff_do_not_claim_or_start_work(
    coordination,
):
    """The actual old flow/event entry now exposes owner admission, retaining historical reports and leaving task/result state unchanged."""
    from backend.autonomy.handlers.task_handlers import TaskFlowHandler
    from backend.flows.investigation_flow import InvestigationFlow

    c = coordination
    c.conn.execute(
        "UPDATE tasks SET type='investigation',status='pending',assigned_to=NULL WHERE id=1001"
    )
    c.conn.execute(
        "INSERT INTO artifacts(project_id,task_id,type,file_path,description,content)VALUES(101,1001,'report','old.md','Prior report','Historical observations remain.')"
    )
    c.conn.commit()
    result = InvestigationFlow().kickoff(
        inputs={"project_id": 101, "task_id": 1001, "researcher_id": "legacy-label"}
    )
    assert result["delivery"] == "native_owner_handoff"
    assert result["inference_started_by_handoff"] is False
    assert result["native_runs"] == []
    returned = TaskFlowHandler().execute(
        {
            "id": 55,
            "project_id": 101,
            "agent_id": "legacy-label",
            "event_type": "task_available",
            "payload_json": json.dumps({"task_id": 1001}),
        }
    )
    assert returned["delivery"] == "native_owner_handoff"
    assert c.conn.execute(
        "SELECT status,assigned_to FROM tasks WHERE id=1001"
    ).fetchone()[:] == ("pending", None)
    assert c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 0
    assert (
        c.conn.execute("SELECT content FROM artifacts WHERE task_id=1001").fetchone()[0]
        == "Historical observations remain."
    )
    with pytest.raises(ValueError, match="project|scope|found"):
        TaskFlowHandler().execute(
            {
                "id": 56,
                "project_id": 202,
                "agent_id": "other",
                "event_type": "task_resume",
                "payload_json": json.dumps({"task_id": 1001}),
            }
        )


def test_legacy_take_task_and_direct_completion_cannot_bypass_owner_investigation(
    coordination,
):
    """Current legacy tools and raw legacy completion/claim statements cannot turn an unadmitted investigation into running or accepted work."""
    import sqlite3

    from backend.tools.base.context import set_context
    from backend.tools.task.take_task import TakeTaskTool

    c = coordination
    c.conn.execute(
        "UPDATE tasks SET type='investigation',status='pending',assigned_to=NULL WHERE id=1001"
    )
    c.conn.commit()
    set_context(project_id=101, agent_id="legacy-test", task_id=1001)
    try:
        result = json.loads(TakeTaskTool()._run(task_id=1001))
        assert result["delivery"] == "native_owner_handoff"
        assert c.conn.execute(
            "SELECT status,assigned_to FROM tasks WHERE id=1001"
        ).fetchone()[:] == ("pending", None)
        for status in ("in_progress", "done"):
            with pytest.raises(sqlite3.IntegrityError, match="native|owner|accept"):
                c.conn.execute("UPDATE tasks SET status=? WHERE id=1001", (status,))
            c.conn.rollback()
    finally:
        set_context(project_id=None, agent_id=None, task_id=None)


@pytest.mark.parametrize("handler_name", ["ReviewHandler", "ReworkHandler"])
def test_legacy_review_and_rework_are_hints_not_authorization(
    coordination, handler_name
):
    """Queued review/rejection messages cannot claim an investigator or create an automatic native review."""
    from backend.autonomy import handlers

    c = coordination
    c.conn.execute(
        "UPDATE tasks SET type='investigation',status='review_ready',assigned_to=NULL,reviewer=NULL WHERE id=1001"
    )
    c.conn.commit()
    result = getattr(handlers, handler_name)().execute(
        {
            "id": 57,
            "project_id": 101,
            "agent_id": "old-reviewer",
            "event_type": "review_ready"
            if handler_name == "ReviewHandler"
            else "task_rejected",
            "payload_json": json.dumps({"task_id": 1001}),
        }
    )
    assert result["delivery"] == "native_owner_handoff"
    assert c.conn.execute(
        "SELECT status,assigned_to,reviewer,retry_count FROM tasks WHERE id=1001"
    ).fetchone()[:] == ("review_ready", None, None, 0)
    assert c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 0


def test_legacy_scavenger_excludes_owner_only_and_native_owned_tasks(coordination):
    """A documentary handoff must not be rediscovered as missing legacy work indefinitely."""
    from backend.autonomy.scavenger import Scavenger

    investigation_state(coordination)
    coordination.conn.execute("UPDATE tasks SET type='code' WHERE id=1002")
    coordination.conn.commit()
    scavenger = Scavenger("legacy-researcher", 101, "researcher")
    rows = scavenger._find_orphan_tasks(
        "SELECT id FROM tasks WHERE project_id=? ORDER BY id", (101,)
    )
    assert [row["id"] for row in rows] == [1002]


def test_legacy_project_stops_dispatching_owner_only_work_without_evaluating_completion(
    coordination, monkeypatch
):
    """Only-native pending work returns a distinct handoff route; it must not re-enter legacy progress inference or call the project complete."""
    from backend.flows.main_project_flow import MainProjectFlow

    c = coordination
    c.conn.execute(
        "UPDATE tasks SET type='investigation',status='pending',assigned_to=NULL WHERE project_id=101"
    )
    c.conn.commit()
    flow = MainProjectFlow()
    flow.state.project_id = 101
    monkeypatch.setattr(
        "backend.flows.main_project_flow.threading.Thread",
        lambda *a, **kw: pytest.fail("No legacy worker may start"),
    )
    assert flow._launch_pending_tasks() == "native_owner_required"
    assert flow.state.running_task_ids == []
    assert c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 0


def test_investigation_summary_keeps_original_intent_and_rejects_foreign_evidence(
    coordination,
):
    """Retry changes, foreign evidence and metadata overwrites cannot manufacture a different original exploratory result."""
    import sqlite3

    from backend.research.investigation import InvestigationSummary
    from backend.research.models import OperationConflict, ResearchNotFound

    c, _run, _lease, _peers, scope, finding = investigation_state(coordination)
    draft = InvestigationSummary.model_validate(summary_packet(finding))
    receipt = c.research.write_investigation_summary(scope, "summary", draft)
    with pytest.raises(OperationConflict):
        c.research.write_investigation_summary(
            scope,
            "summary",
            draft.model_copy(update={"conclusion": "A different conclusion."}),
        )
    foreign = c.conn.execute(
        "INSERT INTO findings(project_id,task_id,topic,content,agent_id,status)VALUES(202,2002,'Other','Foreign assertion','other','provisional') RETURNING id"
    ).fetchone()[0]
    c.conn.commit()
    with pytest.raises(ResearchNotFound):
        c.research.write_investigation_summary(
            scope,
            "foreign-summary",
            InvestigationSummary.model_validate(summary_packet(foreign)),
        )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        c.conn.execute(
            "UPDATE research_investigation_summaries SET summary_json='{}' WHERE artifact_id=?",
            (receipt["artifact_id"],),
        )
    c.conn.rollback()
    assert (
        c.conn.execute(
            "SELECT count(*)FROM research_investigation_summaries"
        ).fetchone()[0]
        == 1
    )
    assert c.conn.execute("SELECT count(*)FROM research_reports").fetchone()[0] == 1


def test_investigation_finding_uses_independent_versioned_review(coordination):
    """The ordinary exact-subject review can inspect an exploratory summary without changing confidence, accepting the result or completing the task."""
    from backend.knowledge.reviews import finding_subject
    from backend.research.investigation import InvestigationSummary
    from backend.research.models import REVIEW_PERMISSIONS, ReviewTarget
    from backend.tests.runtime.test_finding_review import decision

    c, author, lease, peers, scope, finding = investigation_state(coordination)
    c.research.write_investigation_summary(
        scope, "summary", InvestigationSummary.model_validate(summary_packet(finding))
    )
    for peer in peers.ids.values():
        peers.registry.close(peer)
    c.store.finish(lease, native_status="completed", summary="Exploratory draft.")
    subject = finding_subject(c.conn, 101, finding)
    assert subject["reviewable"]
    review = c.store.admit(
        replace(
            c.spec,
            actor_id="independent-reviewer",
            context_version=author.context_version,
            operation_key="review",
            prompt="Check the exact documentary claim.",
        ),
        review=ReviewTarget(finding, subject["subject_sha256"]),
    )
    reviewer, review_peers = AttemptPeers.claim(
        c.store, 101, review.run_id, "synthetic-review-owner"
    )
    c.store.bind_native(reviewer, thread_id="independent-thread", turn_id="review-turn")
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=reviewer.actor_id,
        permissions=set(REVIEW_PERMISSIONS),
    )
    review_scope = c.research.authorize(token)
    c.store.bind_grant(reviewer, review_scope.grant_id)
    source = c.conn.execute(
        "SELECT source_id FROM finding_sources WHERE finding_id=?", (finding,)
    ).fetchone()[0]
    receipt = c.research.record_review(review_scope, "decision", decision(source))
    assert receipt["verdict"] == "supported"
    assert c.conn.execute(
        "SELECT status,confidence FROM findings WHERE id=?", (finding,)
    ).fetchone()[:] == ("provisional", None)
    assert (
        c.conn.execute("SELECT count(*)FROM runtime_result_acceptances").fetchone()[0]
        == 0
    )
    for peer in review_peers.ids.values():
        review_peers.registry.close(peer)
    c.store.finish(
        reviewer, native_status="completed", summary="Documentary review proposed."
    )
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] != "done"
    )


def test_exploratory_schema_upgrade_is_atomic_and_preserves_historical_task_and_report(
    request, monkeypatch
):
    """A failed schema52 install rolls back its table/guards; a repeatable successful upgrade preserves actual schema51 historical records."""
    import sqlite3

    from backend.db import migrations
    from backend.tools.base.db import ensure_migrations

    apply = migrations.apply_sql_resource

    def skip_investigation(conn, path):
        """Prepare exactly schema51 without changing any historical migration resource."""
        if path.name not in ("investigation_schema.sql", "scientific_schema.sql"):
            apply(conn, path)

    monkeypatch.setattr(migrations, "apply_sql_resource", skip_investigation)
    c = request.getfixturevalue("coordination")
    assert (
        c.conn.execute("SELECT max(version)FROM schema_migrations").fetchone()[0] == 51
    )
    c.conn.execute("UPDATE tasks SET type='investigation',status='done' WHERE id=1001")
    artifact = c.conn.execute(
        "INSERT INTO artifacts(project_id,task_id,type,file_path,content)VALUES(101,1001,'report','old-summary.md','Historical record.')RETURNING id"
    ).fetchone()[0]
    before = c.conn.execute(
        "SELECT id,type,status FROM tasks WHERE id=1001"
    ).fetchone()[:]
    c.conn.execute(
        "CREATE TRIGGER reject52 BEFORE INSERT ON schema_migrations WHEN new.version=52 BEGIN SELECT RAISE(ABORT,'injected exploration migration failure');END"
    )
    c.conn.commit()
    monkeypatch.setattr(migrations, "apply_sql_resource", apply)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        ensure_migrations(c.database)
    assert (
        c.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='research_investigation_summaries'"
        ).fetchone()
        is None
    )
    assert (
        c.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='investigation_done_requires_owner_acceptance'"
        ).fetchone()
        is None
    )
    c.conn.execute("DROP TRIGGER reject52")
    c.conn.commit()
    ensure_migrations(c.database)
    ensure_migrations(c.database)
    assert (
        c.conn.execute("SELECT id,type,status FROM tasks WHERE id=1001").fetchone()[:]
        == before
    )
    assert (
        c.conn.execute(
            "SELECT content FROM artifacts WHERE id=?", (artifact,)
        ).fetchone()[0]
        == "Historical record."
    )
    assert (
        c.conn.execute(
            "SELECT count(*)FROM schema_migrations WHERE version=52"
        ).fetchone()[0]
        == 1
    )
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []
