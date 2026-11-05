"""Fresh readonly remote observation after original Git/HTTP closure; positive history and remote uncertainty never grant another write."""

import json
from dataclasses import asdict
from pathlib import Path

from backend.knowledge.reviews import canonical, digest
from backend.runtime.code_publications import CodePublications
from backend.runtime.contracts import RunConflict
from backend.runtime.development_workspace import _source_identity
from backend.runtime.publication_git import PublicationDirectory
from backend.runtime.publication_recovery import PublicationRecovery
from backend.runtime.recovery import RunRecovery


class RemoteRecovery(PublicationRecovery):
    """Reuse the proven fresh-attempt/receipt lifecycle with remote-only subject and result rules; no writer authority is revived."""

    observation_table = "runtime_remote_recoveries"

    def __init__(self, runs):
        """Bind only durable stores; construction opens neither clients nor process domains."""
        from backend.runtime.remote_runtime import RemotePublications

        self.runs = runs
        self.publications = RemotePublications(runs)

    @staticmethod
    def observation(conn, row):
        """Recognize only the run's exact current readonly remote attempt."""
        if row["execution_kind"] != "remote_publication":
            return None
        return conn.execute(
            "SELECT * FROM runtime_remote_recoveries WHERE run_id=? AND attempt_id=?",
            (row["id"], row["current_attempt_id"]),
        ).fetchone()

    @staticmethod
    def intent(**command):
        """Preserve strict owner attempt/fence/key validation while separating remote and local recovery commands."""
        return {**RunRecovery._intent(**command), "kind": "observe_remote_publication"}

    def subject(self, conn, row):
        """Validate original source/metadata and registered remote for historical reads without requiring a current acceptance or candidate directory."""
        if self.observation(conn, row) is None:
            raise RunConflict("No readonly remote authority for this attempt")
        request = self.publications._request(conn, row["project_id"], row["id"])
        local = CodePublications(self.runs)._request(
            conn, row["project_id"], request["local_publication_run_id"]
        )
        view = CodePublications._view(json.loads(local["view_json"]))
        self.runs._check_registration(conn, row["project_id"], view.source)
        _source_identity(view.source)
        if (
            PublicationDirectory.capture(Path(view.source.workspace) / ".git")
            != view.source_metadata
        ):
            raise RunConflict("Original remote source metadata identity changed")
        self.publications._registration(
            conn,
            row["project_id"],
            view,
            self.publications._remote(self.publications._protocol(request)),
        )
        return view

    def begin(self, *, proof, **command):
        """Require exact original HTTP closure in addition to inherited original-domain/fence checks before allocating another readonly lease."""
        if (
            proof.get("http_client_closed") is not True
            or proof.get("http_attempt_id") != command["attempt_id"]
        ):
            raise RunConflict("Exact original HTTP closure proof is required")
        return super().begin(proof=proof, **command)

    def complete(self, lease, observations, proof):
        """Atomically record original remote facts and the observer receipt only after its own clients close; absent effects remain uncertain."""
        from backend.runtime.remote_runtime import EFFECTS

        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            run = self.runs._row(conn, lease.project_id, lease.run_id)
            record = self.observation(conn, run)
            if record is None:
                raise RunConflict("Remote observer is no longer the current attempt")
            if record["result_json"]:
                return json.loads(record["result_json"])
            request = self.publications._request(conn, lease.project_id, lease.run_id)
            if not isinstance(observations, dict) or set(observations) - set(
                EFFECTS[request["stage"]]
            ):
                raise RunConflict("Observation differs from original remote stage")
            if proof.get("http_client_closed") is not True or (
                request["stage"] in ("push", "merge")
                and proof.get("domain_closed") is not True
            ):
                raise RunConflict("Remote observer local closure is unconfirmed")
            self.runs._closed_peer_proof(conn, lease.attempt_id)
            for name, observed in observations.items():
                effect = conn.execute(
                    "SELECT * FROM runtime_remote_effects WHERE run_id=? AND effect_name=?",
                    (lease.run_id, name),
                ).fetchone()
                if effect is None:
                    raise RunConflict(
                        "Readonly recovery cannot create an unissued effect"
                    )
                positive = self.publications._validate(request, name, observed)
                packet = canonical(asdict(observed))
                conn.execute(
                    "INSERT OR IGNORE INTO runtime_remote_observations(run_id,effect_name,observation_sha256,result_json,created_at)VALUES(?,?,?,?,?)",
                    (
                        lease.run_id,
                        name,
                        digest(
                            {"observer": lease.attempt_id, "result": asdict(observed)}
                        ),
                        packet,
                        self.runs.clock(),
                    ),
                )
                if effect["state"] != "observed":
                    conn.execute(
                        "UPDATE runtime_remote_effects SET state=?,outcome_json=?,client_closed=1 WHERE run_id=? AND effect_name=?",
                        (
                            "observed" if positive else "uncertain",
                            packet,
                            lease.run_id,
                            name,
                        ),
                    )
            effects = {
                e["effect_name"]: dict(e)
                for e in conn.execute(
                    "SELECT * FROM runtime_remote_effects WHERE run_id=?",
                    (lease.run_id,),
                )
            }
            known = all(
                name in effects
                and effects[name]["state"] == "observed"
                and effects[name]["client_closed"]
                for name in EFFECTS[request["stage"]]
            )
            current = (
                run["status"] == "running"
                and run["fence"] == lease.fence
                and self.runs._context(conn, lease.task_id) == lease.context_version
                and not run["cancel_requested"]
            )
            if current:
                try:
                    self.publications.current(conn, run)
                except RunConflict:
                    current = False
            if (
                request["stage"] == "pull"
                and "pull" in observations
                and not observations["pull"].candidate_current
            ):
                current = False
            result = {
                "run_id": lease.run_id,
                "stage": request["stage"],
                "local_publication_run_id": request["local_publication_run_id"],
                "context_version": lease.context_version,
                "recovery_operation_key": record["operation_key"],
                "effects_confirmed": known,
                "effects": {
                    name: json.loads(e["outcome_json"])
                    for name, e in effects.items()
                    if e["outcome_json"]
                },
                "observations": {
                    name: asdict(value) for name, value in observations.items()
                },
                "completed_after_withdrawal": not current,
                "proof_sha256": digest(proof),
                "observer_attempt_id": lease.attempt_id,
                "source_attempt_id": record["source_attempt_id"],
                "recorded_at": self.runs.clock(),
            }
            if known:
                conn.execute(
                    "UPDATE runtime_remote_publications SET result_json=? WHERE run_id=? AND result_json IS NULL",
                    (canonical(result), lease.run_id),
                )
            conn.execute(
                "UPDATE runtime_remote_recoveries SET result_json=? WHERE attempt_id=?",
                (canonical(result), lease.attempt_id),
            )
            status = (
                "reconciling"
                if not known
                else "cancelled"
                if run["cancel_requested"]
                else "accepted"
                if current
                else "superseded"
            )
            conn.execute(
                "UPDATE runtime_attempts SET status='finished',ended_at=?WHERE id=?",
                (self.runs.clock(), lease.attempt_id),
            )
            conn.execute(
                "UPDATE runtime_runs SET status=?,updated_at=?,issue_json=?WHERE id=?",
                (
                    status,
                    self.runs.clock(),
                    None if known else canonical(self.publications._issue()),
                    lease.run_id,
                ),
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
                "remote.publication_observed",
                result,
            )
            return result
