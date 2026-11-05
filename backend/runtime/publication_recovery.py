"""Fresh readonly authority reconciles a closed original publication without repeating its ref transaction or requiring current acceptance."""

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.runtime.code_publications import CodePublications
from backend.runtime.contracts import AttemptLease, RunConflict, text
from backend.runtime.development_workspace import _source_identity
from backend.runtime.peer_registry import AttemptPeers, PeerRegistry
from backend.runtime.publication_git import (
    PublicationDirectory,
    PublicationRefIntent,
    PublicationRefObservation,
    _observation,
)
from backend.runtime.recovery import RunRecovery


class PublicationRecovery:
    """Keep recovery receipts, original closure and new observation capability separate from write publication authority."""

    def __init__(self, runs):
        """Use the original SQLite store without acquiring any effect or process authority."""
        self.runs = runs
        self.publications = CodePublications(runs)

    @staticmethod
    def observation(conn, row):
        """Identify only a durable observation attached to the run's exact current attempt."""
        if row["execution_kind"] != "code_publication":
            return None
        return conn.execute(
            "SELECT * FROM runtime_publication_observations WHERE run_id=? AND attempt_id=?",
            (row["id"], row["current_attempt_id"]),
        ).fetchone()

    def subject(self, conn, row):
        """Validate historical source identity and pinned readonly metadata without granting current candidate or write authority."""
        observation = self.observation(conn, row)
        if observation is None:
            raise RunConflict("No readonly observation authority for this attempt")
        request = self.publications._request(conn, row["project_id"], row["id"])
        view = self.publications._view(json.loads(request["view_json"]))
        self.runs._check_registration(conn, row["project_id"], view.source)
        _source_identity(view.source)
        if (
            PublicationDirectory.capture(Path(view.source.workspace) / ".git")
            != view.source_metadata
        ):
            raise RunConflict("Original publication metadata identity changed")
        return view

    @staticmethod
    def intent(**command):
        """Reuse strict owner identity validation while keeping recovery keys distinct from generic native recovery."""
        return {**RunRecovery._intent(**command), "kind": "observe_code_publication"}

    def receipt(self, **command):
        """Read only the durable result of this exact recovery command, including after a later correction."""
        intent = self.intent(**command)
        with self.runs._transaction() as conn:
            row = self.runs._row(conn, command["project_id"], command["run_id"])
            return self.runs._receipt(
                conn,
                row["project_id"],
                row["task_id"],
                command["operation_key"],
                intent,
            )

    def begin(self, *, proof, owner_id, **command):
        """Allocate a fresh fenced readonly observer only after exact host closure; never reactivate the original writer attempt."""
        intent = self.intent(**command)
        text(owner_id, "Owner", 128)
        with self.runs._transaction(write=True) as conn:
            row = self.runs._row(conn, command["project_id"], command["run_id"])
            self.publications._request(conn, row["project_id"], row["id"])
            prior = self.runs._receipt(
                conn,
                row["project_id"],
                row["task_id"],
                command["operation_key"],
                intent,
            )
            if prior is not None:
                raise RunConflict(
                    "Recovery already completed; read its original receipt"
                )
            if conn.execute(
                "SELECT 1 FROM runtime_publication_observations WHERE project_id=? AND task_id=? AND operation_key=?",
                (row["project_id"], row["task_id"], command["operation_key"]),
            ).fetchone():
                raise RunConflict(
                    "Observation already started; inspect its original attempt before another observation"
                )
            source = conn.execute(
                "SELECT * FROM runtime_attempts WHERE id=? AND run_id=?",
                (command["attempt_id"], row["id"]),
            ).fetchone()
            if (
                source is None
                or row["current_attempt_id"] != command["attempt_id"]
                or row["fence"] != command["expected_fence"]
                or row["status"]
                not in ("reconciling", "cancelling", "superseded", "cancelled")
            ):
                raise RunConflict(
                    "Refresh the original uncertain publication before observing"
                )
            if (
                proof.get("execution_closed") is not True
                or proof.get("attempt_id") != source["id"]
                or proof.get("fence") != source["fence"]
                or proof.get("database_identity")
                != PeerRegistry(self.runs)._database_identity()
            ):
                raise RunConflict("Exact original host closure proof is required")
            self.runs._closed_peer_proof(conn, source["id"])
            if conn.execute(
                "SELECT 1 FROM runtime_peers p JOIN runtime_attempts a ON a.id=p.attempt_id JOIN runtime_runs r ON r.id=a.run_id WHERE r.project_id=? AND r.task_id=? AND p.state!='closed' LIMIT 1",
                (row["project_id"], row["task_id"]),
            ).fetchone():
                raise RunConflict("Other task work still has live process authority")
            now = self.runs.clock()
            attempt_id = str(uuid4())
            fence = row["fence"] + 1
            conn.execute(
                "UPDATE runtime_attempts SET status='finished',ended_at=coalesce(ended_at,?) WHERE id=?",
                (now, source["id"]),
            )
            conn.execute(
                "INSERT INTO runtime_attempts(id,run_id,owner_id,fence,status,lease_expires_at,started_at) VALUES(?,?,?,?,'running',?,?)",
                (attempt_id, row["id"], owner_id, fence, now + 30, now),
            )
            conn.execute(
                "INSERT INTO runtime_publication_observations(attempt_id,run_id,project_id,task_id,operation_key,source_attempt_id,expected_fence,request_json,closure_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    attempt_id,
                    row["id"],
                    row["project_id"],
                    row["task_id"],
                    command["operation_key"],
                    source["id"],
                    row["fence"],
                    canonical(intent),
                    canonical(proof),
                    now,
                ),
            )
            conn.execute(
                "UPDATE runtime_runs SET status='running',current_attempt_id=?,fence=?,updated_at=?,issue_json=NULL WHERE id=?",
                (attempt_id, fence, now, row["id"]),
            )
            lease = AttemptLease(
                row["id"],
                attempt_id,
                row["project_id"],
                row["task_id"],
                row["actor_id"],
                row["context_version"],
                owner_id,
                fence,
                now + 30,
            )
            peers = AttemptPeers._prepare(conn, self.runs, lease)
            self.runs._event(
                conn,
                row["project_id"],
                row["task_id"],
                "code.publication_observation_started",
                {
                    "run_id": row["id"],
                    "attempt_id": attempt_id,
                    "source_attempt_id": source["id"],
                    "operation_key": command["operation_key"],
                    "replay": False,
                },
            )
            return lease, peers

    def complete(self, lease, observed, proof):
        """Record a closed readonly observation and original owner receipt atomically; uncertainty never becomes permission to repeat a write."""
        with self.runs._transaction(write=True) as conn:
            row = self.runs._original_attempt(conn, lease)
            row = self.runs._row(conn, lease.project_id, lease.run_id)
            record = self.observation(conn, row)
            if record is None:
                raise RunConflict(
                    "Observation no longer identifies the current attempt"
                )
            if record["result_json"]:
                return json.loads(record["result_json"])
            request = self.publications._request(conn, lease.project_id, lease.run_id)
            view = self.publications._view(json.loads(request["view_json"]))
            ref = PublicationRefIntent(
                lease.run_id, request["target_ref"], request["expected_target_sha"]
            )
            if (
                not isinstance(observed, PublicationRefObservation)
                or observed
                != _observation(
                    view,
                    ref,
                    observed.observed_target_sha,
                    observed.observed_marker_sha,
                )
                or (observed.head_sha, observed.receipt_ref)
                != (view.head_sha, ref.receipt_ref)
                or proof.get("domain_closed") is not True
            ):
                raise RunConflict(
                    "Original exact ref observation and observer closure are required"
                )
            self.runs._closed_peer_proof(conn, lease.attempt_id)
            current = (
                row["status"] == "running"
                and row["fence"] == lease.fence
                and self.runs._context(conn, lease.task_id) == lease.context_version
                and not row["cancel_requested"]
            )
            result = {
                "run_id": lease.run_id,
                "author_run_id": request["author_run_id"],
                "operation_key": row["operation_key"],
                "recovery_operation_key": record["operation_key"],
                "context_version": lease.context_version,
                "publication_performed": observed.state == "published",
                "completed_after_withdrawal": not current,
                "observed": asdict(observed),
                "proof_sha256": digest(proof),
                "grant_id": proof["grant_id"],
                "observer_attempt_id": lease.attempt_id,
                "source_attempt_id": record["source_attempt_id"],
                "recorded_at": self.runs.clock(),
            }
            conn.execute(
                "UPDATE runtime_publication_observations SET result_json=? WHERE attempt_id=?",
                (canonical(result), lease.attempt_id),
            )
            if observed.state != "uncertain":
                conn.execute(
                    "UPDATE runtime_code_publication_requests SET result_json=? WHERE run_id=? AND result_json IS NULL",
                    (canonical(result), lease.run_id),
                )
            status = (
                "reconciling"
                if observed.state == "uncertain"
                else "cancelled"
                if row["cancel_requested"]
                else "superseded"
                if not current
                else "accepted"
                if observed.state == "published"
                else "failed"
            )
            conn.execute(
                "UPDATE runtime_attempts SET status='finished',ended_at=? WHERE id=?",
                (self.runs.clock(), lease.attempt_id),
            )
            conn.execute(
                "UPDATE runtime_runs SET status=?,updated_at=? WHERE id=?",
                (status, self.runs.clock(), lease.run_id),
            )
            self.runs._save_receipt(
                conn,
                lease.project_id,
                lease.task_id,
                record["operation_key"],
                json.loads(record["request_json"]),
                result,
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "code.publication_observed",
                result,
            )
            return result
