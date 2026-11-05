"""Owner-authorized delivery successors retain closed execution history without replaying a native turn or resetting its budget."""

import json
from dataclasses import asdict
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.runtime.contracts import RunConflict, RunNotFound, command_key
from backend.runtime.peer_process import PeerUncertain
from backend.runtime.recovery import RunRecovery


class PlanContinuations:
    """Bind one new delivery to the exact owner-observed terminal predecessor; the existing dispatcher retains all scheduling authority."""

    def __init__(self, executions):
        """Use the existing plan owner and transaction journal rather than a second worker or coordinator."""
        self.executions = executions
        self.runs = executions.runs

    def _delivery(self, conn, project, execution, delivery):
        """Resolve a lineage node only within its original execution and project."""
        e = self.executions._execution(conn, project, execution)
        d = conn.execute(
            "SELECT *FROM runtime_plan_deliveries WHERE execution_id=? AND id=?",
            (execution, delivery),
        ).fetchone()
        if d is None:
            raise RunNotFound("Delivery not found in this execution")
        return e, d

    def _snapshot(self, conn, e, d, *, successor=None):
        """Require current graph and proven closure, preserving complete saved effects, job uncertainty and consumed inference without treating any of them as fresh instructions."""
        manifest = self.executions._current(conn, e, active=False)
        child = conn.execute(
            "SELECT id FROM runtime_plan_deliveries WHERE predecessor_delivery_id=?",
            (d["id"],),
        ).fetchone()
        if child and (successor is None or child[0] != successor["id"]):
            raise RunConflict("Delivery already has an authorized successor")
        if not d["run_id"]:
            raise RunConflict("Unissued delivery needs dispatch, not a successor")
        run = self.runs._row(conn, e["project_id"], d["run_id"])
        if run["status"] not in ("failed", "cancelled", "superseded"):
            raise RunConflict(
                "Reconcile the original attempt before authorizing a successor"
            )
        if (
            successor is None
            and conn.execute(
                "SELECT 1 FROM runtime_runs WHERE project_id=? AND task_id=? AND id!=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')",
                (
                    e["project_id"],
                    d["task_id"],
                    (successor["run_id"] or "") if successor else "",
                ),
            ).fetchone()
        ):
            raise RunConflict("Task has other active or unreconciled work")
        task = self.runs._existing_task(conn, e["project_id"], d["task_id"])
        if successor is None and task["status"] in ("done", "cancelled", "failed"):
            raise RunConflict("Task no longer admits execution")
        attempts = []
        recovery = RunRecovery(self.runs)
        for attempt in conn.execute(
            "SELECT *FROM runtime_attempts WHERE run_id=? ORDER BY started_at,id",
            (run["id"],),
        ):
            try:
                recovery._protocol(conn, attempt["id"])
            except PeerUncertain as error:
                raise RunConflict(
                    "Original peer origin needs reconciliation"
                ) from error
            self.runs._closed_peer_proof(conn, attempt["id"])
            if conn.execute(
                """SELECT 1 FROM runtime_jobs j WHERE j.attempt_id=? AND j.status<>'exited'
                AND NOT EXISTS(SELECT 1 FROM runtime_peers p WHERE p.id=j.peer_id AND p.attempt_id=j.attempt_id
                AND p.kind='command' AND p.state='closed' AND p.database_identity IS NOT NULL)""",
                (attempt["id"],),
            ).fetchone():
                raise RunConflict("Original jobs still need closure reconciliation")
            dispatch = conn.execute(
                "SELECT *FROM runtime_inference_dispatches WHERE attempt_id=?",
                (attempt["id"],),
            ).fetchone()
            effects = conn.execute(
                "SELECT o.operation_key,o.kind,o.result_json FROM tool_operations o JOIN tool_grants g ON g.id=o.grant_id WHERE g.runtime_attempt_id=? ORDER BY o.operation_key",
                (attempt["id"],),
            ).fetchall()
            attempts.append(
                {
                    "attempt_id": attempt["id"],
                    "thread_id": attempt["thread_id"],
                    "turn_id": attempt["turn_id"],
                    "native_result": json.loads(attempt["native_result_json"])
                    if attempt["native_result_json"]
                    else None,
                    "inference": dict(dispatch) if dispatch else None,
                    "effects": [
                        {
                            "operation_key": x["operation_key"],
                            "kind": x["kind"],
                            "receipt": json.loads(x["result_json"]),
                        }
                        for x in effects
                    ],
                    "jobs": [
                        dict(j)
                        for j in conn.execute(
                            "SELECT id,status,exit_code,output_limited FROM runtime_jobs WHERE attempt_id=? ORDER BY id",
                            (attempt["id"],),
                        )
                    ],
                }
            )
        original = conn.execute(
            "SELECT packet_sha256 FROM runtime_plan_handoffs WHERE delivery_id=?",
            (d["id"],),
        ).fetchone()
        candidate = conn.execute(
            "SELECT attempt_id,state,head_sha,tree_sha,diff_sha256,issue FROM runtime_code_candidates WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
            (run["id"],),
        ).fetchone()
        snapshot = {
            "execution_id": e["id"],
            "predecessor_delivery_id": d["id"],
            "manifest_sha256": e["manifest_sha256"],
            "previous_run": asdict(self.runs._view(run)),
            "original_packet_sha256": original[0] if original else None,
            "attempts": attempts,
            "candidate": dict(candidate) if candidate else None,
            "repository": manifest["repository"],
            "limitations": [
                "Previous effects and inference remain recorded; a successor does not undo them or reset the project budget.",
                "Partial reports and code candidates are historical evidence, not accepted results. Private candidate files are not adopted into the successor workspace.",
                "Unknown job results remain unknown even when their local process is proven closed. Do not repeat an effect merely because its result is unknown.",
            ],
        }
        if e["authorization_revision"]:
            snapshot["authorization_revision"] = e["authorization_revision"]
        return snapshot

    def validate(self, conn, execution, delivery):
        """Keep the predecessor's exact observations current through admission/dispatch; later evidence needs another owner decision, never silent adoption."""
        if delivery["predecessor_delivery_id"] is None:
            return
        _, previous = self._delivery(
            conn,
            execution["project_id"],
            execution["id"],
            delivery["predecessor_delivery_id"],
        )
        snapshot = self._snapshot(conn, execution, previous, successor=delivery)
        frozen = json.loads(delivery["continuation_json"])
        if digest(snapshot) != frozen["snapshot_sha256"]:
            raise RunConflict(
                "Original continuation evidence changed after authorization"
            )

    def state(self, project, execution, delivery):
        """Show exact continuation evidence and impediments without granting work or changing a paused graph."""
        with self.runs._transaction() as conn:
            e, d = self._delivery(conn, project, execution, delivery)
            snapshot, reason = None, ""
            try:
                self.executions._validate_delivery(conn, e, d)
                snapshot = self._snapshot(conn, e, d)
            except RunConflict as error:
                reason = str(error)
            return {
                "project_id": project,
                "execution_id": execution,
                "delivery_id": delivery,
                "eligible": snapshot is not None,
                "snapshot": snapshot,
                "snapshot_sha256": digest(snapshot) if snapshot else None,
                "blocked_reason": reason,
                "dispatch_status": e["status"],
            }

    def authorize(
        self, project, execution, delivery, *, operation_key, snapshot_sha256
    ):
        """Atomically record an exact owner decision and one successor; retries return the original receipt before any current-state checks."""
        command_key(operation_key)
        intent = {
            "kind": "plan.continue_delivery",
            "execution_id": execution,
            "delivery_id": delivery,
            "snapshot_sha256": snapshot_sha256,
        }
        with self.runs._transaction(write=True) as conn:
            e, d = self._delivery(conn, project, execution, delivery)
            plan_task = json.loads(e["manifest_json"])["plan_task_id"]
            old = self.runs._receipt(conn, project, plan_task, operation_key, intent)
            if old is not None:
                return old
            self.executions._validate_delivery(conn, e, d)
            snapshot = self._snapshot(conn, e, d)
            if digest(snapshot) != snapshot_sha256:
                raise RunConflict(
                    "Owner continuation snapshot is obsolete; observations changed"
                )
            successor = uuid4().hex
            conn.execute(
                "INSERT INTO runtime_plan_deliveries(id,execution_id,task_id,operation_key,predecessor_delivery_id,continuation_json)VALUES(?,?,?,?,?,?)",
                (
                    successor,
                    execution,
                    d["task_id"],
                    "plan-work-" + successor,
                    delivery,
                    canonical(
                        {
                            **snapshot,
                            "owner_operation_key": operation_key,
                            "snapshot_sha256": snapshot_sha256,
                        }
                    ),
                ),
            )
            receipt = {
                "project_id": project,
                "execution_id": execution,
                "task_id": d["task_id"],
                "plan_run_id": e["plan_run_id"],
                "predecessor_delivery_id": delivery,
                "previous_run_id": d["run_id"],
                "delivery_id": successor,
                "operation_key": operation_key,
                "snapshot_sha256": snapshot_sha256,
                "inference_started": False,
            }
            self.runs._save_receipt(
                conn, project, plan_task, operation_key, intent, receipt
            )
            self.runs._event(
                conn, project, d["task_id"], "work.continuation_authorized", receipt
            )
            return receipt
