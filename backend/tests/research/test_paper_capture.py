"""Paper locators enter the existing scoped capture pipeline without false full-text claims."""

import hashlib

import pytest

from backend.tests.research.pdf_fixtures import pdf_bytes
from backend.tests.research.test_http import (
    credentials,
    research_client,
)
from backend.tests.research.test_pdf_web import pdf_response
from backend.tests.research.test_web_fetcher import TransportOnlyPolicy, fetcher

__all__ = ["research_client"]  # Export the reused pytest fixture explicitly.


@pytest.fixture
def paper_transport(monkeypatch):
    """Retain actual HTTP parsing/URL policy/parser, substituting only DNS/socket responses."""
    from backend.api import research_dependencies

    responses, calls, hosts = [], [], []

    def configured(**options):
        """Keep paper/SSRF coverage focused; HTTP policy integration lives in test_http."""
        options["policy"] = TransportOnlyPolicy()
        web, connections, resolutions = fetcher(responses, **options)
        calls.append(connections)
        hosts.append(resolutions)
        return web

    monkeypatch.setattr(research_dependencies, "PublicWebFetcher", configured)
    return responses, calls, hosts


@pytest.mark.parametrize(
    "locator,requested,kind,value,version",
    [
        (
            {"url": "https://papers.example.org/article.pdf"},
            "https://papers.example.org/article.pdf",
            "url",
            "https://papers.example.org/article.pdf",
            None,
        ),
        (
            {"arxiv_id": "arXiv:2301.07041v2"},
            "https://arxiv.org/pdf/2301.07041v2",
            "arxiv",
            "2301.07041v2",
            "explicit",
        ),
        (
            {"arxiv_id": "hep-th/9901001"},
            "https://arxiv.org/pdf/hep-th/9901001",
            "arxiv",
            "hep-th/9901001",
            "latest_at_capture",
        ),
        (
            {"doi": "doi:10.1000/Évidence?x#y%z"},
            "https://doi.org/10.1000/%C3%89vidence%3Fx%23y%25z",
            "doi",
            "10.1000/Évidence?x#y%z",
            None,
        ),
    ],
)
def test_paper_capture_redirects_to_saved_pdf_with_requested_identity_and_no_refetch(
    research_client,
    research_store,
    research_scope,
    paper_transport,
    db_conn,
    locator,
    requested,
    kind,
    value,
    version,
):
    """Catch lost DOI/arXiv identity, injected URI syntax, missing page provenance and retry I/O."""
    responses, calls, _hosts = paper_transport
    data = pdf_bytes("Tax rates are fractions.", "Rate: 0.21.")
    responses.extend(
        [
            b"HTTP/1.1 302 Found\r\nLocation: https://publisher.example.org/paper.pdf\r\nContent-Length: 0\r\n\r\n",
            pdf_response(data),
        ]
    )
    headers = credentials(research_store)
    command = {"operation_key": "paper", **locator}
    response = research_client.post(
        "/api/research-tools/sources/paper", headers=headers, json=command
    )
    assert response.status_code == 200, response.text
    receipt = response.json()
    source = research_store.read_source(research_scope, receipt["source_id"])
    assert source["locator"] == "https://publisher.example.org/paper.pdf"
    assert source["provenance"]["requested_url"] == requested
    assert source["provenance"]["paper_request"] == {
        "kind": kind,
        "value": value,
        "version_selection": version,
        "identifier_verified": False,
    }
    assert source["provenance"]["byte_sha256"] == hashlib.sha256(data).hexdigest()
    assert (
        source["provenance"]["page_count"] == 2
        and source["provenance"]["ocr_performed"] is False
    )
    assert "[Page 2]\nRate: 0.21." in source["content"]
    assert (
        research_client.post(
            "/api/research-tools/sources/paper", headers=headers, json=command
        ).json()
        == receipt
    )
    assert sum(map(len, calls)) == 2
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 1
    conflict = research_client.post(
        "/api/research-tools/sources/paper",
        headers=headers,
        json={"operation_key": "paper", "doi": "10.1000/different"},
    )
    assert conflict.status_code == 409 and sum(map(len, calls)) == 2
    foreign = research_client.get(
        f"/api/research-tools/sources/{receipt['source_id']}",
        headers=credentials(research_store, 202, 2002),
    )
    assert foreign.status_code == 404


@pytest.mark.parametrize(
    "locator",
    [
        {},
        {"url": "https://example.org/a", "doi": "10.1000/a"},
        {"arxiv_id": "2301.07041v0"},
        {"arxiv_id": "2300.07041"},
        {"arxiv_id": "../../private"},
        {"arxiv_id": "2301.07041?redirect=private"},
        {"doi": "https://evil.example/10.1000/a"},
        {"doi": "10.1000/"},
        {"doi": "10.1000/\nHost:evil"},
        {"doi": "10.1000/a b"},
        {"url": "http://example.org/paper.pdf"},
        {"url": "https://localhost/paper.pdf"},
        {"url": "https://user:secret@example.org/paper.pdf"},
        {"url": "https://example.org/paper.pdf", "project_id": 202},
    ],
)
def test_invalid_or_ambiguous_paper_input_never_fetches_or_persists(
    research_client,
    research_store,
    paper_transport,
    db_conn,
    locator,
):
    """Reject precedence guesses, path injection and identity overrides before I/O or storage."""
    _, calls, _ = paper_transport
    response = research_client.post(
        "/api/research-tools/sources/paper",
        headers=credentials(research_store),
        json={"operation_key": "invalid", **locator},
    )
    assert response.status_code == 422, response.text
    assert not any(calls)
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0


def test_doi_html_landing_page_is_preserved_as_html_evidence_not_a_pdf_claim(
    research_client,
    research_store,
    research_scope,
    paper_transport,
):
    """A DOI resolving to a publisher landing page does not prove access to full paper text."""
    responses, _, _ = paper_transport
    body = b"<html><title>Publisher landing page</title><p>Abstract only. Full text unavailable.</p></html>"
    responses.append(pdf_response(body, mime="text/html"))
    response = research_client.post(
        "/api/research-tools/sources/paper",
        headers=credentials(research_store),
        json={"operation_key": "landing", "doi": "10.1000/abstract"},
    )
    assert response.status_code == 200, response.text
    source = research_store.read_source(research_scope, response.json()["source_id"])
    assert source["provenance"]["mime_type"] == "text/html"
    assert source["provenance"]["paper_request"]["identifier_verified"] is False
    assert "page_count" not in source["provenance"]
    assert "Abstract only. Full text unavailable." in source["content"]


def test_paper_resolution_cannot_bypass_private_redirect_policy(
    research_client,
    research_store,
    paper_transport,
    db_conn,
):
    """Fixed identifier resolvers must still validate every destination, including redirects."""
    responses, calls, _ = paper_transport
    responses.append(
        b"HTTP/1.1 302 Found\r\nLocation: https://127.0.0.1/private\r\nContent-Length: 0\r\n\r\n"
    )
    response = research_client.post(
        "/api/research-tools/sources/paper",
        headers=credentials(research_store),
        json={"operation_key": "private", "doi": "10.1000/private"},
    )
    assert response.status_code == 422, response.text
    assert sum(map(len, calls)) == 1
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0


def test_read_only_grant_cannot_capture_a_paper(
    research_client, research_store, paper_transport
):
    """Adding a locator tool must not broaden source-read authority to network capture."""
    _, calls, _ = paper_transport
    response = research_client.post(
        "/api/research-tools/sources/paper",
        headers=credentials(research_store, permissions={"sources.read"}),
        json={"operation_key": "denied", "arxiv_id": "2301.07041"},
    )
    assert response.status_code == 403, response.text
    assert not any(calls)


@pytest.mark.parametrize(
    "data", [b"%PDF-broken", pdf_bytes(None), pdf_bytes("Private", encrypted=True)]
)
def test_failed_paper_pdf_does_not_create_a_successful_source(
    research_client, research_store, paper_transport, db_conn, data
):
    """Keep malformed, scanned and encrypted paper responses on the same parser failure path."""
    responses, _, _ = paper_transport
    responses.append(pdf_response(data))
    response = research_client.post(
        "/api/research-tools/sources/paper",
        headers=credentials(research_store),
        json={"operation_key": "unreadable", "arxiv_id": "2301.07041v2"},
    )
    assert response.status_code == 422
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0


def test_authority_revoked_after_paper_download_cannot_commit(
    research_client, research_store, db_conn, monkeypatch
):
    """The identifier adapter must retain the acquisition/commit revalidation seam."""
    from backend.api import research_dependencies

    headers = credentials(research_store)
    scope = research_store.authorize(headers["Authorization"].split(" ", 1)[1])

    def configured(**options):
        """Withdraw the database grant after real PDF extraction but before persistence."""
        options["policy"] = TransportOnlyPolicy()
        web, _, _ = fetcher(
            [pdf_response(pdf_bytes("Uncommitted evidence"))], **options
        )
        original = web.fetch

        def revoked(url):
            """Return valid extracted bytes after revoking their permission to commit."""
            snapshot = original(url)
            research_store.revoke_grant(scope.grant_id)
            return snapshot

        web.fetch = revoked
        return web

    monkeypatch.setattr(research_dependencies, "PublicWebFetcher", configured)
    response = research_client.post(
        "/api/research-tools/sources/paper",
        headers=headers,
        json={"operation_key": "late", "doi": "10.1000/late"},
    )
    assert response.status_code == 403
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0


@pytest.mark.parametrize(
    "doi,expected",
    [
        ("10.1000/a/b", "https://doi.org/10.1000/a%2Fb"),
        ("10.1000/..", "https://doi.org/10.1000/%2E%2E"),
        ("10.1000/é?x#y", "https://doi.org/10.1000/%C3%A9%3Fx%23y"),
    ],
)
def test_doi_suffix_cannot_become_a_query_fragment_or_dot_segment(doi, expected):
    """Keep locator characters inside the DOI value instead of changing HTTP request syntax."""
    from urllib.parse import urlsplit

    from backend.research.papers import resolve_paper

    locator = resolve_paper(doi=doi)
    assert locator.url == expected
    parsed = urlsplit(locator.url)
    assert parsed.netloc == "doi.org" and not parsed.query and not parsed.fragment


def test_identifier_length_caps_are_application_limits_not_registry_validity():
    """Reject excess UTF-8/encoded URL size before acquisition without guessing registration."""
    from backend.research.models import ResearchInputError
    from backend.research.papers import resolve_paper

    with pytest.raises(ResearchInputError):
        resolve_paper(doi="10.1000/" + "é" * 1000)
    with pytest.raises(ResearchInputError):
        resolve_paper(doi="10.1000/" + "a" * 2048)
    assert resolve_paper(arxiv_id="0706.0001v2").version_selection == "explicit"
    assert resolve_paper(arxiv_id="math.GT/0301001v3").version_selection == "explicit"
