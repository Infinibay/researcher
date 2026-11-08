"""Owner planning metadata with exact recoverable requests, atomic receipts and protected native history.

These operations neither create a native planning request nor authorize task execution.
Legacy callers without a key retain single-call behavior; only a supplied stable key
can recover a delivery whose response was lost.
"""

import json
from uuid import uuid4

from backend.runtime.contracts import RunConflict, RunNotFound, command_key, identity


class OwnerPlanningRecords:
    """Own group/milestone mutations and their project-scoped receipts in one SQLite transaction."""

    def __init__(self, runs):
        """Reuse the existing source-store transaction boundary without activating a runtime."""
        self.runs = runs

    def _create(self, conn, project, key, kind, intent, insert):
        """Return the exact original resource or atomically persist one new effect and its immutable response."""
        identity(project)
        key = key if key is not None else uuid4().hex
        command_key(key)
        if not conn.execute("SELECT 1 FROM projects WHERE id=?", (project,)).fetchone():
            raise RunNotFound("Proyecto no disponible.")
        encoded = json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        previous = conn.execute("SELECT * FROM owner_planning_commands WHERE project_id=? AND operation_key=?", (project, key)).fetchone()
        table = "epics" if kind == "group.create" else "milestones"
        if previous is not None:
            if previous["kind"] != kind or previous["request_json"] != encoded:
                raise RunConflict("La solicitud original identifica otro contenido; no se creó otro registro.")
            if not conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND project_id=?", (previous["resource_id"], project)).fetchone():
                raise RunConflict("Esta solicitud ya creó un registro que se retiró después. No se creó otro; consulta la historia antes de iniciar una solicitud nueva.")
            return json.loads(previous["response_json"])
        resource_id = insert()
        response = dict(conn.execute(f"SELECT * FROM {table} WHERE id=?", (resource_id,)).fetchone())
        response["operation_key"] = key
        response.update(task_count=0, tasks_done=0)
        if kind == "group.create":
            response["milestone_count"] = 0
        conn.execute("INSERT INTO owner_planning_commands(project_id,operation_key,kind,request_json,response_json,resource_id,created_at) VALUES(?,?,?,?,?,?,?)",
            (project, key, kind, encoded, json.dumps(response, ensure_ascii=False), resource_id, self.runs.clock()))
        return response

    def create_group(self, *, project_id, title, description="", priority=2, operation_key=None):
        """Create or recover one exact owner group, preserving its original response after later metadata edits."""
        intent = {"project_id": project_id, "title": title, "description": description, "priority": priority}
        with self.runs._transaction(write=True) as conn:
            def insert():
                """Write only the group metadata inside its request transaction."""
                return conn.execute("INSERT INTO epics(project_id,title,description,status,priority,created_by) VALUES(?,?,?,'open',?,'api')",
                    (project_id, title, description, priority)).lastrowid

            return self._create(conn, project_id, operation_key, "group.create", intent, insert)

    def create_milestone(self, *, epic_id, title, description="", due_date=None, project_id=None, operation_key=None):
        """Bind the milestone to the original project/group before creating or recovering its exact receipt."""
        identity(epic_id)
        with self.runs._transaction(write=True) as conn:
            group = conn.execute("SELECT project_id FROM epics WHERE id=?", (epic_id,)).fetchone()
            if project_id is None:
                if group is None:
                    raise RunNotFound("Grupo no disponible.")
                project_id = group["project_id"]
            intent = {"project_id": project_id, "epic_id": epic_id, "title": title, "description": description, "due_date": due_date}

            def insert():
                """Reject a removed or foreign parent before writing the milestone in the same transaction."""
                if group is None or group["project_id"] != project_id:
                    raise RunNotFound("El grupo no pertenece al proyecto de esta solicitud.")
                return conn.execute("INSERT INTO milestones(project_id,epic_id,title,description,status,due_date) VALUES(?,?,?,?,'open',?)",
                    (project_id, epic_id, title, description, due_date)).lastrowid

            return self._create(conn, project_id, operation_key, "milestone.create", intent, insert)

    @staticmethod
    def _protect(conn, project, resource, kind):
        """Retain native task and accepted-plan history while preserving the existing manual in-progress guard."""
        column = "epic_id" if kind == "group" else "milestone_id"
        key = "epics" if kind == "group" else "milestones"
        if conn.execute(f"SELECT 1 FROM tasks t WHERE t.project_id=? AND t.{column}=? AND (t.status='in_progress' OR EXISTS(SELECT 1 FROM runtime_runs r WHERE r.project_id=t.project_id AND r.task_id=t.id)) LIMIT 1", (project, resource)).fetchone():
            raise RunConflict("Este registro tiene trabajo en curso o historia nativa protegida; no se retiraron sus asociaciones.")
        if conn.execute(f"SELECT 1 FROM runtime_project_plan_acceptances a,json_each(a.result_json,'$.{key}') item WHERE a.project_id=? AND item.value=? LIMIT 1", (project, resource)).fetchone():
            raise RunConflict("Este registro forma parte de un plan aceptado. Su historia se conserva; revisa el plan original antes de cambiarla.")

    def delete_group(self, group_id):
        """Remove only a manual group and its milestones atomically, preserving tasks and native plan history."""
        with self.runs._transaction(write=True) as conn:
            group = conn.execute("SELECT project_id FROM epics WHERE id=?", (group_id,)).fetchone()
            if group is None:
                return False
            self._protect(conn, group["project_id"], group_id, "group")
            for milestone in conn.execute("SELECT id FROM milestones WHERE epic_id=?", (group_id,)):
                self._protect(conn, group["project_id"], milestone["id"], "milestone")
            conn.execute("DELETE FROM milestones WHERE epic_id=?", (group_id,))
            conn.execute("DELETE FROM epics WHERE id=?", (group_id,))
            return True

    def delete_milestone(self, milestone_id):
        """Remove one manual milestone only after checking its original project and native history under the writer lock."""
        with self.runs._transaction(write=True) as conn:
            row = conn.execute("SELECT project_id FROM milestones WHERE id=?", (milestone_id,)).fetchone()
            if row is None:
                return False
            self._protect(conn, row["project_id"], milestone_id, "milestone")
            conn.execute("DELETE FROM milestones WHERE id=?", (milestone_id,))
            return True
