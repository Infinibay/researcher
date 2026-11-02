"""Findings retain scoped evidence and honest historical assessment metadata."""

import hashlib
import json

from backend.research.models import EvidenceReference, FindingDraft, SourceDraft
from backend.tests.research.test_http import credentials, research_client

__all__ = ["research_client"]


def legacy_finding(
    db,
    *,
    project=101,
    task=1001,
    status="provisional",
    confidence=None,
    content="Tax rates are fractions.",
    topic="Tax policy",
    finding_type="observation",
):
    """Keep historical numeric/flag values without pretending they certify scientific validity."""
    cursor = db.execute(
        "INSERT INTO findings(project_id,task_id,topic,content,agent_id,status,confidence,finding_type) VALUES(?,?,?,?,?,?,?,?)",
        (
            project,
            task,
            topic,
            content,
            "legacy-author",
            status,
            confidence,
            finding_type,
        ),
    )
    db.commit()
    return cursor.lastrowid


def cited_finding(store, scope, *, body="The convention uses fractions."):
    """Create real saved-source relationships through the existing native writer."""
    source = store.capture_source(
        scope,
        "source",
        SourceDraft(
            "web", "https://example.org/policy", "Policy", "Tax rates are fractions."
        ),
        intent={"url": "https://example.org/policy"},
    )["source_id"]
    finding = store.record_finding(
        scope,
        "finding",
        FindingDraft(
            "Convention", body, (EvidenceReference(source, "Tax rates are fractions."),)
        ),
    )["finding_id"]
    return finding, source


def test_owner_finding_detail_requires_explicit_project_and_rejects_a_foreign_id(
    research_client, research_store, db_conn
):
    """An owner-visible project is never inferred from a globally unique finding id."""
    own = legacy_finding(db_conn)
    foreign = legacy_finding(db_conn, project=202, task=2002, topic="FOREIGN SECRET")
    assert research_client.get(f"/api/findings/{own}").status_code == 422
    assert (
        research_client.get(f"/api/findings/{foreign}?project_id=101").status_code
        == 404
    )
    response = research_client.get(f"/api/findings/{own}?project_id=101")
    assert response.status_code == 200, response.text
    assert response.json()["project_id"] == 101


def test_owner_lexical_query_combines_filters_and_keeps_unknown_confidence_without_a_filter(
    research_client, research_store, db_conn
):
    """Typing a search cannot drop the selected type/status or invent zero for unknown values."""
    chosen = legacy_finding(db_conn, status="provisional")
    legacy_finding(db_conn, status="active", confidence=0.9)
    legacy_finding(db_conn, finding_type="hypothesis")
    response = research_client.get(
        "/api/findings",
        params={
            "project_id": 101,
            "q": "fractions",
            "status": "provisional",
            "finding_type": "observation",
        },
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [chosen]
    assert response.json()[0]["confidence"] is None


def test_registry_cursor_and_summary_use_the_same_explicit_project_filters(
    research_store, research_scope, db_conn
):
    """Metadata pages and aggregate counts cover full matching rows rather than one sample."""
    ids = [legacy_finding(db_conn, confidence=value) for value in [None, 0.2, 0.8]]
    legacy_finding(db_conn, project=202, task=2002)
    first = research_store.list_findings(research_scope, limit=2)
    assert [row["id"] for row in first["items"]] == ids[:2]
    assert first["next_after_id"] == ids[1] and first["total_matching"] == 3
    assert all(
        "content" not in row and "embedding" not in row for row in first["items"]
    )
    second = research_store.list_findings(
        research_scope, after_id=first["next_after_id"], limit=2
    )
    assert [row["id"] for row in second["items"]] == ids[2:]
    assert second["next_after_id"] is None
    summary = research_store.summarize_findings(research_scope)
    assert summary["total_count"] == 3
    assert summary["declared_confidence"]["unknown_count"] == 1
    assert summary["declared_confidence"]["known_count"] == 2
    assert summary["scientific_confidence"] is None


def test_finding_reader_pages_long_text_and_labels_legacy_flags_without_accrediting_review(
    research_client, research_store, db_conn
):
    """A stored active flag/method/number is preserved with its actual evidential limits."""
    text = "long text " * 3000 + "Late counterevidence."
    finding = legacy_finding(db_conn, content=text, status="active", confidence=0.91)
    db_conn.execute(
        "UPDATE findings SET validation_method='Agent said validated', reproducibility_score=.8 WHERE id=?",
        (finding,),
    )
    db_conn.commit()
    response = research_client.get(
        f"/api/findings/{finding}", params={"project_id": 101, "max_chars": 9000}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["content"] == text[:9000] and data["next_offset"] == 9000
    assert data["confidence"] == 0.91 and data["scientific_confidence"] is None
    assert data["review_status"] == "unverified_legacy"
    assert data["validation_method"] == "Agent said validated"
    tail = research_client.get(
        f"/api/findings/{finding}",
        params={"project_id": 101, "offset": len(text) - 21, "max_chars": 100},
    ).json()
    assert tail["content"] == text[-21:] and tail["next_offset"] is None


def test_owner_can_inspect_only_a_source_actually_cited_by_the_scoped_finding(
    research_client, research_store, research_scope
):
    """The owner reads the saved snapshot, not arbitrary URLs, paths or another source id."""
    finding, source = cited_finding(research_store, research_scope)
    response = research_client.get(
        f"/api/findings/{finding}/evidence", params={"project_id": 101}
    )
    assert response.status_code == 200, response.text
    quote = response.json()["evidence"][0]
    assert quote["quote"] == "Tax rates are fractions." and quote["quote_is_exact"]
    assert quote["quote_offset"] == 0
    response = research_client.get(
        f"/api/findings/{finding}/sources/{source}",
        params={"project_id": 101, "offset": 4, "max_chars": 5},
    )
    assert response.status_code == 200, response.text
    assert response.json()["content"] == "rates"
    assert (
        response.json()["sha256"]
        == hashlib.sha256(b"Tax rates are fractions.").hexdigest()
    )
    other = research_store.capture_source(
        research_scope,
        "uncited",
        SourceDraft("web", "https://example.org/other", "Other", "Other text"),
        intent={},
    )["source_id"]
    assert (
        research_client.get(
            f"/api/findings/{finding}/sources/{other}?project_id=101"
        ).status_code
        == 404
    )


def test_native_registry_requires_findings_read_and_never_accepts_model_selected_scope(
    research_client, research_store, db_conn
):
    """A token's project and permissions stay authoritative for list and summary tools."""
    own = legacy_finding(db_conn)
    legacy_finding(db_conn, project=202, task=2002, topic="FOREIGN SECRET")
    headers = credentials(research_store)
    response = research_client.get("/api/research-tools/findings", headers=headers)
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [own]
    assert (
        research_client.get(
            "/api/research-tools/findings?project_id=202", headers=headers
        ).status_code
        == 422
    )
    denied = credentials(research_store, permissions={"sources.read"})
    assert (
        research_client.get("/api/research-tools/findings", headers=denied).status_code
        == 403
    )
    assert (
        research_client.get(
            "/api/research-tools/findings-summary", headers=headers
        ).json()["total_count"]
        == 1
    )


def test_owner_registry_uses_serving_database_identity_instead_of_legacy_global_path(
    research_client, research_store, db_conn, monkeypatch
):
    """A configured serving store must win over an unrelated legacy database configuration."""
    own = legacy_finding(db_conn)
    research_client.app.state.runtime_research_store = research_store
    monkeypatch.setattr(
        "backend.tools.base.db.get_db_path", lambda: "/must-not-open-global.db"
    )
    response = research_client.get("/api/findings-index?project_id=101")
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["id"] == own


def test_corrupt_captured_text_cannot_be_presented_as_the_original_source(
    research_client, research_store, research_scope, db_conn
):
    """A saved hash mismatch is a reconciliation error, not a successful source preview."""
    finding, source = cited_finding(research_store, research_scope)
    db_conn.execute(
        "UPDATE research_sources SET content='Replaced text' WHERE id=?", (source,)
    )
    db_conn.commit()
    response = research_client.get(
        f"/api/findings/{finding}/sources/{source}?project_id=101"
    )
    assert response.status_code == 409, response.text
    assert (
        research_client.get(f"/api/findings/{finding}/evidence?project_id=101").json()[
            "evidence"
        ][0]["quote_is_exact"]
        is False
    )


def test_native_finding_reader_declares_long_body_continuation_and_actual_review_provenance(
    research_client, research_store, research_scope
):
    """A native read must expose its bounded text/evidence windows rather than imply complete review."""
    body = "Recorded observation. " * 1000 + "Late limitation."
    finding, _ = cited_finding(research_store, research_scope, body=body)
    response = research_client.get(
        f"/api/research-tools/findings/{finding}",
        headers=credentials(research_store),
        params={"max_chars": 4000},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["content"] == body[:4000] and data["next_offset"] == 4000
    assert data["total_chars"] == len(body) and data["scientific_confidence"] is None
    assert (
        data["review_status"] == "not_recorded"
        and data["evidence"][0]["quote_is_exact"]
    )


def test_historical_source_declarations_remain_readable_without_becoming_captured_citations(
    research_client, research_store, db_conn
):
    """Preserve legacy sources_json as a paged unverified declaration, even when no canonical quotes exist."""
    finding = legacy_finding(db_conn)
    declarations = json.dumps(
        [{"url": "https://example.org/old", "note": "Unverified " + "x" * 9000}]
    )
    db_conn.execute(
        "UPDATE findings SET sources_json=? WHERE id=?", (declarations, finding)
    )
    db_conn.commit()
    response = research_client.get(f"/api/findings/{finding}?project_id=101")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["legacy_sources_json"] == declarations[:8000]
    assert data["legacy_sources_next_offset"] == 8000 and data["total_evidence"] == 0
    tail = research_client.get(
        f"/api/findings/{finding}/legacy-sources?project_id=101&offset=8000"
    )
    assert tail.status_code == 200, tail.text
    assert (
        tail.json()["content"] == declarations[8000:]
        and tail.json()["next_offset"] is None
    )
    assert tail.json()["verification"] == "unverified_legacy_declaration"


def test_lexical_syntax_failure_is_explicit_and_never_becomes_an_unlabelled_like_search(
    research_client, research_store, db_conn
):
    """An empty sanitized FTS expression is invalid input rather than a server error or different search."""
    legacy_finding(db_conn)
    result = research_client.get(
        "/api/findings-index", params={"project_id": 101, "q": '"'}
    )
    assert result.status_code == 422, result.text


def test_native_task_filter_is_a_read_filter_inside_the_bound_project_not_new_authority(
    research_client, research_store, db_conn
):
    """Retain task-specific knowledge inspection without allowing a model to change tool scope."""
    db_conn.execute(
        "INSERT INTO tasks(id,project_id,type,title) VALUES(1002,101,'research','Second')"
    )
    db_conn.commit()
    legacy_finding(db_conn)
    selected = legacy_finding(db_conn, task=1002)
    legacy_finding(db_conn, project=202, task=2002)
    headers = credentials(research_store)
    response = research_client.get(
        "/api/research-tools/findings", headers=headers, params={"for_task_id": 1002}
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [selected]
    summary = research_client.get(
        "/api/research-tools/findings-summary",
        headers=headers,
        params={"for_task_id": 2002},
    )
    assert summary.status_code == 200 and summary.json()["total_count"] == 0


def test_nonempty_malformed_lexical_grammar_is_a_recoverable_input_error(
    research_client, research_store, db_conn
):
    """A malformed prefix/quote cannot become a 500 or a silent change of retrieval method."""
    legacy_finding(db_conn)
    for path in ["/api/findings-index", "/api/findings-summary"]:
        response = research_client.get(path, params={"project_id": 101, "q": 'word"*'})
        assert response.status_code == 422, response.text
