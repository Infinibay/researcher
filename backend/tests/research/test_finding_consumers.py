"""Retained finding consumers share native scope, unknown confidence and complete reads."""

import json

import pytest

from backend.tests.research.test_finding_registry import cited_finding, legacy_finding
from backend.tools.base.context import set_context
from backend.tools.knowledge.read_findings import ReadFindingsTool
from backend.tools.knowledge.search_findings import SearchFindingsTool
from backend.tools.knowledge.search_knowledge import SearchKnowledgeTool
from backend.tools.knowledge.summarize_findings import SummarizeFindingsTool


@pytest.fixture
def finding_context(research_store):
    """Bind only legacy reader scope; it does not create native reviewer authority."""
    set_context(project_id=101, task_id=1001, agent_id="legacy-reader")
    yield
    set_context(project_id=None, task_id=None, agent_id=None, agent_run_id=None)


def test_reader_keeps_unknown_confidence_and_labels_legacy_assertions(
    finding_context, research_store, research_scope, db_conn
):
    """A native NULL-confidence claim remains readable beside historical active declarations."""
    native, _ = cited_finding(research_store, research_scope)
    old = legacy_finding(db_conn, status="active", confidence=0.9)
    data = json.loads(ReadFindingsTool()._run())
    assert {row["id"] for row in data["findings"]} == {native, old}
    rows = {row["id"]: row for row in data["findings"]}
    assert rows[native]["scientific_confidence"] is None
    assert rows[native]["confidence_origin"] == "unknown"
    assert rows[old]["legacy_review_status"] == "unverified_legacy"
    filtered = json.loads(ReadFindingsTool()._run(min_confidence=0.8))
    assert [row["id"] for row in filtered["findings"]] == [old]


@pytest.mark.parametrize(
    "factory",
    [ReadFindingsTool, SummarizeFindingsTool, SearchFindingsTool, SearchKnowledgeTool],
)
def test_missing_project_cannot_widen_a_retained_reader(
    finding_context, db_conn, factory
):
    """A missing project returns an error instead of reading globally or by foreign task id."""
    legacy_finding(
        db_conn, project=202, task=2002, topic="FOREIGN SECRET", confidence=0.99
    )
    set_context(project_id=None, task_id=2002, agent_id="legacy-reader")
    kwargs = (
        {"query": "FOREIGN"}
        if factory in (SearchFindingsTool, SearchKnowledgeTool)
        else {}
    )
    data = json.loads(factory()._run(**kwargs))
    assert "error" in data and "FOREIGN SECRET" not in json.dumps(data)


def test_summary_task_filter_never_replaces_project_scope(finding_context, db_conn):
    """An explicit foreign task cannot disclose that task's topics or counts."""
    legacy_finding(
        db_conn, project=202, task=2002, topic="FOREIGN SECRET", confidence=0.99
    )
    data = json.loads(SummarizeFindingsTool()._run(task_id=2002))
    assert data["total_count"] == 0
    assert "FOREIGN SECRET" not in json.dumps(data)
    assert data["project_id"] == 101


def test_reader_pages_metadata_then_full_text_and_rejects_foreign_id(
    finding_context, db_conn
):
    """Large claim tails remain recoverable and page cursors do not duplicate records."""
    body = (
        "Documented observation. " * 900 + "Late limitation: measurement not repeated."
    )
    own = legacy_finding(db_conn, content=body, topic="Long record")
    other = legacy_finding(db_conn, topic="Second record")
    foreign = legacy_finding(db_conn, project=202, task=2002, topic="FOREIGN SECRET")
    tool = ReadFindingsTool()
    first = json.loads(tool._run(limit=1))
    assert [item["id"] for item in first["findings"]] == [own]
    assert first["next_after_id"] == own and first["total_matching"] == 2
    second = json.loads(tool._run(limit=1, after_id=first["next_after_id"]))
    assert [item["id"] for item in second["findings"]] == [other]
    part = json.loads(tool._run(finding_id=own, max_chars=12000))
    assert part["finding"]["next_offset"] == 12000
    tail = json.loads(tool._run(finding_id=own, offset=12000, max_chars=12000))
    assert "measurement not repeated" in tail["finding"]["content"]
    assert "error" in json.loads(tool._run(finding_id=foreign))


def test_unified_search_keeps_native_unknowns_and_reports_coverage(
    finding_context, research_store, research_scope
):
    """Cross-source lookup must not drop native claims or hide requested-source failures."""
    fid, _ = cited_finding(
        research_store, research_scope, body="UniqueFractionEvidence"
    )
    data = json.loads(
        SearchKnowledgeTool()._run(query="UniqueFractionEvidence", sources=["findings"])
    )
    assert [item["id"] for item in data["results"]] == [fid]
    assert data["results"][0]["scientific_confidence"] is None
    assert data["coverage"]["findings"]["status"] == "searched"


def test_semantic_unprepared_fails_without_old_blob_or_download_fallback(
    finding_context, db_conn, monkeypatch
):
    """An unavailable pinned local model is not an empty search or an implicit Chroma setup."""
    fid = legacy_finding(db_conn, content="The sample contains a limited observation.")
    db_conn.execute(
        "UPDATE findings SET embedding=? WHERE id=?",
        (b"unversioned foreign dimensions", fid),
    )
    db_conn.commit()
    from backend.config.settings import settings

    monkeypatch.setattr(settings, "RETRIEVAL_ASSET_DIR", None)
    data = json.loads(SearchFindingsTool()._run(query="sample limitation", threshold=0))
    assert "error" in data
    assert "prepared" in data["error"] or "configured" in data["error"]


def test_native_and_retained_semantic_instances_share_one_process_slot(tmp_path):
    """Constructing another adapter must not bypass the existing local-worker capacity limit."""
    import hashlib

    from backend.research.retrieval_assets import RetrievalBusy
    from backend.research.semantic import SemanticRetriever

    native = SemanticRetriever(tmp_path)
    retained = SemanticRetriever(tmp_path)
    assert native._capacity.acquire(blocking=False)
    try:
        text = "The sample contains 137 units."
        source = {
            "id": 1,
            "content": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        with pytest.raises(RetrievalBusy):
            retained.query(source, "sample count")
    finally:
        native._capacity.release()


def test_partial_source_failure_is_not_an_empty_success(finding_context, db_conn):
    """A missing attachment index stays visible while findings search still returns its scoped hit."""
    fid = legacy_finding(db_conn, content="UniqueCoverageEvidence")
    db_conn.execute("DROP TABLE reference_files_fts")
    db_conn.commit()
    data = json.loads(
        SearchKnowledgeTool()._run(
            query="UniqueCoverageEvidence", sources=["findings", "reference_files"]
        )
    )
    assert data["partial"] is True
    assert data["coverage"]["reference_files"]["status"] == "failed"
    assert data["coverage"]["reference_files"]["total_matching"] is None
    assert [item["id"] for item in data["results"]] == [fid]
    assert data["coverage"]["findings"]["status"] == "searched"


def test_retained_semantic_search_refuses_a_sampled_501st_candidate(
    finding_context, db_conn
):
    """An oversized complete set is rejected before worker startup instead of hiding older counterevidence."""
    db_conn.executemany(
        "INSERT INTO findings(project_id,task_id,topic,content,agent_id,status) VALUES(101,1001,?,'Complete corpus member','author','provisional')",
        [(f"Observation {i}",) for i in range(501)],
    )
    db_conn.commit()
    data = json.loads(
        SearchFindingsTool()._run(query="older counterevidence", threshold=0)
    )
    assert (
        "error" in data
        and "500" in data["error"]
        and "no partial search" in data["error"]
    )


def test_real_retained_semantic_worker_reads_late_text_and_ignores_old_vectors(
    finding_context, db_conn, monkeypatch
):
    """Prepared offline retrieval sees the full claim and does not trust unversioned stored dimensions."""
    import os
    from pathlib import Path

    from backend.config.settings import settings

    configured = os.environ.get("RESEARCHER_TEST_RETRIEVAL_ASSETS")
    if not configured or not Path(configured).is_dir():
        pytest.skip("Explicit pinned offline assets required")
    monkeypatch.setattr(settings, "RETRIEVAL_ASSET_DIR", configured)
    text = (
        "Geological layers contain sediment and minerals. " * 300
        + "Passwords are salted and hashed with scrypt. They are never stored as readable plaintext."
    )
    target = legacy_finding(db_conn, topic="System notes", content=text)
    legacy_finding(
        db_conn,
        topic="Music",
        content="The orchestra played a melody on violins and cellos.",
    )
    legacy_finding(
        db_conn, project=202, task=2002, content="FOREIGN SECRET passwords scrypt"
    )
    db_conn.execute(
        "UPDATE findings SET embedding=? WHERE id=?",
        (b"unversioned foreign dimensions", target),
    )
    db_conn.commit()
    before = db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0]
    data = json.loads(
        SearchFindingsTool()._run(
            query="How are stored credentials protected?",
            threshold=0,
            include_content=True,
            limit=20,
        )
    )
    assert "error" not in data, data
    assert (
        data["full_coverage"] and data["corpus_count"] == data["total_candidates"] == 2
    )
    matches = [item for item in data["matches"] if item["finding_id"] == target]
    assert any("scrypt" in item["excerpt"] for item in matches)
    assert matches[0]["next_offset"] == 12000
    assert all(item["scientific_confidence"] is None for item in matches)
    assert "FOREIGN SECRET" not in json.dumps(data)
    assert (
        db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == before
    )
    assert (
        db_conn.execute(
            "SELECT embedding FROM findings WHERE id=?", (target,)
        ).fetchone()[0]
        == b"unversioned foreign dimensions"
    )


@pytest.mark.parametrize("change", ["body", "status", "membership"])
def test_retained_semantic_results_reject_changed_corpus_before_disclosure(
    finding_context, db_conn, monkeypatch, change
):
    """A new claim version or metadata/set change during work cannot retain an old search receipt."""
    from backend.tools.knowledge import search_findings as adapter

    fid = legacy_finding(db_conn, content="Initial observation")

    class ChangingRetriever:
        """Model only an intervening commit; actual local ranking is covered separately."""

        def __init__(self, *args, **kwargs):
            """Accept the actual composition signature without creating a worker."""

        def query(self, corpus, query, **kwargs):
            """Change one selected dependency while the consumer is outside its SQL snapshot."""
            if change == "body":
                db_conn.execute(
                    "UPDATE findings SET content='Changed observation' WHERE id=?",
                    (fid,),
                )
            elif change == "status":
                db_conn.execute(
                    "UPDATE findings SET status='superseded' WHERE id=?", (fid,)
                )
            else:
                legacy_finding(db_conn, content="Another observation")
            db_conn.commit()
            return {
                "matches": [],
                "full_coverage": True,
                "search_kind": "controlled",
                "next_rank": None,
            }

    monkeypatch.setattr(adapter, "SemanticRetriever", ChangingRetriever)
    data = json.loads(SearchFindingsTool()._run(query="observation", threshold=0))
    assert "error" in data and "corpus changed" in data["error"].lower()
