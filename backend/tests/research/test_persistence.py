"""Real SQLite behavior; task-scoped evidence and effects must remain truthful."""

from concurrent.futures import ThreadPoolExecutor

import pytest


def source_draft(text="Tax rates are fractions. Round once at the end."):
    from backend.research.models import SourceDraft

    return SourceDraft(
        kind="attachment",
        locator="reference:7",
        title="Policy",
        content=text,
        provenance={"byte_sha256": "fixture-bytes", "extraction": "utf8"},
    )


def capture(store, scope, key="source-1"):
    return store.capture_source(
        scope, key, source_draft(), intent={"reference_file_id": 7}
    )


def finding_draft(source_id, quote="Tax rates are fractions."):
    from backend.research.models import EvidenceReference, FindingDraft

    return FindingDraft(
        topic="Tax representation",
        content="The attached policy represents rates as fractions.",
        finding_type="observation",
        evidence=(EvidenceReference(source_id, quote),),
    )


def record(store, scope, key="finding-1"):
    source = capture(store, scope)
    return store.record_finding(scope, key, finding_draft(source["source_id"]))


def test_lost_response_retry_returns_the_original_receipt_without_duplicate_rows(
    research_store, research_scope, db_conn
):
    first = capture(research_store, research_scope)
    second = capture(research_store, research_scope)
    assert first == second
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 1
    finding = record(research_store, research_scope)
    assert record(research_store, research_scope) == finding
    assert (
        db_conn.execute(
            "SELECT COUNT(*) FROM findings WHERE project_id=101"
        ).fetchone()[0]
        == 1
    )


def test_same_key_with_a_different_intent_or_kind_is_a_conflict(
    research_store, research_scope, db_conn
):
    from backend.research.models import OperationConflict

    source = capture(research_store, research_scope)
    with pytest.raises(OperationConflict):
        research_store.capture_source(
            research_scope, "source-1", source_draft(), intent={"reference_file_id": 8}
        )
    with pytest.raises(OperationConflict):
        research_store.record_finding(
            research_scope, "source-1", finding_draft(source["source_id"])
        )
    assert db_conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


def test_concurrent_retries_have_one_effect_and_one_receipt(
    research_store, research_scope, db_conn
):
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(
            workers.map(lambda _: capture(research_store, research_scope), range(2))
        )
    assert results[0] == results[1]
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 1


def test_finding_quotes_must_match_the_source_and_failure_is_atomic(
    research_store, research_scope, db_conn
):
    from backend.research.models import InvalidEvidence

    source = capture(research_store, research_scope)
    with pytest.raises(InvalidEvidence):
        research_store.record_finding(
            research_scope,
            "finding-bad",
            finding_draft(source["source_id"], "Always round down."),
        )
    assert db_conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0
    assert (
        db_conn.execute(
            "SELECT COUNT(*) FROM tool_operations WHERE operation_key='finding-bad'"
        ).fetchone()[0]
        == 0
    )


def test_cross_project_sources_are_not_citable_or_readable(
    research_store, research_scope, db_conn
):
    from backend.research.models import ResearchNotFound

    source = capture(research_store, research_scope)
    other = research_store.authorize(
        research_store.issue_grant(
            project_id=202,
            task_id=2002,
            agent_id="researcher-b",
            permissions={"sources.read", "findings.write"},
        )
    )
    with pytest.raises(ResearchNotFound):
        research_store.read_source(other, source["source_id"])
    with pytest.raises(ResearchNotFound):
        research_store.record_finding(
            other, "foreign-citation", finding_draft(source["source_id"])
        )
    assert db_conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0


def test_revoked_grant_cannot_replay_a_receipt_or_create_another_effect(
    research_store, research_scope, db_conn
):
    from backend.research.models import ResearchForbidden

    capture(research_store, research_scope)
    research_store.revoke_grant(research_scope.grant_id)
    for key in ["source-1", "source-2"]:
        with pytest.raises(ResearchForbidden):
            capture(research_store, research_scope, key)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 1


def test_context_advanced_after_acquisition_invalidates_the_old_scope(
    research_store, research_scope, db_conn
):
    from backend.research.models import ResearchForbidden

    db_conn.execute("UPDATE task_contexts SET version=2 WHERE task_id=1001")
    db_conn.commit()
    with pytest.raises(ResearchForbidden):
        capture(research_store, research_scope)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0


def test_write_permission_is_checked_inside_the_store(research_store, db_conn):
    from backend.research.models import ResearchForbidden

    scope = research_store.authorize(
        research_store.issue_grant(
            project_id=101,
            task_id=1001,
            agent_id="reader",
            permissions={"sources.read"},
        )
    )
    with pytest.raises(ResearchForbidden):
        capture(research_store, scope)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0


def test_canonical_report_and_citations_survive_reopening_store(
    research_store, research_scope, _isolated_db, db_conn
):
    from backend.research.models import ReportDraft
    from backend.research.sqlite_store import SQLiteResearchStore

    finding = record(research_store, research_scope)
    draft = ReportDraft(
        title="Invoice policy",
        content="The rate is a fraction; see the cited policy.",
        finding_ids=(finding["finding_id"],),
    )
    first = research_store.write_report(research_scope, "final-report", draft)
    reopened = SQLiteResearchStore(_isolated_db)
    assert reopened.write_report(research_scope, "final-report", draft) == first
    report = reopened.read_report(research_scope, first["artifact_id"])
    assert (
        report["content"]
        == "# Invoice policy\n\nThe rate is a fraction; see the cited policy."
    )
    assert report["finding_ids"] == [finding["finding_id"]]
    assert report["status"] == "draft"
    assert report["evidence"][0]["quote"] == "Tax rates are fractions."
    artifact = db_conn.execute(
        "SELECT content,type FROM artifacts WHERE id=?", (first["artifact_id"],)
    ).fetchone()
    assert tuple(artifact) == (report["content"], "report")
    assert db_conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 1


def test_report_cannot_import_foreign_or_superseded_findings(
    research_store, research_scope, db_conn
):
    from backend.research.models import InvalidEvidence, ReportDraft, ResearchNotFound

    finding = record(research_store, research_scope)
    other = research_store.authorize(
        research_store.issue_grant(
            project_id=202, task_id=2002, agent_id="b", permissions={"reports.write"}
        )
    )
    with pytest.raises(ResearchNotFound):
        research_store.write_report(
            other,
            "foreign-report",
            ReportDraft(
                title="Report", content="Claim", finding_ids=(finding["finding_id"],)
            ),
        )
    db_conn.execute(
        "UPDATE findings SET status='superseded' WHERE id=?", (finding["finding_id"],)
    )
    db_conn.commit()
    with pytest.raises(InvalidEvidence):
        research_store.write_report(
            research_scope,
            "stale-report",
            ReportDraft(
                title="Report", content="Claim", finding_ids=(finding["finding_id"],)
            ),
        )
    assert db_conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_new_finding_is_provisional_and_does_not_invent_numeric_confidence(
    research_store, research_scope, db_conn
):
    result = record(research_store, research_scope)
    row = db_conn.execute(
        "SELECT status,confidence,agent_id FROM findings WHERE id=?",
        (result["finding_id"],),
    ).fetchone()
    assert tuple(row) == ("provisional", None, "researcher-a")


def test_actor_and_task_binding_cannot_be_forged_by_replacing_scope_fields(
    research_store, research_scope, db_conn
):
    from dataclasses import replace

    from backend.research.models import ResearchForbidden

    forged = replace(research_scope, project_id=202, task_id=2002, agent_id="b")
    with pytest.raises(ResearchForbidden):
        capture(research_store, forged)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0


def test_expired_scope_cannot_commit_an_effect(research_store, db_conn):
    from backend.research.models import ResearchForbidden

    now = [100.0]
    research_store.clock = lambda: now[0]
    token = research_store.issue_grant(
        project_id=101,
        task_id=1001,
        agent_id="expiring",
        permissions={"sources.capture"},
        ttl_seconds=1,
    )
    scope = research_store.authorize(token)
    now[0] = 102.0
    with pytest.raises(ResearchForbidden):
        capture(research_store, scope)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0


def test_receipt_failure_rolls_back_the_effect_in_the_same_transaction(
    research_store, research_scope, db_conn
):
    import sqlite3

    db_conn.execute(
        "CREATE TRIGGER refuse_receipt BEFORE INSERT ON tool_operations BEGIN SELECT RAISE(ABORT,'receipt failure'); END;"
    )
    db_conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="receipt failure"):
        capture(research_store, research_scope)
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0
    assert db_conn.execute("SELECT COUNT(*) FROM tool_operations").fetchone()[0] == 0
