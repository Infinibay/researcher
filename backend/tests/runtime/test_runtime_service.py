"""Product coordinator with real persistence; only generative inference is doubled."""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest

from backend.runtime.codex_session import ExecutionLimits, NativeTurnResult
from backend.runtime.contracts import RunConflict


class ControlledInference:
    """No model. Startup/run observations mirror the production factory port."""

    def __init__(self, setup):
        self.setup = setup
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.interrupted = asyncio.Event()
        self.closed = asyncio.Event()
        self.prompts = []
        self.model = "fixture-model"
        self.catalog = []
        self.developer_instructions = (
            "Controlled host instructions, not a model response."
        )

    @asynccontextmanager
    async def open(self, *, workspace, tool_token, active, limits, peer_owner=None):
        c = self.setup.c
        # Production mint/bind/live-registration has happened before delivery.
        scope = c.research.authorize(tool_token)
        assert scope.project_id == 101 and scope.task_id == 1001
        assert workspace == self.setup.workspace
        peer = self
        self.thread_id = "controlled-" + str(len(self.prompts))
        self.catalog_hash = hashlib.sha256(
            json.dumps(
                self.catalog, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
        self.active = active
        self.scope = scope
        self.peer_owner = peer_owner
        try:
            yield peer
        finally:
            self.closed.set()
            self.peers_closed = True

    async def run(self, prompt, *, on_started, on_event):
        self.prompts.append(prompt)
        c = self.setup.c
        attempt_id = c.conn.execute(
            "SELECT runtime_attempt_id FROM tool_grants WHERE id=?",
            (self.scope.grant_id,),
        ).fetchone()[0]
        dispatch = c.conn.execute(
            "SELECT * FROM runtime_inference_dispatches WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        assert dispatch["status"] == "reserved", (
            "Native dispatch preceded durable reservation"
        )
        assert (
            c.conn.execute(
                "SELECT thread_id FROM runtime_attempts WHERE id=?", (attempt_id,)
            ).fetchone()[0]
            == self.thread_id
        )
        await on_started(self.thread_id, "turn-a")
        self.started.set()
        await self.release.wait()
        return NativeTurnResult(
            self.thread_id,
            "turn-a",
            "interrupted" if self.interrupted.is_set() else "completed",
            "Proposal with evidence; acceptance remains pending.",
            0,
            None,
            None,
        )

    async def cancel(self):
        self.interrupted.set()
        self.release.set()


def coordinator(setup, runtime, **kwargs):
    from backend.runtime.live_grants import LiveGrants
    from backend.runtime.service import RuntimeService, WorkspaceRegistry

    return RuntimeService(
        setup.c.store,
        setup.c.research,
        LiveGrants(),
        runtime,
        workspaces=WorkspaceRegistry(setup.c.database, setup.root),
        control_root=setup.control,
        limits=ExecutionLimits(5, 3, 1, 10, 100),
        **kwargs,
    )


async def test_question_parks_only_after_peers_close_and_answer_never_dispatches(
    service_setup,
):
    from backend.runtime.questions import Question, QuestionSet

    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        receipt = service.questions.ask(
            native.scope,
            "base-question",
            QuestionSet((Question("base", "¿Base 100 o 200?"),)),
        )
        assert s.c.store.get(101, run.run_id).status == "cancelling"
        service.question_requested(run.run_id, receipt["attempt_id"])
        await service.wait(run.run_id)
        assert native.closed.is_set() and native.interrupted.is_set()
        assert s.c.store.get(101, run.run_id).status == "waiting_input"
        version = service.questions.answer(
            project_id=101,
            task_id=1001,
            request_id=receipt["request_id"],
            expected_version=1,
            operation_key="answer-base",
            answers={"base": "200"},
        )
        assert version == 2 and len(native.prompts) == 1
        assert s.c.store.get(101, run.run_id).status == "superseded"


async def test_question_with_unconfirmed_peer_close_stays_uncertain(service_setup):
    from backend.runtime.questions import Question, QuestionSet

    class UncertainPeer(ControlledInference):
        @asynccontextmanager
        async def open(self, **kwargs):
            async with super().open(**kwargs) as peer:
                yield peer
            self.peers_closed = False

    s = service_setup
    native = UncertainPeer(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        receipt = service.questions.ask(
            native.scope, "ask", QuestionSet((Question("base", "¿Qué base?"),))
        )
        service.question_requested(run.run_id, receipt["attempt_id"])
        await service.wait(run.run_id)
        assert s.c.store.get(101, run.run_id).status == "reconciling"
        with pytest.raises(RunConflict):
            service.questions.answer(
                project_id=101,
                task_id=1001,
                request_id=receipt["request_id"],
                expected_version=1,
                operation_key="answer",
                answers={"base": "200"},
            )


async def test_question_http_tool_stops_its_bound_peer_and_rejects_scope_arguments(
    service_setup,
):
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.research_dependencies import ResearchContext, get_research_context

    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="question-tool-owner-key-32-characters"),
        runtime_service=service,
    )
    # This fixture's clock is deterministic; production dependency still verifies
    # the bearer and grant against the same real DB and live authority gate.
    app.dependency_overrides[get_research_context] = lambda: ResearchContext(
        s.c.research, native.scope, None
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client,
    ):
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        body = {
            "operation_key": "ask",
            "questions": [
                {
                    "id": "base",
                    "question": "¿Qué base?",
                    "why_needed": "Cambia el importe calculado",
                    "options": ["100", "200"],
                }
            ],
        }
        headers = {"Authorization": "Bearer fixture"}
        assert (
            await client.post(
                "/api/research-tools/questions",
                headers=headers,
                json={**body, "project_id": 202},
            )
        ).status_code == 422
        response = await client.post(
            "/api/research-tools/questions", headers=headers, json=body
        )
        assert response.status_code == 201, response.text
        await service.wait(run.run_id)
        assert native.interrupted.is_set()
        assert not service.live_grants.allows(native.scope.grant_id)
        assert s.c.store.get(101, run.run_id).status == "waiting_input"


async def test_product_admission_proposal_and_retry_never_mark_task_done(service_setup):
    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        assert native.peer_owner is not None
        assert (await service.submit(s.c.spec)).run_id == run.run_id
        native.release.set()
        await service.wait(run.run_id)
        result = s.c.store.get(101, run.run_id)
        assert result.status == "needs_review"
        assert result.result["summary"].startswith("Proposal")
        assert len(native.prompts) == 1
        assert native.closed.is_set()
        assert (
            s.c.conn.execute("SELECT status FROM tasks WHERE id=1001").fetchone()[0]
            == "in_progress"
        )
        assert (
            s.c.conn.execute("SELECT revoked_at FROM tool_grants").fetchone()[0]
            is not None
        )
        assert (
            s.c.conn.execute(
                "SELECT observed_tokens FROM runtime_inference_dispatches"
            ).fetchone()[0]
            is None
        )


async def test_native_error_withdraws_tool_authority_before_slow_peer_teardown(
    service_setup,
):
    from backend.research.models import ResearchForbidden, SourceDraft

    class SlowFailure(ControlledInference):
        def __init__(self, setup):
            super().__init__(setup)
            self.tearing_down = asyncio.Event()
            self.close_release = asyncio.Event()

        @asynccontextmanager
        async def open(self, **kwargs):
            async with super().open(**kwargs) as peer:
                try:
                    yield peer
                finally:
                    self.tearing_down.set()
                    await self.close_release.wait()

        async def run(self, *args, **kwargs):
            await super().run(*args, **kwargs)
            raise RuntimeError("Simulated native failure")

    setup = service_setup
    native = SlowFailure(setup)
    service = coordinator(setup, native)
    setup.c.research.runtime_authority = service.live_grants.allows
    async with service:
        run = await service.submit(setup.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        native.release.set()
        await asyncio.wait_for(native.tearing_down.wait(), 2)
        try:
            assert not service.live_grants.allows(native.scope.grant_id)
            with pytest.raises(ResearchForbidden):
                setup.c.research.capture_source(
                    native.scope,
                    "late-during-teardown",
                    SourceDraft("web", "https://example.org", "Late", "No late effect"),
                    intent={},
                )
        finally:
            native.close_release.set()
        await service.wait(run.run_id)


async def test_failed_peer_preparation_does_not_leave_an_unrecoverable_claim(
    service_setup, monkeypatch
):
    from backend.runtime.peer_registry import PeerRegistry

    setup = service_setup
    native = ControlledInference(setup)
    service = coordinator(setup, native)
    original = PeerRegistry._prepare

    def fail_second(registry, conn, lease, kind):
        if kind == "native":
            raise RuntimeError("Injected peer preparation failure")
        return original(registry, conn, lease, kind)

    monkeypatch.setattr(PeerRegistry, "_prepare", fail_second)
    async with service:
        run = await service.submit(setup.c.spec)
        await service.wait(run.run_id)
        row = setup.c.store.get(101, run.run_id)
        assert row.status == "queued" and row.attempt_id is None
        assert (
            setup.c.conn.execute("SELECT COUNT(*) FROM runtime_attempts").fetchone()[0]
            == 0
        )
        assert (
            setup.c.conn.execute("SELECT COUNT(*) FROM runtime_peers").fetchone()[0]
            == 0
        )
        assert native.prompts == []
        assert (await service.stop(101, run.run_id)).status == "cancelled"


async def test_native_failure_is_reconciled_after_peers_close_and_preserves_usage(
    service_setup,
):
    class FailedInference(ControlledInference):
        async def run(self, prompt, *, on_started, on_event):
            await on_started(self.thread_id, "turn-a")
            for total in (40, 200, 10):
                await on_event(
                    {
                        "method": "thread/tokenUsage/updated",
                        "params": {
                            "threadId": self.thread_id,
                            "tokenUsage": {"total": {"totalTokens": total}},
                        },
                    }
                )
            return NativeTurnResult(
                self.thread_id,
                "turn-a",
                "failed",
                "No proposal: native failure.",
                0,
                10,
                {"code": "failure"},
            )

    s = service_setup
    service = coordinator(s, FailedInference(s))
    async with service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        view = s.c.store.get(101, run.run_id)
        assert view.status == "failed"
        assert view.result["native_status"] == "failed"
        assert (
            s.c.conn.execute(
                "SELECT observed_tokens FROM runtime_inference_dispatches"
            ).fetchone()[0]
            == 200
        )
        # Same request remains the same failed result; no hidden retry.
        assert (await service.submit(s.c.spec)).status == "failed"


async def test_stop_physically_interrupts_before_blocked_sqlite_intent_commits(
    service_setup,
):
    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        s.c.conn.execute("BEGIN IMMEDIATE")
        stop = asyncio.create_task(service.stop(101, run.run_id))
        try:
            await asyncio.wait_for(native.interrupted.wait(), 1)
            assert not service.live_grants.allows(native.scope.grant_id)
            assert not native.active()
            assert not stop.done(), "Durable Stop must wait for the real SQLite writer"
        finally:
            s.c.conn.rollback()
        await stop
        await service.wait(run.run_id)
        assert s.c.store.get(101, run.run_id).status == "cancelled"


async def test_peer_teardown_uncertainty_cannot_release_a_run_for_another_dispatch(
    service_setup,
):
    class UncertainClose(ControlledInference):
        @asynccontextmanager
        async def open(self, **kwargs):
            async with super().open(**kwargs) as peer:
                yield peer
            self.peers_closed = False
            raise RuntimeError("Peer closure was not confirmed")

    s = service_setup
    native = UncertainClose(s)
    native.release.set()
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await service.wait(run.run_id)
        view = s.c.store.get(101, run.run_id)
        assert view.status == "reconciling"
        assert view.result["summary"].startswith("Proposal")
        assert (
            s.c.conn.execute(
                "SELECT status FROM runtime_inference_dispatches"
            ).fetchone()[0]
            == "unknown"
        )
        assert not service.live_grants.allows(native.scope.grant_id)
        with pytest.raises(RunConflict):
            await service.submit(replace(s.c.spec, operation_key="unsafe-retry"))


async def test_stop_disconnection_is_terminal_only_with_peer_closure_receipts(
    service_setup,
):
    from backend.runtime.codex_rpc import RpcDisconnected

    class DisconnectOnStop(ControlledInference):
        async def run(self, prompt, *, on_started, on_event):
            await on_started(self.thread_id, "turn-a")
            self.started.set()
            await self.release.wait()
            raise RpcDisconnected("Owned peer was retired by Stop")

    s = service_setup
    native = DisconnectOnStop(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        await service.stop(101, run.run_id)
        await service.wait(run.run_id)
        assert native.peers_closed
        assert s.c.store.get(101, run.run_id).status == "cancelled"


async def test_correction_is_versioned_and_next_explicit_run_receives_it(service_setup):
    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        version = await service.correct(
            project_id=101,
            task_id=1001,
            expected_version=1,
            operation_key="correction",
            statement="Use yearly totals, not monthly.",
            source_kind="user_example",
            source_reference="owner-message-42",
        )
        await service.wait(run.run_id)
        assert version == 2
        assert s.c.store.get(101, run.run_id).status == "superseded"
        # An explicit request is required; correction does not silently infer again.
        assert len(native.prompts) == 1
        native2 = ControlledInference(s)
        native2.release.set()
        service.runtime = native2
        next_run = await service.submit(
            replace(s.c.spec, context_version=2, operation_key="revised")
        )
        await service.wait(next_run.run_id)
        context = json.loads(native2.prompts[0])
        assert context["context_version"] == 2
        assert context["corrections"][0]["source_kind"] == "user_example"
        assert "yearly totals" in context["corrections"][0]["statement"]


async def test_database_has_one_host_owner_and_shutdown_releases_it(service_setup):
    s = service_setup
    one = coordinator(s, ControlledInference(s))
    two = coordinator(s, ControlledInference(s))
    async with one:
        with pytest.raises(RunConflict, match="owner"):
            async with two:
                pass
    async with two:
        pass


async def test_cancelled_startup_does_not_leak_the_exclusive_owner_lock(
    service_setup, monkeypatch
):
    from threading import Event

    s = service_setup
    entered = Event()
    recover = s.c.store.recover_owners

    def recovering(owner):
        entered.set()
        return recover(owner)

    monkeypatch.setattr(s.c.store, "recover_owners", recovering)
    one = coordinator(s, ControlledInference(s))
    two = coordinator(s, ControlledInference(s))
    s.c.conn.execute("BEGIN IMMEDIATE")
    entering = asyncio.create_task(one.__aenter__())
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        entering.cancel()
    finally:
        s.c.conn.rollback()
    with pytest.raises(asyncio.CancelledError):
        await entering
    async with two:
        pass


async def test_invalid_correction_does_not_interrupt_current_work(service_setup):
    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        with pytest.raises(ValueError):
            await service.correct(
                project_id=101,
                task_id=1001,
                expected_version=1,
                operation_key="invalid",
                statement=" ",
                source_kind="user_message",
                source_reference="owner",
            )
        assert native.active()
        assert not native.interrupted.is_set()
        await service.stop(101, run.run_id)
        await service.wait(run.run_id)


async def test_workspace_selection_requires_disambiguation_and_refuses_other_projects(
    service_setup,
):
    from backend.runtime.service import WorkspaceRegistry

    s = service_setup
    other = s.root / "other"
    other.mkdir()
    s.c.conn.execute(
        "INSERT INTO repositories(id,project_id,name,local_path) VALUES(12,101,'other',?)",
        (str(other),),
    )
    s.c.conn.commit()
    registry = WorkspaceRegistry(s.c.database, s.root)
    with pytest.raises(RunConflict, match="repository"):
        registry.select(101)
    assert registry.select(101, 11) == s.workspace
    with pytest.raises(LookupError):
        registry.select(202, 11)
    s.c.conn.execute("UPDATE repositories SET project_id=202 WHERE id=12")
    s.c.conn.execute(
        "UPDATE repositories SET local_path=? WHERE id=12", (str(s.workspace),)
    )
    s.c.conn.commit()
    with pytest.raises(RunConflict, match="shared"):
        registry.select(101, 11)


async def test_authenticated_api_owns_admission_stop_correction_and_ascending_history(
    service_setup,
):
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="api-owner-fixture-with-32-characters"),
        runtime_service=service,
    )
    # The same gate protects the HTTP tools and runtime-owned MCP credentials.
    assert app.state.live_grants is service.live_grants
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client,
    ):
        body = {
            "operation_key": "api-start",
            "context_version": 1,
            "request": "Explain the policy with an example.",
        }
        path = "/api/projects/101/tasks/1001/runs"
        assert (await client.post(path, json=body)).status_code == 401
        paired = await client.post(
            "/api/session",
            json={"code": "api-owner-fixture-with-32-characters"},
            headers={"X-Researcher-Client": "web"},
        )
        assert paired.status_code == 200
        assert (await client.post(path, json=body)).status_code == 403
        client.headers["X-Researcher-CSRF"] = paired.json()["csrf_token"]
        response = await client.post(path, json=body)
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]
        await asyncio.wait_for(native.started.wait(), 2)
        # Agents' bearer credentials do not authorize human control endpoints.
        anonymous = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        )
        try:
            assert (
                await anonymous.get(
                    f"/api/projects/101/runs/{run_id}",
                    headers={"Authorization": "Bearer " + "x" * 40},
                )
            ).status_code == 401
        finally:
            await anonymous.aclose()
        assert (await client.get(f"/api/projects/202/runs/{run_id}")).status_code == 404
        stop = await client.post(f"/api/projects/101/runs/{run_id}/stop")
        assert stop.status_code == 202
        await service.wait(run_id)
        assert (await client.get(f"/api/projects/101/runs/{run_id}")).json()[
            "status"
        ] == "cancelled"
        correction = await client.post(
            "/api/projects/101/tasks/1001/context-corrections",
            json={
                "operation_key": "api-correction",
                "expected_version": 1,
                "statement": "For example, compare yearly values.",
                "source_kind": "user_example",
            },
        )
        assert correction.status_code == 200, correction.text
        assert correction.json() == {
            "context_version": 2,
            "application": "recorded_for_next_run",
            "inference_started": False,
        }
        after = 0
        ids = []
        while True:
            page = (
                await client.get(
                    f"/api/projects/101/runtime-events?after_id={after}&limit=2"
                )
            ).json()
            ids.extend(event["event_id"] for event in page["events"])
            if not page["has_more"]:
                break
            after = page["next_after_id"]
        assert len(ids) >= 5 and ids == sorted(set(ids))


async def test_native_chat_uses_the_selected_thread_and_never_legacy_autonomy(
    service_setup, monkeypatch
):
    import httpx

    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app

    def legacy_dispatch(**kwargs):
        raise AssertionError("Native conversation must not activate legacy autonomy")

    monkeypatch.setattr("backend.autonomy.events.create_message_event", legacy_dispatch)
    s = service_setup
    native = ControlledInference(s)
    service = coordinator(s, native)
    app = create_app(
        access=LocalAccess(pairing_key="native-chat-owner-key-at-least-32-characters"),
        runtime_service=service,
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as owner,
    ):
        paired = await owner.post(
            "/api/session",
            json={"code": "native-chat-owner-key-at-least-32-characters"},
            headers={"X-Researcher-Client": "web"},
        )
        owner.headers["X-Researcher-CSRF"] = paired.json()["csrf_token"]
        body = {
            "operation_key": "native-chat",
            "task_id": 1001,
            "context_version": 1,
            "thread_id": "owner-conversation",
            "message": "Contrast the source and show a simple example.",
        }
        response = await owner.post("/api/chat/101/instructions", json=body)
        assert response.status_code == 202, response.text
        await asyncio.wait_for(native.started.wait(), 2)
        duplicate = await owner.post("/api/chat/101/instructions", json=body)
        assert duplicate.status_code == 202
        assert duplicate.json()["message"]["id"] == response.json()["message"]["id"]
        native.release.set()
        run_id = response.json()["run"]["run_id"]
        await service.wait(run_id)
        messages = (await owner.get("/api/chat/101/threads/owner-conversation")).json()
        assert len(messages) == 2 and messages[1]["runtime_run_id"] == run_id
        assert messages[1]["runtime_status"] == "needs_review"
        assert messages[1]["context_version"] == 1
        assert messages[0]["task_id"] == 1001
        workspace = (await owner.get("/api/projects/101/tasks/1001/workspace")).json()
        assert workspace["runs"][0]["conversation_thread_id"] == "owner-conversation"
        assert len(native.prompts) == 1


async def test_instruction_receipt_survives_a_later_context_correction(service_setup):
    s = service_setup
    native = ControlledInference(s)
    native.release.set()
    service = coordinator(s, native)
    async with service:
        run = await service.submit(s.c.spec, conversation_thread="retry-thread")
        await service.wait(run.run_id)
        await service.correct(
            project_id=101,
            task_id=1001,
            expected_version=1,
            operation_key="updated",
            statement="Use a different example.",
            source_kind="user_example",
            source_reference="user-message:2",
        )
        receipt = await service.submit(s.c.spec, conversation_thread="retry-thread")
        assert receipt.run_id == run.run_id and receipt.status == "superseded"
        assert len(native.prompts) == 1


async def test_old_correction_receipt_does_not_interrupt_new_context_work(
    service_setup,
):
    s = service_setup
    first = ControlledInference(s)
    service = coordinator(s, first)
    command = {
        "project_id": 101,
        "task_id": 1001,
        "expected_version": 1,
        "operation_key": "example-correction",
        "statement": "Use 200 in the example.",
        "source_kind": "user_example",
        "source_reference": "user-message:2",
    }
    async with service:
        run = await service.submit(s.c.spec)
        await asyncio.wait_for(first.started.wait(), 2)
        assert await service.correct(**command) == 2
        await service.wait(run.run_id)
        second = ControlledInference(s)
        service.runtime = second
        revised = await service.submit(
            replace(s.c.spec, context_version=2, operation_key="next")
        )
        await asyncio.wait_for(second.started.wait(), 2)
        assert await service.correct(**command) == 2
        assert second.active() and not second.interrupted.is_set()
        await service.stop(101, revised.run_id)
        await service.wait(revised.run_id)


async def test_native_completion_waits_for_registered_tool_worker_closure(
    service_setup,
):
    """A native completion cannot make a proposal ready while its parser still owns work."""
    setup = service_setup
    native = ControlledInference(setup)
    service = coordinator(setup, native)
    async with service:
        run = await service.submit(setup.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        with service.live_grants.operation(native.scope.grant_id) as cancelled:
            native.release.set()
            assert await asyncio.to_thread(cancelled.wait, 2)
            waiting = asyncio.create_task(service.wait(run.run_id))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(waiting), 0.2)
            assert setup.c.store.get(101, run.run_id).status != "needs_review"
        await asyncio.wait_for(waiting, 2)
        assert setup.c.store.get(101, run.run_id).status == "needs_review"


async def test_unconfirmed_tool_worker_closure_keeps_run_uncertain(
    service_setup, monkeypatch
):
    """Failed closure proof must not be converted into successful native task completion."""
    setup = service_setup
    native = ControlledInference(setup)
    service = coordinator(setup, native)

    def closure_unknown(*args, **kwargs):
        """Represent an uninterruptible or unreaped host worker without leaking a process."""
        raise TimeoutError("tool process closure is unknown")

    monkeypatch.setattr(service.live_grants, "wait_closed", closure_unknown)
    async with service:
        run = await service.submit(setup.c.spec)
        await asyncio.wait_for(native.started.wait(), 2)
        native.release.set()
        await service.wait(run.run_id)
        assert setup.c.store.get(101, run.run_id).status == "reconciling"
