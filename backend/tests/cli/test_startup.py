"""CLI work must not be preceded by an unrelated model capability probe."""

from types import SimpleNamespace

from click.testing import CliRunner


def test_single_prompt_dispatches_without_startup_model_inference(tmp_path, monkeypatch):
    from backend.cli import main as cli
    # CLI initialization loads the tool registry before the legacy orchestrator.
    # Keep that real ordering until the runtime migration removes the registry.
    cli._init_db()
    from backend import orchestrator

    class UnexpectedProbe(BaseException):
        pass

    def forbidden_probe():
        raise UnexpectedProbe("CLI startup tried to probe a model")

    monkeypatch.setattr(cli, "_ensure_researcher_home", lambda: tmp_path)
    monkeypatch.setattr(cli, "_run_initial_index", lambda: None)
    monkeypatch.setattr(cli, "_setup_llm", forbidden_probe, raising=False)
    monkeypatch.setattr(
        orchestrator, "ProjectOrchestrator",
        lambda: SimpleNamespace(
            handle_user_message=lambda message: "Dispatched: " + message,
            shutdown=lambda: None,
        ),
    )

    result = CliRunner().invoke(cli.main, ["--prompt", "Explain this task"])

    assert result.exit_code == 0, result.exception
    assert "Dispatched: Explain this task" in result.output
