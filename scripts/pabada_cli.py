#!/usr/bin/env python3
"""infinibay — CLI helper for INFINIBAY agents running inside sandbox pods.

Standalone script (stdlib only). Communicates with the INFINIBAY backend
via its REST API to perform operations that require host-side DB access.

Environment variables (injected by PodManager):
    INFINIBAY_API_URL    — Backend base URL (e.g. http://host.containers.internal:8000)
    INFINIBAY_PROJECT_ID — Current project ID
    INFINIBAY_AGENT_ID   — This agent's ID
    INFINIBAY_TASK_ID    — Current task ID (optional)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = os.environ.get("INFINIBAY_API_URL", "http://localhost:8000")
PROJECT_ID = os.environ.get("INFINIBAY_PROJECT_ID", "")
AGENT_ID = os.environ.get("INFINIBAY_AGENT_ID", "")
TASK_ID = os.environ.get("INFINIBAY_TASK_ID", "")


def _api(method: str, path: str, data: dict | None = None) -> dict:
    """Make an HTTP request to the INFINIBAY API and return the JSON response."""
    url = f"{API_URL}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"} if body else {}

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"Error {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        sys.exit(1)


# ── Task commands ────────────────────────────────────────────────────────

def cmd_task_get(args: argparse.Namespace) -> None:
    """Get task details."""
    result = _api("GET", f"/api/tasks/{args.id}")
    print(json.dumps(result, indent=2))


def cmd_task_list(args: argparse.Namespace) -> None:
    """List tasks for the current project."""
    params = f"?project_id={PROJECT_ID}"
    if args.status:
        params += f"&status={args.status}"
    result = _api("GET", f"/api/tasks{params}")
    print(json.dumps(result, indent=2))


def cmd_task_update_status(args: argparse.Namespace) -> None:
    """Update task status."""
    result = _api("PUT", f"/api/tasks/{args.id}", {"status": args.status})
    print(json.dumps(result, indent=2))


def cmd_task_add_comment(args: argparse.Namespace) -> None:
    """Add a comment to a task."""
    result = _api("POST", f"/api/tasks/{args.id}/comments", {
        "agent_id": AGENT_ID,
        "content": args.text,
    })
    print(json.dumps(result, indent=2))


# ── Chat commands ────────────────────────────────────────────────────────

def cmd_chat_send(args: argparse.Namespace) -> None:
    """Send a chat message."""
    result = _api("POST", f"/api/chat/{PROJECT_ID}", {
        "from_agent": AGENT_ID,
        "to_agent": args.to,
        "content": args.message,
    })
    print(json.dumps(result, indent=2))


def cmd_chat_read(args: argparse.Namespace) -> None:
    """Read chat messages."""
    path = f"/api/chat/{PROJECT_ID}/agent/{AGENT_ID}"
    if args.unread_only:
        path += "?unread_only=true"
    result = _api("GET", path)
    print(json.dumps(result, indent=2))


def cmd_chat_ask_team_lead(args: argparse.Namespace) -> None:
    """Ask the team lead a question."""
    result = _api("POST", "/api/internal/ask-team-lead", {
        "project_id": int(PROJECT_ID),
        "agent_id": AGENT_ID,
        "question": args.question,
    })
    print(json.dumps(result, indent=2))


# ── Git commands ─────────────────────────────────────────────────────────

def cmd_git_create_pr(args: argparse.Namespace) -> None:
    """Create a pull request."""
    data: dict = {
        "project_id": int(PROJECT_ID),
        "title": args.title,
        "base": args.base,
    }
    if args.head:
        data["head"] = args.head
    if args.body:
        data["body"] = args.body
    result = _api("POST", "/api/internal/git/create-pr", data)
    print(json.dumps(result, indent=2))


# ── Session commands ─────────────────────────────────────────────────────

def cmd_session_save(args: argparse.Namespace) -> None:
    """Save a session note."""
    notes = {}
    if args.notes:
        try:
            notes = json.loads(args.notes)
        except json.JSONDecodeError:
            notes = {"text": args.notes}
    result = _api("POST", "/api/internal/session-note", {
        "project_id": int(PROJECT_ID),
        "agent_id": AGENT_ID,
        "phase": args.phase,
        "notes": notes,
    })
    print(json.dumps(result, indent=2))


def cmd_session_load(args: argparse.Namespace) -> None:
    """Load the latest session note."""
    result = _api("GET",
        f"/api/internal/session-note?project_id={PROJECT_ID}&agent_id={AGENT_ID}")
    print(json.dumps(result, indent=2))


# ── CLI parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="infinibay",
        description="CLI helper for INFINIBAY agents inside sandbox pods",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # task
    task_parser = sub.add_parser("task", help="Task operations")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)

    p = task_sub.add_parser("get", help="Get task details")
    p.add_argument("id", type=int, help="Task ID")
    p.set_defaults(func=cmd_task_get)

    p = task_sub.add_parser("list", help="List tasks")
    p.add_argument("--status", help="Filter by status")
    p.set_defaults(func=cmd_task_list)

    p = task_sub.add_parser("update-status", help="Update task status")
    p.add_argument("id", type=int, help="Task ID")
    p.add_argument("status", help="New status")
    p.set_defaults(func=cmd_task_update_status)

    p = task_sub.add_parser("add-comment", help="Add task comment")
    p.add_argument("id", type=int, help="Task ID")
    p.add_argument("text", help="Comment text")
    p.set_defaults(func=cmd_task_add_comment)

    # chat
    chat_parser = sub.add_parser("chat", help="Chat operations")
    chat_sub = chat_parser.add_subparsers(dest="chat_command", required=True)

    p = chat_sub.add_parser("send", help="Send a message")
    p.add_argument("--to", required=True, help="Recipient agent ID")
    p.add_argument("message", help="Message content")
    p.set_defaults(func=cmd_chat_send)

    p = chat_sub.add_parser("read", help="Read messages")
    p.add_argument("--unread-only", action="store_true", help="Only unread messages")
    p.set_defaults(func=cmd_chat_read)

    p = chat_sub.add_parser("ask-team-lead", help="Ask the team lead")
    p.add_argument("question", help="Question to ask")
    p.set_defaults(func=cmd_chat_ask_team_lead)

    # git
    git_parser = sub.add_parser("git", help="Git operations")
    git_sub = git_parser.add_subparsers(dest="git_command", required=True)

    p = git_sub.add_parser("create-pr", help="Create a pull request")
    p.add_argument("--title", required=True, help="PR title")
    p.add_argument("--base", default="main", help="Base branch (default: main)")
    p.add_argument("--head", help="Head branch (default: current branch)")
    p.add_argument("--body", help="PR description")
    p.set_defaults(func=cmd_git_create_pr)

    # session
    session_parser = sub.add_parser("session", help="Session management")
    session_sub = session_parser.add_subparsers(dest="session_command", required=True)

    p = session_sub.add_parser("save", help="Save session note")
    p.add_argument("--phase", required=True, help="Current phase")
    p.add_argument("--notes", help="JSON notes or plain text")
    p.set_defaults(func=cmd_session_save)

    p = session_sub.add_parser("load", help="Load session note")
    p.set_defaults(func=cmd_session_load)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
