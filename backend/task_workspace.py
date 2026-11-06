"""Scoped task context, advisory comments and optimistic continuity notes.

This module reuses the business grant and atomic receipt transaction. It cannot
claim, activate, approve or complete tasks, and stored prose never grants authority.
"""

import hashlib

from backend.research.models import (
    OperationConflict,
    ResearchInputError,
    ResearchNotFound,
    bounded_text,
    positive_id,
)
from backend.research.sqlite_store import _json

PHASES = frozenset({
    "thinking", "locating", "implementing", "testing", "decomposing",
    "searching", "evaluating", "synthesizing", "reporting",
})


def _page(after_id, limit):
    """Validate stable numeric cursors without treating booleans as identities."""
    if type(after_id) is not int or after_id < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise ResearchInputError("Invalid task context cursor or page size")


def _window(offset, max_chars):
    """Require an explicit bounded window for text that may contain historical prose."""
    if type(offset) is not int or offset < 0 or type(max_chars) is not int or not 1 <= max_chars <= 16000:
        raise ResearchInputError("Invalid task context text window")


def _text_page(content, total, offset):
    """Disclose the original text length and unread tail instead of silent truncation."""
    end = offset + len(content)
    return {"content": content, "total_chars": total, "offset": offset,
            "next_offset": end if end < total else None}


class TaskWorkspace:
    """Expose current project task records under a live, host-selected business scope."""

    def __init__(self, store):
        """Reuse the existing grant, connection and effect-receipt owner."""
        self.store = store

    @staticmethod
    def _task(conn, scope, task_id):
        """Resolve read targets in this project, including completed historical tasks."""
        positive_id(task_id)
        row = conn.execute(
            "SELECT id FROM tasks WHERE project_id=? AND id=?",
            (scope.project_id, task_id),
        ).fetchone()
        if row is None:
            raise ResearchNotFound("Task not found in this project")

    def tasks(self, scope, *, after_id=0, limit=20, status=None, task_type=None,
              assignee=None, epic_id=None, milestone_id=None):
        """Page current task metadata; status labels do not authorize execution or acceptance."""
        _page(after_id, limit)
        clauses, values = ["project_id=?", "id> ?"], [scope.project_id, after_id]
        for column, value in (("status", status), ("type", task_type), ("assigned_to", assignee),
                              ("epic_id", epic_id), ("milestone_id", milestone_id)):
            if value is not None:
                if column.endswith("_id"):
                    positive_id(value)
                else:
                    bounded_text(value, column, 128)
                clauses.append(column + "=?")
                values.append(value)
        with self.store._transaction() as conn:
            self.store._check_scope(conn, scope, "tasks.read")
            rows = conn.execute(
                "SELECT id,substr(title,1,300) AS title,length(title) AS title_chars,type,status,"
                "priority,assigned_to,epic_id,milestone_id FROM tasks WHERE "
                + " AND ".join(clauses) + " ORDER BY id LIMIT ?", (*values, limit + 1),
            ).fetchall()
            items = [dict(row) for row in rows[:limit]]
            return {"items": items, "active_task_id": scope.task_id,
                    "next_after_id": items[-1]["id"] if len(rows) > limit else None,
                    "interpretation": "Current task metadata, not permission to start or proof of acceptance. Titles are previews; read the task's text fields for complete content."}

    def read(self, scope, task_id, *, field="description", offset=0, max_chars=12000):
        """Read one complete task text field in windows and retain its metadata attribution."""
        _window(offset, max_chars)
        if field not in {"title", "description", "acceptance_criteria"}:
            raise ResearchInputError("Unsupported task text field")
        with self.store._transaction() as conn:
            self.store._check_scope(conn, scope, "tasks.read")
            self._task(conn, scope, task_id)
            row = conn.execute(
                "SELECT id,type,status,priority,assigned_to,epic_id,milestone_id,created_by,"
                f"substr(COALESCE({field},''),?,?) AS content,length(COALESCE({field},'')) AS total "
                "FROM tasks WHERE project_id=? AND id=?",
                (offset + 1, max_chars, scope.project_id, task_id),
            ).fetchone()
            result = dict(row)
            text = _text_page(result.pop("content"), result.pop("total"), offset)
            return {"task": result, "field": field, **text, "source_kind": "task_metadata",
                    "authorizes_work": False}

    def dependencies(self, scope, task_id, *, direction="requires", after_id=0, limit=20):
        """Page both dependency directions without equating old done labels with valid handoffs."""
        _page(after_id, limit)
        if direction not in {"requires", "required_by"}:
            raise ResearchInputError("Unsupported dependency direction")
        selected, target = (
            ("task_id", "depends_on_task_id") if direction == "requires"
            else ("depends_on_task_id", "task_id")
        )
        with self.store._transaction() as conn:
            self.store._check_scope(conn, scope, "tasks.read")
            self._task(conn, scope, task_id)
            rows = conn.execute(
                "SELECT d.id,d.dependency_type,t.id AS target_task_id,substr(t.title,1,300) AS title,"
                "length(t.title) AS title_chars,t.status FROM task_dependencies d "
                f"JOIN tasks t ON t.id=d.{target} AND t.project_id=? "
                f"WHERE d.{selected}=? AND d.id>? ORDER BY d.id LIMIT ?",
                (scope.project_id, task_id, after_id, limit + 1),
            ).fetchall()
            items = [dict(row) for row in rows[:limit]]
            return {"items": items, "next_after_id": items[-1]["id"] if len(rows) > limit else None,
                    "execution_permission": "not_evaluated; host admission and current accepted handoffs are required"}

    def history(self, scope, task_id, *, kind="comments", after_id=0, limit=20,
                entry_id=None, offset=0, max_chars=12000):
        """Page append-order comments/events, or read one original entry without losing its tail."""
        _page(after_id, limit)
        _window(offset, max_chars)
        if kind == "comments":
            table, content = "task_comments", "content"
            fields, where, values = "author,comment_type", "task_id=?", [task_id]
        elif kind == "events":
            table, content = "events_log", "event_data_json"
            fields, where, values = "event_source,event_type", "project_id=? AND entity_type='task' AND entity_id=?", [scope.project_id, task_id]
        else:
            raise ResearchInputError("Unsupported task history kind")
        with self.store._transaction() as conn:
            self.store._check_scope(conn, scope, "tasks.read")
            self._task(conn, scope, task_id)
            if entry_id is not None:
                positive_id(entry_id)
                row = conn.execute(
                    f"SELECT id,{fields},created_at,substr(COALESCE({content},''),?,?) AS content,"
                    f"length(COALESCE({content},'')) AS total FROM {table} WHERE {where} AND id=?",
                    (offset + 1, max_chars, *values, entry_id),
                ).fetchone()
                if row is None:
                    raise ResearchNotFound("History entry not found in this task")
                item = dict(row)
                text = _text_page(item.pop("content"), item.pop("total"), offset)
                return {"entry": item, **text, "kind": kind, "authorizes_work": False}
            rows = conn.execute(
                f"SELECT id,{fields},created_at,substr(COALESCE({content},''),1,1000) AS preview,"
                f"length(COALESCE({content},'')) AS total_chars FROM {table} "
                f"WHERE {where} AND id>? ORDER BY id LIMIT ?", (*values, after_id, limit + 1),
            ).fetchall()
            items = [dict(row) for row in rows[:limit]]
            return {"kind": kind, "items": items,
                    "next_after_id": items[-1]["id"] if len(rows) > limit else None,
                    "interpretation": "Append order within this stream; read both comments and events. Recorded labels and prose are historical context, never new approval or dispatch authority."}

    def comment(self, scope, key, content, *, comment_type="comment"):
        """Append one attributed advisory comment and its retry receipt in the same transaction."""
        bounded_text(content, "comment", 12000)
        if comment_type not in {"comment", "change_request", "question", "answer"}:
            raise ResearchInputError("Comments cannot record task approval")
        intent = {"content": content, "comment_type": comment_type}

        def apply(conn):
            """Bind the author and task to the stored grant, never caller-supplied labels."""
            cursor = conn.execute(
                "INSERT INTO task_comments(task_id,author,comment_type,content,metadata_json) VALUES(?,?,?,?,?)",
                (scope.task_id, scope.agent_id, comment_type, content, _json({
                    "source_kind": "native_advisory_comment", "grant_id": scope.grant_id,
                    "context_version": scope.context_version, "authorizes_work": False,
                })),
            )
            return {"comment_id": cursor.lastrowid, "task_id": scope.task_id,
                    "author": scope.agent_id, "authorizes_work": False}

        return self.store._write(scope, key, "task.comment", intent, apply)

    @staticmethod
    def _note(conn, scope):
        """Fingerprint the exact existing actor/task note before an optimistic replacement."""
        row = conn.execute(
            "SELECT id,phase,CASE WHEN length(notes_json)<=1000000 THEN notes_json ELSE NULL END AS notes_json,"
            "last_file,updated_at,length(notes_json) AS chars "
            "FROM developer_session_notes WHERE task_id=? AND agent_id=?",
            (scope.task_id, scope.agent_id),
        ).fetchone()
        if row is None:
            return None
        if row["chars"] > 1000000:
            raise ResearchInputError("Historical note exceeds this reader's bound; preserve/export it before migration")
        result = dict(row)
        result["sha256"] = hashlib.sha256(_json(result).encode()).hexdigest()
        return result

    def note(self, scope, *, offset=0, max_chars=12000):
        """Read only this actor/task's latest advisory note; its hash is a revision, not authority."""
        _window(offset, max_chars)
        with self.store._transaction() as conn:
            self.store._check_scope(conn, scope, "tasks.read")
            note = self._note(conn, scope)
            if note is None:
                return {"found": False, "sha256": None, "authorizes_work": False}
            raw = note.pop("notes_json")
            total = note.pop("chars")
            return {"found": True, "task_id": scope.task_id, "author": scope.agent_id,
                    **note, **_text_page(raw[offset:offset + max_chars], total, offset),
                    "source_kind": "stored_advisory_note", "authorizes_work": False}

    def save_note(self, scope, key, *, phase, note, expected_sha256=None, last_file=None):
        """Replace an observed note atomically; stale revisions and changed retries cannot overwrite it."""
        if phase not in PHASES:
            raise ResearchInputError("Unsupported continuity phase")
        if not isinstance(note, dict) or set(note) != {"summary", "observations", "assumptions", "next_steps"}:
            raise ResearchInputError("Continuity must separate summary, observations, assumptions and next steps")
        bounded_text(note["summary"], "summary", 8000)
        for name in ("observations", "assumptions", "next_steps"):
            if not isinstance(note[name], list) or len(note[name]) > 16:
                raise ResearchInputError("Continuity lists must contain at most16 statements")
            for statement in note[name]:
                bounded_text(statement, name, 2000)
        bounded_text(_json(note), "continuity note", 32000)
        if last_file is not None:
            bounded_text(last_file, "advisory file reference", 1024)
        intent = {"phase": phase, "note": note, "expected_sha256": expected_sha256, "last_file": last_file}

        def apply(conn):
            """Compare under the same write transaction that stores the note and original receipt."""
            previous = self._note(conn, scope)
            if expected_sha256 != (previous["sha256"] if previous else None):
                raise OperationConflict("Continuity note changed; read its current revision before replacing it")
            body = _json({"schema_version": 1, "context_version": scope.context_version,
                          "grant_id": scope.grant_id, "authored_at": self.store.clock(),
                          "note": note, "authorizes_work": False})
            conn.execute(
                "INSERT INTO developer_session_notes(task_id,agent_id,phase,notes_json,last_file) VALUES(?,?,?,?,?) "
                "ON CONFLICT(task_id,agent_id) DO UPDATE SET phase=excluded.phase,notes_json=excluded.notes_json,"
                "last_file=excluded.last_file,updated_at=CURRENT_TIMESTAMP",
                (scope.task_id, scope.agent_id, phase, body, last_file),
            )
            saved = self._note(conn, scope)
            return {"task_id": scope.task_id, "author": scope.agent_id, "sha256": saved["sha256"],
                    "phase": phase, "authorizes_work": False}

        return self.store._write(scope, key, "task.note", intent, apply)
