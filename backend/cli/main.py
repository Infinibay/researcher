"""Researcher CLI — main entry point.

Launches the TUI (Textual) or classic REPL based on settings.
Handles initialization: .researcher/ directory, DB, code indexing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

logger = logging.getLogger(__name__)


def _setup_logging(log_dir: Path) -> None:
    """Configure file logging to .researcher/logs/researcher.log."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "researcher.log"

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # Silence noisy libraries
    for name in ("httpx", "httpcore", "litellm", "chromadb", "watchfiles"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _ensure_researcher_home() -> Path:
    """Create .researcher/ directory structure."""
    from backend.config.user_settings import RESEARCHER_HOME, ensure_researcher_home
    ensure_researcher_home()
    return RESEARCHER_HOME


def _init_db() -> None:
    """Migrate an initialized database; installation is an explicit command."""
    from backend.tools.base.db import ensure_migrations

    ensure_migrations(existing_only=True)


def _run_initial_index(project_id: int = 1) -> None:
    """Run code intelligence indexing on the workspace."""
    from backend.config.settings import settings

    if not settings.CODE_INTEL_ENABLED:
        return

    try:
        from backend.cli.initial_index import run_initial_index

        print("Indexing workspace...", end=" ", flush=True)
        stats = run_initial_index(project_id=project_id)
        if stats:
            files = stats.get("files_indexed", 0)
            symbols = stats.get("symbols_total", 0)
            elapsed = stats.get("elapsed_ms", 0)
            print(f"done ({files} files, {symbols} symbols, {elapsed}ms)")
        else:
            print("done")
    except ImportError:
        logger.debug("Code intelligence not available (missing dependencies)")
    except Exception as exc:
        logger.warning("Initial indexing failed: %s", exc)
        print(f"failed ({exc})")


def _handle_command(command: str) -> str | None:
    """Handle slash commands. Returns response text or None to continue."""
    cmd = command.strip().lower()

    if cmd in ("/exit", "/quit", "/q"):
        return "__EXIT__"

    if cmd == "/help":
        return (
            "Commands:\n"
            "  /settings      — View/edit settings\n"
            "  /models        — Show/switch LLM models\n"
            "  /status        — Show agent status\n"
            "  /tasks         — List current tasks\n"
            "  /index         — Re-index workspace\n"
            "  /help          — This help\n"
            "  /exit          — Quit\n"
            "\n"
            "Anything else is sent to the Project Lead for processing."
        )

    if cmd.startswith("/settings"):
        return _handle_settings(command)

    if cmd.startswith("/models"):
        return _handle_models(command)

    if cmd == "/status":
        return _handle_status()

    if cmd == "/tasks":
        return _handle_tasks()

    if cmd == "/index":
        _run_initial_index()
        return "Workspace re-indexed."

    return None  # Not a command — treat as user message


def _handle_settings(command: str) -> str:
    """Handle /settings command."""
    from backend.config.settings import settings
    from backend.config.user_settings import load_user_settings, save_user_settings

    parts = command.strip().split(maxsplit=2)

    if len(parts) == 1:
        # /settings — show all
        user = load_user_settings()
        lines = ["Current settings (.researcher/settings.json):"]
        if not user:
            lines.append("  (no overrides — using defaults)")
        for key, val in sorted(user.items()):
            lines.append(f"  {key} = {val}")
        lines.append("\nKey defaults:")
        lines.append(f"  LLM_MODEL = {settings.LLM_MODEL or '(not set)'}")
        lines.append(f"  LLM_BASE_URL = {settings.LLM_BASE_URL or '(not set)'}")
        lines.append(f"  MULTI_DEV_ENABLED = {settings.MULTI_DEV_ENABLED}")
        lines.append(f"  CODE_INTEL_ENABLED = {settings.CODE_INTEL_ENABLED}")
        lines.append(f"  REVIEW_ENABLED = {settings.REVIEW_ENABLED}")
        lines.append(f"  ANALYSIS_ENABLED = {settings.ANALYSIS_ENABLED}")
        return "\n".join(lines)

    if len(parts) == 2:
        # /settings KEY — show one setting
        key = parts[1].upper()
        if hasattr(settings, key):
            return f"{key} = {getattr(settings, key)}"
        return f"Unknown setting: {key}"

    if len(parts) >= 3:
        # /settings KEY VALUE — set a setting
        key = parts[1].upper()
        value_str = parts[2]

        if not hasattr(settings, key):
            return f"Unknown setting: {key}"

        # Type coercion
        current = getattr(settings, key)
        try:
            if isinstance(current, bool):
                value = value_str.lower() in ("true", "1", "yes", "on")
            elif isinstance(current, int):
                value = int(value_str)
            elif isinstance(current, float):
                value = float(value_str)
            else:
                value = value_str
        except (ValueError, TypeError):
            return f"Invalid value for {key}: {value_str}"

        save_user_settings({key: value})
        setattr(settings, key, value)
        return f"Set {key} = {value}"

    return "Usage: /settings [KEY [VALUE]]"


def _handle_models(command: str) -> str:
    """Handle /models command."""
    from backend.config.settings import settings

    parts = command.strip().split(maxsplit=1)

    if len(parts) == 1:
        # Show current model
        return f"Current model: {settings.LLM_MODEL or '(not set)'}"

    # /models MODEL_NAME — switch model
    model = parts[1].strip()
    from backend.config.user_settings import save_user_settings
    save_user_settings({"LLM_MODEL": model})
    settings.LLM_MODEL = model
    return f"Switched to model: {model}"


def _handle_status() -> str:
    """Show orchestrator status."""
    return "Status: Use the TUI sidebar for real-time status."


def _handle_tasks() -> str:
    """Show current tasks."""
    return "Tasks: Use the TUI tasks panel for task overview."


def _run_classic_repl() -> None:
    """Run the classic REPL (no TUI)."""
    from backend.orchestrator import ProjectOrchestrator

    orchestrator = ProjectOrchestrator()

    print("\nResearcher CLI (classic mode)")
    print("Type /help for commands, or describe what you need.\n")

    try:
        while True:
            try:
                user_input = input("researcher> ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                result = _handle_command(user_input)
                if result == "__EXIT__":
                    break
                if result:
                    print(result)
                continue

            # Send to orchestrator
            try:
                result = orchestrator.handle_user_message(user_input)
                print(f"\n{result}\n")
            except KeyboardInterrupt:
                print("\nInterrupted.")
            except Exception as exc:
                print(f"\nError: {exc}")

    finally:
        orchestrator.shutdown()
        print("Goodbye!")


@click.command()
@click.option("--no-tui", is_flag=True, help="Use classic REPL instead of TUI")
@click.option("--model", default=None, help="Override LLM model (temporary)")
@click.option("--prompt", default=None, help="Single prompt mode (non-interactive)")
def main(no_tui: bool, model: str | None, prompt: str | None) -> None:
    """Researcher — multi-agent AI programming tool."""

    # 1. Ensure .researcher/ exists
    home = _ensure_researcher_home()
    _setup_logging(home / "logs")

    # 2. Load user settings
    from backend.config.user_settings import reload_all
    reload_all()

    # 3. Apply model override (temporary, not saved)
    if model:
        from backend.config.settings import settings
        settings.LLM_MODEL = model

    # 5. Init DB
    _init_db()

    # 6. Index workspace
    _run_initial_index()

    # 7. Single prompt mode
    if prompt:
        from backend.orchestrator import ProjectOrchestrator
        orchestrator = ProjectOrchestrator()
        result = orchestrator.handle_user_message(prompt)
        print(result)
        orchestrator.shutdown()
        return

    # 8. Launch TUI or classic REPL
    if no_tui:
        _run_classic_repl()
    else:
        try:
            from backend.cli.tui import ResearcherTUI
            app = ResearcherTUI()
            app.run()
        except ImportError:
            logger.warning("Textual not available, falling back to classic REPL")
            _run_classic_repl()


if __name__ == "__main__":
    main()
