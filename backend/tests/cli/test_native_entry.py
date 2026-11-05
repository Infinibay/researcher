"""CLI/TUI entry projects owner API state and must never create a competing engine, local database or provider configuration."""

import json

import httpx
from click.testing import CliRunner


def test_single_prompt_admits_native_planning_through_shared_owner_api(
    tmp_path, monkeypatch
):
    """The executable entry returns an admitted original run and never probes LLMs, initializes a local DB or indexes the terminal cwd."""
    from backend.cli import main as cli
    from backend.cli.owner_client import OwnerClient
    from backend.tests.cli.test_owner_client import client_config

    config = client_config(tmp_path)
    posts = []

    def forbidden(*_a, **_k):
        """Detect the old competing startup pipeline."""
        raise AssertionError("Legacy startup reached")

    def handle(request):
        """Control HTTP only, retaining real client/journal/Click/controller behavior."""
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
            return httpx.Response(200, json={"id": 101, "name": "Alpha"})
        body = json.loads(request.content)
        posts.append((request.url.path, body))
        return httpx.Response(
            200,
            json={
                "request": body,
                "planning_task_id": 42,
                "run": {
                    "project_id": 101,
                    "task_id": 42,
                    "run_id": "plan:a",
                    "actor_id": "native-project-planner",
                    "execution_kind": "research",
                },
            },
        )

    monkeypatch.setattr(
        cli,
        "OwnerClient",
        lambda **kwargs: OwnerClient(**kwargs, transport=httpx.MockTransport(handle)),
        raising=False,
    )
    for name in ("_init_db", "_run_initial_index", "_setup_llm"):
        monkeypatch.setattr(cli, name, forbidden, raising=False)
    result = CliRunner().invoke(
        cli.main,
        [
            "--project-id",
            "101",
            "--owner-key-file",
            str(config["key_file"]),
            "--state-dir",
            str(config["state_dir"]),
            "--prompt",
            "Investigate this behavior",
        ],
    )
    assert result.exit_code == 0, result.exception
    assert posts[0][0] == "/api/projects/101/start"
    assert posts[0][1]["prompt"] == "Investigate this behavior"
    assert "plan:a" in result.output and "aceptación" in result.output


def test_terminal_model_override_cannot_silently_change_unrelated_legacy_settings(
    tmp_path,
):
    """The removed local LLM override is rejected before connecting; native model selection belongs to the configured server."""
    from backend.cli.main import main
    from backend.tests.cli.test_owner_client import client_config

    config = client_config(tmp_path)
    result = CliRunner().invoke(
        main,
        [
            "--project-id",
            "101",
            "--owner-key-file",
            str(config["key_file"]),
            "--state-dir",
            str(config["state_dir"]),
            "--model",
            "a-model",
            "--prompt",
            "Inspect",
        ],
    )
    assert result.exit_code != 0
    assert "INFINIBAY_RUNTIME_CONFIG" in result.output


async def test_tui_keeps_owner_context_visible_and_uses_typed_command_port():
    """Textual presents explicit selected project/server and dispatches a note without constructing a local orchestrator/team."""
    from types import SimpleNamespace

    from backend.cli.tui import ResearcherTUI

    calls = []

    class Controller:
        """Replace only the external owner controller port in this widget interaction test."""

        project_id = 101
        client = SimpleNamespace(origin="http://127.0.0.1:8000")

        def handle_user_message(self, message):
            """Observe the submitted intent without implementing domain behavior in a widget test."""
            calls.append(message)
            return "Nota guardada; no inició agentes."

        def shutdown(self):
            """No server is owned by this widget fixture."""

    app = ResearcherTUI(Controller())
    async with app.run_test(size=(100, 35)) as pilot:
        from textual.widgets import Input

        assert "101" in str(app.query_one("#scope").render())
        app.query_one("#command", Input).value = "Gracias"
        await pilot.press("enter")
        await pilot.pause()
        assert calls == ["Gracias"]
