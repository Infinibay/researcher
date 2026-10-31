import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


@pytest.fixture
def tool_http_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.endswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", "/api/research-tools/landed")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path.endswith("/conflict"):
                body = json.dumps(
                    {
                        "detail": [
                            {
                                "loc": ["body", "finding_ids"],
                                "msg": "Invalid finding identity",
                                "input": "test-secret-token",
                            }
                        ]
                    }
                ).encode()
                status = 409
            elif self.path.endswith("/large"):
                body = b"x" * 2000
                status = 200
            else:
                body = json.dumps(
                    {
                        "authorized": self.headers.get("Authorization")
                        == "Bearer test-secret-token",
                        "path": self.path,
                    }
                ).encode()
                status = 200
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_tool_http_uses_explicit_loopback_origin_and_does_not_inherit_proxies(
    tool_http_server, monkeypatch
):
    from backend.research.http_client import ResearcherHTTPClient

    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("no_proxy", "")
    client = ResearcherHTTPClient(tool_http_server, "test-secret-token")
    result = client.request("GET", "/references")
    assert result == {"authorized": True, "path": "/api/research-tools/references"}


def test_tool_http_does_not_forward_bearer_credentials_on_redirect(tool_http_server):
    from backend.research.http_client import ResearcherClientError, ResearcherHTTPClient

    client = ResearcherHTTPClient(tool_http_server, "test-secret-token")
    with pytest.raises(ResearcherClientError) as error:
        client.request("GET", "/redirect")
    assert error.value.status == 302


def test_tool_errors_are_not_success_results_or_echoes_of_validation_input(
    tool_http_server,
):
    from backend.research.http_client import ResearcherClientError, ResearcherHTTPClient

    client = ResearcherHTTPClient(tool_http_server, "test-secret-token")
    with pytest.raises(ResearcherClientError) as error:
        client.request("GET", "/conflict")
    assert error.value.status == 409
    assert "finding_ids" in str(error.value)
    assert "test-secret-token" not in str(error.value)


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.org",
        "http://localhost:8000",
        "http://user:password@127.0.0.1:8000",
        "http://127.0.0.1:8000/other",
        "file:///tmp/backend",
    ],
)
def test_backend_origin_must_be_explicit_numeric_loopback(origin):
    from backend.research.http_client import ResearcherClientError, ResearcherHTTPClient

    with pytest.raises(ResearcherClientError):
        ResearcherHTTPClient(origin, "test-secret-token")


def test_tool_response_limit_fails_instead_of_returning_partial_json(tool_http_server):
    from backend.research.http_client import ResearcherClientError, ResearcherHTTPClient

    with pytest.raises(ResearcherClientError):
        ResearcherHTTPClient(
            tool_http_server, "test-secret-token", response_limit=128
        ).request("GET", "/large")


def test_generic_adapter_cannot_target_legacy_sql_or_other_routes(tool_http_server):
    from backend.research.http_client import ResearcherClientError, ResearcherHTTPClient

    with pytest.raises(ResearcherClientError):
        ResearcherHTTPClient(tool_http_server, "test-secret-token").request(
            "GET", "/../internal/sql"
        )
