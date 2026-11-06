"""SQLite planning adapter: immutable original inputs, fenced proposals and atomic explicit owner graph expansion; no inference or dispatch."""

import json
from dataclasses import asdict
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.planning.models import validate_plan
from backend.planning.project_history import capture_project_history
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    RunSpec,
    WorkspaceBinding,
    command_key,
    text,
)


class ProjectPlans:
    """Own one planning proposal and its original owner decision without letting model output create or complete other work."""

    def __init__(self, runs):
        """Use the original scoped run store; construction has no side effects."""
        self.runs = runs

    @staticmethod
    def _project(conn, project_id):
        """Read only project premises; operational progress/status is not a planning requirement change."""
        row = conn.execute(
            "SELECT name,description FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        if row is None:
            raise RunNotFound("Project not found")
        return dict(row)

    @classmethod
    def capture(cls, conn, runs, spec, run_id):
        """Freeze original plan task/project material in its admission transaction, before any native authority exists."""
        task = conn.execute(
            "SELECT type FROM tasks WHERE project_id=? AND id=?",
            (spec.project_id, spec.task_id),
        ).fetchone()
        if task is None or task["type"] != "plan":
            return
        project = cls._project(conn, spec.project_id)
        start = conn.execute(
            "SELECT request_json FROM runtime_project_plan_starts WHERE project_id=? AND task_id=?",
            (spec.project_id, spec.task_id),
        ).fetchone()
        origin = "owner_message"
        if start is not None:
            origin = (
                "owner_message"
                if json.loads(start["request_json"])["intent"]["prompt"] is not None
                else "host_default"
            )
        task_context = runs._context_snapshot(conn, spec.project_id, spec.task_id)
        snapshot = {
            "project": project,
            "owner_request": spec.prompt,
            "instruction_origin": origin,
            "task_context": task_context,
            "source_origins": {
                "owner_request": origin,
                "project_name": "project_metadata",
                "project_description": "project_metadata",
                "task_description": "task_metadata",
                "acceptance_criteria": "task_metadata",
            },
            "sources": {
                "owner_request": spec.prompt,
                "project_name": project["name"],
                "project_description": project["description"] or "",
                "task_description": task_context["task"]["description"] or "",
                "acceptance_criteria": task_context["task"]["acceptance_criteria"]
                or "",
            },
        }
        snapshot["project_history"] = capture_project_history(
            conn, spec.project_id, spec.task_id, snapshot["sources"], snapshot["source_origins"]
        )
        for correction in task_context["corrections"]:
            key = "correction:" + str(correction["version"])
            snapshot["sources"][key] = correction["statement"]
            snapshot["source_origins"][key] = correction["source_kind"]
        conn.execute(
            "INSERT INTO runtime_project_plan_requests(run_id,project_id,task_id,context_version,snapshot_json,snapshot_sha256,created_at)VALUES(?,?,?,?,?,?,?)",
            (
                run_id,
                spec.project_id,
                spec.task_id,
                spec.context_version,
                canonical(snapshot),
                digest(snapshot),
                runs.clock(),
            ),
        )

    def _request(self, conn, project_id, run_id):
        """Resolve planning only inside its original project/run; labels or role names cannot manufacture its scope."""
        row = conn.execute(
            "SELECT *FROM runtime_project_plan_requests WHERE project_id=? AND run_id=?",
            (project_id, run_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Structured planning request not found")
        return dict(row)

    def current(self, conn, run):
        """Revalidate exact project premises for a planning run while ordinary native runs retain their existing subject policy."""
        row = conn.execute(
            "SELECT *FROM runtime_project_plan_requests WHERE project_id=? AND run_id=?",
            (run["project_id"], run["id"]),
        ).fetchone()
        if (
            row is not None
            and self._project(conn, run["project_id"])
            != json.loads(row["snapshot_json"])["project"]
        ):
            raise RunConflict("Original project planning premises changed")
        return dict(row) if row else None

    def material(self, lease, offset=0, max_chars=16000):
        """Read a bounded original JSON context window with explicit total/hash/unread tail; project metadata is attributed data, not shared user knowledge."""
        if (
            type(offset) is not int
            or offset < 0
            or type(max_chars) is not int
            or not 1 <= max_chars <= 24000
        ):
            raise ValueError("Invalid planning context window")
        with self.runs._transaction() as conn:
            run = self.runs._authority(conn, lease)
            row = self._request(conn, lease.project_id, lease.run_id)
            self.current(conn, run)
            full = row["snapshot_json"]
            end = min(len(full), offset + max_chars)
            return {
                "content": full[offset:end],
                "snapshot_sha256": row["snapshot_sha256"],
                "offset": offset,
                "total_chars": len(full),
                "next_offset": end if end < len(full) else None,
                "truncated": end < len(full),
            }

    def propose(self, lease, operation_key, packet):
        """Record one immutable validated DAG under the actual planning lease; this operation creates no task, assignment, acceptance or agent activation."""
        command_key(operation_key)
        with self.runs._transaction(write=True) as conn:
            run = self.runs._authority(conn, lease)
            request = self._request(conn, lease.project_id, lease.run_id)
            self.current(conn, run)
            draft = validate_plan(
                packet, json.loads(request["snapshot_json"])["sources"]
            )
            proposal = {
                "run_id": lease.run_id,
                "attempt_id": lease.attempt_id,
                "context_version": lease.context_version,
                "snapshot_sha256": request["snapshot_sha256"],
                "draft": draft,
            }
            fingerprint = digest(proposal)
            existing = conn.execute(
                "SELECT *FROM runtime_project_plan_proposals WHERE attempt_id=? OR (run_id=? AND operation_key=?)",
                (lease.attempt_id, lease.run_id, operation_key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["operation_key"] != operation_key
                    or existing["proposal_sha256"] != fingerprint
                ):
                    raise RunConflict(
                        "Original planning proposal differs; do not replace its identity"
                    )
                return {
                    **json.loads(existing["proposal_json"]),
                    "proposal_sha256": fingerprint,
                }
            conn.execute(
                "INSERT INTO runtime_project_plan_proposals(id,run_id,attempt_id,operation_key,proposal_sha256,proposal_json,created_at)VALUES(?,?,?,?,?,?,?)",
                (
                    uuid4().hex,
                    lease.run_id,
                    lease.attempt_id,
                    operation_key,
                    fingerprint,
                    canonical(proposal),
                    self.runs.clock(),
                ),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "plan.proposed",
                {
                    "run_id": lease.run_id,
                    "proposal_sha256": fingerprint,
                    "creates_work": False,
                },
            )
            return {**proposal, "proposal_sha256": fingerprint}

    def _ready(self, conn, run, proposal):
        """Require current completed original native authority and actual registered peer closure before owner acceptance can expand work."""
        request = self._request(conn, run["project_id"], run["id"])
        self.current(conn, run)
        if (
            proposal is None
            or proposal["attempt_id"] != run["current_attempt_id"]
            or run["status"] != "needs_review"
            or run["attempt_status"] != "finished"
            or run["cancel_requested"]
            or request["context_version"] != self.runs._context(conn, run["task_id"])
        ):
            raise RunConflict(
                "Planning proposal is not current, completed and awaiting owner decision"
            )
        if (
            not run["native_result_json"]
            or json.loads(run["native_result_json"])["native_status"] != "completed"
        ):
            raise RunConflict("Original planning turn did not complete")
        if (
            conn.execute(
                "SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=? AND protocol_version=1",
                (proposal["attempt_id"],),
            ).fetchone()
            is None
        ):
            raise RunConflict("Original planning peer scope is unconfirmed")
        self.runs._closed_peer_proof(conn, proposal["attempt_id"])
        if conn.execute(
            "SELECT 1 FROM runtime_runs WHERE project_id=? AND task_id=? AND id!=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')",
            (run["project_id"], run["task_id"], run["id"]),
        ).fetchone():
            raise RunConflict("Other unresolved planning work remains")
        return request

    def state(self, project_id, run_id):
        """Read original material/proposal/acceptance after withdrawal, with an explicit current eligibility assessment and no dispatch."""
        with self.runs._transaction() as conn:
            run = self.runs._row(conn, project_id, run_id)
            request = self._request(conn, project_id, run_id)
            proposal = conn.execute(
                "SELECT *FROM runtime_project_plan_proposals WHERE run_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            acceptance = conn.execute(
                "SELECT result_json FROM runtime_project_plan_acceptances WHERE run_id=?",
                (run_id,),
            ).fetchone()
            acceptance_current = bool(
                acceptance
                and run["status"] == "accepted"
                and request["context_version"]
                == self.runs._context(conn, run["task_id"])
            )
            if acceptance_current:
                try:
                    self.current(conn, run)
                except RunConflict:
                    acceptance_current = False
            eligible = False
            reason = ""
            try:
                self._ready(conn, run, proposal)
                eligible = True
            except RunConflict as error:
                reason = str(error)
            return {
                "project_id": project_id,
                "task_id": run["task_id"],
                "run_id": run_id,
                "context_version": request["context_version"],
                "snapshot": json.loads(request["snapshot_json"]),
                "proposal": {
                    **json.loads(proposal["proposal_json"]),
                    "proposal_sha256": proposal["proposal_sha256"],
                }
                if proposal
                else None,
                "acceptance": json.loads(acceptance["result_json"])
                if acceptance
                else None,
                "acceptance_current": acceptance_current,
                "eligible": eligible,
                "blocked_reason": reason,
            }

    def accept(
        self, project_id, run_id, *, operation_key, proposal_sha256, context_version
    ):
        """Atomically expand only the exact closed owner-observed plan; retry returns the same IDs without another graph or execution."""
        command_key(operation_key)
        intent = {
            "kind": "plan.accept",
            "run_id": run_id,
            "proposal_sha256": proposal_sha256,
            "context_version": context_version,
        }
        with self.runs._transaction(write=True) as conn:
            run = self.runs._row(conn, project_id, run_id)
            request = self._request(conn, project_id, run_id)
            receipt = self.runs._receipt(
                conn, project_id, run["task_id"], operation_key, intent
            )
            if receipt is not None:
                return receipt
            proposal = conn.execute(
                "SELECT *FROM runtime_project_plan_proposals WHERE run_id=? AND proposal_sha256=?",
                (run_id, proposal_sha256),
            ).fetchone()
            self._ready(conn, run, proposal)
            if (
                type(context_version) is not int
                or context_version != request["context_version"]
            ):
                raise RunConflict("Owner planning decision uses a different context")
            if conn.execute(
                "SELECT 1 FROM runtime_project_plan_acceptances WHERE run_id=?",
                (run_id,),
            ).fetchone():
                raise RunConflict("Plan already has an original owner acceptance")
            packet = json.loads(proposal["proposal_json"])
            plan = validate_plan(
                packet["draft"], json.loads(request["snapshot_json"])["sources"]
            )
            acceptance_id = uuid4().hex
            epics = {}
            tasks = {}
            for index, epic in enumerate(plan["epics"]):
                epics[epic["key"]] = conn.execute(
                    "INSERT INTO epics(project_id,title,description,order_index,created_by)VALUES(?,?,?,?,'native-plan')",
                    (project_id, epic["title"], epic["description"], index),
                ).lastrowid
            for task in plan["tasks"]:
                tasks[task["key"]] = conn.execute(
                    "INSERT INTO tasks(project_id,epic_id,type,status,title,description,acceptance_criteria,priority,created_by)VALUES(?,?,?,'pending',?,?,?,?,'native-plan')",
                    (
                        project_id,
                        epics[task["epic_key"]],
                        task["type"],
                        task["title"],
                        task["description"],
                        task["acceptance_criteria"],
                        task["priority"],
                    ),
                ).lastrowid
            for task in plan["tasks"]:
                for dep in task["depends_on"]:
                    conn.execute(
                        "INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type)VALUES(?,?,'blocks')",
                        (tasks[task["key"]], tasks[dep]),
                    )
            result = {
                "run_id": run_id,
                "project_id": project_id,
                "task_id": run["task_id"],
                "operation_key": operation_key,
                "proposal_sha256": proposal_sha256,
                "context_version": context_version,
                "epics": epics,
                "tasks": tasks,
                "execution_started": False,
            }
            conn.execute(
                "INSERT INTO runtime_project_plan_acceptances(id,project_id,task_id,run_id,proposal_id,context_version,operation_key,result_json,created_at)VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    acceptance_id,
                    project_id,
                    run["task_id"],
                    run_id,
                    proposal["id"],
                    context_version,
                    operation_key,
                    canonical(result),
                    self.runs.clock(),
                ),
            )
            for key, task_id in tasks.items():
                conn.execute(
                    "INSERT INTO runtime_project_plan_tasks(task_id,acceptance_id,local_key)VALUES(?,?,?)",
                    (task_id, acceptance_id, key),
                )
            conn.execute(
                "UPDATE runtime_runs SET status='accepted',updated_at=?WHERE id=?",
                (self.runs.clock(), run_id),
            )
            conn.execute(
                "UPDATE tasks SET status='done',completed_at=CURRENT_TIMESTAMP WHERE project_id=? AND id=?",
                (project_id, run["task_id"]),
            )
            self.runs._save_receipt(
                conn, project_id, run["task_id"], operation_key, intent, result
            )
            self.runs._event(conn, project_id, run["task_id"], "plan.accepted", result)
            return result

    def start_receipt(self, project_id, run_id):
        """Read the original project-level start intent linked to its admitted run, without exposing source paths or host control state."""
        with self.runs._transaction() as conn:
            row = conn.execute(
                "SELECT s.*FROM runtime_project_plan_starts s JOIN runtime_runs r ON r.project_id=s.project_id AND r.task_id=s.task_id WHERE s.project_id=? AND r.id=?",
                (project_id, run_id),
            ).fetchone()
            if row is None:
                raise RunNotFound("Original native project start not found")
            packet = json.loads(row["request_json"])
            return {"operation_key": row["operation_key"], **packet["intent"]}

    def prepare_start(
        self,
        project_id,
        *,
        operation_key=None,
        prompt=None,
        repository_id=None,
        binding=None,
    ):
        """Keep a project-level start and binding stable before run admission; a response loss or missing admission can never mint another planning task."""
        if prompt is not None:
            text(prompt, "Planning request", 50000)
        body = {"prompt": prompt, "repository_id": repository_id}
        with self.runs._transaction(write=binding is not None) as conn:
            project = self._project(conn, project_id)
            key = operation_key or "project-plan-" + digest(project)
            command_key(key)
            row = conn.execute(
                "SELECT *FROM runtime_project_plan_starts WHERE project_id=? AND operation_key=?",
                (project_id, key),
            ).fetchone()
            if row is not None:
                packet = json.loads(row["request_json"])
                if packet["intent"] != body:
                    raise RunConflict(
                        "Project planning key already identifies another intent"
                    )
                return self._start_packet(row)
            if binding is None:
                return None
            self.runs._check_registration(conn, project_id, binding)
            effective = (
                prompt
                or "Propose an actionable plan for the registered project. Separate observed project data from assumptions. Do not execute the proposed work."
            )
            task_id = conn.execute(
                "INSERT INTO tasks(project_id,type,status,title,description,created_by)VALUES(?,'plan','pending','Planificar el proyecto',?,'native-project-planner')",
                (project_id, effective),
            ).lastrowid
            packet = {"intent": body, "prompt": effective, "context_version": 1}
            conn.execute(
                "INSERT INTO runtime_project_plan_starts(project_id,operation_key,task_id,request_json,binding_json,project_json,created_at)VALUES(?,?,?,?,?,?,?)",
                (
                    project_id,
                    key,
                    task_id,
                    canonical(packet),
                    canonical(asdict(binding)),
                    canonical(project),
                    self.runs.clock(),
                ),
            )
            conn.execute(
                "UPDATE projects SET status='planning'WHERE id=?", (project_id,)
            )
            row = conn.execute(
                "SELECT *FROM runtime_project_plan_starts WHERE project_id=? AND operation_key=?",
                (project_id, key),
            ).fetchone()
            return self._start_packet(row)

    @staticmethod
    def _start_packet(row):
        """Restore the original persisted native request and repository identity without selecting a new source or refreshing its context."""
        packet = json.loads(row["request_json"])
        spec = RunSpec(
            row["project_id"],
            row["task_id"],
            "native-project-planner",
            packet["context_version"],
            "plan-" + digest({"key": row["operation_key"]}),
            packet["prompt"],
            "codex",
        )
        return spec, WorkspaceBinding(**json.loads(row["binding_json"]))
