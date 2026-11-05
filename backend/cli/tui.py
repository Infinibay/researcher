"""Textual owner console for the shared native service; all state comes from owner APIs and every mutation uses the original terminal journal."""

from typing import ClassVar

try:
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal
    from textual.widgets import Button, Footer, Header, Input, RichLog, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class ResearcherTUI(App):
        """Present explicit owner scope, explanatory conversation and typed work decisions without another engine, local DB or model picker."""

        TITLE = "Researcher"
        CSS = """
        Screen { background: #172326; color: #e5ede9; }
        #scope { padding: 1 2; height: auto; background: #213336; }
        #views { height: 3; padding: 0 1; }
        #views Button { margin-right: 1; min-width: 13; border: none; background: #304c48; color: #e5ede9; }
        #output { height: 1fr; padding: 1 2; background: #172326; }
        #command { margin: 0 1; border: solid #70ad9a; }
        #hint { height: auto; padding: 0 2; color: #b4c7bf; }
        """
        BINDINGS: ClassVar[list[Binding]] = [
            Binding("ctrl+q", "quit", "Cerrar"),
            Binding("f1", "help", "Ayuda"),
            Binding("f2", "tasks", "Tareas"),
            Binding("f3", "events", "Actividad"),
            Binding("f4", "knowledge", "Hallazgos"),
        ]

        def __init__(self, controller):
            """Receive the already selected owner client; mounting never creates or initializes a second coordinator."""
            super().__init__()
            self.controller = controller

        def compose(self) -> ComposeResult:
            """Keep project/server and distinct note/work semantics visible beside an interactive command console."""
            yield Header()
            yield Static(
                f"Proyecto {self.controller.project_id} · {self.controller.client.origin}",
                id="scope",
                markup=False,
            )
            with Horizontal(id="views"):
                yield Button("Tareas", id="tasks")
                yield Button("Actividad", id="events")
                yield Button("Hallazgos", id="knowledge")
                yield Button("Estado", id="status")
            yield RichLog(
                id="output", wrap=True, markup=False, highlight=False, max_lines=8000
            )
            yield Input(placeholder="Una nota, /plan OBJETIVO o /help", id="command")
            yield Static(
                "Texto libre guarda una nota. Las acciones requieren comandos explícitos. Cerrar no detiene el servicio. Salida: últimas 8000 líneas.",
                id="hint",
                markup=False,
            )
            yield Footer()

        def on_mount(self):
            """Explain the note/planning/execution bridge without assuming the person knows the agent's internal workflow."""
            self.query_one("#output", RichLog).write(
                "Investigar → corregir: la corrección espera tu aceptación de la investigación. /help muestra cómo observar, decidir y recuperar una solicitud."
            )
            self.query_one("#command", Input).focus()

        @on(Input.Submitted, "#command")
        def submitted(self, event):
            """Pass exactly one explicit user message to the owner controller; text content is never interpreted as a completion signal."""
            message = event.value.strip()
            if not message:
                return
            event.input.value = ""
            if message in ("/exit", "/quit", "/q"):
                self.exit()
                return
            self.query_one("#output", RichLog).write("> " + message)
            self._execute(message)

        @on(Button.Pressed)
        def view(self, event):
            """Buttons are readonly projections of real server state, with no implied task assignment."""
            if event.button.id in ("tasks", "events", "knowledge", "status"):
                self._execute("/" + event.button.id)

        @work(thread=True)
        def _execute(self, message):
            """Keep the UI responsive while bounded HTTP requests run; the private journal preserves any uncertain mutation."""
            try:
                result = self.controller.handle_user_message(message)
            except Exception as error:  # noqa: BLE001 -- terminal boundary presents an error; never starts a fallback engine
                result = str(error)
            self.call_from_thread(self.query_one("#output", RichLog).write, result)

        def action_help(self):
            """Show typed actions and their distinct authority without making an HTTP mutation."""
            self._execute("/help")

        def action_tasks(self):
            """Read actual task state through the configured owner API."""
            self._execute("/tasks")

        def action_events(self):
            """Read the first durable activity page; /events CURSOR explicitly continues it."""
            self._execute("/events")

        def action_knowledge(self):
            """Read a bounded finding page whose excerpts and continuation remain explicit."""
            self._execute("/knowledge")

        def on_unmount(self):
            """Close the terminal transport only; server-owned attempts and pending receipts survive the view."""
            self.controller.shutdown()
else:

    class ResearcherTUI:
        """Optional terminal view unavailable without Textual; the classic owner console remains usable."""

        def __init__(self, controller):
            """Report an absent optional view without creating agents or selecting another inference provider."""
            raise ImportError("Textual is unavailable; use --no-tui.")
