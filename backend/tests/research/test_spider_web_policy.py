"""Ensure advanced scraping cannot bypass the host's source acquisition policy."""

import json

import pytest

from backend.research.models import SourceUnavailable
from backend.research.spider import SpiderReader
from backend.research.web_policy import WebAccessPolicy
from backend.tests.research.test_context7 import response as provider_response
from backend.tests.research.test_spider import PAGE
from backend.tests.research.test_web_policy import Wire, response


def reader(wire, **options):
    """Keep real provider and source policy while substituting only public transport."""
    return SpiderReader(
        api_key="synthetic-spider-key",
        resolver=lambda host, timeout: ["93.184.216.34"],
        connection_factory=wire.connect,
        **options,
    )


def test_spider_checks_robots_before_any_billable_provider_request():
    """A disallowed initial target must never reach the provider POST boundary."""
    wire = Wire([response(b"User-agent: Researcher\nDisallow: /\n")])
    with pytest.raises(SourceUnavailable, match="robots"):
        reader(wire).fetch("https://spider-denial.example.org/private")
    assert wire.targets == ["/robots.txt"]
    assert b"Authorization" not in wire.connections[0].buffer.sent


def test_spider_uses_matching_remote_policy_without_leaking_the_provider_key():
    """Keep local decisions and remote assertions separate while binding the same identity."""
    wire = Wire([
        response(b"User-agent: Researcher\nAllow: /app\n"),
        provider_response([PAGE]),
    ])
    source = reader(wire, web_policy=WebAccessPolicy()).fetch(PAGE["url"])
    assert wire.targets == ["/robots.txt", "/scrape"]
    assert b"synthetic-spider-key" not in wire.connections[0].buffer.sent
    header, body = wire.connections[1].buffer.sent.split(b"\r\n\r\n", 1)
    assert b"Authorization: Bearer synthetic-spider-key" in header
    payload = json.loads(body)
    assert payload["respect_robots"] is True
    assert payload["user_agent"] == "Researcher/0.1 source-reader"
    assert source.content == PAGE["content"]
    assert source.provenance["access_policy"][0]["robots_status"] == 200
    assert source.provenance["remote_policy_verified"] is False
    assert "synthetic-spider-key" not in str(source)


def test_spider_and_direct_capture_share_the_request_budget():
    """Advanced scraping must not evade a quota exhausted by ordinary page capture."""
    policy = WebAccessPolicy(requests_per_minute=2)
    wire = Wire([response(status=404), response(b"direct page")])
    assert wire.fetcher(policy=policy).fetch(PAGE["url"]).content == "direct page"
    with pytest.raises(SourceUnavailable, match="frequency"):
        reader(wire, web_policy=policy).fetch(PAGE["url"])
    assert wire.targets == ["/robots.txt", "/app"]


def test_spider_preflight_dns_failure_remains_a_source_error():
    """A later DNS failure cannot escape the typed boundary or trigger provider billing."""
    from backend.network_destinations import PublicNetworkError

    wire = Wire([])
    lookups = []

    def resolve(host, timeout):
        """Allow initial target vetting, then fail the robots DNS exchange."""
        lookups.append(host)
        if len(lookups) == 1:
            return ["93.184.216.34"]
        raise PublicNetworkError("controlled DNS failure")

    spider = SpiderReader(
        api_key="synthetic-spider-key", resolver=resolve,
        connection_factory=wire.connect, web_policy=WebAccessPolicy(),
    )
    with pytest.raises(SourceUnavailable, match="DNS"):
        spider.fetch(PAGE["url"])
    assert wire.targets == []


def test_stop_during_spider_preflight_closes_owned_io_without_calling_provider():
    """The existing Spider operation owns robots reads until physical cleanup completes."""
    import io
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from backend.research.models import ResearchForbidden
    from backend.runtime.live_grants import LiveGrants
    from backend.tests.research.test_web_fetcher import MemoryConnection

    reached, release = Event(), Event()
    body = response(b"User-agent: *\nAllow: /\n")
    calls = []

    class PausedBody(io.BytesIO):
        """Pause real response parsing at the body's owned read boundary."""

        def read1(self, *args):
            """Let Stop arrive before the read finishes, retaining its resource meanwhile."""
            reached.set()
            assert release.wait(3)
            return super().read1(*args)

    def connection(host, port, address, timeout):
        """Keep serialization and HTTP parsing while exposing the blocked read."""
        conn = MemoryConnection(host, port, address, timeout, body)
        conn.buffer.makefile = lambda *args, **kwargs: PausedBody(body)
        calls.append(conn)
        return conn

    gate = LiveGrants()
    gate.activate("spider-capture")
    spider = SpiderReader(
        api_key="synthetic-spider-key", owner=gate, grant_id="spider-capture",
        resolver=lambda host, timeout: ["93.184.216.34"],
        connection_factory=connection, web_policy=WebAccessPolicy(),
    )
    with ThreadPoolExecutor() as executor:
        pending = executor.submit(spider.fetch, PAGE["url"])
        try:
            assert reached.wait(2)
            gate.withdraw("spider-capture")
            with pytest.raises(TimeoutError):
                gate.wait_closed("spider-capture", timeout=0.01)
        finally:
            release.set()
        with pytest.raises(ResearchForbidden):
            pending.result(timeout=2)
    gate.wait_closed("spider-capture", timeout=0.1)
    assert len(calls) == 1 and calls[0].buffer.sent.startswith(b"GET /robots.txt ")
