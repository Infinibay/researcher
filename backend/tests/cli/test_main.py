"""Local terminal command handling preserves explicit owner intent; legacy settings are not an inference authority."""

import pytest
from click.testing import CliRunner

from backend.cli.main import _handle_command, _run_classic_repl, main


def test_local_help_describes_distinct_observation_and_execution():
    """Help explains the bridge with an example and separate plan/result decisions."""
    text = _handle_command("/help")
    assert "/proposal" in text and "/accept-plan" in text and "/execute-plan" in text
    assert "Gracias" in text and "nota" in text


@pytest.mark.parametrize("command", ["/exit", "/quit", "/q"])
def test_local_exit_does_not_infer_a_server_stop(command):
    """Closing a projection is separate from withdrawing shared server work."""
    assert _handle_command(command) == "__EXIT__"


@pytest.mark.parametrize(
    "command", ["Gracias", "/plan Inspect", "/models", "/settings LLM_MODEL other"]
)
def test_local_commands_cannot_fall_back_to_a_model_or_mutate_legacy_settings(command):
    """Domain commands need a configured owner controller; the local parser performs no work."""
    assert _handle_command(command) is None


def test_classic_console_routes_plain_notes_and_typed_commands_to_shared_controller(
    monkeypatch, capsys
):
    """The REPL preserves explicit messages and has no hidden per-message team pipeline."""
    from types import SimpleNamespace

    messages = []

    class Controller:
        """Only external owner transport is replaced in this console input test."""

        project_id = 101
        client = SimpleNamespace(origin="http://127.0.0.1:8000")

        def handle_user_message(self, message):
            """Record exactly the intent entered by the person."""
            messages.append(message)
            return "Solicitud o nota conservada."

    inputs = iter(["Gracias", "/tasks", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    _run_classic_repl(Controller())
    assert messages == ["Gracias", "/tasks"]
    assert "101" in capsys.readouterr().out


def test_single_action_does_not_mix_prompt_and_unrelated_command(tmp_path):
    """Ambiguous noninteractive intent is rejected before contacting or mutating the server."""
    key = tmp_path / "owner.key"
    key.write_text("synthetic-owner-key-at-least-32-characters")
    key.chmod(0o600)
    result = CliRunner().invoke(
        main,
        [
            "--project-id",
            "101",
            "--owner-key-file",
            str(key),
            "--prompt",
            "Inspect",
            "--command",
            "/tasks",
        ],
    )
    assert result.exit_code == 2
    assert "no ambos" in result.output
