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


def test_terminal_corrected_graph_keeps_original_adoption_packet_across_restart(tmp_path):
    """A lost graph-revision receipt keeps the inspected snapshot, intended revision and manifest instead of silently adopting newer context."""
    import json

    import httpx

    from backend.cli.owner_client import OwnerClient, TerminalError
    from backend.orchestrator import ProjectOrchestrator
    from backend.tests.cli.test_owner_client import client_config

    posts = []

    def handle(request):
        """Control only transport replies while the terminal persists and validates the original decision."""
        if request.url.path == "/api/session":
            return httpx.Response(200, json={"authenticated": True, "csrf_token": "csrf", "endpoint_id": "a" * 64, "workspace_roots": []})
        if request.method == "GET":
            return httpx.Response(200, json={"project_id": 101, "execution_id": "exec:a", "plan_run_id": "plan:a", "eligible": True, "manifest_sha256": "c" * 64, "snapshot_sha256": "d" * 64, "snapshot": {"previous_revision": 1, "changes": [], "corrected_tasks": [], "retained_results": []}})
        body = json.loads(request.content)
        posts.append(body)
        if len(posts) == 1:
            raise httpx.ReadError("Lost graph adoption response")
        return httpx.Response(200, json={"project_id": 101, "execution_id": "exec:a", "plan_run_id": "plan:a", "authorization_revision": 2, "manifest_sha256": "c" * 64, "status": "paused", "deliveries": {"42": "new:a"}, "retained_results": [], "inference_started": False, **body})

    config = client_config(tmp_path)
    client = OwnerClient(**config, transport=httpx.MockTransport(handle))
    controller = ProjectOrchestrator(project_id=101, owner_client=client)
    with pytest.raises(TerminalError):
        controller.handle_user_message("/reauthorize-plan exec:a")
    controller.handle_user_message("/graph-revision exec:a")
    with pytest.raises(TerminalError):
        controller.handle_user_message("/reauthorize-plan exec:a")
    client.close()
    client = OwnerClient(**config, transport=httpx.MockTransport(handle))
    try:
        result = client.retry()
        assert posts[0] == posts[1]
        assert result["authorization_revision"] == 2
        assert client.pending() is None
    finally:
        client.close()


@pytest.mark.parametrize('receipt_revision', [7, 8])
def test_terminal_code_acceptance_binds_observed_check_policy(tmp_path, receipt_revision):
    """Send the policy actually shown to the owner and retain uncertainty for a receipt identifying another revision."""
    import json

    import httpx

    from backend.cli.owner_client import OwnerClient, TerminalError
    from backend.orchestrator import ProjectOrchestrator
    from backend.tests.cli.test_owner_client import client_config

    reads = []
    posts = []
    observed = {
        'project_id': 101,
        'eligible': True,
        'candidate_current': True,
        'candidate': {'attempt_id': 'author:a', 'context_version': 3},
        'subject_sha256': 'b' * 64,
        'review_sha256': 'c' * 64,
        'requires_acknowledgement': True,
        'project_check_policy': {'revision': 7, 'mode': 'allow_missing'},
    }

    def handle(request):
        """Control transport and receipt identity only; canonical policy guards are tested separately."""
        if request.url.path == '/api/session':
            return httpx.Response(200, json={
                'authenticated': True, 'csrf_token': 'csrf',
                'endpoint_id': 'a' * 64, 'workspace_roots': [],
            })
        if request.method == 'GET':
            reads.append(request.url.path)
            return httpx.Response(200, json=observed)
        body = json.loads(request.content)
        posts.append(body)
        return httpx.Response(200, json={
            **body, 'project_id': 101, 'run_id': 'code:a',
            'task_accepted': True, 'publication_performed': False,
            'check_policy_revision': receipt_revision,
        })

    client = OwnerClient(**client_config(tmp_path), transport=httpx.MockTransport(handle))
    controller = ProjectOrchestrator(project_id=101, owner_client=client)
    try:
        controller.handle_user_message('/code code:a')
        if receipt_revision == 7:
            assert 'no publica' in controller.handle_user_message('/accept-code code:a --ack-limits')
            assert client.pending() is None
        else:
            with pytest.raises(TerminalError):
                controller.handle_user_message('/accept-code code:a --ack-limits')
            pending = client.pending()
            assert pending['body'] == posts[0]
            assert pending['expected']['check_policy_revision'] == 7
        assert posts[0]['check_policy_revision'] == 7
        assert reads == ['/api/projects/101/runs/code:a/code-result']
    finally:
        controller.shutdown()
