"""Terminal entry to the shared local owner API; server configuration owns models, source workspaces and native execution."""

import os
from pathlib import Path

import click

from backend.cli.owner_client import OwnerClient, TerminalError
from backend.orchestrator import HELP, ProjectOrchestrator


def _init_db():
    """Retain explicit initialized-database migration for existing host callers; terminal startup never invokes it."""
    from backend.tools.base.db import ensure_migrations

    ensure_migrations(existing_only=True)


def _handle_command(command):
    """Handle local help/exit only; domain commands require the explicit shared owner controller."""
    if command.strip() in ("/exit", "/quit", "/q"):
        return "__EXIT__"
    if command.strip() == "/help":
        return HELP
    return None


def _run_classic_repl(controller):
    """Read explicit owner intent without blocking on generation or owning any server-side worker."""
    click.echo(
        f"Researcher · proyecto {controller.project_id} · {controller.client.origin}"
    )
    click.echo(
        "Texto libre guarda notas; /help muestra decisiones de trabajo. Cerrar esta terminal no detiene el servicio."
    )
    while True:
        try:
            message = input("researcher> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not message:
            continue
        local = _handle_command(message)
        if local == "__EXIT__":
            break
        try:
            click.echo(local or controller.handle_user_message(message))
        except (TerminalError, ValueError) as error:
            click.echo(str(error), err=True)


@click.command()
@click.option(
    "--no-tui", is_flag=True, help="Use the classic owner console instead of Textual."
)
@click.option(
    "--server",
    "origin",
    default="http://127.0.0.1:8000",
    envvar="RESEARCHER_OWNER_URL",
    show_default=True,
    help="Origin of the already configured local owner service.",
)
@click.option(
    "--project-id",
    type=click.IntRange(min=1),
    required=True,
    envvar="RESEARCHER_PROJECT_ID",
    help="Explicit project in that service.",
)
@click.option(
    "--owner-key-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    envvar="RESEARCHER_OWNER_KEY_FILE",
    help="Private pairing key file announced by the service; never the key text.",
)
@click.option(
    "--state-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Private terminal state outside source repositories.",
)
@click.option(
    "--prompt",
    default=None,
    help="Admit native project planning for this goal and return its identity.",
)
@click.option(
    "--command",
    default=None,
    help="Perform one explicit terminal command, for example /proposal RUN.",
)
@click.option(
    "--model",
    default=None,
    hidden=True,
    help="Removed terminal-local model override; the server owns model selection.",
)
def main(no_tui, origin, project_id, owner_key_file, state_dir, prompt, command, model):
    """Researcher owner terminal: shared project state, explicit work decisions and recoverable receipts."""
    if model is not None:
        raise click.ClickException(
            "Elige el campo model en INFINIBAY_RUNTIME_CONFIG del servicio. --model ya no cambia LLM_MODEL local ni configura otro proveedor."
        )
    if prompt is not None and command is not None:
        raise click.UsageError("Elige --prompt o --command, no ambos.")
    state_dir = (
        state_dir
        or Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "researcher/terminal"
    )
    controller = None
    try:
        client = OwnerClient(
            origin=origin,
            project_id=project_id,
            key_file=owner_key_file,
            state_dir=state_dir,
        )
        controller = ProjectOrchestrator(project_id=project_id, owner_client=client)
        controller.initialize()
        if prompt is not None or command is not None:
            click.echo(
                controller.handle_user_message(
                    "/plan " + prompt if prompt is not None else command
                )
            )
        elif no_tui:
            _run_classic_repl(controller)
        else:
            from backend.cli.tui import TEXTUAL_AVAILABLE, ResearcherTUI

            if TEXTUAL_AVAILABLE:
                ResearcherTUI(controller).run()
            else:
                _run_classic_repl(controller)
    except (TerminalError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    finally:
        if controller is not None:
            controller.shutdown()


if __name__ == "__main__":
    main()
