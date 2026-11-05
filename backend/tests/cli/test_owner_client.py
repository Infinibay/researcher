"""Terminal owner transport retains exact intent and endpoint scope; HTTP fixtures control transport only, never domain execution."""

import json

import httpx
import pytest


def client_config(tmp_path):
    """Create explicit private synthetic credentials and a journal outside the repository."""
    key = tmp_path / "owner.key"
    key.write_text("synthetic-owner-key-at-least-32-characters")
    key.chmod(0o600)
    return {
        "origin": "http://127.0.0.1:8000",
        "project_id": 101,
        "key_file": key,
        "state_dir": tmp_path / "terminal",
    }


def test_terminal_lost_response_reloads_exact_original_packet_and_receipt(tmp_path):
    """Reopening the client after uncertain admission cannot change the original operation, target or expected receipt."""
    from backend.cli.owner_client import OwnerClient, TerminalError

    config = client_config(tmp_path)
    sent = []

    def handler(request):
        """Simulate reply loss only after receiving the first original action."""
        if request.url.path == "/api/session":
            assert json.loads(request.content)["code"].startswith("synthetic-owner")
            return httpx.Response(
                200,
                json={
                    "authenticated": True,
                    "csrf_token": "fixture-csrf",
                    "endpoint_id": "a" * 64,
                    "workspace_roots": [],
                },
            )
        assert request.headers["X-Researcher-Endpoint"] == "a" * 64
        body = json.loads(request.content)
        sent.append([str(request.url), body])
        if len(sent) == 1:
            raise httpx.ReadError("Original response lost")
        return httpx.Response(
            200,
            json={
                "project_id": 101,
                "run_id": "plan:a",
                **body,
                "tasks": {"one": 11},
                "execution_started": False,
            },
        )

    client = OwnerClient(**config, transport=httpx.MockTransport(handler))
    body = {
        "operation_key": "owner-original",
        "proposal_sha256": "b" * 64,
        "context_version": 1,
    }
    expected = {
        "project_id": 101,
        "run_id": "plan:a",
        "operation_key": body["operation_key"],
        "proposal_sha256": body["proposal_sha256"],
        "context_version": 1,
        "execution_started": False,
    }
    with pytest.raises(TerminalError, match="original|pendiente"):
        client.post(
            "plan.accept",
            "/api/projects/101/runs/plan:a/project-plan/accept",
            body,
            expected,
        )
    client.close()
    reopened = OwnerClient(**config, transport=httpx.MockTransport(handler))
    with pytest.raises(TerminalError, match="pendiente"):
        reopened.post(
            "plan.accept",
            "/api/projects/101/runs/plan:b/project-plan/accept",
            body,
            {**expected, "run_id": "plan:b"},
        )
    assert reopened.retry()["run_id"] == "plan:a"
    assert sent[0] == sent[1]
    assert reopened.pending() is None
    reopened.close()


def test_terminal_changed_database_identity_cannot_replay_pending_work(tmp_path):
    """The same host/port/project IDs do not prove that a replacement database shares the original intent or receipt history."""
    from backend.cli.owner_client import OwnerClient, TerminalError

    config = client_config(tmp_path)
    identity = ["a" * 64]
    posts = []

    def handler(request):
        """Change only endpoint identity across process reconnect, with no new domain response."""
        if request.url.path == "/api/session":
            return httpx.Response(
                200,
                json={
                    "authenticated": True,
                    "csrf_token": "csrf",
                    "endpoint_id": identity[0],
                    "workspace_roots": [],
                },
            )
        posts.append(str(request.url))
        raise httpx.ReadError("Unknown original outcome")

    client = OwnerClient(**config, transport=httpx.MockTransport(handler))
    with pytest.raises(TerminalError):
        client.post(
            "plan.execute",
            "/api/projects/101/runs/plan:a/project-plan/execution",
            {"operation_key": "execute-a", "manifest_sha256": "b" * 64},
            {
                "project_id": 101,
                "plan_run_id": "plan:a",
                "operation_key": "execute-a",
                "manifest_sha256": "b" * 64,
                "status": "active",
            },
        )
    client.close()
    identity[0] = "c" * 64
    other = OwnerClient(**config, transport=httpx.MockTransport(handler))
    with pytest.raises(TerminalError, match="identidad|base"):
        other.retry()
    assert len(posts) == 1
    assert other.pending() is not None
    other.close()


def test_terminal_rejects_foreign_receipt_and_requires_explicit_disposal_of_rejection(
    tmp_path,
):
    """A successful HTTP response from another scope stays uncertain; only a definite owner-visible rejection may be dismissed."""
    from backend.cli.owner_client import OwnerClient, TerminalError

    status = [200]

    def handler(request):
        """Expose a wrong-scope receipt, then a definite unchanged-intent conflict."""
        if request.url.path == "/api/session":
            return httpx.Response(
                200,
                json={
                    "authenticated": True,
                    "csrf_token": "csrf",
                    "endpoint_id": "a" * 64,
                    "workspace_roots": [],
                },
            )
        return httpx.Response(
            status[0],
            json={
                "project_id": 202,
                "operation_key": "note",
                "message": "Thanks",
                "delivery": "recorded",
                "detail": "Original context changed",
            },
        )

    c = OwnerClient(**client_config(tmp_path), transport=httpx.MockTransport(handler))
    with pytest.raises(TerminalError, match="recibo"):
        c.post(
            "note.create",
            "/api/chat/101",
            {
                "operation_key": "note",
                "message": "Thanks",
                "thread_id": None,
                "to_agent": None,
                "to_role": "project_lead",
            },
            {
                "project_id": 101,
                "operation_key": "note",
                "message": "Thanks",
                "delivery": "recorded",
            },
        )
    with pytest.raises(TerminalError):
        c.dismiss_rejected()
    status[0] = 409
    with pytest.raises(TerminalError):
        c.retry()
    status[0] = 200
    with pytest.raises(TerminalError, match="recibo"):
        c.retry()
    with pytest.raises(TerminalError):
        c.dismiss_rejected()
    status[0] = 409
    with pytest.raises(TerminalError):
        c.retry()
    c.dismiss_rejected()
    assert c.pending() is None
    c.close()


def test_terminal_configuration_cannot_send_credentials_to_remote_or_untrusted_state(
    tmp_path,
):
    """Credentials must remain private and belong to the explicit loopback endpoint; wrong configuration cannot reach HTTP."""
    from backend.cli.owner_client import OwnerClient, TerminalError

    config = client_config(tmp_path)
    for url in (
        "http://example.org:8000",
        "http://localhost:8000/path",
        "http://user@localhost:8000",
        "http://localhost:8000?code=secret",
    ):
        with pytest.raises(TerminalError):
            OwnerClient(**{**config, "origin": url})
    config["key_file"].chmod(0o644)
    with pytest.raises(TerminalError):
        OwnerClient(**config)


def test_terminal_finding_page_cannot_change_its_project_scope(tmp_path):
    """The readonly finding view retains its explicit project/cursor and refuses ambiguous or foreign filters before HTTP."""
    from backend.cli.owner_client import OwnerClient, TerminalError

    def handler(request):
        """Expose paired metadata and one explicitly bounded finding index page."""
        if request.url.path == "/api/session":
            return httpx.Response(
                200,
                json={
                    "authenticated": True,
                    "csrf_token": "csrf",
                    "endpoint_id": "a" * 64,
                    "workspace_roots": [],
                },
            )
        assert request.url.path == "/api/findings-index"
        assert request.url.params["project_id"] == "101"
        return httpx.Response(200, json={"items": [], "next_after_id": None})

    client = OwnerClient(
        **client_config(tmp_path), transport=httpx.MockTransport(handler)
    )
    assert client.get("/api/findings-index?project_id=101&after_id=0")["items"] == []
    for path in (
        "/api/findings-index?project_id=202",
        "/api/findings-index?project_id=101&project_id=202",
        "/api/findings-index?project_id=101&scope=global",
    ):
        with pytest.raises(TerminalError):
            client.get(path)
    client.close()


def test_terminal_cwd_is_not_assumed_to_be_the_servers_source_workspace(
    tmp_path, monkeypatch
):
    """Launching from a home-like directory cannot make its private state look like repository data without server evidence."""
    from backend.cli.owner_client import OwnerClient

    config = client_config(tmp_path)
    source = tmp_path / "registered-source"
    source.mkdir()
    monkeypatch.chdir(tmp_path)

    def handler(request):
        """Declare the actual protected source root independently of the terminal cwd."""
        if request.url.path == "/api/session":
            return httpx.Response(
                200,
                json={
                    "authenticated": True,
                    "csrf_token": "csrf",
                    "endpoint_id": "a" * 64,
                    "workspace_roots": [str(source)],
                },
            )
        return httpx.Response(200, json={"id": 101})

    client = OwnerClient(**config, transport=httpx.MockTransport(handler))
    assert client.get("/api/projects/101")["id"] == 101
    client.close()


def test_terminal_pending_state_cannot_be_inside_declared_server_workspace(tmp_path):
    """The source guard uses owner-served workspace evidence and rejects before releasing domain work."""
    from backend.cli.owner_client import OwnerClient, TerminalError

    config = client_config(tmp_path)
    source = tmp_path / "registered-source"
    source.mkdir()
    config["state_dir"] = source / "private-terminal"
    posts = []

    def handler(request):
        """Only pairing may occur before the source/state boundary is checked."""
        if request.url.path == "/api/session":
            return httpx.Response(
                200,
                json={
                    "authenticated": True,
                    "csrf_token": "csrf",
                    "endpoint_id": "a" * 64,
                    "workspace_roots": [str(source)],
                },
            )
        posts.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "project_id": 101,
                "operation_key": "n",
                "message": "note",
                "delivery": "recorded",
                "id": 1,
                "thread_id": "t",
            },
        )

    client = OwnerClient(**config, transport=httpx.MockTransport(handler))
    with pytest.raises(TerminalError, match="repositorio|workspace"):
        client.post(
            "note.create",
            "/api/chat/101",
            {"operation_key": "n", "message": "note"},
            {
                "project_id": 101,
                "operation_key": "n",
                "message": "note",
                "delivery": "recorded",
            },
        )
    assert posts == []
    client.close()


def test_terminal_cannot_resolve_acceptance_without_created_task_identities(tmp_path):
    """An incomplete success response cannot erase the original pending intent or leave the owner without its created graph identities."""
    from backend.cli.owner_client import OwnerClient, TerminalError

    def handler(request):
        """Return matching scope and decision fields but deliberately omit created task identities."""
        if request.url.path == "/api/session":
            return httpx.Response(
                200,
                json={
                    "authenticated": True,
                    "csrf_token": "csrf",
                    "endpoint_id": "a" * 64,
                    "workspace_roots": [],
                },
            )
        return httpx.Response(
            200,
            json={
                "project_id": 101,
                "run_id": "plan:a",
                "operation_key": "accept",
                "proposal_sha256": "b" * 64,
                "context_version": 1,
                "execution_started": False,
            },
        )

    client = OwnerClient(
        **client_config(tmp_path), transport=httpx.MockTransport(handler)
    )
    expected = {
        "project_id": 101,
        "run_id": "plan:a",
        "operation_key": "accept",
        "proposal_sha256": "b" * 64,
        "context_version": 1,
        "execution_started": False,
    }
    with pytest.raises(TerminalError, match="recibo"):
        client.post(
            "plan.accept",
            "/api/projects/101/runs/plan:a/project-plan/accept",
            {
                "operation_key": "accept",
                "proposal_sha256": "b" * 64,
                "context_version": 1,
            },
            expected,
        )
    assert client.pending() is not None
    client.close()
