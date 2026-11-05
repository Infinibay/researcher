"""Terminal commands are owner intent and evidence presentation, not another agent engine or a prose completion parser."""

import pytest


def test_terminal_continuation_retains_observed_snapshot_after_reply_loss(tmp_path):
    """The terminal cannot silently refresh successor permission; its original packet survives process restart and receipt recovery."""
    import json

    import httpx

    from backend.cli.owner_client import OwnerClient, TerminalError
    from backend.orchestrator import ProjectOrchestrator
    from backend.tests.cli.test_owner_client import client_config

    posts = []
    snapshot = "d" * 64

    def handle(request):
        """Control only transport observations and lost replies, leaving retained-packet validation real."""
        if request.url.path == "/api/session":
            return httpx.Response(200, json={"authenticated": True, "csrf_token": "csrf", "endpoint_id": "a" * 64, "workspace_roots": []})
        if request.method == "GET":
            return httpx.Response(200, json={"project_id": 101, "execution_id": "exec:a", "delivery_id": "work:a", "eligible": True, "snapshot_sha256": snapshot, "snapshot": {"previous_run": {"run_id": "old:a"}}, "dispatch_status": "paused"})
        body = json.loads(request.content)
        posts.append(body)
        if len(posts) == 1:
            raise httpx.ReadError("Lost original continuation reply")
        return httpx.Response(200, json={"project_id": 101, "execution_id": "exec:a", "predecessor_delivery_id": "work:a", "previous_run_id": "old:a", "delivery_id": "work:b", "inference_started": False, **body})

    config = client_config(tmp_path)
    client = OwnerClient(**config, transport=httpx.MockTransport(handle))
    controller = ProjectOrchestrator(project_id=101, owner_client=client)
    with pytest.raises(TerminalError):
        controller.handle_user_message("/continue-delivery exec:a work:a")
    controller.handle_user_message("/continuation exec:a work:a")
    snapshot = "e" * 64
    with pytest.raises(TerminalError):
        controller.handle_user_message("/continue-delivery exec:a work:a")
    client.close()
    client = OwnerClient(**config, transport=httpx.MockTransport(handle))
    try:
        receipt = client.retry()
        assert posts[0] == posts[1]
        assert receipt["snapshot_sha256"] == "d" * 64
        assert receipt["delivery_id"] == "work:b"
        assert client.pending() is None
    finally:
        client.close()


def test_terminal_plan_and_acceptance_use_exact_observed_versions(tmp_path):
    """Acceptance uses the proposal offered earlier, without silently fetching a newer hash or activating its children."""
    import httpx

    from backend.cli.owner_client import OwnerClient
    from backend.orchestrator import ProjectOrchestrator
    from backend.tests.cli.test_owner_client import client_config

    reads = []
    posts = []
    proposal = {
        "project_id": 101,
        "task_id": 42,
        "run_id": "plan:a",
        "context_version": 1,
        "eligible": True,
        "acceptance": None,
        "snapshot": {
            "instruction_origin": "owner_message",
            "source_origins": {"owner_request": "owner_message"},
        },
        "proposal": {
            "proposal_sha256": "b" * 64,
            "draft": {
                "title": "Evidence before change",
                "rationale": "Measure first.",
                "assumptions": ["The source is representative."],
                "basis": [
                    {"source": "owner_request", "quote": "Investigate this behavior"}
                ],
                "epics": [],
                "tasks": [
                    {
                        "key": "inspect",
                        "title": "Inspect",
                        "description": "Read source",
                        "acceptance_criteria": "Citations",
                        "depends_on": [],
                        "type": "research",
                    }
                ],
            },
        },
    }

    def handle(request):
        """Expose a real owner HTTP transport boundary with controlled JSON data only."""
        import json

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
        if request.method == "GET":
            reads.append(request.url.path)
            return httpx.Response(200, json=proposal)
        body = json.loads(request.content)
        posts.append(body)
        return httpx.Response(
            200,
            json={
                "project_id": 101,
                "task_id": 42,
                "run_id": "plan:a",
                **body,
                "tasks": {"inspect": 43},
                "execution_started": False,
            },
        )

    client = OwnerClient(
        **client_config(tmp_path), transport=httpx.MockTransport(handle)
    )
    controller = ProjectOrchestrator(project_id=101, owner_client=client)
    shown = controller.handle_user_message("/proposal plan:a")
    assert "representative" in shown and "Investigate this behavior" in shown
    assert "b" * 64 in shown
    proposal["proposal"]["proposal_sha256"] = "c" * 64
    result = controller.handle_user_message("/accept-plan plan:a")
    assert posts[0]["proposal_sha256"] == "b" * 64
    assert len(reads) == 1
    assert "pendientes" in result
    controller.shutdown()


def test_terminal_requires_observation_and_has_no_local_task_completion(tmp_path):
    """A task cannot become DONE from returned prose; unknown commands and missing explicit preview perform no mutation."""
    import httpx

    from backend.cli.owner_client import OwnerClient, TerminalError
    from backend.orchestrator import ProjectOrchestrator
    from backend.tests.cli.test_owner_client import client_config

    calls = []

    def handle(request):
        """No action in this test should reach transport."""
        calls.append(request.url.path)
        raise AssertionError("No observed proposal/manifest")

    client = OwnerClient(
        **client_config(tmp_path), transport=httpx.MockTransport(handle)
    )
    controller = ProjectOrchestrator(project_id=101, owner_client=client)
    with pytest.raises(TerminalError):
        controller.handle_user_message("/accept-plan plan:a")
    with pytest.raises(TerminalError):
        controller.handle_user_message("/execute-plan plan:a")
    with pytest.raises(TerminalError):
        controller.handle_user_message("/unknown")
    assert calls == []
    assert not hasattr(controller, "tasks")
    controller.shutdown()
