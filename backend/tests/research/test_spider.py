"""Verify optional Spider scraping preserves source evidence, scope, budget and closure."""

import hashlib
import json

import pytest

from backend.tests.research.test_context7 import response
from backend.tests.research.test_http import credentials, research_client
from backend.tests.research.test_web_fetcher import MemoryConnection

__all__ = ["research_client"]

PAGE = {
    "url": "https://docs.example.org/app",
    "status": 200,
    "content": "# Rendered documentation\nThe timeout is 5 seconds.",
    "costs": {"total_cost": 0.0002},
    "metadata": {"title": "Rendered documentation"},
}


def provider(responses, *, addresses=("93.184.216.34",), **options):
    """Replace only DNS/socket bytes, retaining actual HTTP parsing and provider policy."""
    from backend.research.spider import SpiderReader

    calls, resolutions = [], []

    def resolve(host, timeout):
        """Record public-origin vetting before host credentials can be sent."""
        resolutions.append(host)
        return list(addresses)

    def connection(host, port, address, timeout):
        """Use the real HTTP serializer to inspect the fixed POST endpoint and body."""
        conn = MemoryConnection(host, port, address, timeout, responses.pop(0))
        calls.append(conn)
        return conn

    return (
        SpiderReader(
            api_key="synthetic-spider-key",
            resolver=resolve,
            connection_factory=connection,
            **options,
        ),
        calls,
        resolutions,
    )


@pytest.fixture
def spider_transport(monkeypatch):
    """Compose the adapter with the production host owner and grant, without a real provider call."""
    from backend.api import research_dependencies

    responses, calls = [], []

    def configured(**options):
        """Keep all production options while replacing only DNS and socket responses."""
        reader, connections, _ = provider(responses, **options)
        calls.append(connections)
        return reader

    monkeypatch.setattr(
        research_dependencies.SpiderReader, "from_environment", configured
    )
    return responses, calls


@pytest.mark.parametrize("mode", ["smart", "browser", "http"])
@pytest.mark.parametrize("format", ["markdown", "text"])
def test_single_page_scraping_keeps_rendering_choice_budget_and_provenance(
    mode, format
):
    """Advanced rendering remains available without sending arbitrary parameters or trusting provider costs."""
    reader, calls, hosts = provider([response([PAGE])], max_credits=25)
    source = reader.fetch(PAGE["url"], mode=mode, format=format)
    assert source.content == PAGE["content"] and source.locator == PAGE["url"]
    assert source.provenance["provider"] == "spider"
    assert source.provenance["provider_costs"] == PAGE["costs"]
    assert source.provenance["provider_assertions_verified"] is False
    assert (
        source.provenance["byte_sha256"]
        == hashlib.sha256(json.dumps([PAGE]).encode()).hexdigest()
    )
    assert hosts == ["docs.example.org", "api.spider.cloud"]
    header, body = calls[0].buffer.sent.split(b"\r\n\r\n", 1)
    assert (
        header.startswith(b"POST /scrape HTTP/1.1")
        and b"Host: api.spider.cloud" in header
    )
    assert b"Authorization: Bearer synthetic-spider-key" in header
    payload = json.loads(body)
    assert payload["url"] == PAGE["url"] and payload["request"] == mode
    assert payload["return_format"] == format and payload["max_credits_allowed"] == 25
    assert payload["max_credits_per_page"] == 25 and payload["request_timeout"] == 10
    assert payload["session"] is False and payload["run_in_background"] is False
    assert (
        not {
            "llm_extract",
            "execution_scripts",
            "data_connectors",
            "headers",
            "cookies",
        }
        & payload.keys()
    )
    assert "synthetic-spider-key" not in str(source)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://127.0.0.1",
        "https://user:pass@example.org",
        "https://example.org,https://another.org",
        "https://example.org/path,other",
        "file:///etc/passwd",
    ],
)
def test_unsafe_or_ambiguous_batch_targets_fail_before_provider_io(url):
    """The one-page tool cannot smuggle a second URL or expose host-private targets."""
    from backend.research.models import SourceUnavailable

    reader, calls, _ = provider([])
    with pytest.raises(SourceUnavailable):
        reader.fetch(url)
    assert calls == []


@pytest.mark.parametrize(
    "value",
    [
        [],
        [PAGE, PAGE],
        [{**PAGE, "status": 403}],
        [{**PAGE, "error": "rendering failed"}],
        [{**PAGE, "content": ""}],
        [{**PAGE, "content": {"text": "wrong"}}],
        [{**PAGE, "url": "https://127.0.0.1/"}],
        {"data": [PAGE]},
    ],
)
def test_failed_or_unexpected_provider_pages_are_not_plausible_sources(value):
    """Reject failure/challenge/batch/schema responses rather than saving an arbitrary first page."""
    from backend.research.models import SourceUnavailable

    reader, calls, _ = provider([response(value)])
    with pytest.raises(SourceUnavailable):
        reader.fetch(PAGE["url"])
    assert len(calls) == 1


@pytest.mark.parametrize("status", [202, 301, 401, 402, 429, 503])
def test_provider_failure_does_not_retry_or_leak_credentials(status):
    """Quota, redirect and service failures produce one explicit error, never another billable lookup."""
    from backend.research.models import SourceUnavailable

    reader, calls, _ = provider(
        [response({"error": "synthetic-spider-key"}, status=status)]
    )
    with pytest.raises(SourceUnavailable) as error:
        reader.fetch(PAGE["url"])
    assert str(status) in str(error.value) and "synthetic-spider-key" not in str(
        error.value
    )
    assert len(calls) == 1


def test_missing_configuration_private_dns_and_invalid_budget_do_not_call_provider(
    monkeypatch,
):
    """No optional key, invalid host budget or nonpublic DNS means no external request."""
    from backend.research.models import SourceUnavailable
    from backend.research.spider import SpiderReader

    monkeypatch.delenv("SPIDER_API_KEY", raising=False)
    monkeypatch.delenv("INFINIBAY_SPIDER_API_KEY", raising=False)
    with pytest.raises(SourceUnavailable, match="configured"):
        SpiderReader.from_environment().fetch(PAGE["url"])
    reader, calls, _ = provider([], addresses=("127.0.0.1",))
    with pytest.raises(SourceUnavailable):
        reader.fetch(PAGE["url"])
    assert not calls
    for budget in (0, -1, float("inf"), "bad"):
        reader, calls, _ = provider([], max_credits=budget)
        with pytest.raises(SourceUnavailable, match="budget"):
            reader.fetch(PAGE["url"])
        assert not calls


@pytest.mark.parametrize(
    "body,byte_limit",
    [
        (response([{**PAGE, "content": "x" * 200001}]), 1000000),
        (response([PAGE]), 100),
        (response(b"not-json"), 1000000),
        (response([{**PAGE, "content": "\ud800"}]), 1000000),
        (response([PAGE])[:-2], 1000000),
    ],
)
def test_provider_content_limits_do_not_silently_capture_partial_evidence(
    body, byte_limit
):
    """Bound raw bytes and decoded text separately; malformed/truncated content is never saved."""
    from backend.research.models import SourceTooLarge, SourceUnavailable

    reader, calls, _ = provider([body], max_bytes=byte_limit)
    with pytest.raises((SourceTooLarge, SourceUnavailable)):
        reader.fetch(PAGE["url"])
    assert len(calls) == 1


def test_retired_spider_leaf_and_review_acquisition_are_not_available():
    """The native installation no longer includes the old SDK wrapper or grants scraping to reviewers."""
    from pathlib import Path

    import backend
    from backend.runtime.business_mediation import (
        DEVELOPMENT_NAMES,
        RESEARCH_NAMES,
        REVIEW_NAMES,
    )

    assert not (Path(backend.__file__).parent / "tools/web/spider_scrape.py").exists()
    name = "researcher_capture_spider"
    assert (
        name in RESEARCH_NAMES
        and name in DEVELOPMENT_NAMES
        and name not in REVIEW_NAMES
    )


async def test_mcp_spider_capture_read_cite_and_reuse_without_refetch(
    research_client, research_store, research_scope, spider_transport, monkeypatch
):
    """Drive real MCP/async HTTP/API/SQLite, including receipt recovery after provider configuration disappears."""
    import anyio
    import httpx
    from mcp import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    from backend.research.async_http_client import AsyncResearcherHTTPClient
    from backend.research.spider import SpiderReader
    from backend.research.stdio_server import BusinessGateway, create_server

    responses, calls = spider_transport
    responses.append(response([PAGE]))
    token = credentials(research_store)["Authorization"].split(" ", 1)[1]
    async with AsyncResearcherHTTPClient(
        "http://127.0.0.1",
        token,
        transport=httpx.ASGITransport(app=research_client.app),
    ) as port:
        server = create_server(BusinessGateway(port))
        async with create_client_server_memory_streams() as (
            client_streams,
            server_streams,
        ):
            async with anyio.create_task_group() as group:
                group.start_soon(
                    server.run, *server_streams, server.create_initialization_options()
                )
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    arguments = {
                        "operation_key": "rendered-page",
                        "url": PAGE["url"],
                        "mode": "browser",
                    }
                    saved = await client.call_tool(
                        "researcher_capture_spider", arguments
                    )
                    assert not saved.isError
                    source_id = saved.structuredContent["source_id"]
                    read = await client.call_tool(
                        "researcher_source_read", {"source_id": source_id}
                    )
                    assert (
                        not read.isError
                        and PAGE["content"] == read.structuredContent["content"]
                    )
                    finding = await client.call_tool(
                        "researcher_finding_record",
                        {
                            "operation_key": "derived-finding",
                            "topic": "Timeout",
                            "content": "The rendered page reports a timeout of five seconds.",
                            "evidence": [
                                {
                                    "source_id": source_id,
                                    "quote": "The timeout is 5 seconds.",
                                }
                            ],
                        },
                    )
                    assert not finding.isError

                    def disabled(**options):
                        """Model an owner disabling this integration after a durable source receipt."""
                        return SpiderReader(api_key="", **options)

                    monkeypatch.setattr(SpiderReader, "from_environment", disabled)
                    retry = await client.call_tool(
                        "researcher_capture_spider", arguments
                    )
                    assert retry.structuredContent == saved.structuredContent
                    conflict = await client.call_tool(
                        "researcher_capture_spider", {**arguments, "mode": "http"}
                    )
                    assert conflict.isError
                    forged = await client.call_tool(
                        "researcher_capture_spider",
                        {**arguments, "max_credits": 999, "api_key": "model"},
                    )
                    assert forged.isError
                group.cancel_scope.cancel()
    assert sum(map(len, calls)) == 1
    assert (
        research_store.read_source(research_scope, source_id)["content"]
        == PAGE["content"]
    )


def test_scope_and_revocation_fence_provider_capture(
    research_client, research_store, spider_transport, monkeypatch, db_conn
):
    """No grant/read-only grant cannot acquire; withdrawal after external I/O cannot commit a late source."""
    from backend.research.spider import SpiderReader

    responses, calls = spider_transport
    url = "/api/research-tools/sources/spider"
    command = {"operation_key": "spider", "url": PAGE["url"]}
    assert research_client.post(url, json=command).status_code == 401
    denied = credentials(research_store, permissions={"sources.read"})
    assert research_client.post(url, headers=denied, json=command).status_code == 403
    allowed = credentials(research_store)
    assert (
        research_client.post(
            url, headers=allowed, json={**command, "project_id": 202}
        ).status_code
        == 422
    )
    assert sum(map(len, calls)) == 0
    original = SpiderReader.fetch

    def revoked(self, *args, **kwargs):
        """Revoke between acquisition and commit while retaining the real provider response parsing."""
        snapshot = original(self, *args, **kwargs)
        scope = research_store.authorize(allowed["Authorization"].split(" ", 1)[1])
        research_store.revoke_grant(scope.grant_id)
        return snapshot

    monkeypatch.setattr(SpiderReader, "fetch", revoked)
    responses.append(response([PAGE]))
    assert research_client.post(url, headers=allowed, json=command).status_code == 403
    assert db_conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0
