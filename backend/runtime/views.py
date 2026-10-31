"""Read projections for the authenticated owner, never agent bearer authority."""

import json
from contextlib import closing
from dataclasses import asdict

from backend.db.connection import connect
from backend.runtime.contracts import RunNotFound
from backend.runtime.sqlite_runs import SQLiteRunStore

MESSAGE_SELECT = """SELECT cm.*,r.id AS runtime_run_id,r.status AS runtime_status,
    r.context_version,r.task_id FROM chat_messages cm
    LEFT JOIN runtime_chat_links link ON cm.id=link.user_message_id OR cm.id=link.proposal_message_id
    LEFT JOIN runtime_runs r ON r.id=link.run_id"""


class OwnerRuntimeView:
    def __init__(self, database):
        self.database = str(database)
        self.runs = SQLiteRunStore(database)

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
        return {
            "context": context,
            "runs": [asdict(run) for run in runs],
            "sources": [dict(row) for row in sources],
            "reports": [dict(row) for row in reports],
            "repositories": [dict(row) for row in repositories],
            "references": [dict(row) for row in references],
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
