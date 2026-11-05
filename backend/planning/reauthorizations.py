"""Immutable owner adoption of a corrected graph and exact historical evidence, using the existing native execution owner."""

import json
from dataclasses import asdict
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.planning.store import ProjectPlans
from backend.runtime.contracts import RunConflict, command_key
from backend.runtime.peer_process import PeerUncertain
from backend.runtime.peer_registry import PeerRegistry


class PlanReauthorizations:
    """Own successive explicit graph decisions without changing the original model proposal, acceptance or execution receipt."""

    def __init__(self, executions):
        """Reuse the single transaction journal and deterministic dispatcher; create no sessions, tasks or secondary coordinator."""
        self.executions = executions
        self.runs = executions.runs

    def _history(self, conn, project, task_ids, *, only_ids=None):
        """Require closure of every related attempt and retain stable execution/effect facts; operational supersession cannot erase or rewrite the observations."""
        history = []
        peers = PeerRegistry(self.runs)
        for task in task_ids:
            for reference in conn.execute(
                "SELECT id FROM runtime_runs WHERE project_id=? AND task_id=? ORDER BY rowid",
                (project, task),
            ):
                if only_ids is not None and reference[0] not in only_ids:
                    continue
                run = self.runs._row(conn, project, reference[0])
                if run["status"] in ("running", "cancelling", "reconciling"):
                    raise RunConflict(
                        "Reconcile every original attempt before reauthorizing the graph"
                    )
                attempts = []
                for attempt in conn.execute(
                    "SELECT *FROM runtime_attempts WHERE run_id=? ORDER BY started_at,id",
                    (run["id"],),
                ):
                    scope = conn.execute(
                        "SELECT protocol_version FROM runtime_peer_scopes WHERE attempt_id=?",
                        (attempt["id"],),
                    ).fetchone()
                    if scope is None or scope[0] != 1:
                        raise RunConflict(
                            "Historical attempt has no known peer closure protocol"
                        )
                    for peer in conn.execute(
                        "SELECT *FROM runtime_peers WHERE attempt_id=?",
                        (attempt["id"],),
                    ):
                        try:
                            peers._check_origin(peer)
                        except PeerUncertain as error:
                            raise RunConflict(
                                "Original peer origin needs reconciliation"
                            ) from error
                    self.runs._closed_peer_proof(conn, attempt["id"])
                    if conn.execute(
                        """SELECT 1 FROM runtime_jobs j WHERE attempt_id=? AND status<>'exited'
                        AND NOT EXISTS(SELECT 1 FROM runtime_peers p WHERE p.id=j.peer_id AND p.attempt_id=j.attempt_id
                        AND p.kind='command' AND p.state='closed' AND p.database_identity IS NOT NULL)""",
                        (attempt["id"],),
                    ).fetchone():
                        raise RunConflict("Original job closure is unproven")
                    inference = conn.execute(
                        "SELECT *FROM runtime_inference_dispatches WHERE attempt_id=?",
                        (attempt["id"],),
                    ).fetchone()
                    effects = [
                        dict(e)
                        for e in conn.execute(
                            "SELECT o.operation_key,o.kind,o.result_json FROM tool_operations o JOIN tool_grants g ON g.id=o.grant_id WHERE g.runtime_attempt_id=? ORDER BY o.operation_key",
                            (attempt["id"],),
                        )
                    ]
                    attempts.append(
                        {
                            "attempt_id": attempt["id"],
                            "native_result_json": attempt["native_result_json"],
                            "inference": dict(inference) if inference else None,
                            "effects": effects,
                            "jobs": [
                                dict(j)
                                for j in conn.execute(
                                    "SELECT id,status,exit_code,output_limited FROM runtime_jobs WHERE attempt_id=? ORDER BY id",
                                    (attempt["id"],),
                                )
                            ],
                        }
                    )
                view = asdict(self.runs._view(run))
                for key in ("status", "fence", "cancel_requested"):
                    view.pop(key)
                remote = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT effect_name,operation_id,state,outcome_json,client_closed FROM runtime_remote_effects WHERE run_id=? ORDER BY effect_name",
                        (run["id"],),
                    )
                ]
                if any(not item["client_closed"] for item in remote):
                    raise RunConflict(
                        "Original remote effect transport still needs closure reconciliation"
                    )
                candidate = conn.execute(
                    "SELECT attempt_id,state,head_sha,tree_sha,diff_sha256,issue FROM runtime_code_candidates WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
                    (run["id"],),
                ).fetchone()
                history.append(
                    {
                        "run": view,
                        "status_at_decision": run["status"],
                        "attempts": attempts,
                        "remote_effects": remote,
                        "candidate": dict(candidate) if candidate else None,
                    }
                )
        return history

    @staticmethod
    def _facts(history):
        """Exclude lifecycle labels changed by this decision while keeping all original input, output, effect and budget observations exact."""
        return [
            {k: v for k, v in item.items() if k != "status_at_decision"}
            for item in history
        ]

    def _snapshot(self, conn, execution):
        """Compose an exact reviewable current graph, changes and closed history; neither a metadata edit nor original plan acceptance alone grants this authority."""
        if execution["status"] != "paused":
            raise RunConflict("Pause dispatch before reviewing graph reauthorization")
        manifest = self.executions._manifest(
            conn, execution["project_id"], execution["plan_run_id"], reauthorized=True
        )
        graph = {t["task_id"]: set(t["depends_on"]) for t in manifest["tasks"]}
        remaining, done = dict(graph), set()
        while remaining:
            ready = {key for key, deps in remaining.items() if deps <= done}
            if not ready:
                raise RunConflict("Corrected graph dependencies contain a cycle")
            done.update(ready)
            remaining = {
                key: deps for key, deps in remaining.items() if key not in ready
            }
        project = execution["project_id"]
        corrected = []
        retained = []
        changes = []
        previous = json.loads(execution["manifest_json"])
        if execution["authorization_snapshot_json"]:
            prior_tasks = {
                t["task_id"]: t["task"]
                for t in json.loads(execution["authorization_snapshot_json"])[
                    "corrected_tasks"
                ]
            }
        else:
            proposal = conn.execute(
                "SELECT p.proposal_json FROM runtime_project_plan_proposals p JOIN runtime_project_plan_acceptances a ON a.proposal_id=p.id WHERE a.id=?",
                (execution["acceptance_id"],),
            ).fetchone()
            proposed = {t["key"]: t for t in json.loads(proposal[0])["draft"]["tasks"]}
            prior_tasks = {
                r["task_id"]: proposed[r["local_key"]]
                for r in conn.execute(
                    "SELECT task_id,local_key FROM runtime_project_plan_tasks WHERE acceptance_id=?",
                    (execution["acceptance_id"],),
                )
            }
        for task in manifest["tasks"]:
            context = self.runs._context_snapshot(conn, project, task["task_id"])
            if context["task"]["status"] in ("cancelled", "failed"):
                raise RunConflict(
                    "Reopen cancelled or failed tasks before graph reauthorization"
                )
            corrected.append(
                {
                    "task_id": task["task_id"],
                    **context,
                    "depends_on": task["depends_on"],
                    "origin": "observed_task_metadata_and_attributed_corrections",
                }
            )
            old = next(t for t in previous["tasks"] if t["task_id"] == task["task_id"])
            fields = {
                key: {"before": old.get(key), "after": value}
                for key, value in task.items()
                if old.get(key) != value
            }
            for key in (
                "description",
                "acceptance_criteria",
                "type",
                "title",
                "priority",
            ):
                before, after = (
                    prior_tasks[task["task_id"]].get(key),
                    context["task"].get(key),
                )
                if before != after:
                    fields[key] = {"before": before, "after": after}
            if fields:
                changes.append({"task_id": task["task_id"], "changes": fields})
            accepted = self.executions._prerequisites(
                conn, project, {"depends_on": [task["task_id"]]}
            )
            if accepted:
                retained.extend(accepted)
            elif context["task"]["status"] == "done":
                raise RunConflict(
                    "Completed task has no current native acceptance; inspect its status before reauthorization"
                )
        original = ProjectPlans(self.runs)._request(
            conn, project, execution["plan_run_id"]
        )
        old_project = previous.get(
            "project", json.loads(original["snapshot_json"])["project"]
        )
        if manifest["project"] != old_project:
            changes.append(
                {"project": {"before": old_project, "after": manifest["project"]}}
            )
        history = self._history(conn, project, graph)
        return {
            "execution_id": execution["id"],
            "previous_revision": execution["authorization_revision"],
            "previous_manifest_sha256": execution["manifest_sha256"],
            "manifest": manifest,
            "plan_context": self.runs._context_snapshot(
                conn, project, manifest["plan_task_id"]
            ),
            "corrected_tasks": corrected,
            "changes": changes,
            "retained_results": retained,
            "history": history,
            "history_sha256": digest(self._facts(history)),
            "limitations": [
                "Original model plan and acceptances stay historical; this is a new owner decision over the observed corrected graph.",
                "Closed proposals replaced by this decision remain evidence, not accepted results. Prior effects and consumed or uncertain inference remain recorded.",
                "Private code candidate files are not adopted into new workspaces. Reauthorization leaves dispatch paused until a separate resume decision.",
            ],
        }

    def state(self, project, execution_id):
        """Offer the exact graph decision without mutating work, accepting results or spending inference."""
        with self.runs._transaction() as conn:
            e = self.executions._execution(conn, project, execution_id)
            snapshot, reason = None, ""
            try:
                snapshot = self._snapshot(conn, e)
            except RunConflict as error:
                reason = str(error)
            return {
                "project_id": project,
                "execution_id": execution_id,
                "plan_run_id": e["plan_run_id"],
                "eligible": snapshot is not None,
                "snapshot": snapshot,
                "snapshot_sha256": digest(snapshot) if snapshot else None,
                "manifest_sha256": digest(snapshot["manifest"]) if snapshot else None,
                "blocked_reason": reason,
            }

    def validate_history(self, conn, execution):
        """Reject late changes to previously observed execution/effect facts without including new explicitly authorized runs in the older snapshot."""
        if not execution["authorization_revision"]:
            return
        frozen = json.loads(execution["authorization_snapshot_json"])
        original_ids = {item["run"]["run_id"] for item in frozen["history"]}
        current = self._history(
            conn,
            execution["project_id"],
            [t["task_id"] for t in frozen["manifest"]["tasks"]],
            only_ids=original_ids,
        )
        if digest(self._facts(current)) != frozen["history_sha256"]:
            raise RunConflict("Original graph reauthorization evidence changed")

    def retained(self, conn, execution, delivery):
        """Allow historical accepted provenance only when the current owner revision explicitly retained that exact still-current result."""
        if not delivery["run_id"] or not execution["authorization_snapshot_json"]:
            return False
        snapshot = json.loads(execution["authorization_snapshot_json"])
        accepted = self.executions._prerequisites(
            conn, execution["project_id"], {"depends_on": [delivery["task_id"]]}
        )
        return bool(
            accepted
            and accepted[0]["run_id"] == delivery["run_id"]
            and accepted[0] in snapshot["retained_results"]
        )

    def authorize(self, project, execution_id, *, operation_key, snapshot_sha256):
        """Atomically adopt one observed graph revision and replace only work needing new authority; exact retries recover the original revision and delivery IDs."""
        command_key(operation_key)
        intent = {
            "kind": "plan.reauthorize",
            "execution_id": execution_id,
            "snapshot_sha256": snapshot_sha256,
        }
        with self.runs._transaction(write=True) as conn:
            e = self.executions._execution(conn, project, execution_id)
            task = json.loads(e["manifest_json"])["plan_task_id"]
            previous = self.runs._receipt(conn, project, task, operation_key, intent)
            if previous is not None:
                return previous
            snapshot = self._snapshot(conn, e)
            if digest(snapshot) != snapshot_sha256:
                raise RunConflict(
                    "Owner graph snapshot is obsolete; observations changed"
                )
            revision = e["authorization_revision"] + 1
            manifest = snapshot["manifest"]
            conn.execute(
                "INSERT INTO runtime_plan_execution_revisions VALUES(?,?,?,?,?,?,?,?)",
                (
                    execution_id,
                    revision,
                    operation_key,
                    canonical(manifest),
                    digest(manifest),
                    canonical(snapshot),
                    snapshot_sha256,
                    self.runs.clock(),
                ),
            )
            keep = {item["task_id"] for item in snapshot["retained_results"]}
            deliveries = {}
            for t in manifest["tasks"]:
                if t["task_id"] in keep:
                    continue
                leaf = conn.execute(
                    "SELECT d.*FROM runtime_plan_deliveries d WHERE execution_id=? AND task_id=? AND NOT EXISTS(SELECT 1 FROM runtime_plan_deliveries child WHERE child.predecessor_delivery_id=d.id)",
                    (execution_id, t["task_id"]),
                ).fetchone()
                for old in conn.execute(
                    "SELECT *FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','needs_review','waiting_input')",
                    (project, t["task_id"]),
                ).fetchall():
                    self.runs._withdraw(conn, old, "superseded")
                    conn.execute(
                        "UPDATE user_requests SET status='expired' WHERE status='pending' AND id IN(SELECT request_id FROM runtime_question_links WHERE run_id=?)",
                        (old["id"],),
                    )
                did = uuid4().hex
                decision = {
                    "kind": "graph_reauthorization",
                    "authorization_revision": revision,
                    "owner_operation_key": operation_key,
                    "snapshot_sha256": snapshot_sha256,
                    "predecessor_delivery_id": leaf["id"],
                    "snapshot": snapshot,
                }
                conn.execute(
                    "INSERT INTO runtime_plan_deliveries(id,execution_id,task_id,operation_key,predecessor_delivery_id,continuation_json)VALUES(?,?,?,?,?,?)",
                    (
                        did,
                        execution_id,
                        t["task_id"],
                        "plan-work-" + did,
                        leaf["id"],
                        canonical(decision),
                    ),
                )
                deliveries[str(t["task_id"])] = did
            result = {
                "project_id": project,
                "plan_run_id": e["plan_run_id"],
                "execution_id": execution_id,
                "operation_key": operation_key,
                "snapshot_sha256": snapshot_sha256,
                "manifest_sha256": digest(manifest),
                "authorization_revision": revision,
                "status": "paused",
                "deliveries": deliveries,
                "retained_results": snapshot["retained_results"],
                "inference_started": False,
            }
            self.runs._save_receipt(conn, project, task, operation_key, intent, result)
            self.runs._event(conn, project, task, "plan.graph_reauthorized", result)
            return result
