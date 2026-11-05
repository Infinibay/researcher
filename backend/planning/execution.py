"""Durable accepted-plan execution adapter: explicit owner authority, original causal deliveries and evidence-bound readiness; no model loop or peer chat control."""

import json
from dataclasses import asdict
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.planning.store import ProjectPlans
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    RunSpec,
    WorkspaceBinding,
    command_key,
)


class PlanExecutions:
    """Own one explicit execution decision per accepted plan; author results still require their existing independent review and owner acceptance."""

    def __init__(self, runs):
        """Reuse the single run journal and its transaction/receipt boundary without owning threads or inference."""
        self.runs = runs

    def _manifest(self, conn, project, plan_run):
        """Capture current accepted plan, original repository and exact node contexts/edges, excluding operational status so accepting a result does not change the intent."""
        run = self.runs._row(conn, project, plan_run)
        request = ProjectPlans(self.runs)._request(conn, project, plan_run)
        ProjectPlans(self.runs).current(conn, run)
        acceptance = conn.execute(
            "SELECT *FROM runtime_project_plan_acceptances WHERE project_id=? AND run_id=?",
            (project, plan_run),
        ).fetchone()
        if (
            acceptance is None
            or run["status"] != "accepted"
            or request["context_version"] != self.runs._context(conn, run["task_id"])
        ):
            raise RunConflict("Plan acceptance is not current")
        tasks = []
        for row in conn.execute(
            "SELECT t.* FROM tasks t JOIN runtime_project_plan_tasks p ON p.task_id=t.id WHERE p.acceptance_id=? ORDER BY t.id",
            (acceptance["id"],),
        ):
            tasks.append(
                {
                    "task_id": row["id"],
                    "context_version": self.runs._context(conn, row["id"]),
                    "type": row["type"],
                    "title": row["title"],
                    "priority": row["priority"],
                    "depends_on": [
                        d[0]
                        for d in conn.execute(
                            "SELECT depends_on_task_id FROM task_dependencies WHERE task_id=? AND dependency_type='blocks' ORDER BY depends_on_task_id",
                            (row["id"],),
                        )
                    ],
                }
            )
        expected = set(json.loads(acceptance["result_json"])["tasks"].values())
        binding = conn.execute(
            "SELECT *FROM runtime_workspace_bindings WHERE run_id=?", (plan_run,)
        ).fetchone()
        if binding is None:
            raise RunConflict("Original plan repository binding is missing")
        if (
            not tasks
            or {t["task_id"] for t in tasks} != expected
            or any(
                t["type"] not in ("research", "code", "bug_fix")
                or not set(t["depends_on"]) <= expected
                for t in tasks
            )
        ):
            raise RunConflict(
                "Accepted graph no longer has its original supported nodes"
            )
        return {
            "plan_run_id": plan_run,
            "plan_task_id": run["task_id"],
            "plan_context_version": request["context_version"],
            "acceptance_id": acceptance["id"],
            "proposal_id": acceptance["proposal_id"],
            "repository": asdict(self.runs._binding_view(binding)),
            "tasks": tasks,
        }

    def _execution(self, conn, project, execution):
        """Resolve a durable execution only in its actual project scope."""
        row = conn.execute(
            "SELECT *FROM runtime_plan_executions WHERE project_id=? AND id=?",
            (project, execution),
        ).fetchone()
        if row is None:
            raise RunNotFound("Plan execution not found in this project")
        return row

    def _current(self, conn, execution, *, active=True):
        """Reject changed premises or paused dispatch; a previous receipt never refreshes the original owner authorization."""
        if active and execution["status"] != "active":
            raise RunConflict("Plan execution is paused")
        manifest = self._manifest(
            conn, execution["project_id"], execution["plan_run_id"]
        )
        if digest(manifest) != execution["manifest_sha256"]:
            raise RunConflict(
                "Execution manifest context or prerequisite premises changed"
            )
        return manifest

    def state(self, project, plan_run):
        """Read preview and original delivery history without granting authority, inference or dispatch."""
        with self.runs._transaction() as conn:
            run = self.runs._row(conn, project, plan_run)
            manifest = None
            reason = ""
            try:
                manifest = self._manifest(conn, project, plan_run)
            except RunConflict as error:
                reason = str(error)
            execution = conn.execute(
                "SELECT *FROM runtime_plan_executions WHERE project_id=? AND plan_run_id=?",
                (project, plan_run),
            ).fetchone()
            result = None
            if execution:
                current = False
                try:
                    self._current(conn, execution, active=False)
                    current = True
                except RunConflict as error:
                    reason = str(error)
                deliveries = []
                for d in conn.execute(
                    "SELECT d.*,h.packet_json FROM runtime_plan_deliveries d LEFT JOIN runtime_plan_handoffs h ON h.delivery_id=d.id WHERE d.execution_id=? ORDER BY d.task_id",
                    (execution["id"],),
                ):
                    status = "pending"
                    issue = d["issue_json"]
                    if d["run_id"]:
                        native = self.runs._row(conn, project, d["run_id"])
                        status = native["status"]
                        issue = native["issue_json"] or issue
                    deliveries.append(
                        {
                            "delivery_id": d["id"],
                            "task_id": d["task_id"],
                            "run_id": d["run_id"],
                            "status": status,
                            "issue": json.loads(issue) if issue else None,
                            "handoff": json.loads(d["packet_json"])
                            if d["packet_json"]
                            else None,
                        }
                    )
                result = {
                    "execution_id": execution["id"],
                    "operation_key": execution["operation_key"],
                    "manifest_sha256": execution["manifest_sha256"],
                    "status": execution["status"],
                    "current": current,
                    "deliveries": deliveries,
                }
            return {
                "project_id": project,
                "task_id": run["task_id"],
                "plan_run_id": plan_run,
                "manifest": manifest,
                "manifest_sha256": digest(manifest) if manifest else None,
                "eligible": manifest is not None and execution is None,
                "blocked_reason": reason,
                "execution": result,
            }

    def authorize(self, project, plan_run, *, operation_key, manifest_sha256):
        """Persist a distinct exact owner decision and one delivery per node; acceptance alone cannot create this authority."""
        command_key(operation_key)
        intent = {
            "kind": "plan.execute",
            "run_id": plan_run,
            "manifest_sha256": manifest_sha256,
        }
        with self.runs._transaction(write=True) as conn:
            run = self.runs._row(conn, project, plan_run)
            previous = self.runs._receipt(
                conn, project, run["task_id"], operation_key, intent
            )
            if previous is not None:
                return previous
            manifest = self._manifest(conn, project, plan_run)
            if digest(manifest) != manifest_sha256:
                raise RunConflict("Owner execution manifest is obsolete")
            if conn.execute(
                "SELECT 1 FROM runtime_plan_executions WHERE plan_run_id=?", (plan_run,)
            ).fetchone():
                raise RunConflict(
                    "Plan already has an original execution; inspect its controls and history"
                )
            for task in manifest["tasks"]:
                conn.execute(
                    "INSERT OR IGNORE INTO task_contexts(task_id,version)VALUES(?,1)",
                    (task["task_id"],),
                )
            eid = uuid4().hex
            now = self.runs.clock()
            conn.execute(
                "INSERT INTO runtime_plan_executions VALUES(?,?,?,?,?,?,?,'active',?,?)",
                (
                    eid,
                    project,
                    plan_run,
                    manifest["acceptance_id"],
                    operation_key,
                    manifest_sha256,
                    canonical(manifest),
                    now,
                    now,
                ),
            )
            for task in manifest["tasks"]:
                did = uuid4().hex
                conn.execute(
                    "INSERT INTO runtime_plan_deliveries(id,execution_id,task_id,operation_key) VALUES(?,?,?,?)",
                    (did, eid, task["task_id"], "plan-work-" + did),
                )
            receipt = {
                "execution_id": eid,
                "project_id": project,
                "task_id": run["task_id"],
                "plan_run_id": plan_run,
                "operation_key": operation_key,
                "manifest_sha256": manifest_sha256,
                "status": "active",
            }
            self.runs._save_receipt(
                conn, project, run["task_id"], operation_key, intent, receipt
            )
            self.runs._event(
                conn, project, run["task_id"], "plan.execution_authorized", receipt
            )
            return receipt

    def control(self, project, execution_id, *, operation_key, manifest_sha256, status):
        """Persist pause/resume before any live notice; resume never replays a previously attempted delivery."""
        command_key(operation_key)
        if status not in ("active", "paused"):
            raise ValueError("Invalid execution control")
        intent = {
            "kind": "plan.execution_control",
            "execution_id": execution_id,
            "manifest_sha256": manifest_sha256,
            "status": status,
        }
        with self.runs._transaction(write=True) as conn:
            e = self._execution(conn, project, execution_id)
            task = json.loads(e["manifest_json"])["plan_task_id"]
            receipt = self.runs._receipt(conn, project, task, operation_key, intent)
            if receipt is not None:
                return receipt
            if manifest_sha256 != e["manifest_sha256"]:
                raise RunConflict(
                    "Control identifies another original execution manifest"
                )
            if status == "active":
                self._current(conn, e, active=False)
            conn.execute(
                "UPDATE runtime_plan_executions SET status=?,updated_at=? WHERE id=?",
                (status, self.runs.clock(), execution_id),
            )
            receipt = {
                "execution_id": execution_id,
                "project_id": project,
                "task_id": task,
                "plan_run_id": e["plan_run_id"],
                "operation_key": operation_key,
                "manifest_sha256": manifest_sha256,
                "status": status,
            }
            self.runs._save_receipt(conn, project, task, operation_key, intent, receipt)
            self.runs._event(conn, project, task, "plan.execution_control", receipt)
            return receipt

    def pause_project(self, project):
        """Close durable project dispatch before enumerating live runs for Stop, without claiming any peer has closed."""
        with self.runs._transaction(write=True) as conn:
            conn.execute(
                "UPDATE runtime_plan_executions SET status='paused',updated_at=? WHERE project_id=? AND status='active'",
                (self.runs.clock(), project),
            )

    def pending(self):
        """List original deliveries from active owner authorizations, including linked queued work for never-started recovery."""
        with self.runs._transaction() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT d.*,e.project_id FROM runtime_plan_deliveries d JOIN runtime_plan_executions e ON e.id=d.execution_id LEFT JOIN runtime_runs r ON r.id=d.run_id WHERE e.status='active' AND (d.run_id IS NULL OR (r.status='queued' AND r.current_attempt_id IS NULL)) ORDER BY e.created_at,d.task_id"
                )
            ]

    def note_issue(self, execution_id, task_id, code):
        """Persist a redacted dispatch impediment once per changed observation; observation failure cannot grant another attempt."""
        with self.runs._transaction(write=True) as conn:
            row = conn.execute(
                "SELECT d.*,e.project_id FROM runtime_plan_deliveries d JOIN runtime_plan_executions e ON e.id=d.execution_id WHERE d.execution_id=? AND d.task_id=?",
                (execution_id, task_id),
            ).fetchone()
            issue = canonical(
                {
                    "code": code,
                    "next_action": "inspect_execution_context_and_original_run",
                }
            )
            if row and row["issue_json"] != issue:
                conn.execute(
                    "UPDATE runtime_plan_deliveries SET issue_json=? WHERE id=?",
                    (issue, row["id"]),
                )
                self.runs._event(
                    conn,
                    row["project_id"],
                    task_id,
                    "work.dispatch_blocked",
                    {"delivery_id": row["id"], "code": code},
                )

    def _prerequisites(self, conn, project, task):
        """Select exact current owner-accepted results, never prose or done alone; retain evidence and limitations for the consumer."""
        results = []
        for dep in task["depends_on"]:
            row = conn.execute(
                "SELECT r.* FROM runtime_runs r JOIN tasks t ON t.project_id=r.project_id AND t.id=r.task_id WHERE r.project_id=? AND r.task_id=? AND t.status='done' AND r.status='accepted' AND r.context_version=? ORDER BY r.created_at DESC LIMIT 1",
                (project, dep, self.runs._context(conn, dep)),
            ).fetchone()
            if row is None:
                return None
            source = {
                "task_id": dep,
                "run_id": row["id"],
                "attempt_id": row["current_attempt_id"],
                "actor_id": row["actor_id"],
                "context_version": row["context_version"],
            }
            accepted = conn.execute(
                "SELECT a.id,a.subject_sha256,a.review_sha256,p.snapshot_json FROM runtime_result_acceptances a JOIN runtime_result_proposals p ON p.id=a.proposal_id WHERE a.run_id=?",
                (row["id"],),
            ).fetchone()
            if accepted:
                source.update(
                    kind="accepted_research_reports",
                    acceptance={
                        key: accepted[key]
                        for key in ("id", "subject_sha256", "review_sha256")
                    },
                    snapshot=json.loads(accepted["snapshot_json"]),
                )
            else:
                accepted = conn.execute(
                    "SELECT a.id,a.subject_sha256,a.review_sha256,a.attempt_id,c.head_sha,c.tree_sha,c.diff_sha256 FROM runtime_code_acceptances a JOIN runtime_code_candidates c ON c.attempt_id=a.attempt_id WHERE a.run_id=?",
                    (row["id"],),
                ).fetchone()
                if accepted is None:
                    return None
                source.update(
                    kind="accepted_code_candidate",
                    acceptance={
                        key: accepted[key]
                        for key in ("id", "subject_sha256", "review_sha256")
                    },
                    snapshot={
                        key: accepted[key]
                        for key in ("attempt_id", "head_sha", "tree_sha", "diff_sha256")
                    },
                    limitation="Candidate acceptance is not publication; do not assume its changes exist in the registered source repository.",
                )
            results.append(source)
        return results

    def prepare(self, execution_id, task_id):
        """Freeze one ready original delivery before admission; unfinished dependencies and attempted deliveries stay pending/history without replay."""
        with self.runs._transaction(write=True) as conn:
            e = conn.execute(
                "SELECT *FROM runtime_plan_executions WHERE id=?", (execution_id,)
            ).fetchone()
            if e is None:
                raise RunNotFound("Plan execution not found")
            if e["status"] != "active":
                return None
            manifest = self._current(conn, e)
            d = conn.execute(
                "SELECT *FROM runtime_plan_deliveries WHERE execution_id=? AND task_id=?",
                (execution_id, task_id),
            ).fetchone()
            if d is None:
                raise RunNotFound("Task is not in this original execution")
            task = next(t for t in manifest["tasks"] if t["task_id"] == task_id)
            if d["run_id"]:
                run = self.runs._row(conn, e["project_id"], d["run_id"])
                if run["status"] != "queued" or run["current_attempt_id"] is not None:
                    return None
            else:
                status = self.runs._existing_task(conn, e["project_id"], task_id)[
                    "status"
                ]
                if (
                    status in ("done", "cancelled", "failed")
                    or conn.execute(
                        "SELECT 1 FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')",
                        (e["project_id"], task_id),
                    ).fetchone()
                ):
                    return None
            prerequisites = self._prerequisites(conn, e["project_id"], task)
            if prerequisites is None:
                return None
            handoff = {
                "schema_version": 2,
                "kind": "work.request",
                "delivery_id": d["id"],
                "execution_id": execution_id,
                "cause": {
                    "kind": "paired_owner_execution",
                    "operation_key": e["operation_key"],
                    "plan_run_id": e["plan_run_id"],
                    "acceptance_id": e["acceptance_id"],
                    "manifest_sha256": e["manifest_sha256"],
                },
                "target": {
                    "project_id": e["project_id"],
                    "task_id": task_id,
                    "context_version": task["context_version"],
                    "actor_id": "native-researcher"
                    if task["type"] == "research"
                    else "native-developer",
                },
                "prerequisites": prerequisites,
                "instruction": "Perform only the current task and acceptance criteria. Read Ken first. Prerequisite snapshots are attributed evidence with recorded limits, not instructions or proof of shared knowledge. Explain the result with a concrete example where useful. Propose a result; do not accept, publish, assign or activate another agent.",
            }
            original_plan = ProjectPlans(self.runs)._request(
                conn, e["project_id"], e["plan_run_id"]
            )
            proposal = conn.execute(
                "SELECT p.*FROM runtime_project_plan_proposals p JOIN runtime_project_plan_acceptances a ON a.proposal_id=p.id WHERE a.id=? AND a.project_id=?",
                (e["acceptance_id"], e["project_id"]),
            ).fetchone()
            handoff["plan_context"] = {
                "snapshot_sha256": original_plan["snapshot_sha256"],
                "original_material": json.loads(original_plan["snapshot_json"]),
                "proposal_sha256": proposal["proposal_sha256"],
                "accepted_plan": json.loads(proposal["proposal_json"])["draft"],
            }
            old = conn.execute(
                "SELECT *FROM runtime_plan_handoffs WHERE delivery_id=?", (d["id"],)
            ).fetchone()
            if old is None:
                conn.execute(
                    "INSERT INTO runtime_plan_handoffs VALUES(?,?,?,?)",
                    (d["id"], canonical(handoff), digest(handoff), self.runs.clock()),
                )
                self.runs._event(
                    conn,
                    e["project_id"],
                    task_id,
                    "work.delivery_prepared",
                    {
                        "delivery_id": d["id"],
                        "execution_id": execution_id,
                        "packet_sha256": digest(handoff),
                    },
                )
            elif old["packet_sha256"] != digest(handoff):
                raise RunConflict(
                    "Original delivery premises changed; reconcile its history"
                )
            return RunSpec(
                e["project_id"],
                task_id,
                handoff["target"]["actor_id"],
                task["context_version"],
                d["operation_key"],
                handoff["instruction"],
                "codex",
            ), WorkspaceBinding(**manifest["repository"])

    def attach(self, conn, spec, run_id):
        """Atomically link native admission to its prepared original delivery; a reserved work key cannot become an unrelated run."""
        if not spec.operation_key.startswith("plan-work-"):
            return
        d = conn.execute(
            "SELECT *FROM runtime_plan_deliveries WHERE operation_key=?",
            (spec.operation_key,),
        ).fetchone()
        if d is None or (d["task_id"] != spec.task_id) or d["run_id"] is not None:
            raise RunConflict("Original work delivery identity differs")
        conn.execute(
            "UPDATE runtime_plan_deliveries SET run_id=? WHERE id=?", (run_id, d["id"])
        )
        row = self.runs._row(conn, spec.project_id, run_id)
        self.input(conn, row)
        self.runs._event(
            conn,
            spec.project_id,
            spec.task_id,
            "work.delivery_admitted",
            {
                "delivery_id": d["id"],
                "execution_id": d["execution_id"],
                "run_id": run_id,
            },
        )

    def input(self, conn, row):
        """Revalidate source acceptances and return the immutable typed delivery for exact native input; ordinary/reviewer runs have no delivery."""
        d = conn.execute(
            "SELECT d.*,h.packet_json,h.packet_sha256 FROM runtime_plan_deliveries d JOIN runtime_plan_handoffs h ON h.delivery_id=d.id WHERE d.run_id=?",
            (row["id"],),
        ).fetchone()
        if d is None:
            return None
        e = self._execution(conn, row["project_id"], d["execution_id"])
        manifest = self._current(conn, e)
        binding = conn.execute(
            "SELECT *FROM runtime_workspace_bindings WHERE run_id=?", (row["id"],)
        ).fetchone()
        if (
            binding is None
            or asdict(self.runs._binding_view(binding)) != manifest["repository"]
        ):
            raise RunConflict("Original execution repository binding changed")
        packet = json.loads(d["packet_json"])
        task = next(t for t in manifest["tasks"] if t["task_id"] == row["task_id"])
        target = packet["target"]
        if (
            digest(packet) != d["packet_sha256"]
            or any(
                target[k] != row[k]
                for k in ("project_id", "task_id", "context_version", "actor_id")
            )
            or packet["prerequisites"]
            != self._prerequisites(conn, row["project_id"], task)
            or row["prompt"] != packet["instruction"]
        ):
            raise RunConflict(
                "Original typed delivery context or accepted evidence changed"
            )
        return packet
