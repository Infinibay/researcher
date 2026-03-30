"""Researcher TUI — Textual-based terminal user interface.

Multi-agent AI programming tool with:
- Chat panel (user <-> Project Lead)
- File explorer
- Agent status sidebar
- Task progress tracking
- Real-time event display
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

try:
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widgets import (
        Button,
        DirectoryTree,
        Footer,
        Header,
        Input,
        Label,
        ListView,
        ListItem,
        Markdown,
        OptionList,
        RichLog,
        Static,
        TabbedContent,
        TabPane,
        TextArea,
    )
    from textual.widgets.option_list import Option
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

logger = logging.getLogger(__name__)


if TEXTUAL_AVAILABLE:

    class ChatMessage(Static):
        """A single chat message in the conversation."""

        def __init__(self, role: str, content: str, **kwargs: Any) -> None:
            self.role = role
            super().__init__(self._format(role, content), **kwargs)

        def _format(self, role: str, content: str) -> str:
            if role == "user":
                return f"**You:** {content}"
            elif role == "system":
                return f"*{content}*"
            else:
                return f"**{role}:** {content}"

    class ChatInput(TextArea):
        """Custom text input for chat — Enter sends, Shift+Enter for newline."""

        BINDINGS = [
            Binding("enter", "submit", "Send", show=False),
        ]

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(
                language=None,
                show_line_numbers=False,
                **kwargs,
            )

        def action_submit(self) -> None:
            text = self.text.strip()
            if text:
                self.post_message(self.Submitted(text))
                self.clear()

        class Submitted:
            """Message posted when user submits text."""

            def __init__(self, text: str) -> None:
                self.text = text

    class SidebarPanel(Static):
        """A collapsible panel in the sidebar."""

        def __init__(self, title: str, **kwargs: Any) -> None:
            self._title = title
            self._content = ""
            super().__init__(**kwargs)

        def compose(self) -> ComposeResult:
            yield Label(f"[bold]{self._title}[/bold]", classes="panel-title")
            yield Static(self._content, id=f"panel-content-{self._title.lower()}")

        def update_content(self, content: str) -> None:
            self._content = content
            try:
                widget = self.query_one(f"#panel-content-{self._title.lower()}", Static)
                widget.update(content)
            except Exception:
                pass

    class ResearcherTUI(App):
        """Main Researcher TUI application."""

        TITLE = "Researcher"
        SUB_TITLE = "Multi-Agent AI Programming Tool"

        CSS = """
        Screen {
            layout: horizontal;
        }

        #explorer {
            width: 25%;
            min-width: 20;
            max-width: 40;
            border-right: solid $primary;
            display: none;
        }

        #explorer.visible {
            display: block;
        }

        #content {
            width: 1fr;
        }

        #sidebar {
            width: 30%;
            min-width: 25;
            max-width: 45;
            border-left: solid $primary;
        }

        #chat-messages {
            height: 1fr;
            padding: 1;
        }

        #chat-input {
            height: 5;
            margin: 0 1;
        }

        .panel-title {
            background: $primary-background;
            padding: 0 1;
            text-style: bold;
        }

        #agent-panel, #tasks-panel, #steps-panel, #logs-panel {
            height: auto;
            max-height: 25%;
            border-bottom: dashed $primary;
            padding: 0 1;
        }

        ChatMessage {
            padding: 0 1;
            margin: 0 0 1 0;
        }
        """

        BINDINGS = [
            Binding("ctrl+e", "toggle_explorer", "Explorer", show=True),
            Binding("ctrl+c", "quit", "Quit", show=True),
            Binding("f2", "focus_chat", "Chat", show=True),
        ]

        show_explorer: reactive[bool] = reactive(False)

        def __init__(self) -> None:
            super().__init__()
            self._orchestrator = None
            self._worker_thread: threading.Thread | None = None

        def compose(self) -> ComposeResult:
            yield Header()

            with Horizontal():
                # File explorer (hidden by default)
                with Vertical(id="explorer"):
                    yield DirectoryTree(os.getcwd(), id="file-tree")

                # Main content area
                with Vertical(id="content"):
                    with TabbedContent(id="tabs"):
                        with TabPane("Chat", id="chat-tab"):
                            with VerticalScroll(id="chat-messages"):
                                yield ChatMessage(
                                    "system",
                                    "Welcome to Researcher! Describe what you need, "
                                    "or type /help for commands.",
                                )
                            yield ChatInput(id="chat-input")

                # Sidebar
                with VerticalScroll(id="sidebar"):
                    with Vertical(id="agent-panel"):
                        yield Label("[bold]AGENTS[/bold]", classes="panel-title")
                        yield Static("Initializing...", id="agent-status")
                    with Vertical(id="tasks-panel"):
                        yield Label("[bold]TASKS[/bold]", classes="panel-title")
                        yield Static("No active tasks", id="task-status")
                    with Vertical(id="steps-panel"):
                        yield Label("[bold]STEPS[/bold]", classes="panel-title")
                        yield Static("Idle", id="step-status")
                    with Vertical(id="logs-panel"):
                        yield Label("[bold]LOGS[/bold]", classes="panel-title")
                        yield RichLog(id="log-output", max_lines=100, wrap=True)

            yield Footer()

        def on_mount(self) -> None:
            """Initialize orchestrator after mount."""
            self._init_orchestrator()
            self.query_one("#chat-input", ChatInput).focus()

        def _init_orchestrator(self) -> None:
            """Create and initialize the orchestrator."""
            from backend.orchestrator import ProjectOrchestrator

            self._orchestrator = ProjectOrchestrator(
                on_event=self._on_orchestrator_event,
            )
            try:
                self._orchestrator.initialize()
                self._update_agent_panel()
            except Exception as exc:
                self._log(f"Orchestrator init failed: {exc}")

        def _on_orchestrator_event(self, event: Any) -> None:
            """Handle events from the orchestrator (called from worker thread)."""
            self.call_from_thread(self._process_event, event)

        def _process_event(self, event: Any) -> None:
            """Process orchestrator event on the main thread."""
            etype = event.event_type
            data = event.data

            if etype == "plan_created":
                self._update_step_status(f"Plan: {data.get('plan', '')[:200]}")
            elif etype == "task_started":
                self._update_task_status(
                    f"[{event.agent_id}] Working: {data.get('description', '')[:80]}"
                )
                self._log(f"Task {data.get('task_id')} started by {event.agent_id}")
            elif etype == "task_completed":
                self._log(f"Task {data.get('task_id')} completed by {event.agent_id}")
            elif etype == "review_started":
                self._update_step_status("Code review in progress...")
            elif etype == "review_completed":
                self._log(f"Review: {data.get('result', '')[:100]}")
            elif etype == "merge_completed":
                self._log(f"Merged work from {event.agent_id}")
            elif etype == "done":
                self._update_step_status("Idle")
                self._update_task_status("No active tasks")

        @on(ChatInput.Submitted)
        def on_chat_submitted(self, event: ChatInput.Submitted) -> None:
            """Handle chat message submission."""
            text = event.text.strip()
            if not text:
                return

            # Add user message to chat
            self._add_chat_message("user", text)

            # Handle commands
            if text.startswith("/"):
                from backend.cli.main import _handle_command
                result = _handle_command(text)
                if result == "__EXIT__":
                    self.exit()
                    return
                if result:
                    self._add_chat_message("system", result)
                return

            # Send to orchestrator in background
            self._process_user_message(text)

        @work(thread=True)
        def _process_user_message(self, message: str) -> None:
            """Process user message in a background thread."""
            if not self._orchestrator:
                self.call_from_thread(
                    self._add_chat_message,
                    "system", "Orchestrator not initialized.",
                )
                return

            self.call_from_thread(
                self._update_step_status, "Processing..."
            )

            try:
                result = self._orchestrator.handle_user_message(message)
                self.call_from_thread(
                    self._add_chat_message,
                    "Lead", result,
                )
            except Exception as exc:
                self.call_from_thread(
                    self._add_chat_message,
                    "system", f"Error: {exc}",
                )

        def _add_chat_message(self, role: str, content: str) -> None:
            """Add a message to the chat display."""
            container = self.query_one("#chat-messages", VerticalScroll)
            container.mount(ChatMessage(role, content))
            container.scroll_end(animate=False)

        def _update_agent_panel(self) -> None:
            """Update the agent status panel."""
            if not self._orchestrator:
                return
            status = self._orchestrator.get_status()
            lines = []
            for aid, info in status["agents"].items():
                lines.append(f"  {info['name']} ({info['role']})")
            text = "\n".join(lines) if lines else "No agents"
            try:
                self.query_one("#agent-status", Static).update(text)
            except Exception:
                pass

        def _update_task_status(self, text: str) -> None:
            """Update the task panel."""
            try:
                self.query_one("#task-status", Static).update(text)
            except Exception:
                pass

        def _update_step_status(self, text: str) -> None:
            """Update the steps panel."""
            try:
                self.query_one("#step-status", Static).update(text)
            except Exception:
                pass

        def _log(self, message: str) -> None:
            """Add a log entry."""
            try:
                self.query_one("#log-output", RichLog).write(message)
            except Exception:
                pass

        def action_toggle_explorer(self) -> None:
            """Toggle the file explorer visibility."""
            explorer = self.query_one("#explorer")
            self.show_explorer = not self.show_explorer
            if self.show_explorer:
                explorer.add_class("visible")
            else:
                explorer.remove_class("visible")

        def action_focus_chat(self) -> None:
            """Focus the chat input."""
            self.query_one("#chat-input", ChatInput).focus()

        def action_quit(self) -> None:
            """Shut down gracefully."""
            if self._orchestrator:
                self._orchestrator.shutdown()
            self.exit()
