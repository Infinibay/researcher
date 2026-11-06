"""Scientific domain outcomes reuse native evidence and explicit owner control; storage peer witnesses are synthetic, not physical process proof."""

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from backend.research.models import (
    RESEARCH_PERMISSIONS,
    EvidenceReference,
    FindingDraft,
    ReportDraft,
    ResultDraft,
)
from backend.runtime.peer_registry import AttemptPeers


def scientific_state(coordination):
    """Bind one current native researcher and original tool scope without invoking a model."""
    c = coordination
    run = c.store.admit(c.spec)
    lease, peers = AttemptPeers.claim(c.store, 101, run.run_id, "scientific-fixture")
    c.store.bind_native(lease, thread_id="scientific-author", turn_id="scientific-turn")
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id=lease.actor_id,
        permissions=set(RESEARCH_PERMISSIONS),
    )
    scope = c.research.authorize(token)
    c.store.bind_grant(lease, scope.grant_id)
    return c, run, lease, peers, scope


def command_receipt(
    c,
    run,
    lease,
    peers,
    *,
    status="exited",
    stdout=b"200\n",
    exit_code=0,
    limited=False,
    closed=True,
):
    """Insert an explicitly synthetic command receipt linked to an actual registered fixture peer."""
    peer = peers.registry.prepare(lease, "command")
    job = str(uuid4())
    # Synthetic storage-only binding. Never pass this identity to a process API.
    c.conn.execute(
        "UPDATE runtime_peers SET state='bound',init_pid=0,start_ticks=0,init_namespace=0,bound_at=1000 WHERE id=?",
        (peer,),
    )
    c.conn.execute(
        """INSERT INTO runtime_jobs(id,run_id,attempt_id,executor_id,operation_key,request_hash,argv_json,cwd,workspace,timeout_seconds,output_bytes,status,exit_code,stdout,stderr,output_limited,error,created_at,ended_at,peer_id)
    VALUES(?,?,?,?,?,?,?,?,?,5,65536,?,?,?,X'',?,?,1000,1000,?)""",
        (
            job,
            run.run_id,
            lease.attempt_id,
            "synthetic-executor",
            job,
            "a" * 64,
            json.dumps(["python", "-c", "print(137+63)"]),
            ".",
            "/synthetic-readonly",
            status,
            exit_code,
            stdout,
            int(limited),
            None if exit_code is not None else "Missing terminal receipt",
            peer,
        ),
    )
    c.conn.commit()
    if closed:
        c.conn.execute(
            "UPDATE runtime_peers SET state='closed',reason='synthetic_storage_fixture',closed_at=1000 WHERE id=?",
            (peer,),
        )
        c.conn.commit()
    return job


def test_captured_command_is_real_citable_source_with_original_receipt_and_no_scientific_certainty(
    coordination,
):
    """A retained job's exact stdout becomes cited experimental evidence, not a model-supplied transcript or confidence score."""
    from backend.tests.runtime.test_result_acceptance import accept

    c, run, lease, peers, scope = scientific_state(coordination)
    job = command_receipt(c, run, lease, peers)
    receipt = c.research.capture_command(scope, "capture-calculation", job)
    assert c.research.capture_command(scope, "capture-calculation", job) == receipt
    source = c.research.read_source(scope, receipt["source_id"])
    assert "200\n" in source["content"]
    assert source["provenance"]["origin"] == "retained_command_receipt"
    assert source["provenance"]["job"]["attempt_id"] == lease.attempt_id
    assert source["provenance"]["job"]["job_id"] == job
    assert source["provenance"]["job"]["local_execution_closed"] is True
    refs = (EvidenceReference(receipt["source_id"], "200"),)
    ids = []
    for kind, claim in [
        ("hypothesis", "Adding 63 to the recorded input predicts 200."),
        (
            "experiment",
            "The retained calculation output is 200; the original measurement was not repeated.",
        ),
        (
            "conclusion",
            "This calculation supports the arithmetic claim, not a population causal effect.",
        ),
    ]:
        ids.append(
            c.research.record_finding(
                scope, kind, FindingDraft(kind, claim, refs, kind)
            )["finding_id"]
        )
    report = c.research.write_report(
        scope,
        "research-report",
        ReportDraft(
            "Arithmetic and measurement limits",
            "Question: which interpretation is supported?\nMethod: retained calculation print(137+63).\nAlternative: treating the original137as200 is not supported.\nSearch scope: supplied fixture only.\nConclusion: arithmetic, no independent empirical replication.\nLimit: sampling unit and measurement protocol unknown.",
            tuple(ids),
        ),
    )
    c.research.propose_result(
        scope,
        "deliver",
        ResultDraft(
            (report["artifact_id"],),
            "A traceable arithmetic check.",
            ("No empirical replication or calibrated certainty.",),
        ),
    )
    for peer in peers.ids.values():
        peers.registry.close(peer)
    c.store.finish(
        lease, native_status="completed", summary="Research candidate ready."
    )
    state = c.store.result_state(101, run.run_id)
    assert state["eligible"]
    snapshot = json.loads(
        c.conn.execute(
            "SELECT snapshot_json FROM runtime_result_proposals WHERE run_id=?",
            (run.run_id,),
        ).fetchone()[0]
    )
    assert snapshot["scientific_confidence"] is None
    assert c.conn.execute("SELECT count(*)FROM research_sources").fetchone()[0] == 1
    accept(c, lease, state)
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] == "done"
    )


@pytest.mark.parametrize("fault", ["active", "unknown", "live_peer", "binary"])
def test_command_capture_refuses_incomplete_or_lossy_evidence(coordination, fault):
    """A terminal-looking row is insufficient while its peer remains open, output is binary, or dispatch outcome is unknown."""
    from backend.research.models import ResearchInputError

    c, run, lease, peers, scope = scientific_state(coordination)
    job = command_receipt(
        c,
        run,
        lease,
        peers,
        status="dispatching"
        if fault == "active"
        else "unknown"
        if fault == "unknown"
        else "exited",
        exit_code=None if fault in ("active", "unknown") else 0,
        closed=fault != "live_peer",
        stdout=b"\xff" if fault == "binary" else b"200\n",
    )
    with pytest.raises(ResearchInputError):
        c.research.capture_command(scope, "capture", job)
    assert c.conn.execute("SELECT count(*)FROM research_sources").fetchone()[0] == 0


def test_command_capture_exposes_failed_exit_and_output_limit_instead_of_inventing_success(
    coordination,
):
    """A closed failing/truncated experiment can be retained as limited evidence, with all failure flags visible."""
    c, run, lease, peers, scope = scientific_state(coordination)
    job = command_receipt(c, run, lease, peers, exit_code=2, limited=True)
    source = c.research.capture_command(scope, "failed-experiment", job)
    recorded = c.research.read_source(scope, source["source_id"])
    meta = recorded["provenance"]["job"]
    assert meta["exit_code"] == 2 and meta["output_limited"] is True
    assert '"output_limited": true' in recorded["content"]
    assert '"exit_code": 2' in recorded["content"]




def test_command_capture_rejects_foreign_attempt_and_unbound_grant(coordination):
    """A current author cannot borrow another task's actual job, and an unbound broad grant cannot substitute for an admitted author."""
    from backend.research.models import ResearchForbidden

    c, _run, _lease, _peers, scope = scientific_state(coordination)
    other = c.store.admit(replace(c.spec, task_id=1002, operation_key="other-task"))
    other_lease, other_peers = AttemptPeers.claim(
        c.store, 101, other.run_id, "other-fixture"
    )
    job = command_receipt(c, other, other_lease, other_peers)
    with pytest.raises(ResearchForbidden, match="attempt"):
        c.research.capture_command(scope, "foreign", job)
    token = c.research.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="unbound",
        permissions=set(RESEARCH_PERMISSIONS),
    )
    with pytest.raises(ResearchForbidden):
        c.research.capture_command(c.research.authorize(token), "unbound", job)
    assert c.conn.execute("SELECT count(*)FROM research_sources").fetchone()[0] == 0


def test_command_capture_key_cannot_select_another_original_job(coordination):
    """A lost capture reply can recover only its original job/source, never a new experiment under the same key."""
    from backend.research.models import OperationConflict

    c, run, lease, peers, scope = scientific_state(coordination)
    first = command_receipt(c, run, lease, peers)
    second = command_receipt(c, run, lease, peers, stdout=b"999\n")
    original = c.research.capture_command(scope, "original-experiment", first)
    with pytest.raises(OperationConflict):
        c.research.capture_command(scope, "original-experiment", second)
    assert c.research.capture_command(scope, "original-experiment", first) == original
    assert c.conn.execute("SELECT count(*)FROM research_sources").fetchone()[0] == 1


@pytest.mark.parametrize(
    "handler,event_type",
    [
        ("TaskFlowHandler", "task_available"),
        ("TaskFlowHandler", "task_resume"),
        ("ReviewHandler", "review_ready"),
        ("ReworkHandler", "task_rejected"),
    ],
)
def test_queued_scientific_events_do_not_start_old_claim_review_or_rework(
    coordination, handler, event_type
):
    """Old hints cannot select a scientific worker, use a review label as authority or complete best-effort work."""
    from backend.autonomy import handlers

    c = coordination
    c.conn.execute(
        "UPDATE tasks SET status='pending',assigned_to=NULL,reviewer=NULL WHERE id=1001"
    )
    c.conn.commit()
    result = getattr(handlers, handler)().execute(
        {
            "id": 701,
            "project_id": 101,
            "agent_id": "old-scientist",
            "event_type": event_type,
            "payload_json": json.dumps({"task_id": 1001}),
        }
    )
    assert (
        result["delivery"] == "native_owner_handoff"
        and not result["inference_started_by_handoff"]
    )
    assert c.conn.execute(
        "SELECT status,assigned_to,reviewer,retry_count FROM tasks WHERE id=1001"
    ).fetchone()[:] == ("pending", None, None, 0)
    assert c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 0


def test_pre_admission_scientific_claim_and_completion_are_owner_guarded(coordination):
    """Historical research remains readable, while a new raw legacy claim/completion requires native admission/acceptance."""
    import sqlite3

    c = coordination
    c.conn.execute("UPDATE tasks SET status='pending',assigned_to=NULL WHERE id=1001")
    c.conn.commit()
    for status in ("in_progress", "done"):
        with pytest.raises(sqlite3.IntegrityError, match="native|owner|accept"):
            c.conn.execute("UPDATE tasks SET status=? WHERE id=1001", (status,))
        c.conn.rollback()


def test_scientific_owner_guard_upgrade_is_atomic_and_keeps_historical_reports(
    request, monkeypatch
):
    """A failed schema53 install leaves schema52 data/guards intact; a repeatable retry preserves historical scientific completion without inventing acceptance."""
    import sqlite3

    from backend.db import migrations
    from backend.tools.base.db import ensure_migrations

    apply = migrations.apply_sql_resource

    def skip_scientific(conn, path):
        """Prepare exactly the prior schema, without editing historical migration SQL."""
        if path.name not in ("scientific_schema.sql", "native_task_cutover_schema.sql", "model_settings_schema.sql"):
            apply(conn, path)

    monkeypatch.setattr(migrations, "apply_sql_resource", skip_scientific)
    c = request.getfixturevalue("coordination")
    assert (
        c.conn.execute("SELECT max(version)FROM schema_migrations").fetchone()[0] == 52
    )
    c.conn.execute("UPDATE tasks SET status='done' WHERE id=1001")
    artifact = c.conn.execute(
        "INSERT INTO artifacts(project_id,task_id,type,file_path,content)VALUES(101,1001,'report','historical-science.md','Original scientific report.')RETURNING id"
    ).fetchone()[0]
    c.conn.execute(
        "CREATE TRIGGER reject53 BEFORE INSERT ON schema_migrations WHEN new.version=53 BEGIN SELECT RAISE(ABORT,'injected scientific migration failure');END"
    )
    c.conn.commit()
    monkeypatch.setattr(migrations, "apply_sql_resource", apply)
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        ensure_migrations(c.database)
    assert (
        c.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='research_done_requires_owner_acceptance'"
        ).fetchone()
        is None
    )
    assert (
        c.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='investigation_done_requires_owner_acceptance'"
        ).fetchone()
        is not None
    )
    c.conn.execute("DROP TRIGGER reject53")
    c.conn.commit()
    ensure_migrations(c.database)
    ensure_migrations(c.database)
    assert (
        c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0] == "done"
    )
    assert (
        c.conn.execute(
            "SELECT content FROM artifacts WHERE id=?", (artifact,)
        ).fetchone()[0]
        == "Original scientific report."
    )
    assert (
        c.conn.execute("SELECT count(*)FROM runtime_result_acceptances").fetchone()[0]
        == 0
    )
    assert (
        c.conn.execute(
            "SELECT count(*)FROM schema_migrations WHERE version=53"
        ).fetchone()[0]
        == 1
    )
    assert c.conn.execute("PRAGMA foreign_key_check").fetchall() == []
