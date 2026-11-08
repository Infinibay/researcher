"""Owner recovery closes registered actors and preserves results without replay."""

import json

from backend.runtime.contracts import RunConflict, command_key, identity, text
from backend.runtime.peer_process import boot_id, observer_namespace
from backend.runtime.peer_registry import PeerRegistry
from backend.runtime.sqlite_runs import _digest


class RunRecovery:
    """Plan and record recovery from original peer/grant identities, preserving receipts."""

    def __init__(self, runs):
        """Bind recovery to the existing run store and its peer registry without discovering or
        starting replacement actors.
        """
        self.runs = runs
        self.peers = PeerRegistry(runs)

    def inspection(self, project_id, run_id):
        """Return bounded current peer/job/effect evidence and protocol/origin blockers for owner
        recovery without retiring actors or replaying effects.
        """
        with self.runs._transaction() as conn:
            row = self.runs._row(conn, project_id, run_id)
            scope = conn.execute(
                "SELECT protocol_version FROM runtime_peer_scopes WHERE attempt_id=?",
                (row["current_attempt_id"],),
            ).fetchone()
            peers = conn.execute(
                "SELECT * FROM runtime_peers WHERE attempt_id=? ORDER BY kind,id",
                (row["current_attempt_id"],),
            ).fetchall()
            jobs = conn.execute(
                """SELECT j.id,j.status,j.exit_code,j.output_limited,
                EXISTS(SELECT 1 FROM runtime_peers p WHERE p.id=j.peer_id AND p.kind='command'
                AND p.attempt_id=j.attempt_id AND p.state='closed' AND p.database_identity IS NOT NULL)
                AS local_execution_closed FROM runtime_jobs j WHERE attempt_id=? ORDER BY rowid LIMIT 25""",
                (row["current_attempt_id"],),
            ).fetchall()
            unknown_jobs = conn.execute(
                "SELECT COUNT(*) FROM runtime_jobs WHERE attempt_id=? AND status<>'exited'",
                (row["current_attempt_id"],),
            ).fetchone()[0]
            unmanaged_jobs = conn.execute(
                """SELECT COUNT(*) FROM runtime_jobs j WHERE attempt_id=? AND status<>'exited'
                AND NOT EXISTS(SELECT 1 FROM runtime_peers p WHERE p.id=j.peer_id
                AND p.kind='command' AND p.attempt_id=j.attempt_id AND p.database_identity IS NOT NULL)""",
                (row["current_attempt_id"],),
            ).fetchone()[0]
            job_count = conn.execute(
                "SELECT COUNT(*) FROM runtime_jobs WHERE attempt_id=?",
                (row["current_attempt_id"],),
            ).fetchone()[0]
            dispatch = conn.execute(
                "SELECT model,status,native_status,observed_tokens,token_ceiling FROM runtime_inference_dispatches WHERE attempt_id=?",
                (row["current_attempt_id"],),
            ).fetchone()
            effects = conn.execute(
                """SELECT o.operation_key,o.kind,o.result_json FROM tool_operations o
                JOIN tool_grants g ON g.id=o.grant_id WHERE o.project_id=? AND o.task_id=? AND g.runtime_attempt_id=?
                ORDER BY o.created_at,o.operation_key LIMIT 101""",
                (project_id, row["task_id"], row["current_attempt_id"]),
            ).fetchall()
            supported = (
                scope is not None
                and scope[0] == 1
                and {"native", "business"} <= {p["kind"] for p in peers}
                and all(p["database_identity"] is not None for p in peers)
            )
            blocked = None
            if not supported:
                blocked = "missing_proof"
            elif any(
                p["database_identity"] != self.peers._database_identity() for p in peers
            ):
                blocked = "different_database"
            elif any(
                p["state"] != "closed"
                and (p["boot_id"], p["observer_namespace"])
                != (boot_id(), observer_namespace())
                for p in peers
            ):
                blocked = "different_kernel"
            elif unmanaged_jobs:
                blocked = "unknown_job"
            return {
                "run_id": run_id,
                "attempt_id": row["current_attempt_id"],
                "fence": row["fence"],
                "status": row["status"],
                "supported": supported,
                "can_reconcile": supported
                and blocked is None
                and row["status"] in ("reconciling", "cancelling"),
                "blocked_reason": blocked,
                "peers": [
                    {key: p[key] for key in ("kind", "state", "reason")} for p in peers
                ],
                "jobs": [dict(j) for j in jobs],
                "unknown_jobs": unknown_jobs,
                "jobs_truncated": job_count > 25,
                "dispatch": dict(dispatch) if dispatch else None,
                "effects": [
                    {
                        "operation_key": e["operation_key"],
                        "kind": e["kind"],
                        "receipt": json.loads(e["result_json"]),
                    }
                    for e in effects[:100]
                ],
                "effects_truncated": len(effects) > 100,
            }

    @staticmethod
    def _intent(project_id, run_id, attempt_id, expected_fence, operation_key):
        """Validate the explicit recovery command and build the attempt/fence-bound intent used to
        compare durable operation receipts.
        """
        identity(project_id)
        identity(expected_fence)
        text(run_id, "run_id", 128)
        text(attempt_id, "attempt_id", 128)
        command_key(operation_key)
        return {
            "kind": "recover_run",
            "run_id": run_id,
            "attempt_id": attempt_id,
            "expected_fence": expected_fence,
        }

    def _protocol(self, conn, attempt_id):
        """Require the original recoverable native/business peer protocol and validate each stored
        origin before allowing recovery work.
        """
        scope = conn.execute(
            "SELECT protocol_version FROM runtime_peer_scopes WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        peers = conn.execute(
            "SELECT * FROM runtime_peers WHERE attempt_id=?", (attempt_id,)
        ).fetchall()
        if (
            scope is None
            or scope[0] != 1
            or not {"native", "business"} <= {row["kind"] for row in peers}
            or any(row["database_identity"] is None for row in peers)
        ):
            raise RunConflict(
                "No recoverable peer protocol was recorded for this historical attempt"
            )
        for peer in peers:
            self.peers._check_origin(peer)
        return peers

    def preflight(self, **command):
        """Inspect original peers and bound grants before closing an attempt without replay."""
        return self._prepare_command(command, write=False)

    def begin(self, **command):
        """Persist one original recovery intent, withdraw run authority and return scoped peer/grant
        identities, or recover its existing completion receipt.
        """
        return self._prepare_command(command, write=True)

    def _prepare_command(self, command, *, write):
        """Resolve scoped original actors and optionally persist their retirement intent."""
        intent = self._intent(**command)
        with self.runs._transaction(write=write) as conn:
            row = self.runs._row(conn, command["project_id"], command["run_id"])
            receipt = self.runs._receipt(
                conn,
                row["project_id"],
                row["task_id"],
                command["operation_key"],
                intent,
            )
            if receipt is not None:
                return {"completed": receipt, "peers": []}
            operation = conn.execute(
                "SELECT * FROM runtime_recovery_operations WHERE project_id=? AND task_id=? AND operation_key=?",
                (row["project_id"], row["task_id"], command["operation_key"]),
            ).fetchone()
            if operation is not None:
                if operation["request_hash"] != _digest(intent):
                    raise RunConflict("Recovery key already identifies another intent")
            elif (
                row["current_attempt_id"] != command["attempt_id"]
                or row["fence"] != command["expected_fence"]
                or row["status"] not in ("reconciling", "cancelling")
            ):
                raise RunConflict("Refresh the uncertain attempt before recovering it")
            peers = self._protocol(conn, command["attempt_id"])
            if operation is None and write:
                conn.execute(
                    "INSERT INTO runtime_recovery_operations(project_id,task_id,operation_key,request_hash,run_id,attempt_id,requested_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        row["project_id"],
                        row["task_id"],
                        command["operation_key"],
                        _digest(intent),
                        row["id"],
                        command["attempt_id"],
                        self.runs.clock(),
                    ),
                )
                self.runs._withdraw(conn, row, "reconciling")
                self.runs._event(
                    conn,
                    row["project_id"],
                    row["task_id"],
                    "recovery.requested",
                    {
                        "run_id": row["id"],
                        "attempt_id": command["attempt_id"],
                        "operation_key": command["operation_key"],
                        "replay": False,
                    },
                )
            grants = conn.execute(
                "SELECT id FROM tool_grants WHERE runtime_attempt_id=? AND project_id=? AND task_id=?",
                (command["attempt_id"], command["project_id"], row["task_id"]),
            ).fetchall()
            return {
                "completed": None,
                "peers": [peer["id"] for peer in peers],
                "tool_grant_ids": [grant[0] for grant in grants],
            }

    def complete(self, **command):
        """Require matching recovery intent and closed-peer proof before retiring the attempt and
        storing its receipt/event; never start inference or accept the task.
        """
        intent = self._intent(**command)
        with self.runs._transaction(write=True) as conn:
            row = self.runs._row(conn, command["project_id"], command["run_id"])
            receipt = self.runs._receipt(
                conn,
                row["project_id"],
                row["task_id"],
                command["operation_key"],
                intent,
            )
            if receipt is not None:
                return receipt
            operation = conn.execute(
                "SELECT * FROM runtime_recovery_operations WHERE project_id=? AND task_id=? AND operation_key=?",
                (row["project_id"], row["task_id"], command["operation_key"]),
            ).fetchone()
            if (
                operation is None
                or operation["request_hash"] != _digest(intent)
                or row["current_attempt_id"] != command["attempt_id"]
            ):
                raise RunConflict("No matching recovery intent for this attempt")
            self._protocol(conn, command["attempt_id"])
            self.runs._closed_peer_proof(conn, command["attempt_id"])
            if row["status"] not in (
                "failed",
                "cancelled",
                "superseded",
                "waiting_input",
                "needs_review",
                "accepted",
            ):
                question = conn.execute(
                    "SELECT 1 FROM runtime_question_links q JOIN user_requests u ON u.id=q.request_id WHERE q.attempt_id=? AND u.status='pending'",
                    (command["attempt_id"],),
                ).fetchone()
                if row["cancel_requested"]:
                    status = "cancelled"
                elif self.runs._context(conn, row["task_id"]) != row["context_version"]:
                    status = "superseded"
                elif question:
                    status = "waiting_input"
                else:
                    status = "failed"
                self.runs._retire_closed(conn, row, status)
            current = self.runs._row(conn, row["project_id"], row["id"])
            result = {
                "run_id": row["id"],
                "attempt_id": command["attempt_id"],
                "status": current["status"],
                "local_execution_closed": True,
                "inference_started": False,
                "task_accepted": False,
            }
            self.runs._save_receipt(
                conn,
                row["project_id"],
                row["task_id"],
                command["operation_key"],
                intent,
                result,
            )
            conn.execute(
                "UPDATE runtime_recovery_operations SET completed_at=? WHERE project_id=? AND task_id=? AND operation_key=?",
                (
                    self.runs.clock(),
                    row["project_id"],
                    row["task_id"],
                    command["operation_key"],
                ),
            )
            self.runs._event(
                conn, row["project_id"], row["task_id"], "recovery.completed", result
            )
            return result

    def reconcile(self, **command):
        """Recover an existing receipt or retire each originally registered peer and complete the same
        recovery intent without replaying business work.
        """
        work = self.begin(**command)
        if work["completed"] is not None:
            return work["completed"]
        for peer in work["peers"]:
            self.peers.close(peer)
        return self.complete(**command)
