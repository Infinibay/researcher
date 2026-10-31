"""Our pinned TLS boundary, against a local server with an ephemeral test CA."""

import socket
import ssl
import subprocess
import threading
import time
from contextlib import closing, contextmanager

import pytest

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


@pytest.fixture
def tls_server(tmp_path):
    key = tmp_path / "server.key"
    cert = tmp_path / "server.crt"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=docs.example.org",
            "-addext",
            "subjectAltName=DNS:docs.example.org",
        ],
        capture_output=True,
        check=True,
        timeout=5,
    )

    @contextmanager
    def serve(*, drip=False):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        names = []
        context.set_servername_callback(lambda conn, name, ctx: names.append(name))

        def respond():
            try:
                with (
                    listener.accept()[0] as raw,
                    context.wrap_socket(raw, server_side=True) as connection,
                ):
                    connection.settimeout(2)
                    request = b""
                    while b"\r\n\r\n" not in request:
                        request += connection.recv(4096)
                    if drip:
                        connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                        for _ in range(12):
                            connection.sendall(b"x")
                            time.sleep(0.05)
                        connection.sendall(
                            b"\r\nContent-Type: text/plain\r\nContent-Length: 8\r\n\r\nEvidence"
                        )
                    else:
                        connection.sendall(
                            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 8\r\n\r\nEvidence"
                        )
            except OSError:
                pass  # Expected when the client rejects TLS or times out.

        worker = threading.Thread(target=respond, daemon=True)
        worker.start()
        try:
            yield (
                listener.getsockname()[1],
                ssl.create_default_context(cafile=str(cert)),
                names,
            )
        finally:
            listener.close()
            worker.join(timeout=2)

    return serve


def test_numeric_pin_keeps_original_hostname_for_tls_and_certificate_verification(
    tls_server,
):
    from backend.research.web_fetcher import PinnedHTTPSConnection

    with tls_server() as (port, context, names):
        with closing(
            PinnedHTTPSConnection(
                "docs.example.org", port, "127.0.0.1", 1, context=context
            )
        ) as conn:
            conn.request("GET", "/")
            response = conn.getresponse()
            assert response.read() == b"Evidence"
        assert names == ["docs.example.org"]


def test_certificate_for_another_hostname_is_not_accepted_when_address_is_pinned(
    tls_server,
):
    from backend.research.web_fetcher import PinnedHTTPSConnection

    with (
        tls_server() as (port, context, _),
        pytest.raises(ssl.SSLCertVerificationError),
        closing(
            PinnedHTTPSConnection(
                "other.example.org", port, "127.0.0.1", 1, context=context
            )
        ) as conn,
    ):
        conn.request("GET", "/")


def test_slow_drip_headers_cannot_extend_the_total_acquisition_deadline(tls_server):
    from backend.research.models import SourceUnavailable
    from backend.research.web_fetcher import PinnedHTTPSConnection, PublicWebFetcher

    with tls_server(drip=True) as (port, context, _):
        web = PublicWebFetcher(
            resolver=lambda host, timeout: ["93.184.216.34"],
            connection_factory=lambda host, unused_port, address, timeout: (
                PinnedHTTPSConnection(host, port, "127.0.0.1", timeout, context=context)
            ),
            timeout_seconds=0.2,
        )
        started = time.monotonic()
        with pytest.raises(SourceUnavailable):
            web.fetch("https://docs.example.org/policy")
        assert time.monotonic() - started < 0.45, (
            "Per-read timeout allowed a slow response to overrun the acquisition deadline"
        )
