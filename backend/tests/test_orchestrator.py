"""Actual terminal owner HTTP entry through the owned native broker/kernel/Git chain; generation and Ken commands are controlled fixtures, never a real subscription turn."""

import asyncio
import json
import socket

import httpx
import pytest
import uvicorn

from backend.tests.runtime.conftest import (
    code_host_asset as code_host_asset,  # noqa: PLC0414 -- actual owned runtime fixtures.
)
from backend.tests.runtime.conftest import (
    coordination as coordination,  # noqa: PLC0414
)
from backend.tests.runtime.conftest import (
    ken_installation as ken_installation,  # noqa: PLC0414
)
from backend.tests.runtime.conftest import (
    schema_target as schema_target,  # noqa: PLC0414 -- transitive coordination fixture.
)
from backend.tests.runtime.conftest import (
    service_setup as service_setup,  # noqa: PLC0414
)
from backend.tests.runtime.test_owned_factory import owned_config as owned_config  # noqa: PLC0414


@pytest.mark.timeout(220)
async def test_terminal_owns_no_engine_and_recovers_exact_work_through_real_owner_http(
    owned_config, socket_enabled
):
    """One server handles web-equivalent terminal planning/research/private development/review/acceptance; lost execution response and terminal restart never create another turn or auto-merge."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.cli.owner_client import OwnerClient, TerminalError
    from backend.orchestrator import ProjectOrchestrator
    from backend.tests.runtime.test_development_workspace import fixture_git

    c = owned_config
    await fixture_git(c.s.workspace, "init", "-q")
    await fixture_git(c.s.workspace, "add", "fact.txt")
    await fixture_git(
        c.s.workspace,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@localhost",
        "commit",
        "-qm",
        "base",
    )
    c.settings["development_checks"] = [
        {
            "argv": [
                "/usr/bin/python3",
                "-c",
                "from pathlib import Path; assert Path('fact.txt').read_text() == '200'; print('exact value checked')",
            ],
            "framework": "command",
            "timeout_seconds": 5,
            "environment_id": "system",
        }
    ]
    c.settings["limits"]["wall_seconds"] = 90
    c.path.write_text(json.dumps(c.settings))
    code = "synthetic-terminal-owner-key-at-least-32-characters"
    app = create_app(access=LocalAccess(pairing_key=code))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    origin = "http://127.0.0.1:" + str(listener.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    key = c.s.control.parent / "terminal-owner.key"
    key.write_text(code)
    key.chmod(0o600)
    options = {
        "origin": origin,
        "project_id": 101,
        "key_file": key,
        "state_dir": c.s.control.parent / "terminal-state",
    }
    sent = []

    class LostExecutionReply(httpx.BaseTransport):
        """Lose only the original execution response after actual HTTP/domain commit; never replace the server or domain with a fake."""

        def __init__(self):
            """Use the real localhost TCP transport."""
            self.transport = httpx.HTTPTransport(trust_env=False)

        def handle_request(self, request):
            """Retain both original execute requests and drop the first already-completed response."""
            response = self.transport.handle_request(request)
            if request.method == "POST" and request.url.path.endswith(
                "/project-plan/execution"
            ):
                sent.append(json.loads(request.content))
                if len(sent) == 1:
                    response.read()
                    response.close()
                    raise httpx.ReadError("Actual original response lost")
            return response

        def close(self):
            """Close only this terminal's HTTP projection."""
            self.transport.close()

    controller = None
    try:
        for _ in range(100):
            if server.started:
                break
            if serving.done():
                await serving
            await asyncio.sleep(0.05)
        assert server.started
        async with httpx.AsyncClient(base_url=origin, trust_env=False) as owner:
            paired = await owner.post('/api/session', json={'code': code}, headers={'X-Researcher-Client': 'web'})
            assert paired.status_code == 200, paired.text
            owner.headers['X-Researcher-CSRF'] = paired.json()['csrf_token']
            policy = (await owner.get('/api/projects/101/check-policy')).json()
            assert policy == {'revision': 0, 'mode': None}
            chosen = await owner.post('/api/projects/101/check-policy', json={
                'operation_key': 'terminal-project-check-policy',
                'expected_revision': policy['revision'], 'mode': 'allow_missing',
            })
            assert chosen.status_code == 200, chosen.text
            assert chosen.json()['revision'] == 1 and chosen.json()['inference_started'] is False
        controller = ProjectOrchestrator(
            project_id=101,
            owner_client=OwnerClient(**options, transport=LostExecutionReply()),
        )
        await asyncio.to_thread(controller.initialize)
        note = await asyncio.to_thread(
            controller.handle_user_message, "Gracias. Esta nota no es una tarea."
        )
        assert "no inició agentes" in note
        assert c.s.c.conn.execute("SELECT count(*)FROM agent_events").fetchone()[0] == 0
        assert c.s.c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 0
        planning = await asyncio.to_thread(
            controller.handle_user_message,
            "/plan Investigate the issue and propose a plan. Change fact.txt from 137 to 200 when the inspection supports it.",
        )
        runtime = app.state.runtime_service
        plan_id = c.s.c.conn.execute(
            "SELECT id FROM runtime_runs WHERE actor_id='native-project-planner'"
        ).fetchone()[0]
        assert plan_id in planning

        async def terminal_run(task):
            """Observe an original scoped run until its actual terminal proposal state, without restarting from observation timeout."""
            for _ in range(800):
                rows = runtime.store.task_runs(101, task)
                if rows and rows[0].status not in ("queued", "running", "cancelling"):
                    return rows[0]
                await asyncio.sleep(0.05)
            raise AssertionError(
                "Original native run did not produce a terminal observation"
            )

        plan = runtime.store.get(101, plan_id)
        assert (await terminal_run(plan.task_id)).status == "needs_review"
        shown = await asyncio.to_thread(
            controller.handle_user_message, "/proposal " + plan_id
        )
        assert "Supuestos" in shown and "owner_message" in shown
        accepted = await asyncio.to_thread(
            controller.handle_user_message, "/accept-plan " + plan_id
        )
        assert "pendientes" in accepted
        graph = json.loads(
            c.s.c.conn.execute(
                "SELECT result_json FROM runtime_project_plan_acceptances WHERE run_id=?",
                (plan_id,),
            ).fetchone()[0]
        )
        ids = list(graph["tasks"].values())
        typed = dict(
            c.s.c.conn.execute("SELECT type,id FROM tasks WHERE id IN (?,?)", ids)
        )
        tasks = [typed["research"], typed["code"]]
        assert not runtime.store.task_runs(
            101, tasks[0]
        ) and not runtime.store.task_runs(101, tasks[1])
        await asyncio.to_thread(controller.handle_user_message, "/execution " + plan_id)
        with pytest.raises(TerminalError, match="original|pendiente"):
            await asyncio.to_thread(
                controller.handle_user_message, "/execute-plan " + plan_id
            )
        controller.shutdown()
        controller = ProjectOrchestrator(
            project_id=101,
            owner_client=OwnerClient(**options, transport=LostExecutionReply()),
        )
        recovered = await asyncio.to_thread(controller.handle_user_message, "/retry")
        assert "original" in recovered and sent[0] == sent[1]
        root = await terminal_run(tasks[0])
        assert root.status == "needs_review", root
        assert not runtime.store.task_runs(101, tasks[1])
        source = await asyncio.to_thread(
            controller.handle_user_message, "/result " + root.run_id
        )
        assert "La medición original no se repitió" in source
        await asyncio.to_thread(
            controller.handle_user_message,
            "/accept-result " + root.run_id + " --ack-limits",
        )
        child = await terminal_run(tasks[1])
        assert (
            child.status == "needs_review" and child.execution_kind == "development"
        ), child
        await asyncio.to_thread(controller.handle_user_message, "/code " + child.run_id)
        review = await asyncio.to_thread(
            controller.handle_user_message, "/review-code " + child.run_id
        )
        assert "independiente" in review
        reviewer = c.s.c.conn.execute(
            "SELECT id FROM runtime_runs WHERE execution_kind='code_review'"
        ).fetchone()[0]
        for _ in range(800):
            if (
                runtime.store.get(101, reviewer).status != "queued"
                and reviewer in runtime._workers
            ):
                await runtime.wait(reviewer)
                break
            if runtime.store.get(101, reviewer).status not in ("queued", "running"):
                break
            await asyncio.sleep(0.05)
        await asyncio.to_thread(controller.handle_user_message, "/code " + child.run_id)
        decision = await asyncio.to_thread(
            controller.handle_user_message,
            "/accept-code " + child.run_id + " --ack-limits",
        )
        assert "no publica" in decision
        assert runtime.store.get(101, child.run_id).status == "accepted"
        await asyncio.to_thread(controller.handle_user_message, "/execution " + plan_id)
        await asyncio.to_thread(
            controller.handle_user_message, "/pause-plan " + plan_id
        )
        assert (c.s.workspace / "fact.txt").read_text() == "137"
        assert (
            c.s.c.conn.execute(
                "SELECT count(*)FROM runtime_inference_dispatches"
            ).fetchone()[0]
            == 4
        )
        assert c.s.c.conn.execute("SELECT count(*)FROM runtime_runs").fetchone()[0] == 4
        assert (
            c.s.c.conn.execute(
                "SELECT count(*)FROM runtime_peers WHERE state!='closed'"
            ).fetchone()[0]
            == 0
        )
        assert "items" in await asyncio.to_thread(
            controller.handle_user_message, "/knowledge"
        )
        assert "events" in await asyncio.to_thread(
            controller.handle_user_message, "/events"
        )
        assert "Alpha" in await asyncio.to_thread(
            controller.handle_user_message, "/status"
        )
    finally:
        if controller:
            controller.shutdown()
        server.should_exit = True
        await asyncio.wait_for(serving, 15)
        listener.close()
