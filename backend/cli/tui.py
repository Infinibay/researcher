"""Researcher TUI — Textual-based terminal user interface.

Multi-agent AI programming tool with:
- Left navigation panel (toggleable) for view switching
- Chat panel (user <-> Project Lead)
- Tasks browser with comments
- Knowledge/findings explorer
- Agent detail: plan, steps, actions per agent
- Settings modal with Ollama model dropdown
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sqlite3
import threading
from pathlib import Path
from typing import Any

try:
    from textual import events, on, work
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
        Select,
        Static,
        TabbedContent,
        TabPane,
        TextArea,
    )
    from textual.widgets.option_list import Option
    try:
        from textual.widgets.option_list import Separator
    except ImportError:
        Separator = None

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────

def _query_db(fn):
    """Run a DB query via execute_with_retry. Returns None on failure."""
    try:
        from backend.tools.base.db import execute_with_retry
        return execute_with_retry(fn)
    except Exception as exc:
        logger.warning("DB query failed: %s", exc)
        return None


def _get_ollama_models() -> list[str]:
    """Get list of available Ollama models via HTTP API."""
    import urllib.request
    from backend.config.settings import settings
    base_url = (settings.LLM_BASE_URL or "http://localhost:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return [m["name"] for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


COMMANDS = [
    ("/settings", "Open settings editor"),
    ("/models", "Switch LLM model"),
    ("/status", "Show agent status"),
    ("/tasks", "Go to tasks view"),
    ("/knowledge", "Go to knowledge view"),
    ("/agents", "Go to agents view"),
    ("/clear", "Clear chat history"),
    ("/help", "Show available commands"),
    ("/exit", "Quit"),
]

STATUS_ICONS = {
    "done": "[green]●[/green]",
    "completed": "[green]●[/green]",
    "in_progress": "[yellow]◐[/yellow]",
    "running": "[yellow]◐[/yellow]",
    "pending": "[dim]○[/dim]",
    "backlog": "[dim]○[/dim]",
    "review_ready": "[cyan]◑[/cyan]",
    "rejected": "[red]✗[/red]",
    "failed": "[red]✗[/red]",
    "cancelled": "[dim]✗[/dim]",
    "blocked": "[red]◌[/red]",
    "active": "[green]●[/green]",
    "provisional": "[yellow]○[/yellow]",
    "superseded": "[dim]✗[/dim]",
    "idle": "[dim]○[/dim]",
}


if TEXTUAL_AVAILABLE:

    # ── Reusable Widgets ─────────────────────────────────────────────────

    class ChatMessage(Static):
        """A single chat message in the conversation."""

        def __init__(self, role: str, content: str, **kwargs: Any) -> None:
            self.role = role
            super().__init__(self._format(role, content), **kwargs)

        def _format(self, role: str, content: str) -> str:
            if role == "user":
                return f"[bold cyan]You:[/bold cyan] {content}"
            elif role == "system":
                return f"[dim italic]{content}[/dim italic]"
            else:
                return f"[bold green]{role}:[/bold green] {content}"

    class ChatInput(TextArea):
        """Chat input — Enter sends, Up/Down for history."""

        class Submitted(events.Message):
            def __init__(self, text: str) -> None:
                super().__init__()
                self.text = text

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(language=None, show_line_numbers=False, **kwargs)
            self._msg_history: list[str] = []
            self._history_index: int = 0
            self._draft: str = ""

        async def _on_key(self, event: events.Key) -> None:
            if event.key == "enter":
                event.prevent_default()
                event.stop()
                text = self.text.strip()
                if text:
                    self._msg_history.append(self.text)
                    self._history_index = len(self._msg_history)
                    self._draft = ""
                    self.post_message(self.Submitted(text))
                    self.text = ""
                return
            if event.key == "up" and self.cursor_location[0] == 0 and self._msg_history:
                event.prevent_default()
                event.stop()
                if self._history_index > 0:
                    if self._history_index == len(self._msg_history):
                        self._draft = self.text
                    self._history_index -= 1
                    self.text = self._msg_history[self._history_index]
                    self.move_cursor(self.document.end)
                return
            if event.key == "down" and self.cursor_location[0] == self.document.line_count - 1 and self._msg_history:
                event.prevent_default()
                event.stop()
                if self._history_index < len(self._msg_history) - 1:
                    self._history_index += 1
                    self.text = self._msg_history[self._history_index]
                    self.move_cursor(self.document.end)
                elif self._history_index == len(self._msg_history) - 1:
                    self._history_index = len(self._msg_history)
                    self.text = self._draft
                    self.move_cursor(self.document.end)
                return
            if event.key == "tab":
                try:
                    menu = self.app.query_one("#autocomplete-menu", OptionList)
                    if menu.has_class("-visible"):
                        event.prevent_default()
                        event.stop()
                        menu.focus()
                        return
                except Exception:
                    pass
            if event.key == "escape":
                try:
                    menu = self.app.query_one("#autocomplete-menu", OptionList)
                    if menu.has_class("-visible"):
                        event.prevent_default()
                        event.stop()
                        menu.remove_class("-visible")
                        return
                except Exception:
                    pass

    # ── Modal Screens ────────────────────────────────────────────────────

    class ModelPickerScreen(ModalScreen[str | None]):
        """Dropdown modal to pick an Ollama model."""

        BINDINGS = [Binding("escape", "cancel", "Cancel", show=True)]

        def __init__(self) -> None:
            super().__init__()
            self._models: list[str] = []

        def compose(self) -> ComposeResult:
            with Vertical(id="model-picker-box"):
                yield Label("Select Model", id="model-picker-title")
                yield OptionList(id="model-picker-list")
                yield Label("[dim]Enter to select, Esc to cancel[/dim]", id="model-picker-hint")

        def on_mount(self) -> None:
            self._models = _get_ollama_models()
            ol = self.query_one("#model-picker-list", OptionList)
            if not self._models:
                ol.add_option(Option("[dim]No models found — is Ollama running?[/dim]", id="__none__"))
            else:
                from backend.config.settings import settings
                current = settings.LLM_MODEL.replace("ollama_chat/", "").replace("ollama/", "")
                for m in self._models:
                    prefix = "[bold green]> [/bold green]" if m == current else "  "
                    ol.add_option(Option(f"{prefix}{m}", id=m))
            ol.focus()

        @on(OptionList.OptionSelected, "#model-picker-list")
        def on_select(self, event: OptionList.OptionSelected) -> None:
            if event.option.id and event.option.id != "__none__":
                self.dismiss(event.option.id)
            else:
                self.dismiss(None)

        def action_cancel(self) -> None:
            self.dismiss(None)

    class SettingValueEditor(ModalScreen[str | None]):
        """Modal to edit a single setting value."""

        BINDINGS = [Binding("escape", "cancel", "Cancel", show=True)]

        def __init__(self, key: str, current_value: Any, value_type: str,
                     description: str = "", choices: list[str] | None = None,
                     label: str = "") -> None:
            super().__init__()
            self._key = key
            self._label = label or key
            self._current_value = current_value
            self._value_type = value_type
            self._description = description
            self._choices = choices
            self._new_value = str(current_value)

        def compose(self) -> ComposeResult:
            with Vertical(id="setting-editor-box"):
                yield Label(self._label, id="setting-editor-title")
                if self._description:
                    yield Label(f"[dim]{self._description}[/dim]", id="setting-editor-desc")
                if self._value_type == "bool":
                    options = [("true", "true"), ("false", "false")]
                    current = "true" if str(self._current_value).lower() in ("true", "1", "yes") else "false"
                    yield Select(options, value=current, id="setting-editor-select")
                elif self._value_type == "select" and self._choices:
                    options = [(c, c) for c in self._choices]
                    current = str(self._current_value) if str(self._current_value) in self._choices else self._choices[0]
                    yield Select(options, value=current, id="setting-editor-select")
                else:
                    yield TextArea(self._new_value, id="setting-editor-input")
                with Vertical(id="setting-editor-footer"):
                    with Horizontal():
                        yield Button("Save", variant="success", id="btn-editor-save")
                        yield Button("Cancel", variant="error", id="btn-editor-cancel")

        def on_mount(self) -> None:
            try:
                ta = self.query_one("#setting-editor-input", TextArea)
                ta.focus()
                ta.select_all()
            except Exception:
                try:
                    self.query_one("#setting-editor-select", Select).focus()
                except Exception:
                    pass

        @on(TextArea.Changed, "#setting-editor-input")
        def on_change(self, event: TextArea.Changed) -> None:
            self._new_value = event.control.text

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn-editor-save":
                self.action_save()
            elif event.button.id == "btn-editor-cancel":
                self.action_cancel()

        def action_save(self) -> None:
            try:
                sel = self.query_one("#setting-editor-select", Select)
                value = str(sel.value) if sel.value is not None else str(self._current_value)
                self.dismiss(value)
                return
            except Exception:
                pass
            self.dismiss(self._new_value if self._new_value else str(self._current_value))

        def action_cancel(self) -> None:
            self.dismiss(None)

    class SettingsEditorScreen(ModalScreen[None]):
        """Settings editor with two-panel layout. Model uses Ollama dropdown."""

        BINDINGS = [
            Binding("escape", "cancel", "Cancel", show=True),
            Binding("ctrl+s", "save", "Save", show=True),
        ]

        SECTION_ORDER = [
            ("LLM", "Model"),
            ("Embedding", "Embeddings"),
            ("Loop Engine", "Loop Engine"),
            ("Phases", "Phases"),
            ("Sandbox", "Sandbox"),
            ("Timeouts", "Timeouts"),
            ("File Limits", "File Limits"),
            ("Database", "Database"),
            ("Web Tools", "Web Tools"),
            ("Code Intel", "Code Intelligence"),
            ("Workspace", "Workspace"),
        ]

        SETTINGS_INFO = {
            "LLM_MODEL": {"section": "LLM", "label": "Model", "default": "", "type": "ollama_model",
                          "desc": "Ollama model to use. Populated from `ollama list`."},
            "LLM_BASE_URL": {"section": "LLM", "label": "Base URL", "default": "http://localhost:11434", "type": "string",
                             "desc": "Base URL for Ollama. Default: http://localhost:11434"},
            "LLM_API_KEY": {"section": "LLM", "label": "API Key", "default": "", "type": "string",
                            "desc": "API key for the LLM provider."},
            "LLM_THINKING": {"section": "LLM", "label": "Thinking Mode", "default": False, "type": "bool",
                             "desc": "Enable thinking/reasoning mode (Qwen3, etc)."},
            "EMBEDDING_PROVIDER": {"section": "Embedding", "label": "Provider", "default": "", "type": "string",
                                   "desc": "Embedding provider. Empty = auto-derive from LLM model."},
            "EMBEDDING_MODEL": {"section": "Embedding", "label": "Model", "default": "", "type": "string",
                                "desc": "Embedding model name. Empty = auto-derive."},
            "LOOP_MAX_ITERATIONS": {"section": "Loop Engine", "label": "Max Iterations", "default": 120, "type": "int",
                                    "desc": "Maximum plan-execute-summarize iterations per task."},
            "LOOP_MAX_TOOL_CALLS_PER_ACTION": {"section": "Loop Engine", "label": "Tool Calls / Step", "default": 40, "type": "int",
                                               "desc": "Max tool calls per step. 0 = unlimited."},
            "LOOP_MAX_TOTAL_TOOL_CALLS": {"section": "Loop Engine", "label": "Total Tool Calls", "default": 600, "type": "int",
                                          "desc": "Hard limit on total tool calls per task."},
            "LOOP_HISTORY_WINDOW": {"section": "Loop Engine", "label": "History Window", "default": 0, "type": "int",
                                    "desc": "Past action summaries to keep in context. 0 = keep all."},
            "LOOP_SUMMARIZER_ENABLED": {"section": "Loop Engine", "label": "Summarizer", "default": True, "type": "bool",
                                        "desc": "Use dedicated LLM call for structured step summaries."},
            "ANALYSIS_ENABLED": {"section": "Phases", "label": "Analysis Phase", "default": True, "type": "bool",
                                 "desc": "Enable pre-development analyst phase."},
            "REVIEW_ENABLED": {"section": "Phases", "label": "Review Phase", "default": True, "type": "bool",
                               "desc": "Enable post-development code review phase."},
            "SANDBOX_ENABLED": {"section": "Sandbox", "label": "Enabled", "default": False, "type": "bool",
                                "desc": "Restrict file access to allowed base directories."},
            "COMMAND_TIMEOUT": {"section": "Timeouts", "label": "Shell Command (s)", "default": 60, "type": "int",
                                "desc": "Max seconds for a shell command."},
            "WEB_TIMEOUT": {"section": "Timeouts", "label": "Web Requests (s)", "default": 30, "type": "int",
                            "desc": "Max seconds for web fetch/search."},
            "GIT_PUSH_TIMEOUT": {"section": "Timeouts", "label": "Git Push (s)", "default": 120, "type": "int",
                                 "desc": "Max seconds for git push."},
            "MAX_FILE_SIZE_BYTES": {"section": "File Limits", "label": "Max File Size (bytes)", "default": 10485760, "type": "int",
                                    "desc": "Max file size the agent can read. Default 10 MB."},
            "MAX_DIR_LISTING": {"section": "File Limits", "label": "Max Dir Entries", "default": 1000, "type": "int",
                                "desc": "Max entries returned by list_directory."},
            "DB_PATH": {"section": "Database", "label": "Database Path", "default": "", "type": "string",
                        "desc": "Path to the SQLite database."},
            "MAX_RETRIES": {"section": "Database", "label": "Max Retries", "default": 5, "type": "int",
                            "desc": "Max retries for DB operations."},
            "WEB_CACHE_TTL_SECONDS": {"section": "Web Tools", "label": "Cache TTL (s)", "default": 3600, "type": "int",
                                      "desc": "Cache duration for web results."},
            "WEB_RPM_LIMIT": {"section": "Web Tools", "label": "Rate Limit (rpm)", "default": 20, "type": "int",
                              "desc": "Max web requests per minute."},
            "CODE_INTEL_ENABLED": {"section": "Code Intel", "label": "Enabled", "default": True, "type": "bool",
                                   "desc": "Enable code intelligence indexing."},
            "CODE_INTEL_AUTO_INDEX": {"section": "Code Intel", "label": "Auto Index", "default": True, "type": "bool",
                                      "desc": "Automatically index workspace on startup."},
            "MULTI_DEV_ENABLED": {"section": "Workspace", "label": "Multi-Dev", "default": False, "type": "bool",
                                  "desc": "Enable multiple developer agents with git worktrees."},
            "DEV_COUNT": {"section": "Workspace", "label": "Developer Count", "default": 1, "type": "int",
                          "desc": "Number of developer agents when multi-dev is enabled."},
        }

        def __init__(self) -> None:
            super().__init__()
            from backend.config.settings import settings
            self._settings = settings
            self._edited_values: dict[str, Any] = {}
            self._current_section: str = self.SECTION_ORDER[0][0]
            self._sections: dict[str, list[str]] = {}
            for key, info in self.SETTINGS_INFO.items():
                sec = info["section"]
                if sec not in self._sections:
                    self._sections[sec] = []
                self._sections[sec].append(key)

        def compose(self) -> ComposeResult:
            with Vertical(id="settings-box"):
                yield Label("Settings", id="settings-title")
                with Horizontal(id="settings-body"):
                    yield OptionList(id="settings-sections")
                    with Vertical(id="settings-right"):
                        yield OptionList(id="settings-list")
                        yield Label("", id="settings-desc")
                with Horizontal(id="settings-footer"):
                    yield Label("[dim]Ctrl+S save   Esc cancel[/dim]", id="settings-hint")
                    with Horizontal(id="settings-buttons"):
                        yield Button("Save", variant="success", id="btn-save")
                        yield Button("Cancel", variant="default", id="btn-cancel")

        def on_mount(self) -> None:
            sections_ol = self.query_one("#settings-sections", OptionList)
            for section_key, section_label in self.SECTION_ORDER:
                if section_key in self._sections:
                    sections_ol.add_option(Option(section_label, id=section_key))
            if sections_ol.option_count > 0:
                sections_ol.highlighted = 0
            self._populate_settings(self._current_section)
            sections_ol.focus()

        def _populate_settings(self, section: str) -> None:
            self._current_section = section
            ol = self.query_one("#settings-list", OptionList)
            ol.clear_options()
            keys = self._sections.get(section, [])
            for key in keys:
                info = self.SETTINGS_INFO[key]
                label = info.get("label", key)
                if key in self._edited_values:
                    val = self._edited_values[key]
                    display_val = str(val) if not isinstance(val, list) else ", ".join(val)
                    line = f"[bold]{label}[/bold]  [bold green]{display_val}[/bold green] [dim italic]*[/dim italic]"
                else:
                    current_value = getattr(self._settings, key, info.get("default", ""))
                    display = str(current_value) if current_value not in (None, "", []) else "[dim]not set[/dim]"
                    line = f"[bold]{label}[/bold]  [dim]{display}[/dim]"
                ol.add_option(Option(line, id=key))
            if keys:
                desc = self.SETTINGS_INFO[keys[0]].get("desc", "")
                self.query_one("#settings-desc", Label).update(f"[dim]{desc}[/dim]")

        @on(OptionList.OptionHighlighted, "#settings-sections")
        def on_section_highlight(self, event: OptionList.OptionHighlighted) -> None:
            if event.option and event.option.id:
                self._populate_settings(event.option.id)

        @on(OptionList.OptionSelected, "#settings-sections")
        def on_section_select(self, event: OptionList.OptionSelected) -> None:
            self.query_one("#settings-list", OptionList).focus()

        @on(OptionList.OptionHighlighted, "#settings-list")
        def on_setting_highlight(self, event: OptionList.OptionHighlighted) -> None:
            if event.option and event.option.id:
                info = self.SETTINGS_INFO.get(event.option.id, {})
                self.query_one("#settings-desc", Label).update(
                    f"[dim italic]{event.option.id}[/dim italic]\n[dim]{info.get('desc', '')}[/dim]"
                )

        @on(OptionList.OptionSelected, "#settings-list")
        def on_setting_select(self, event: OptionList.OptionSelected) -> None:
            if event.option and event.option.id:
                key = event.option.id
                info = self.SETTINGS_INFO.get(key, {})
                # Model picker: open Ollama dropdown
                if info.get("type") == "ollama_model":
                    self.app.push_screen(
                        ModelPickerScreen(),
                        lambda model: self._on_model_picked(key, model),
                    )
                    return
                current_value = self._edited_values.get(key, getattr(self._settings, key, None))
                editor = SettingValueEditor(
                    key, current_value, info.get("type", "string"),
                    description=info.get("desc", ""),
                    choices=info.get("choices", None),
                    label=info.get("label", key),
                )
                self.app.push_screen(editor, lambda value: self._on_value_updated(key, value))

        def _on_model_picked(self, key: str, model: str | None) -> None:
            if model:
                self._edited_values[key] = f"ollama_chat/{model}"
                self._populate_settings(self._current_section)
            self.query_one("#settings-list", OptionList).focus()

        def _on_value_updated(self, key: str, value: str | None) -> None:
            if value is not None:
                from backend.config.user_settings import _coerce_value
                self._edited_values[key] = _coerce_value(self._settings, key, value)
                self._populate_settings(self._current_section)
            self.query_one("#settings-list", OptionList).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn-save":
                self.action_save()
            elif event.button.id == "btn-cancel":
                self.action_cancel()

        def action_save(self) -> None:
            if not self._edited_values:
                self.dismiss(None)
                return
            from backend.config.user_settings import save_user_settings, reload_all
            try:
                save_user_settings(self._edited_values)
                reload_all()
                self.notify(f"Saved {len(self._edited_values)} setting(s).", timeout=3)
                self.dismiss(None)
            except Exception as e:
                self.notify(f"Failed to save: {e}", severity="error", timeout=5)
                self.dismiss(None)

        def action_cancel(self) -> None:
            self.dismiss(None)

    # ── Main Application ─────────────────────────────────────────────────

    class ResearcherTUI(App):
        """Main Researcher TUI application."""

        TITLE = "Researcher"
        SUB_TITLE = "Multi-Agent AI Programming Tool"

        CSS = """
        Screen { layout: horizontal; }

        /* ── Left Navigation ── */
        #nav-panel {
            width: 24;
            border-right: solid $primary;
            background: $surface-darken-1;
        }
        #nav-panel.-hidden { display: none; }
        #nav-title {
            width: 100%;
            text-align: center;
            text-style: bold;
            color: $primary;
            padding: 1 1;
            background: $surface-darken-2;
            border-bottom: solid $primary-darken-2;
        }
        #nav-list {
            height: 1fr;
            background: $surface-darken-1;
            padding: 0;
        }
        #nav-list > .option-list--option-highlighted {
            background: $primary 30%;
            text-style: bold;
        }
        #nav-model {
            height: auto;
            padding: 1;
            color: $text-muted;
            background: $surface-darken-2;
            border-top: solid $primary-darken-3;
        }

        /* ── Main Content ── */
        #content { width: 1fr; height: 100%; }

        /* View switching */
        .view-panel { display: none; height: 100%; }
        .view-panel.-active { display: block; }

        /* Chat view */
        #chat-messages { height: 1fr; padding: 1; }
        #autocomplete-menu {
            display: none; height: auto; max-height: 8;
            border-top: solid $accent; background: $surface-lighten-1;
        }
        #autocomplete-menu.-visible { display: block; }
        #chat-input { height: 4; margin: 0 1; }
        ChatMessage { padding: 0 1; margin: 0 0 1 0; }

        /* Tasks view */
        #tasks-list-panel { width: 40%; border-right: solid $primary-darken-3; }
        #tasks-toolbar { height: auto; padding: 0 1; background: $surface-darken-1; border-bottom: solid $primary-darken-3; }
        #tasks-ol { height: 1fr; }
        #task-detail { width: 1fr; padding: 1; }
        #task-detail-content { height: 1fr; }

        /* Knowledge view */
        #knowledge-list-panel { width: 40%; border-right: solid $primary-darken-3; }
        #knowledge-toolbar { height: auto; padding: 0 1; background: $surface-darken-1; border-bottom: solid $primary-darken-3; }
        #knowledge-ol { height: 1fr; }
        #knowledge-detail { width: 1fr; padding: 1; }
        #knowledge-detail-content { height: 1fr; }

        /* Agents view */
        #agents-list-panel { width: 30%; border-right: solid $primary-darken-3; }
        #agents-ol { height: 1fr; }
        #agent-detail-panel { width: 1fr; }
        #agent-header { height: auto; padding: 1; background: $surface-darken-1; border-bottom: solid $primary-darken-3; }
        #agent-plan-section { height: auto; max-height: 30%; padding: 0 1; border-bottom: dashed $primary-darken-3; }
        #agent-plan-title { text-style: bold; padding: 0 0 0 0; background: $surface-darken-1; }
        #agent-actions-section { height: 1fr; padding: 0 1; }
        #agent-actions-title { text-style: bold; padding: 0 0 0 0; background: $surface-darken-1; }
        #agent-actions-log { height: 1fr; }

        /* ── Right Sidebar ── */
        #sidebar {
            width: 28;
            border-left: solid $primary;
            background: $surface-darken-1;
        }
        .sidebar-title {
            background: $surface-darken-2;
            padding: 0 1;
            text-style: bold;
            border-bottom: solid $primary-darken-3;
        }
        .sidebar-section { height: auto; max-height: 25%; padding: 0 1; border-bottom: dashed $primary-darken-3; }
        #log-output { height: 1fr; max-height: 100%; }

        /* ── Modals ── */
        SettingsEditorScreen { align: center middle; background: rgba(0, 0, 0, 0.65); }
        #settings-box { width: 85%; height: 80%; background: $surface; border: round $primary; padding: 0; }
        #settings-title { width: 100%; text-align: center; text-style: bold; color: $primary; padding: 1 2; background: $surface-darken-2; border-bottom: solid $primary-darken-2; }
        #settings-body { height: 1fr; }
        #settings-sections { width: 22; height: 100%; background: $surface-darken-1; border-right: solid $primary-darken-3; padding: 0; scrollbar-size-vertical: 1; }
        #settings-sections > .option-list--option-highlighted { background: $primary 30%; text-style: bold; }
        #settings-right { width: 1fr; height: 100%; }
        #settings-list { height: 1fr; background: $surface; padding: 0 1; scrollbar-size-vertical: 1; }
        #settings-list > .option-list--option-highlighted { background: $primary 20%; }
        #settings-desc { width: 100%; height: auto; min-height: 3; max-height: 4; padding: 1 2; background: $surface-darken-1; border-top: solid $primary-darken-3; color: $text-muted; }
        #settings-footer { width: 100%; height: auto; padding: 0 2; background: $surface-darken-2; border-top: solid $primary-darken-2; }
        #settings-hint { width: 1fr; color: $text-muted; padding: 1 0; height: auto; }
        #settings-buttons { width: auto; height: auto; align: right middle; }
        #settings-buttons Button { margin: 0 0 0 1; }

        ModelPickerScreen { align: center middle; background: rgba(0, 0, 0, 0.65); }
        #model-picker-box { width: 50%; height: 60%; background: $surface; border: round $primary; padding: 0; }
        #model-picker-title { width: 100%; text-align: center; text-style: bold; color: $primary; padding: 1 2; background: $surface-darken-2; border-bottom: solid $primary-darken-2; }
        #model-picker-list { height: 1fr; background: $surface; }
        #model-picker-list > .option-list--option-highlighted { background: $primary 20%; }
        #model-picker-hint { width: 100%; text-align: center; color: $text-muted; padding: 1; background: $surface-darken-2; border-top: solid $primary-darken-2; }

        SettingValueEditor { align: center middle; background: rgba(0, 0, 0, 0.7); }
        #setting-editor-box { width: 60%; max-height: 50%; background: $surface; border: round $primary; padding: 0; }
        #setting-editor-title { width: 100%; text-align: center; text-style: bold; color: $primary; padding: 1 2; background: $surface-darken-2; border-bottom: solid $primary-darken-2; }
        #setting-editor-desc { width: 100%; padding: 1 2; color: $text-muted; }
        #setting-editor-input { width: 100%; height: auto; max-height: 8; margin: 0 2 1 2; }
        #setting-editor-select { width: 100%; margin: 0 2 1 2; }
        #setting-editor-footer { width: 100%; height: auto; align: center middle; padding: 1 2; background: $surface-darken-2; border-top: solid $primary-darken-2; }
        #setting-editor-footer Horizontal { width: auto; height: auto; align: center middle; }
        #setting-editor-footer Button { margin: 0 1; }
        """

        BINDINGS = [
            Binding("ctrl+b", "toggle_nav", "Nav", show=True),
            Binding("ctrl+c", "quit", "Quit", show=True),
            Binding("f1", "go_chat", "Chat", show=True),
            Binding("f2", "go_tasks", "Tasks", show=True),
            Binding("f3", "go_knowledge", "Knowledge", show=True),
            Binding("f4", "go_agents", "Agents", show=True),
        ]

        current_view: reactive[str] = reactive("chat")

        def __init__(self) -> None:
            super().__init__()
            self._orchestrator = None
            self._agent_state: dict[str, dict[str, Any]] = {}
            self._selected_agent: str | None = None
            self._project_id: int = 1

        def compose(self) -> ComposeResult:
            yield Header()

            with Horizontal(id="main-container"):
                # ── Left Navigation ──
                with Vertical(id="nav-panel"):
                    yield Static("[bold]RESEARCHER[/bold]", id="nav-title")
                    nav_items = [
                        Option("  Chat", id="chat"),
                        Option("  Tasks", id="tasks"),
                        Option("  Knowledge", id="knowledge"),
                        Option("  Agents", id="agents"),
                        Option("  ─────────", id="__sep__"),
                        Option("  Settings", id="__settings__"),
                        Option("  Switch Model", id="__models__"),
                    ]
                    yield OptionList(*nav_items, id="nav-list")
                    yield Static("", id="nav-model")

                # ── Main Content Area ──
                with Vertical(id="content"):
                    # Chat View
                    with Vertical(id="view-chat", classes="view-panel -active"):
                        with VerticalScroll(id="chat-messages"):
                            yield ChatMessage(
                                "system",
                                "Welcome to Researcher! Describe what you need, or type /help for commands.",
                            )
                        yield OptionList(id="autocomplete-menu")
                        yield ChatInput(id="chat-input")

                    # Tasks View
                    with Vertical(id="view-tasks", classes="view-panel"):
                        with Horizontal():
                            with Vertical(id="tasks-list-panel"):
                                with Horizontal(id="tasks-toolbar"):
                                    yield Button("Refresh", variant="primary", id="btn-tasks-refresh")
                                    yield Static("  [dim]Tasks[/dim]")
                                yield OptionList(id="tasks-ol")
                            with VerticalScroll(id="task-detail"):
                                yield Static("Select a task to view details.", id="task-detail-content")

                    # Knowledge View
                    with Vertical(id="view-knowledge", classes="view-panel"):
                        with Horizontal():
                            with Vertical(id="knowledge-list-panel"):
                                with Horizontal(id="knowledge-toolbar"):
                                    yield Button("Refresh", variant="primary", id="btn-knowledge-refresh")
                                    yield Static("  [dim]Findings & Knowledge[/dim]")
                                yield OptionList(id="knowledge-ol")
                            with VerticalScroll(id="knowledge-detail"):
                                yield Static("Select a finding to view details.", id="knowledge-detail-content")

                    # Agents View
                    with Vertical(id="view-agents", classes="view-panel"):
                        with Horizontal():
                            with Vertical(id="agents-list-panel"):
                                yield OptionList(id="agents-ol")
                            with Vertical(id="agent-detail-panel"):
                                yield Static("[dim]Select an agent[/dim]", id="agent-header")
                                with Vertical(id="agent-plan-section"):
                                    yield Label("PLAN", id="agent-plan-title")
                                    yield Static("[dim]No plan yet[/dim]", id="agent-plan-content")
                                with Vertical(id="agent-actions-section"):
                                    yield Label("ACTIONS", id="agent-actions-title")
                                    yield RichLog(id="agent-actions-log", max_lines=500, wrap=True)

                # ── Right Sidebar ──
                with Vertical(id="sidebar"):
                    with Vertical(classes="sidebar-section"):
                        yield Label("AGENTS", classes="sidebar-title")
                        yield Static("Initializing...", id="sb-agents")
                    with Vertical(classes="sidebar-section"):
                        yield Label("CURRENT", classes="sidebar-title")
                        yield Static("Idle", id="sb-current")
                    with Vertical(classes="sidebar-section"):
                        yield Label("LOGS", classes="sidebar-title")
                        yield RichLog(id="log-output", max_lines=200, wrap=True)

            yield Footer()

        # ── Lifecycle ────────────────────────────────────────────────────

        def on_mount(self) -> None:
            self._init_orchestrator()
            self._update_model_display()
            self.query_one("#chat-input", ChatInput).focus()

        def _init_orchestrator(self) -> None:
            from backend.orchestrator import ProjectOrchestrator

            self._orchestrator = ProjectOrchestrator(
                on_event=self._on_orchestrator_event,
            )
            try:
                self._orchestrator.initialize()
                self._update_sidebar_agents()
            except Exception as exc:
                self._log(f"Orchestrator init failed: {exc}")

        def _update_model_display(self) -> None:
            from backend.config.settings import settings
            model = settings.LLM_MODEL or "(not set)"
            try:
                self.query_one("#nav-model", Static).update(
                    f"[dim]Model:[/dim]\n[bold]{model}[/bold]"
                )
            except Exception:
                pass

        # ── View Switching ───────────────────────────────────────────────

        def _switch_view(self, view_id: str) -> None:
            """Switch the active view panel."""
            for panel in self.query(".view-panel"):
                panel.remove_class("-active")
            try:
                self.query_one(f"#view-{view_id}").add_class("-active")
            except Exception:
                self.query_one("#view-chat").add_class("-active")
                view_id = "chat"

            self.current_view = view_id

            # Load data for the view
            if view_id == "tasks":
                self._load_tasks()
            elif view_id == "knowledge":
                self._load_knowledge()
            elif view_id == "agents":
                self._load_agents_list()
            elif view_id == "chat":
                self.query_one("#chat-input", ChatInput).focus()

        @on(OptionList.OptionSelected, "#nav-list")
        def on_nav_select(self, event: OptionList.OptionSelected) -> None:
            if not event.option or not event.option.id:
                return
            nav_id = event.option.id
            if nav_id.startswith("__sep"):
                return
            if nav_id == "__settings__":
                self.push_screen(SettingsEditorScreen())
                return
            if nav_id == "__models__":
                self.push_screen(ModelPickerScreen(), self._on_model_selected)
                return
            self._switch_view(nav_id)

        def _on_model_selected(self, model: str | None) -> None:
            if model:
                from backend.config.settings import settings
                from backend.config.user_settings import save_user_settings, reload_all
                new_model = f"ollama_chat/{model}"
                save_user_settings({"LLM_MODEL": new_model})
                settings.LLM_MODEL = new_model
                self._update_model_display()
                self._add_chat_message("system", f"Model switched to {new_model}")

        def action_toggle_nav(self) -> None:
            nav = self.query_one("#nav-panel")
            if nav.has_class("-hidden"):
                nav.remove_class("-hidden")
            else:
                nav.add_class("-hidden")

        def action_go_chat(self) -> None:
            self._switch_view("chat")

        def action_go_tasks(self) -> None:
            self._switch_view("tasks")

        def action_go_knowledge(self) -> None:
            self._switch_view("knowledge")

        def action_go_agents(self) -> None:
            self._switch_view("agents")

        # ── Chat ─────────────────────────────────────────────────────────

        @on(TextArea.Changed, "#chat-input")
        def show_autocomplete(self, event: TextArea.Changed) -> None:
            text = event.text_area.text.lstrip()
            menu = self.query_one("#autocomplete-menu", OptionList)
            if text.startswith("/"):
                matches = [
                    Option(f"{cmd}  {desc}", id=cmd)
                    for cmd, desc in COMMANDS
                    if cmd.startswith(text)
                ]
                if matches:
                    menu.clear_options()
                    menu.add_options(matches)
                    menu.add_class("-visible")
                    return
            menu.remove_class("-visible")

        @on(OptionList.OptionSelected, "#autocomplete-menu")
        def apply_autocomplete(self, event: OptionList.OptionSelected) -> None:
            cmd = event.option.id
            input_widget = self.query_one("#chat-input", ChatInput)
            input_widget.text = f"{cmd} "
            input_widget.focus()
            input_widget.move_cursor(input_widget.document.end)
            self.query_one("#autocomplete-menu", OptionList).remove_class("-visible")

        @on(ChatInput.Submitted)
        def on_chat_submitted(self, event: ChatInput.Submitted) -> None:
            try:
                self.query_one("#autocomplete-menu", OptionList).remove_class("-visible")
            except Exception:
                pass
            text = event.text.strip()
            if not text:
                return

            self._add_chat_message("user", text)

            # Handle commands
            if text.startswith("/"):
                self._handle_slash_command(text)
                return

            # Send to orchestrator
            self._process_user_message(text)

        def _handle_slash_command(self, text: str) -> None:
            cmd = text.strip().lower()
            if cmd in ("/settings", "/settings browse"):
                self.push_screen(SettingsEditorScreen())
            elif cmd == "/models":
                self.push_screen(ModelPickerScreen(), self._on_model_selected)
            elif cmd == "/tasks":
                self._switch_view("tasks")
            elif cmd == "/knowledge":
                self._switch_view("knowledge")
            elif cmd == "/agents":
                self._switch_view("agents")
            elif cmd == "/clear":
                container = self.query_one("#chat-messages", VerticalScroll)
                container.remove_children()
            elif cmd in ("/exit", "/quit", "/q"):
                self.action_quit()
            elif cmd == "/help":
                lines = ["[bold]Commands:[/bold]"]
                for c, d in COMMANDS:
                    lines.append(f"  {c:16s} {d}")
                lines.append(f"\n[bold]Keys:[/bold]")
                lines.append(f"  Ctrl+B  Toggle nav panel")
                lines.append(f"  F1-F4   Switch views")
                self._add_chat_message("system", "\n".join(lines))
            else:
                from backend.cli.main import _handle_command
                result = _handle_command(text)
                if result == "__EXIT__":
                    self.action_quit()
                elif result:
                    self._add_chat_message("system", result)

        @work(thread=True)
        def _process_user_message(self, message: str) -> None:
            if not self._orchestrator:
                self.call_from_thread(
                    self._add_chat_message, "system", "Orchestrator not initialized.",
                )
                return
            self.call_from_thread(self._update_sidebar_current, "Processing...")
            try:
                result = self._orchestrator.handle_user_message(message)
                self.call_from_thread(self._add_chat_message, "Lead", result)
            except Exception as exc:
                self.call_from_thread(self._add_chat_message, "system", f"Error: {exc}")
            finally:
                self.call_from_thread(self._update_sidebar_current, "Idle")

        def _add_chat_message(self, role: str, content: str) -> None:
            container = self.query_one("#chat-messages", VerticalScroll)
            container.mount(ChatMessage(role, content))
            container.scroll_end(animate=False)

        # ── Tasks View ───────────────────────────────────────────────────

        @work(thread=True)
        def _load_tasks(self) -> None:
            def _query(conn: sqlite3.Connection) -> list[dict]:
                rows = conn.execute(
                    """SELECT id, title, status, priority, type, assigned_to,
                              estimated_complexity, created_at, completed_at
                       FROM tasks WHERE project_id = ?
                       ORDER BY
                         CASE status
                           WHEN 'in_progress' THEN 0
                           WHEN 'review_ready' THEN 1
                           WHEN 'pending' THEN 2
                           WHEN 'rejected' THEN 3
                           WHEN 'backlog' THEN 4
                           WHEN 'done' THEN 5
                           ELSE 6
                         END,
                         priority ASC, created_at DESC""",
                    (self._project_id,),
                ).fetchall()
                return [dict(r) for r in rows]

            tasks = _query_db(_query) or []
            self.call_from_thread(self._populate_tasks_list, tasks)

        def _populate_tasks_list(self, tasks: list[dict]) -> None:
            ol = self.query_one("#tasks-ol", OptionList)
            ol.clear_options()
            if not tasks:
                ol.add_option(Option("[dim]No tasks found[/dim]", id="__none__"))
                return
            for t in tasks:
                icon = STATUS_ICONS.get(t["status"], "?")
                prio = f"P{t['priority']}" if t.get("priority") else ""
                assigned = f"[dim]@{t['assigned_to']}[/dim]" if t.get("assigned_to") else ""
                label = f"{icon} {t['title'][:50]}  {prio} {assigned}"
                ol.add_option(Option(label, id=str(t["id"])))

        @on(OptionList.OptionSelected, "#tasks-ol")
        def on_task_selected(self, event: OptionList.OptionSelected) -> None:
            if event.option and event.option.id and event.option.id != "__none__":
                self._load_task_detail(int(event.option.id))

        @on(OptionList.OptionHighlighted, "#tasks-ol")
        def on_task_highlighted(self, event: OptionList.OptionHighlighted) -> None:
            if event.option and event.option.id and event.option.id != "__none__":
                self._load_task_detail(int(event.option.id))

        @work(thread=True)
        def _load_task_detail(self, task_id: int) -> None:
            def _query(conn: sqlite3.Connection) -> dict | None:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if not row:
                    return None
                task = dict(row)
                comments = conn.execute(
                    """SELECT author, comment_type, content, created_at
                       FROM task_comments WHERE task_id = ?
                       ORDER BY created_at ASC""",
                    (task_id,),
                ).fetchall()
                task["comments"] = [dict(c) for c in comments]
                return task

            task = _query_db(_query)
            if task:
                self.call_from_thread(self._render_task_detail, task)

        def _render_task_detail(self, task: dict) -> None:
            icon = STATUS_ICONS.get(task["status"], "?")
            lines = [
                f"[bold]{task['title']}[/bold]",
                f"",
                f"Status: {icon} {task['status']}    Type: {task.get('type', '?')}    Priority: {task.get('priority', '?')}",
                f"Complexity: {task.get('estimated_complexity', '?')}    Assigned: {task.get('assigned_to', 'unassigned')}",
            ]
            if task.get("branch_name"):
                lines.append(f"Branch: [cyan]{task['branch_name']}[/cyan]")
            if task.get("pr_url"):
                lines.append(f"PR: {task['pr_url']}")
            lines.append(f"Created: {task.get('created_at', '?')}")
            if task.get("completed_at"):
                lines.append(f"Completed: {task['completed_at']}")

            lines.append(f"\n[bold]Description:[/bold]")
            lines.append(task.get("description", "[dim]No description[/dim]") or "[dim]No description[/dim]")

            if task.get("acceptance_criteria"):
                lines.append(f"\n[bold]Acceptance Criteria:[/bold]")
                lines.append(task["acceptance_criteria"])

            comments = task.get("comments", [])
            if comments:
                lines.append(f"\n[bold]Comments ({len(comments)}):[/bold]")
                for c in comments:
                    ctype = c.get("comment_type", "comment")
                    author = c.get("author", "?")
                    time = c.get("created_at", "")
                    icon_c = {"approval": "[green]✓[/green]", "change_request": "[red]✗[/red]"}.get(ctype, "[dim]>[/dim]")
                    lines.append(f"  {icon_c} [bold]{author}[/bold] ({ctype}) [dim]{time}[/dim]")
                    lines.append(f"    {c.get('content', '')}")

            try:
                self.query_one("#task-detail-content", Static).update("\n".join(lines))
            except Exception:
                pass

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn-tasks-refresh":
                self._load_tasks()
            elif event.button.id == "btn-knowledge-refresh":
                self._load_knowledge()

        # ── Knowledge View ───────────────────────────────────────────────

        @work(thread=True)
        def _load_knowledge(self) -> None:
            def _query(conn: sqlite3.Connection) -> list[dict]:
                rows = conn.execute(
                    """SELECT id, topic, finding_type, confidence, status, agent_id, created_at
                       FROM findings WHERE project_id = ?
                       ORDER BY created_at DESC LIMIT 200""",
                    (self._project_id,),
                ).fetchall()
                return [dict(r) for r in rows]

            findings = _query_db(_query) or []
            self.call_from_thread(self._populate_knowledge_list, findings)

        def _populate_knowledge_list(self, findings: list[dict]) -> None:
            ol = self.query_one("#knowledge-ol", OptionList)
            ol.clear_options()
            if not findings:
                ol.add_option(Option("[dim]No findings yet[/dim]", id="__none__"))
                return
            for f in findings:
                icon = STATUS_ICONS.get(f["status"], "?")
                conf = f"[{'green' if f['confidence'] >= 0.7 else 'yellow' if f['confidence'] >= 0.4 else 'red'}]{f['confidence']:.0%}[/]"
                ftype = f.get("finding_type", "?")[:6]
                label = f"{icon} [{ftype}] {f['topic'][:40]}  {conf}"
                ol.add_option(Option(label, id=str(f["id"])))

        @on(OptionList.OptionHighlighted, "#knowledge-ol")
        def on_knowledge_highlighted(self, event: OptionList.OptionHighlighted) -> None:
            if event.option and event.option.id and event.option.id != "__none__":
                self._load_finding_detail(int(event.option.id))

        @on(OptionList.OptionSelected, "#knowledge-ol")
        def on_knowledge_selected(self, event: OptionList.OptionSelected) -> None:
            if event.option and event.option.id and event.option.id != "__none__":
                self._load_finding_detail(int(event.option.id))

        @work(thread=True)
        def _load_finding_detail(self, finding_id: int) -> None:
            def _query(conn: sqlite3.Connection) -> dict | None:
                row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
                return dict(row) if row else None

            finding = _query_db(_query)
            if finding:
                self.call_from_thread(self._render_finding_detail, finding)

        def _render_finding_detail(self, f: dict) -> None:
            icon = STATUS_ICONS.get(f["status"], "?")
            conf = f["confidence"]
            conf_bar = "[green]" + "█" * int(conf * 10) + "[/green]" + "[dim]" + "░" * (10 - int(conf * 10)) + "[/dim]"
            lines = [
                f"[bold]{f['topic']}[/bold]",
                f"",
                f"Status: {icon} {f['status']}    Type: {f.get('finding_type', '?')}",
                f"Confidence: {conf_bar} {conf:.0%}",
                f"Agent: {f.get('agent_id', '?')}    Task: #{f.get('task_id', '?')}",
                f"Created: {f.get('created_at', '?')}",
                f"\n[bold]Content:[/bold]",
                f.get("content", "[dim]No content[/dim]") or "[dim]No content[/dim]",
            ]
            sources_raw = f.get("sources_json", "[]")
            try:
                sources = json.loads(sources_raw) if isinstance(sources_raw, str) else sources_raw
                if sources:
                    lines.append(f"\n[bold]Sources:[/bold]")
                    for s in sources:
                        lines.append(f"  - {s}")
            except Exception:
                pass

            try:
                self.query_one("#knowledge-detail-content", Static).update("\n".join(lines))
            except Exception:
                pass

        # ── Agents View ──────────────────────────────────────────────────

        def _load_agents_list(self) -> None:
            """Populate agents list from orchestrator + DB."""
            ol = self.query_one("#agents-ol", OptionList)
            ol.clear_options()

            # From orchestrator (in-memory agents)
            if self._orchestrator:
                try:
                    status = self._orchestrator.get_status()
                    for aid, info in status.get("agents", {}).items():
                        role = info.get("role", "?")
                        name = info.get("name", aid)
                        state = self._agent_state.get(aid, {})
                        current = state.get("current_task", "")
                        task_hint = f" [dim]— {current[:30]}[/dim]" if current else ""
                        status_icon = STATUS_ICONS.get("running" if current else "idle", "○")
                        ol.add_option(Option(
                            f"{status_icon} [bold]{name}[/bold] ({role}){task_hint}",
                            id=aid,
                        ))
                    return
                except Exception:
                    pass

            # Fallback: from DB roster
            def _query(conn: sqlite3.Connection) -> list[dict]:
                return [dict(r) for r in conn.execute(
                    "SELECT agent_id, name, role, status FROM roster ORDER BY role"
                ).fetchall()]

            agents = _query_db(_query) or []
            if not agents:
                ol.add_option(Option("[dim]No agents registered[/dim]", id="__none__"))
                return
            for a in agents:
                icon = STATUS_ICONS.get(a["status"], "○")
                ol.add_option(Option(
                    f"{icon} [bold]{a['name']}[/bold] ({a['role']})",
                    id=a["agent_id"],
                ))

        @on(OptionList.OptionSelected, "#agents-ol")
        def on_agent_selected(self, event: OptionList.OptionSelected) -> None:
            if event.option and event.option.id and event.option.id != "__none__":
                self._selected_agent = event.option.id
                self._render_agent_detail(event.option.id)

        @on(OptionList.OptionHighlighted, "#agents-ol")
        def on_agent_highlighted(self, event: OptionList.OptionHighlighted) -> None:
            if event.option and event.option.id and event.option.id != "__none__":
                self._selected_agent = event.option.id
                self._render_agent_detail(event.option.id)

        def _render_agent_detail(self, agent_id: str) -> None:
            state = self._agent_state.get(agent_id, {})
            role = state.get("role", "?")
            current_task = state.get("current_task", "No active task")

            # Header
            try:
                self.query_one("#agent-header", Static).update(
                    f"[bold]{agent_id}[/bold]  ({role})\n"
                    f"Task: {current_task}"
                )
            except Exception:
                pass

            # Plan
            plan_steps = state.get("plan_steps", [])
            if plan_steps:
                lines = []
                for step in plan_steps:
                    idx = step.get("index", "?")
                    desc = step.get("description", "?")
                    status = step.get("status", "pending")
                    icon = {"done": "[green]✓[/green]", "active": "[yellow]>[/yellow]", "skipped": "[dim]–[/dim]"}.get(status, "[dim]○[/dim]")
                    lines.append(f"  {icon} Step {idx}: {desc}")
                plan_text = "\n".join(lines)
            else:
                plan_text = "[dim]No plan generated yet[/dim]"

            try:
                self.query_one("#agent-plan-content", Static).update(plan_text)
            except Exception:
                pass

            # Actions log — show recent actions from state
            actions = state.get("actions", [])
            try:
                log = self.query_one("#agent-actions-log", RichLog)
                log.clear()
                if actions:
                    for action in actions[-50:]:
                        log.write(action)
                else:
                    log.write("[dim]No actions recorded yet[/dim]")
            except Exception:
                pass

        # ── Orchestrator Events ──────────────────────────────────────────

        def _on_orchestrator_event(self, event: Any) -> None:
            self.call_from_thread(self._process_event, event)

        def _process_event(self, event: Any) -> None:
            etype = getattr(event, "event_type", "")
            agent_id = getattr(event, "agent_id", "unknown")
            data = getattr(event, "data", {})

            # Ensure agent state exists
            if agent_id not in self._agent_state:
                self._agent_state[agent_id] = {
                    "role": "",
                    "current_task": "",
                    "plan_steps": [],
                    "actions": [],
                }

            state = self._agent_state[agent_id]

            if etype == "plan_created":
                plan_text = data.get("plan", "")
                # Try to parse plan steps
                steps = []
                for i, line in enumerate(plan_text.strip().splitlines()):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith("-")):
                        steps.append({"index": i + 1, "description": line.lstrip("0123456789.-) "), "status": "pending"})
                if steps:
                    state["plan_steps"] = steps
                state["actions"].append(f"[cyan]Plan created[/cyan] ({len(steps)} steps)")
                self._log(f"[{agent_id}] Plan created ({len(steps)} steps)")

            elif etype == "task_started":
                desc = data.get("description", "")[:80]
                state["current_task"] = desc
                state["role"] = data.get("role", state.get("role", ""))
                state["actions"].append(f"[yellow]Task started:[/yellow] {desc}")
                self._update_sidebar_current(f"[{agent_id}] {desc}")
                self._log(f"[{agent_id}] Started: {desc}")

            elif etype == "task_completed":
                result = data.get("result", "")[:100]
                state["current_task"] = ""
                state["actions"].append(f"[green]Task completed[/green]")
                self._log(f"[{agent_id}] Task completed")

            elif etype == "tool_call":
                tool_name = data.get("tool", "?")
                state["actions"].append(f"  [dim]tool:[/dim] {tool_name}")

            elif etype == "step_completed":
                step_idx = data.get("step_index", "?")
                summary = data.get("summary", "")[:80]
                # Update plan step status
                for s in state["plan_steps"]:
                    if s["index"] == step_idx:
                        s["status"] = "done"
                    elif s["status"] == "pending" and s["index"] == step_idx + 1:
                        s["status"] = "active"
                state["actions"].append(f"  [green]Step {step_idx} done:[/green] {summary}")

            elif etype == "review_started":
                state["actions"].append(f"[cyan]Review started[/cyan]")
                self._log(f"[{agent_id}] Review started")

            elif etype == "review_completed":
                result = data.get("result", "")[:100]
                state["actions"].append(f"[green]Review completed:[/green] {result}")
                self._log(f"[{agent_id}] Review: {result}")

            elif etype == "error":
                error = data.get("error", "unknown")
                state["actions"].append(f"[red]Error:[/red] {error}")
                self._log(f"[red][{agent_id}] Error: {error}[/red]")

            elif etype == "done":
                state["current_task"] = ""
                self._update_sidebar_current("Idle")

            # Refresh agent detail if viewing this agent
            if self._selected_agent == agent_id and self.current_view == "agents":
                self._render_agent_detail(agent_id)

            # Update sidebar agents
            self._update_sidebar_agents()

        # ── Sidebar Updates ──────────────────────────────────────────────

        def _update_sidebar_agents(self) -> None:
            if not self._orchestrator:
                return
            try:
                status = self._orchestrator.get_status()
                lines = []
                for aid, info in status.get("agents", {}).items():
                    state = self._agent_state.get(aid, {})
                    current = state.get("current_task", "")
                    icon = STATUS_ICONS.get("running" if current else "idle", "○")
                    lines.append(f"{icon} {info.get('name', aid)}")
                    if current:
                        lines.append(f"  [dim]{current[:25]}[/dim]")
                self.query_one("#sb-agents", Static).update("\n".join(lines) if lines else "No agents")
            except Exception:
                pass

        def _update_sidebar_current(self, text: str) -> None:
            try:
                self.query_one("#sb-current", Static).update(text)
            except Exception:
                pass

        def _log(self, message: str) -> None:
            try:
                self.query_one("#log-output", RichLog).write(message)
            except Exception:
                pass

        # ── Global Key Handling ──────────────────────────────────────────

        def on_key(self, event: events.Key) -> None:
            # Dismiss autocomplete on Escape
            if event.key == "escape":
                try:
                    menu = self.query_one("#autocomplete-menu", OptionList)
                    if menu.has_class("-visible"):
                        event.prevent_default()
                        menu.remove_class("-visible")
                        self.query_one("#chat-input", ChatInput).focus()
                except Exception:
                    pass

        def action_quit(self) -> None:
            if self._orchestrator:
                try:
                    self._orchestrator.shutdown()
                except Exception:
                    pass
            self.exit()
