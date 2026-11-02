"""Finding similarity searches declare full corpus coverage and never certify scientific confidence."""

import os
from pathlib import Path

import pytest

from backend.tests.research.test_finding_registry import legacy_finding
from backend.tests.research.test_http import credentials, research_client

__all__ = ["research_client"]


def test_finding_semantic_unavailable_stays_explicit_instead_of_falling_back_to_lexical(
    research_client, research_store, db_conn
):
    """A lexical hit is not a successful semantic response when local assets are unprepared."""
    from backend.research.semantic import SemanticRetriever

    research_client.app.state.retrieval = SemanticRetriever(None)
    legacy_finding(db_conn)
    result = research_client.get(
        "/api/findings-query", params={"project_id": 101, "query": "fractions"}
    )
    assert result.status_code == 503, result.text
    assert result.json()["code"] == "retrieval_unavailable"


def test_finding_corpus_rejects_excess_size_and_missing_selected_members_without_sampling(
    research_store, research_scope, db_conn
):
    """An oversized or partly foreign selection fails as a whole rather than pretending completeness."""
    from backend.research.models import ResearchNotFound, SourceTooLarge

    one = legacy_finding(db_conn, content="x" * 110000)
    two = legacy_finding(db_conn, content="y" * 110000)
    foreign = legacy_finding(db_conn, project=202, task=2002)
    with pytest.raises(SourceTooLarge):
        research_store.finding_corpus(research_scope)
    small = research_store.finding_corpus(research_scope, finding_ids=[one])
    assert small["finding_ids"] == [one] and small["corpus_count"] == 1
    with pytest.raises(ResearchNotFound):
        research_store.finding_corpus(research_scope, finding_ids=[one, foreign])
    assert two not in small["finding_ids"]


@pytest.mark.parametrize("change", ["revoke", "edit", "insert", "withdraw"])
def test_native_finding_query_revalidates_authority_and_exact_corpus_after_worker(
    research_client, research_store, db_conn, change
):
    """Late text, matching rows or authority changes cannot disclose a stale semantic receipt."""
    finding = legacy_finding(db_conn)
    headers = credentials(research_store)
    scope = research_store.authorize(headers["Authorization"].split()[1])

    class ChangingRetriever:
        """Model only the intervening commit/withdrawal, not the actual semantic ranking quality."""

        def query(self, corpus, query, **kwargs):
            """Change one observed precondition after admission but before the route discloses results."""
            if change == "revoke":
                research_store.revoke_grant(scope.grant_id)
            elif change == "withdraw":
                research_client.app.state.live_grants.withdraw(scope.grant_id)
            else:
                import sqlite3

                with sqlite3.connect(research_store.database) as conn:
                    if change == "edit":
                        conn.execute(
                            "UPDATE findings SET content='Changed evidence' WHERE id=?",
                            (finding,),
                        )
                    else:
                        conn.execute(
                            "INSERT INTO findings(project_id,task_id,topic,content,agent_id) VALUES(101,1001,'New','New','other')"
                        )
            return {
                "source_id": corpus["id"],
                "sha256": corpus["sha256"],
                "matches": [],
                "search_kind": "semantic_cosine",
                "full_coverage": True,
            }

    research_client.app.state.retrieval = ChangingRetriever()
    response = research_client.get(
        "/api/research-tools/findings-query",
        headers=headers,
        params={"query": "fractions"},
    )
    assert response.status_code == (403 if change in {"revoke", "withdraw"} else 503), (
        response.text
    )
    research_client.app.state.live_grants.wait_closed(scope.grant_id)


def test_real_local_finding_query_reaches_late_body_text_and_does_not_create_a_source_or_confidence(
    research_client, research_store, db_conn
):
    """The actual offline worker sees full current claim text beyond the legacy 500-character sample."""
    from backend.research.semantic import SemanticRetriever

    configured = os.environ.get("RESEARCHER_TEST_RETRIEVAL_ASSETS")
    if not configured or not Path(configured).is_dir():
        pytest.skip("Explicit pinned offline assets are required")
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
    before = db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0]
    research_client.app.state.retrieval = SemanticRetriever(configured)
    result = research_client.get(
        "/api/research-tools/findings-query",
        headers=credentials(research_store),
        params={"query": "How are stored credentials protected?", "limit": 5},
    )
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["corpus_count"] == 2 and data["full_coverage"]
    assert "source_id" not in data and data["scientific_confidence"] is None
    matches = [m for m in data["matches"] if m["finding_id"] == target]
    assert any("scrypt" in m["excerpt"] for m in matches), data
    for match in matches:
        assert match["text_scope"] == "title_and_body"
        combined = "System notes\n\n" + text
        assert (
            combined[match["finding_start_offset"] : match["finding_end_offset"]]
            == match["excerpt"]
        )
    assert data["execution"]["worker_closed"]
    assert (
        db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == before
    )


def test_finding_corpus_counts_exact_normalized_bytes_and_keeps_the_complete_historical_title(
    research_store, research_scope, db_conn
):
    """Admission must measure actual normalization and search beyond a clipped metadata title."""
    title = "Historical title " * 100 + "Late title condition"
    identity = legacy_finding(db_conn, topic=title, content="Short claim.")
    corpus = research_store.finding_corpus(research_scope, finding_ids=[identity])
    assert title + "\n\nShort claim." in corpus["content"]
    db_conn.execute(
        "UPDATE findings SET topic=?,content=? WHERE id=?",
        ("T", "x" * 199980, identity),
    )
    db_conn.commit()
    corpus = research_store.finding_corpus(research_scope, finding_ids=[identity])
    assert len(corpus["content"].encode()) <= 200000 and corpus["content"].endswith(
        "x" * 199980
    )


@pytest.mark.parametrize("native", [False, True])
def test_semantic_continuation_requires_the_same_observed_corpus_before_starting_a_worker(
    research_client, research_store, research_scope, db_conn, native
):
    """Rank offsets from one mutable finding set cannot be applied to another set after an edit."""
    finding = legacy_finding(db_conn)
    corpus = research_store.finding_corpus(research_scope)

    class ForbiddenRetriever:
        """No worker may start for a stale or unbound continuation."""

        def query(self, *args, **kwargs):
            """Fail loudly if continuation preconditions are checked after admission."""
            raise AssertionError("stale continuation started a worker")

    research_client.app.state.retrieval = ForbiddenRetriever()
    path = "/api/research-tools/findings-query" if native else "/api/findings-query"
    headers = credentials(research_store) if native else {}
    params = {"query": "tax rates", "after_rank": 1}
    if not native:
        params["project_id"] = 101
    missing = research_client.get(path, headers=headers, params=params)
    assert missing.status_code == 422, missing.text
    db_conn.execute("UPDATE findings SET content=? WHERE id=?", ("Changed", finding))
    db_conn.commit()
    params.update(
        expected_corpus_sha256=corpus["sha256"],
        expected_record_set_sha256=corpus["record_set_sha256"],
    )
    stale = research_client.get(path, headers=headers, params=params)
    assert stale.status_code == 409, stale.text
