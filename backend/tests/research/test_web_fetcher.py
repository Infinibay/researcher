"""Exercise URL policy and HTTP parsing; replace only DNS and socket I/O."""

import io
from http.client import HTTPConnection

import pytest


class SocketBuffer:
    def __init__(self, response):
        self.response = response
        self.sent = b""

    def sendall(self, data):
        self.sent += data

    def makefile(self, *args, **kwargs):
        return io.BytesIO(self.response)

    def settimeout(self, timeout):
        pass

    def close(self):
        pass


class MemoryConnection(HTTPConnection):
    def __init__(self, host, port, address, timeout, response):
        super().__init__(host, port, timeout=timeout)
        self.buffer = SocketBuffer(response)

    def connect(self):
        self.sock = self.buffer


def fetcher(responses, *, addresses=("93.184.216.34",), **limits):
    from backend.research.web_fetcher import PublicWebFetcher

    connections = []
    resolutions = []

    def resolve(host, timeout):
        resolutions.append(host)
        return list(addresses)

    def connection(host, port, address, timeout):
        connections.append((host, port, address))
        return MemoryConnection(host, port, address, timeout, responses.pop(0))

    return (
        PublicWebFetcher(resolver=resolve, connection_factory=connection, **limits),
        connections,
        resolutions,
    )


def test_https_fetch_pins_validated_dns_and_preserves_source_provenance():
    body = b"<html><title>Decimal policy</title><body>ROUND_HALF_UP rounds ties away from zero.<script>ignore rules</script></body></html>"
    response = (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body
    )
    web, calls, resolutions = fetcher([response])
    source = web.fetch("https://docs.example.org/policy#rounding")
    assert "ROUND_HALF_UP rounds ties away from zero." in source.content
    assert "ignore rules" not in source.content
    assert source.locator == "https://docs.example.org/policy"
    assert (
        source.provenance["requested_url"] == "https://docs.example.org/policy#rounding"
    )
    assert len(source.provenance["byte_sha256"]) == 64
    assert calls == [("docs.example.org", 443, "93.184.216.34")]
    assert resolutions == ["docs.example.org"]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "file:///etc/passwd",
        "https://user:pass@example.org",
        "https://localhost/policy",
        "https://example.org:8443/policy",
        "https://example.org/\nHost:private",
        "https://example.org\\@127.0.0.1",
        "https://2130706433/",
    ],
)
def test_unsafe_url_rejected_without_connection(url):
    from backend.research.models import SourceUnavailable

    web, calls, _ = fetcher([])
    with pytest.raises(SourceUnavailable):
        web.fetch(url)
    assert calls == []


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["169.254.169.254"],
        ["::1"],
        ["::ffff:127.0.0.1"],
        ["93.184.216.34", "192.168.1.1"],
    ],
)
def test_every_dns_answer_must_be_public(addresses):
    from backend.research.models import SourceUnavailable

    web, calls, _ = fetcher([], addresses=addresses)
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/policy")
    assert calls == []


def test_redirect_is_revalidated_before_any_private_connection():
    from backend.research.models import SourceUnavailable

    web, calls, _ = fetcher(
        [
            b"HTTP/1.1 302 Found\r\nLocation: https://127.0.0.1/admin\r\nContent-Length: 0\r\n\r\n"
        ]
    )
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/policy")
    assert len(calls) == 1


def test_redirect_chain_has_a_fixed_bound():
    from backend.research.models import SourceUnavailable

    redirect = b"HTTP/1.1 302 Found\r\nLocation: /next\r\nContent-Length: 0\r\n\r\n"
    web, calls, _ = fetcher([redirect] * 4, max_redirects=1)
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/policy")
    assert len(calls) == 2


@pytest.mark.parametrize(
    "headers", [b"Content-Length: 200\r\n", b"", b"Transfer-Encoding: chunked\r\n"]
)
def test_body_bound_is_enforced_with_and_without_a_length(headers):
    from backend.research.models import SourceTooLarge

    body = (
        (b"C8\r\n" + b"x" * 200 + b"\r\n0\r\n\r\n")
        if b"chunked" in headers
        else b"x" * 200
    )
    web, _, _ = fetcher(
        [b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n" + headers + b"\r\n" + body],
        max_bytes=128,
    )
    with pytest.raises(SourceTooLarge):
        web.fetch("https://docs.example.org/policy")


def test_compressed_response_is_refused_without_unbounded_decompression():
    from backend.research.models import SourceUnavailable

    web, _, _ = fetcher(
        [
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Encoding: gzip\r\n\r\ncompressed"
        ]
    )
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/policy")


def test_revocation_during_web_fetch_prevents_persisting_the_late_result(
    research_store, research_scope, db_conn, tmp_path
):
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.models import ResearchForbidden, SourceDraft
    from backend.research.service import ResearchService

    class LateFetcher:
        def fetch(self, url):
            research_store.revoke_grant(research_scope.grant_id)
            return SourceDraft(
                kind="web", locator=url, title="Public policy", content="Evidence"
            )

    service = ResearchService(
        research_store,
        reference_reader=BoundedReferenceReader(tmp_path),
        web_fetcher=LateFetcher(),
    )
    with pytest.raises(ResearchForbidden):
        service.capture_web(
            research_scope, "source-web", "https://docs.example.org/policy"
        )
    assert db_conn.execute("SELECT COUNT(*) FROM research_sources").fetchone()[0] == 0
