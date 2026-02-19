"""Project progress metrics service."""

import sqlite3

from backend.tools.base.db import execute_with_retry


class ProgressService:
    """Calculates project-level progress metrics."""

    @staticmethod
    def get_project_metrics(project_id: int) -> dict:
        """Return a comprehensive progress snapshot for a project."""

        def _query(conn: sqlite3.Connection) -> dict:
            # Task counts by status
            rows = conn.execute(
                """SELECT status, COUNT(*) as cnt
                   FROM tasks WHERE project_id = ?
                   GROUP BY status""",
                (project_id,),
            ).fetchall()
            by_status: dict[str, int] = {r["status"]: r["cnt"] for r in rows}

            total = sum(by_status.values())
            done = by_status.get("done", 0)
            in_progress = by_status.get("in_progress", 0)

            # Blocked: tasks in backlog/pending with at least one unmet blocking dep
            blocked_row = conn.execute(
                """SELECT COUNT(DISTINCT t.id) as cnt
                   FROM tasks t
                   JOIN task_dependencies td ON td.task_id = t.id
                   JOIN tasks dep ON dep.id = td.depends_on_task_id
                   WHERE t.project_id = ?
                     AND t.status IN ('backlog', 'pending')
                     AND td.dependency_type = 'blocks'
                     AND dep.status != 'done'""",
                (project_id,),
            ).fetchone()
            blocked = blocked_row["cnt"] if blocked_row else 0

            # Blocked task details (id, title, and what blocks them)
            blocked_detail_rows = conn.execute(
                """SELECT t.id, t.title, t.status,
                          dep.id as blocking_id, dep.title as blocking_title,
                          dep.status as blocking_status
                   FROM tasks t
                   JOIN task_dependencies td ON td.task_id = t.id
                   JOIN tasks dep ON dep.id = td.depends_on_task_id
                   WHERE t.project_id = ?
                     AND t.status IN ('backlog', 'pending')
                     AND td.dependency_type = 'blocks'
                     AND dep.status != 'done'
                   ORDER BY t.id""",
                (project_id,),
            ).fetchall()

            # Group by blocked task, collecting blockers
            blocked_map: dict[int, dict] = {}
            for bdr in blocked_detail_rows:
                tid = bdr["id"]
                if tid not in blocked_map:
                    blocked_map[tid] = {
                        "id": tid,
                        "title": bdr["title"],
                        "status": bdr["status"],
                        "blocked_by": [],
                    }
                blocked_map[tid]["blocked_by"].append({
                    "id": bdr["blocking_id"],
                    "title": bdr["blocking_title"],
                    "status": bdr["blocking_status"],
                })
            blocked_tasks = list(blocked_map.values())

            completion_pct = round((done / total) * 100) if total > 0 else 0

            # Epic progress
            epic_rows = conn.execute(
                """SELECT e.id, e.title,
                          COUNT(t.id) as total,
                          SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done
                   FROM epics e
                   LEFT JOIN tasks t ON t.epic_id = e.id
                   WHERE e.project_id = ?
                   GROUP BY e.id
                   ORDER BY e.priority ASC, e.id ASC""",
                (project_id,),
            ).fetchall()
            epic_progress = []
            for er in epic_rows:
                ep_total = er["total"] or 0
                ep_done = er["done"] or 0
                epic_progress.append({
                    "id": er["id"],
                    "title": er["title"],
                    "total": ep_total,
                    "done": ep_done,
                    "pct": round((ep_done / ep_total) * 100) if ep_total > 0 else 0,
                })

            # Milestone progress
            ms_rows = conn.execute(
                """SELECT m.id, m.title,
                          COUNT(t.id) as total,
                          SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done
                   FROM milestones m
                   LEFT JOIN tasks t ON t.milestone_id = m.id
                   WHERE m.project_id = ?
                   GROUP BY m.id
                   ORDER BY m.id ASC""",
                (project_id,),
            ).fetchall()
            milestone_progress = []
            for mr in ms_rows:
                ms_total = mr["total"] or 0
                ms_done = mr["done"] or 0
                milestone_progress.append({
                    "id": mr["id"],
                    "title": mr["title"],
                    "total": ms_total,
                    "done": ms_done,
                    "pct": round((ms_done / ms_total) * 100) if ms_total > 0 else 0,
                })

            return {
                "total_tasks": total,
                "done": done,
                "in_progress": in_progress,
                "blocked": blocked,
                "blocked_tasks": blocked_tasks,
                "completion_pct": completion_pct,
                "by_status": by_status,
                "epic_progress": epic_progress,
                "milestone_progress": milestone_progress,
            }

        return execute_with_retry(_query)

    @staticmethod
    def get_blocked_tasks(project_id: int) -> list[dict]:
        """Return tasks blocked by unmet dependencies."""

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT DISTINCT t.id, t.title, t.status,
                          dep.id as blocking_id, dep.title as blocking_title, dep.status as blocking_status
                   FROM tasks t
                   JOIN task_dependencies td ON td.task_id = t.id
                   JOIN tasks dep ON dep.id = td.depends_on_task_id
                   WHERE t.project_id = ?
                     AND t.status IN ('backlog', 'pending')
                     AND td.dependency_type = 'blocks'
                     AND dep.status != 'done'
                   ORDER BY t.id""",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        return execute_with_retry(_query)

    @staticmethod
    def get_epic_progress(project_id: int) -> list[dict]:
        """Return per-epic task completion stats."""

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT e.id, e.title,
                          COUNT(t.id) as total,
                          SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done
                   FROM epics e
                   LEFT JOIN tasks t ON t.epic_id = e.id
                   WHERE e.project_id = ?
                   GROUP BY e.id
                   ORDER BY e.priority ASC, e.id ASC""",
                (project_id,),
            ).fetchall()
            result = []
            for r in rows:
                t = r["total"] or 0
                d = r["done"] or 0
                result.append({
                    "id": r["id"],
                    "title": r["title"],
                    "total": t,
                    "done": d,
                    "pct": round((d / t) * 100) if t > 0 else 0,
                })
            return result

        return execute_with_retry(_query)

    @staticmethod
    def get_milestone_progress(project_id: int) -> list[dict]:
        """Return per-milestone task completion stats."""

        def _query(conn: sqlite3.Connection) -> list[dict]:
            rows = conn.execute(
                """SELECT m.id, m.title,
                          COUNT(t.id) as total,
                          SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done
                   FROM milestones m
                   LEFT JOIN tasks t ON t.milestone_id = m.id
                   WHERE m.project_id = ?
                   GROUP BY m.id
                   ORDER BY m.id ASC""",
                (project_id,),
            ).fetchall()
            result = []
            for r in rows:
                t = r["total"] or 0
                d = r["done"] or 0
                result.append({
                    "id": r["id"],
                    "title": r["title"],
                    "total": t,
                    "done": d,
                    "pct": round((d / t) * 100) if t > 0 else 0,
                })
            return result

        return execute_with_retry(_query)
