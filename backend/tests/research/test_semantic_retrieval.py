"""Scoped semantic source retrieval keeps exact evidence, revision and coverage explicit."""

import os
from pathlib import Path

import pytest

from backend.research.models import SourceDraft
from backend.tests.research.test_http import credentials, research_client

__all__ = ["research_client"]


@pytest.fixture(autouse=True)
def isolated_semantic_configuration(monkeypatch):
    """Keep the owner's deployment model path out of synthetic HTTP tests."""
    from backend.config.settings import settings

    monkeypatch.setattr(settings, "RETRIEVAL_ASSET_DIR", None)


@pytest.fixture
def captured_source(research_store, research_scope):
    """Persist an actual canonical source, without a model or uploaded-file dependency."""
    receipt = research_store.capture_source(
        research_scope,
        "semantic-source",
        SourceDraft(
            "web",
            "https://example.org/trial",
            "Trial",
            "Patients did not improve after taking the medication.",
        ),
        intent={"url": "https://example.org/trial"},
    )
    return receipt["source_id"]


def test_semantic_unavailable_is_explicit_and_does_not_fall_back_to_literal_or_remote(
    research_client, research_store, captured_source
):
    """A missing local model must not become empty results, an embedding API call or fake success."""
    response = research_client.get(
        f"/api/research-tools/sources/{captured_source}/query",
        headers=credentials(research_store),
        params={"query": "treatment outcomes"},
    )
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "retrieval_unavailable"


@pytest.mark.parametrize("query", ["", "   ", "x" * 1001])
def test_invalid_semantic_query_is_rejected_before_model_work(
    research_client, research_store, captured_source, query
):
    """Bound query text and reject empty meaning without silently truncating token input."""
    response = research_client.get(
        f"/api/research-tools/sources/{captured_source}/query",
        headers=credentials(research_store),
        params={"query": query},
    )
    assert response.status_code == 422, response.text


def test_foreign_project_source_is_rejected_before_model_availability(
    research_client, research_store, captured_source
):
    """A source id is not authority to inspect another project's document or retrieval status."""
    response = research_client.get(
        f"/api/research-tools/sources/{captured_source}/query",
        headers=credentials(research_store, 202, 2002),
        params={"query": "treatment outcomes"},
    )
    assert response.status_code == 404, response.text


def assets():
    """Require explicit offline test assets; never download weights from a test/request."""
    value = os.environ.get("RESEARCHER_TEST_RETRIEVAL_ASSETS")
    if not value:
        pytest.skip("Explicit pinned local semantic model fixture not prepared")
    return Path(value)


def test_real_multilingual_query_recovers_tail_evidence_with_exact_offsets(
    research_client, research_store, research_scope, db_conn, monkeypatch
):
    """Use real local embeddings for an English-source/Spanish-query paraphrase beyond the first window."""
    from backend.research.semantic import SemanticRetriever

    research_client.app.state.retrieval = SemanticRetriever(assets())
    tail = "The controlled trial found no improvement in patient symptoms with the new medication compared with placebo."
    text = (
        ("The museum collection includes paintings and sculptures.\n" * 300)
        + "\n"
        + tail
    )
    receipt = research_store.capture_source(
        research_scope,
        "semantic-tail",
        SourceDraft("web", "https://example.org/trial", "Trial", text),
        intent={"url": "https://example.org/trial"},
    )
    source_id = receipt["source_id"]
    tables = ("research_sources", "findings", "artifacts", "tool_operations")
    before = {
        table: db_conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    response = research_client.get(
        f"/api/research-tools/sources/{source_id}/query",
        headers=credentials(research_store, permissions={"sources.read"}),
        params={
            "query": "¿El tratamiento produjo mejoras en los síntomas?",
            "limit": 5,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert (
        result["search_kind"] == "semantic_cosine"
        and result["sha256"] == receipt["sha256"]
    )
    assert (
        result["full_coverage"] is True
        and result["considered_chunks"] == result["total_chunks"]
    )
    assert (
        result["model"]["dimension"] == 384
        and result["model"]["revision"] == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    )
    assert any(tail in match["excerpt"] for match in result["matches"])
    for match in result["matches"]:
        assert text[match["start_offset"] : match["end_offset"]] == match["excerpt"]
        assert len(match["excerpt"].encode()) <= 8000
        assert -1 <= match["score"] <= 1
    again = research_client.get(
        f"/api/research-tools/sources/{source_id}/query",
        headers=credentials(research_store, permissions={"sources.read"}),
        params={
            "query": "¿El tratamiento produjo mejoras en los síntomas?",
            "limit": 5,
            "after_rank": result["next_rank"],
        },
    )
    assert again.status_code == 200, again.text
    assert {m["start_offset"] for m in result["matches"]}.isdisjoint(
        m["start_offset"] for m in again.json()["matches"]
    )
    assert {
        table: db_conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in tables
    } == before


def test_changed_or_missing_model_asset_fails_without_a_partial_semantic_result(
    research_client, research_store, captured_source, tmp_path
):
    """A configured path is not proof that the pinned weights/tokenizer are present or intact."""
    from backend.research.semantic import SemanticRetriever

    research_client.app.state.retrieval = SemanticRetriever(tmp_path)
    (tmp_path / "model.onnx").write_bytes(b"wrong model")
    (tmp_path / "tokenizer.json").write_text("{}")
    response = research_client.get(
        f"/api/research-tools/sources/{captured_source}/query",
        headers=credentials(research_store),
        params={"query": "treatment outcomes"},
    )
    assert response.status_code == 503, response.text
    assert "matches" not in response.json()


def test_real_pdf_semantic_result_maps_the_exact_excerpt_to_captured_pages(
    research_client, research_store, research_scope, db_conn, tmp_path
):
    """Page citations must use actual parser offset keys, not invented result page numbers."""
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.semantic import SemanticRetriever
    from backend.research.service import ResearchService
    from backend.tests.research.pdf_fixtures import pdf_bytes
    from backend.tests.research.test_acquisition import reference

    research_client.app.state.retrieval = SemanticRetriever(assets())
    root, _, record = reference(
        research_store,
        db_conn,
        tmp_path,
        content=pdf_bytes(
            "Preliminary observations.",
            "The medication did not improve symptoms compared with placebo.",
        ),
    )
    db_conn.execute(
        "UPDATE reference_files SET file_type='application/pdf' WHERE id=?",
        (record.id,),
    )
    db_conn.commit()
    receipt = ResearchService(
        research_store, reference_reader=BoundedReferenceReader(root)
    ).capture_reference(research_scope, "semantic-pdf", record.id)
    response = research_client.get(
        f"/api/research-tools/sources/{receipt['source_id']}/query",
        headers=credentials(research_store),
        params={"query": "Was the treatment effective?"},
    )
    assert response.status_code == 200, response.text
    match = response.json()["matches"][0]
    assert 2 in match["page_numbers"] and "did not improve" in match["excerpt"]
    assert response.json()["execution"]["worker_closed"] is True


@pytest.mark.parametrize(
    "options",
    [
        {"cpu_seconds": 0},
        {"wall_seconds": float("nan")},
        {"memory_bytes": 1},
        {"max_output_bytes": 0},
    ],
)
def test_semantic_host_budgets_cannot_disable_the_worker_fuses(options):
    """Reject invalid host limits before any encoder process can be admitted."""
    from backend.research.semantic import SemanticLimits

    with pytest.raises(ValueError):
        SemanticLimits(**options)


@pytest.mark.parametrize("payload", [b"[]", b"null", b"not-json"])
def test_invalid_semantic_worker_receipts_are_explicit_unavailable_errors(
    monkeypatch, tmp_path, payload
):
    """Malformed IPC is not an unhandled exception or a successful partial result."""
    import hashlib
    from contextlib import contextmanager

    import backend.research.semantic as module
    from backend.research.retrieval_assets import RetrievalUnavailable

    @contextmanager
    def pinned(*args, **kwargs):
        """Substitute only verified asset handles; no encoder or model download is run."""
        yield {}

    monkeypatch.setattr(module, "pinned_assets", pinned)
    monkeypatch.setattr(module, "exchange", lambda *args, **kwargs: payload)
    source = {
        "id": 1,
        "content": "Evidence",
        "sha256": hashlib.sha256(b"Evidence").hexdigest(),
        "provenance": {},
    }
    with pytest.raises(RetrievalUnavailable):
        module.SemanticRetriever(tmp_path).query(source, "meaning")


def test_semantic_api_revalidates_grant_before_disclosing_results(
    research_client, research_store, captured_source
):
    """A grant withdrawn during model work cannot disclose a stale read result."""
    headers = credentials(research_store)
    scope = research_store.authorize(headers["Authorization"].split(" ", 1)[1])

    class RevokingRetriever:
        """Represent successful local work whose caller lost authority before API return."""

        def query(self, *args, **kwargs):
            """Revoke only this scoped token and provide a value that must never reach the client."""
            research_store.revoke_grant(scope.grant_id)
            return {"matches": ["MUST NOT DISCLOSE"]}

    research_client.app.state.retrieval = RevokingRetriever()
    response = research_client.get(
        f"/api/research-tools/sources/{captured_source}/query",
        headers=headers,
        params={"query": "outcomes"},
    )
    assert response.status_code == 403
    assert "MUST NOT DISCLOSE" not in response.text


def test_source_catalog_reports_unconfigured_semantics_without_loading_a_model(
    research_client, research_store, captured_source
):
    """Plan retrieval from declared availability, without interpreting a configured path as ready."""
    response = research_client.get(
        "/api/research-tools/sources", headers=credentials(research_store)
    )
    assert response.status_code == 200
    assert response.json()["retrieval"]["semantic"]["assets_status"] == "not_configured"
    assert response.json()["retrieval"]["literal"]["method"] == "exact_text"
