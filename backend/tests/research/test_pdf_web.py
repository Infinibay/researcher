"""Public PDF acquisition preserves URL policy, byte identity and page citations."""

import hashlib

import pytest

from backend.research.models import SourceUnavailable
from backend.tests.research.pdf_fixtures import pdf_bytes
from backend.tests.research.test_web_fetcher import TransportOnlyPolicy, fetcher


def pdf_response(data, *, mime="application/pdf"):
    """Build a complete HTTP response while retaining real header/body parsing."""
    return (
        b"HTTP/1.1 200 OK\r\nContent-Type: "
        + mime.encode()
        + b"\r\nContent-Length: "
        + str(len(data)).encode()
        + b"\r\n\r\n"
        + data
    )


def test_public_pdf_redirect_keeps_original_bytes_final_url_and_page_offsets():
    """Catch PDF rejection, stale redirect identity and lost page provenance."""
    data = pdf_bytes("Tax rates are fractions.", "Rate: 0.21.")
    web, connections, resolutions = fetcher(
        [
            b"HTTP/1.1 302 Found\r\nLocation: https://papers.example.org/policy.pdf\r\nContent-Length: 0\r\n\r\n",
            pdf_response(data),
        ]
    )
    source = web.fetch("https://docs.example.org/policy")
    assert source.kind == "web"
    assert source.locator == "https://papers.example.org/policy.pdf"
    assert (
        source.content == "[Page 1]\nTax rates are fractions.\n\n[Page 2]\nRate: 0.21."
    )
    assert source.provenance["requested_url"] == "https://docs.example.org/policy"
    assert source.provenance["byte_sha256"] == hashlib.sha256(data).hexdigest()
    assert source.provenance["page_count"] == 2 and source.provenance["redirects"] == 1
    assert source.provenance["execution"]["worker_closed"] is True
    assert resolutions == ["docs.example.org", "papers.example.org"]
    assert [host for host, _, _ in connections] == resolutions


def test_octet_stream_requires_a_pdf_signature_instead_of_decoding_arbitrary_binary():
    """Support download endpoints with generic MIME only when their bytes identify PDF."""
    web, _, _ = fetcher(
        [
            pdf_response(
                pdf_bytes("Verified PDF header"), mime="application/octet-stream"
            )
        ]
    )
    assert (
        "Verified PDF header" in web.fetch("https://docs.example.org/download").content
    )
    web, _, _ = fetcher(
        [pdf_response(b"PK-not-a-PDF", mime="application/octet-stream")]
    )
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/download")


@pytest.mark.parametrize(
    "data", [pdf_bytes(None), pdf_bytes("Private", encrypted=True), b"%PDF-broken"]
)
def test_unreadable_web_pdf_is_rejected_before_a_source_can_be_returned(data):
    """Catch successful/partial sources created from textless, encrypted or malformed PDF."""
    web, _, _ = fetcher([pdf_response(data)])
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/policy.pdf")


def test_withdrawn_web_fetch_retains_ownership_until_blocked_io_closes():
    """A blocking receive cannot disappear from the host's closure accounting after Stop."""
    import io
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from backend.research.models import ResearchForbidden
    from backend.research.web_fetcher import PublicWebFetcher
    from backend.runtime.live_grants import LiveGrants
    from backend.tests.research.test_web_fetcher import MemoryConnection

    reached, released = threading.Event(), threading.Event()
    body = pdf_response(pdf_bytes("Must not be committed after Stop"))

    class PausedBody(io.BytesIO):
        """Pause one actual HTTP body read without replacing URL policy or parsing."""

        def read1(self, *args, **kwargs):
            """Keep the network resource open until the test permits physical cleanup."""
            reached.set()
            assert released.wait(3)
            return super().read1(*args, **kwargs)

    def connection(host, port, address, timeout):
        """Replace only transport I/O with a controlled complete HTTP response."""
        result = MemoryConnection(host, port, address, timeout, body)
        result.buffer.makefile = lambda *args, **kwargs: PausedBody(body)
        return result

    gate = LiveGrants()
    gate.activate("attempt-a")
    web = PublicWebFetcher(
        policy=TransportOnlyPolicy(),
        resolver=lambda host, timeout: ["93.184.216.34"],
        connection_factory=connection,
        owner=gate,
        grant_id="attempt-a",
    )
    with ThreadPoolExecutor() as executor:
        pending = executor.submit(web.fetch, "https://docs.example.org/policy.pdf")
        try:
            assert reached.wait(2)
            gate.withdraw("attempt-a")
            with pytest.raises(TimeoutError):
                gate.wait_closed("attempt-a", timeout=0.01)
        finally:
            released.set()
        with pytest.raises(ResearchForbidden):
            pending.result(timeout=2)
    gate.wait_closed("attempt-a", timeout=0.1)


def test_pdf_served_as_plain_text_is_not_misrepresented_as_decoded_text():
    """Catch binary PDF bytes being recorded as an ordinary text document on MIME mismatch."""
    web, _, _ = fetcher([pdf_response(pdf_bytes("Input"), mime="text/plain")])
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/mislabeled")


def test_complete_pdf_bytes_do_not_hide_an_incomplete_http_response():
    """Reject a valid older PDF prefix when HTTP promised additional revision bytes."""
    data = pdf_bytes("Valid prefix; the promised trailing revision is missing")
    response = pdf_response(data).replace(
        b"Content-Length: " + str(len(data)).encode(),
        b"Content-Length: " + str(len(data) + 100).encode(),
        1,
    )
    web, _, _ = fetcher([response])
    with pytest.raises(SourceUnavailable):
        web.fetch("https://docs.example.org/incomplete.pdf")


def test_default_pdf_parser_inherits_the_web_fetch_owners_cancellation(
    monkeypatch, tmp_path
):
    """A caller providing only web ownership must not receive an uncancellable default parser."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    from backend.research.models import ResearchForbidden
    from backend.runtime.live_grants import LiveGrants
    from backend.tests.research.test_parser_process import worker_fault

    marker = worker_fault(monkeypatch, tmp_path, "while True: pass")
    gate = LiveGrants()
    gate.activate("attempt-a")
    web, _, _ = fetcher(
        [pdf_response(pdf_bytes("Input"))], owner=gate, grant_id="attempt-a"
    )
    with ThreadPoolExecutor() as executor:
        pending = executor.submit(web.fetch, "https://docs.example.org/policy.pdf")
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists()
        gate.withdraw("attempt-a")
        gate.wait_closed("attempt-a", timeout=0.5)
        with pytest.raises(ResearchForbidden):
            pending.result(timeout=0.5)
