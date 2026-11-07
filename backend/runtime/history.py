"""Owner-only paginated execution history and recorded work budgets without runtime authority."""

import json
from contextlib import closing
from dataclasses import asdict

from backend.db.connection import connect
from backend.runtime.contracts import RunNotFound, identity
from backend.runtime.sqlite_runs import SQLiteRunStore
from backend.runtime.work_budget import project_work_usage


def _page_arguments(before_seq, limit):
    """Reject ambiguous cursors and unbounded reads before opening a history snapshot."""
    if before_seq is not None and (type(before_seq) is not int or not 1 <= before_seq <= 9223372036854775807):
        raise ValueError("Invalid history cursor")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid history page size")


class RuntimeHistory:
    """Read original scoped receipts while current execution controls retain separate authority."""

    def __init__(self, database):
        """Bind the existing migrated owner database; reads never initialize an installation."""
        self.database = str(database)

    def task_runs(self, project_id, task_id, *, before_seq=None, limit=25):
        """Page all saved task runs by stable sequence, including equal timestamps and old contexts."""
        _page_arguments(before_seq, limit)
        with closing(connect(self.database, existing_only=True)) as conn, conn:
            conn.execute("BEGIN")
            SQLiteRunStore._existing_task(conn, project_id, task_id)
            total = conn.execute("SELECT count(*) FROM runtime_runs WHERE project_id=? AND task_id=?", (project_id, task_id)).fetchone()[0]
            rows = conn.execute(
                "SELECT rowid AS seq,id FROM runtime_runs WHERE project_id=? AND task_id=? AND (? IS NULL OR rowid<?) ORDER BY rowid DESC LIMIT ?",
                (project_id, task_id, before_seq, before_seq, limit + 1),
            ).fetchall()
            items = [dict(asdict(SQLiteRunStore._view(SQLiteRunStore._row(conn, project_id, row["id"]))), seq=str(row["seq"])) for row in rows[:limit]]
        return {"project_id": project_id, "task_id": task_id, "total": total, "items": items,
                "next_before_seq": items[-1]["seq"] if len(rows) > limit else None}

    def attempts(self, project_id, run_id, *, before_seq=None, limit=25):
        """Read each original attempt's model, outcome and usage without substituting current receipts."""
        _page_arguments(before_seq, limit)
        with closing(connect(self.database, existing_only=True)) as conn, conn:
            conn.execute("BEGIN")
            run = SQLiteRunStore._row(conn, project_id, run_id)
            total = conn.execute("SELECT count(*) FROM runtime_attempts WHERE run_id=?", (run_id,)).fetchone()[0]
            rows = conn.execute(
                """SELECT a.fence AS seq,a.id AS attempt_id,a.status,a.started_at,a.ended_at,
                a.thread_id,a.turn_id,a.native_result_json,d.model,d.status AS dispatch_status,
                d.observed_tokens,d.token_ceiling,m.selection_json AS model_selection
                FROM runtime_attempts a
                LEFT JOIN runtime_inference_dispatches d ON d.attempt_id=a.id AND d.project_id=?
                LEFT JOIN runtime_attempt_models m ON m.attempt_id=a.id
                WHERE a.run_id=? AND (? IS NULL OR a.fence<?) ORDER BY a.fence DESC LIMIT ?""",
                (project_id, run_id, before_seq, before_seq, limit + 1),
            ).fetchall()
            items = []
            for row in rows[:limit]:
                item = dict(row)
                item["seq"] = str(item["seq"])
                item["is_current"] = item["attempt_id"] == run["current_attempt_id"]
                item["result"] = json.loads(item.pop("native_result_json")) if row["native_result_json"] else None
                item.pop("native_result_json", None)
                item["model_selection"] = json.loads(item["model_selection"]) if item["model_selection"] else None
                items.append(item)
        return {"project_id": project_id, "run_id": run_id, "total": total, "items": items,
                "next_before_seq": items[-1]["seq"] if len(rows) > limit else None}

    def budget(self, project_id):
        """Explain lifetime project admission accounting; missing subscription quota and price stay unknown."""
        identity(project_id)
        with closing(connect(self.database, existing_only=True)) as conn, conn:
            conn.execute("BEGIN")
            if conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
                raise RunNotFound("Project not found")
            policy = conn.execute("SELECT turn_limit,token_limit FROM runtime_project_budgets WHERE project_id=?", (project_id,)).fetchone()
            usage = project_work_usage(conn, project_id)
        return {"project_id": project_id, "policy": dict(policy) if policy else None, **usage,
                "remaining_turns": max(0, policy["turn_limit"] - usage["used_turns"]) if policy else None,
                "remaining_tokens": max(0, policy["token_limit"] - usage["accounted_tokens"]) if policy else None,
                "overrun_tokens": max(0, usage["accounted_tokens"] - policy["token_limit"]) if policy else None}
