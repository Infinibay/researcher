"""Read projections for the authenticated owner, never agent bearer authority."""

import json
from contextlib import closing
from dataclasses import asdict

from backend.db.connection import connect
from backend.runtime.contracts import RunNotFound, identity
from backend.runtime.run_inputs import MESSAGE_SELECT
from backend.runtime.sqlite_runs import SQLiteRunStore


class OwnerRuntimeView:
    def __init__(self, database):
        self.database = str(database)
        self.runs = SQLiteRunStore(database)

    def question_inbox(self, project_id, *, after_id=0, limit=100):
        identity(project_id)
        if type(after_id) is not int or not 0 <= after_id <= 9223372036854775807:
            raise ValueError("Invalid question cursor")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid question page size")
        with closing(connect(self.database)) as conn, conn:
            conn.execute("BEGIN")
            if (
                conn.execute(
                    "SELECT 1 FROM projects WHERE id=?", (project_id,)
                ).fetchone()
                is None
            ):
                raise RunNotFound("Project not found")
            total = conn.execute(
                "SELECT COUNT(*) FROM user_requests WHERE project_id=? AND status='pending'",
                (project_id,),
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT u.id AS request_id,u.title,u.body,u.created_at,u.request_type,
                q.run_id,q.context_version,q.question_set_json,q.thread_id,
                r.task_id,r.status AS run_status,t.title AS task_title,
                COALESCE(c.version,1) AS current_context_version
                FROM user_requests u
                LEFT JOIN runtime_question_links q ON q.request_id=u.id AND q.project_id=u.project_id
                LEFT JOIN runtime_runs r ON r.id=q.run_id AND r.project_id=u.project_id
                LEFT JOIN tasks t ON t.id=r.task_id AND t.project_id=u.project_id
                LEFT JOIN task_contexts c ON c.task_id=t.id
                WHERE u.project_id=? AND u.status='pending' AND u.id>?
                ORDER BY u.id LIMIT ?""",
                (project_id, after_id, limit + 1),
            ).fetchall()
        return {
            "items": [
                {
                    "request_id": row["request_id"],
                    "kind": "native" if row["run_id"] is not None else "legacy",
                    "title": row["title"],
                    "body": row["body"],
                    "request_type": row["request_type"],
                    "created_at": row["created_at"],
                    "task_id": row["task_id"],
                    "task_title": row["task_title"],
                    "run_id": row["run_id"],
                    "thread_id": row["thread_id"],
                    "context_version": row["context_version"],
                    "current_context_version": row["current_context_version"]
                    if row["task_id"] is not None
                    else None,
                    "questions": json.loads(row["question_set_json"])
                    if row["question_set_json"]
                    else None,
                    "ready_for_answer": row["run_status"] == "waiting_input"
                    and row["context_version"] == row["current_context_version"],
                }
                for row in rows[:limit]
            ],
            "total_pending": total,
            "next_after_id": rows[limit - 1]["request_id"]
            if len(rows) > limit
            else None,
        }

    def workspace(self, project_id, task_id):
        context = self.runs.context_snapshot(project_id, task_id)
        runs = self.runs.task_runs(project_id, task_id)
        with closing(connect(self.database)) as conn:
            sources = conn.execute(
                """SELECT id,title,kind,sha256,captured_at,task_id AS captured_for_task_id
                FROM research_sources WHERE project_id=? ORDER BY id DESC LIMIT 100""",
                (project_id,),
            ).fetchall()
            reports = conn.execute(
                """SELECT a.id,r.title,r.status,a.created_at FROM artifacts a
                JOIN research_reports r ON r.artifact_id=a.id WHERE a.project_id=? AND a.task_id=? ORDER BY a.id DESC LIMIT 100""",
                (project_id, task_id),
            ).fetchall()
            repositories = conn.execute(
                "SELECT id,name,default_branch FROM repositories WHERE project_id=? AND status='active' ORDER BY id",
                (project_id,),
            ).fetchall()
            references = conn.execute(
                "SELECT id,file_name,file_type FROM reference_files WHERE project_id=? ORDER BY id",
                (project_id,),
            ).fetchall()
            questions = conn.execute(
                """SELECT q.request_id,q.run_id,q.context_version,q.question_set_json,q.answer_context_version,
                u.status,u.response,r.status AS run_status FROM runtime_question_links q
                JOIN user_requests u ON u.id=q.request_id JOIN runtime_runs r ON r.id=q.run_id
                WHERE q.project_id=? AND r.task_id=? ORDER BY q.request_id""",
                (project_id, task_id),
            ).fetchall()
        return {
            "context": context,
            "runs": [asdict(run) for run in runs],
            "sources": [dict(row) for row in sources],
            "reports": [dict(row) for row in reports],
            "repositories": [dict(row) for row in repositories],
            "references": [dict(row) for row in references],
            "questions": [
                {
                    "request_id": q["request_id"],
                    "run_id": q["run_id"],
                    "context_version": q["context_version"],
                    "questions": json.loads(q["question_set_json"]),
                    "status": q["status"],
                    "answers": json.loads(q["response"]) if q["response"] else None,
                    "answer_context_version": q["answer_context_version"],
                    "ready_for_answer": q["status"] == "pending"
                    and q["run_status"] == "waiting_input",
                }
                for q in questions
            ],
        }

    def source(self, project_id, source_id, *, offset=0, max_chars=12000):
        with closing(connect(self.database)) as conn:
            row = conn.execute(
                "SELECT * FROM research_sources WHERE project_id=? AND id=?",
                (project_id, source_id),
            ).fetchone()
            if row is None:
                raise RunNotFound("Captured source not found in this project")
            content = row["content"]
            end = min(len(content), offset + max_chars)
            return {
                "source_id": source_id,
                "project_id": project_id,
                "title": row["title"],
                "kind": row["kind"],
                "sha256": row["sha256"],
                "captured_at": row["captured_at"],
                "provenance": json.loads(row["provenance_json"]),
                "content": content[offset:end],
                "offset": offset,
                "total_chars": len(content),
                "next_offset": end if end < len(content) else None,
            }

    def instruction_message(self, project_id, run_id):
        with closing(connect(self.database)) as conn:
            row = conn.execute(
                MESSAGE_SELECT
                + " WHERE cm.project_id=? AND r.id=? AND cm.id=link.user_message_id",
                (project_id, run_id),
            ).fetchone()
            if row is None:
                raise RunNotFound("Instruction not found in this project")
            return dict(row)
