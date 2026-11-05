"""Durable remote owner actions and original effect stages, separate from inference and the already closed local publication.

A reservation is not a network grant. The host transport must bind each issued
stage to fresh authority and record actual local closure. Unknown remote effects
are retained for readonly observation, never dispatched again by owner retry.
"""

import json
from dataclasses import asdict, dataclass
from typing import ClassVar
from uuid import uuid4

from backend.knowledge.reviews import canonical, digest
from backend.runtime.code_publications import CodePublications
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, text
from backend.runtime.forgejo_publication import (
    RemoteMergeObservation,
    RemotePullIntent,
    RemotePullObservation,
)
from backend.runtime.remote_publication import (
    RemotePushIntent,
    RemotePushObservation,
    RemoteRepository,
)

EFFECTS = {"push": ("push",), "pull": ("pull",), "merge": ("merge_git", "merge_record")}


@dataclass(frozen=True)
class RemotePushRequest:
    """Original scoped owner push action over an explicitly observed remote destination and successful local publication."""

    operation_key: str
    origin_run_id: str
    remote: RemoteRepository
    target_ref: str
    expected_target_sha: str | None
    stage: ClassVar[str] = "push"


@dataclass(frozen=True)
class RemotePullRequest:
    """Original PR request over one exact completed remote push; its prose and observed base do not refresh on retry."""

    operation_key: str
    origin_run_id: str
    base_ref: str
    base_sha: str
    title: str
    body: str
    stage: ClassVar[str] = "pull"


@dataclass(frozen=True)
class RemoteMergeRequest:
    """Explicit owner merge decision over the exact original PR, distinct from push and PR creation permission."""

    operation_key: str
    origin_run_id: str
    stage: ClassVar[str] = "merge"


class RemotePublications:
    """Own immutable remote actions, fresh host identity and issue-once effect history without granting network or model capacity."""

    def __init__(self, runs):
        """Use the existing scoped transaction/receipt store; no migration or effect occurs at construction."""
        self.runs = runs
        self.local = CodePublications(runs)

    @staticmethod
    def linked_runs(conn, project_id, local_ids):
        """Exclude only remote activity descended from exact acceptance-linked local publications, never by broad execution label."""
        if (
            not local_ids
            or conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_remote_publications'"
            ).fetchone()
            is None
        ):
            return set()
        rows = conn.execute(
            """SELECT p.run_id,p.local_publication_run_id FROM runtime_remote_publications p
            JOIN runtime_runs r ON r.id=p.run_id JOIN runtime_code_publication_requests l ON l.run_id=p.local_publication_run_id
            WHERE p.project_id=? AND r.execution_kind='remote_publication' AND r.project_id=p.project_id
            AND r.task_id=p.task_id AND l.project_id=p.project_id AND l.task_id=p.task_id AND r.context_version=l.context_version""",
            (project_id,),
        ).fetchall()
        return {r["run_id"] for r in rows if r["local_publication_run_id"] in local_ids}

    def _request(self, conn, project_id, run_id):
        """Read only a typed remote action in its original project; another run or project cannot adopt its stages."""
        run = self.runs._row(conn, project_id, run_id)
        row = conn.execute(
            "SELECT * FROM runtime_remote_publications WHERE project_id=? AND run_id=?",
            (project_id, run_id),
        ).fetchone()
        if row is None or run["execution_kind"] != "remote_publication":
            raise RunNotFound("Remote publication request not found")
        return dict(row)

    @staticmethod
    def _protocol(row):
        """Rebuild exactly the original typed host protocol, including its globally scoped effect identities."""
        packet = json.loads(row["protocol_json"])

        def typed(kind, value):
            """Restore only the declared remote identity and frozen protocol fields."""
            value = dict(value)
            value["remote"] = RemoteRepository(**value["remote"])
            return kind(**value)

        if row["stage"] == "push":
            return typed(RemotePushIntent, packet)
        if row["stage"] == "pull":
            return typed(RemotePullIntent, packet)
        return {
            "push": typed(RemotePushIntent, packet["push"]),
            "pull": typed(RemotePullIntent, packet["pull"]),
            "number": packet["number"],
        }

    def protocol(self, project_id, run_id):
        """Read host protocol without scheduling or reserving an effect."""
        with self.runs._transaction() as conn:
            return self._protocol(self._request(conn, project_id, run_id))

    def request(self, project_id, run_id):
        """Inspect immutable owner intent and original effect history; inspection never retries a network write."""
        with self.runs._transaction() as conn:
            row = self._request(conn, project_id, run_id)
            effects = [
                {
                    **dict(e),
                    "request": json.loads(e["request_json"]),
                    "outcome": json.loads(e["outcome_json"])
                    if e["outcome_json"]
                    else None,
                }
                for e in conn.execute(
                    "SELECT * FROM runtime_remote_effects WHERE run_id=? ORDER BY effect_name",
                    (run_id,),
                )
            ]
            return {
                "run_id": run_id,
                "stage": row["stage"],
                "origin_run_id": row["origin_run_id"],
                "local_publication_run_id": row["local_publication_run_id"],
                "intent": json.loads(row["intent_json"]),
                "protocol": json.loads(row["protocol_json"]),
                "effects": effects,
                "result": json.loads(row["result_json"])
                if row["result_json"]
                else None,
            }

    def _root(self, conn, project_id, local_id):
        """Require a positive original local publication and its exact current acceptance/source metadata before any remote write authority."""
        local = self.local._request(conn, project_id, local_id)
        result = json.loads(local["result_json"]) if local["result_json"] else None
        if not result or result.get("publication_performed") is not True:
            raise RunConflict(
                "Remote action requires a confirmed original local publication"
            )
        view = self.local.current(conn, self.runs._row(conn, project_id, local_id))
        return local, view

    @staticmethod
    def _remote(protocol):
        """Read the one exact remote binding shared by this stage's Git/HTTP effects."""
        return (
            protocol["push"].remote if isinstance(protocol, dict) else protocol.remote
        )

    @staticmethod
    def _registration(conn, project_id, view, remote):
        """Bind remote destination to the current original repository registration, not a client-selected credential URL."""
        row = conn.execute(
            "SELECT remote_url FROM repositories WHERE project_id=? AND id=? AND status='active'",
            (project_id, view.source.repository_id),
        ).fetchone()
        if row is None or row["remote_url"] != remote.clone_url:
            raise RunConflict(
                "Remote destination differs from the original registered repository"
            )

    def current(self, conn, run):
        """Revalidate exact accepted local provenance and registered remote while retaining the already done task."""
        row = self._request(conn, run["project_id"], run["id"])
        _local, view = self._root(
            conn, run["project_id"], row["local_publication_run_id"]
        )
        protocol = self._protocol(row)
        self._registration(conn, run["project_id"], view, self._remote(protocol))
        return view

    def admit_once(self, project_id, request):
        """Atomically bind one explicit owner action to a new host run, its exact prerequisite and original command receipt."""
        if not isinstance(
            request, (RemotePushRequest, RemotePullRequest, RemoteMergeRequest)
        ):
            raise TypeError("Typed remote owner action required")
        command_key(request.operation_key)
        text(request.origin_run_id, "Original run", 128)
        with self.runs._transaction(write=True) as conn:
            origin = self.runs._row(conn, project_id, request.origin_run_id)
            body = {
                "kind": "remote_publication.admit",
                "stage": request.stage,
                **asdict(request),
            }
            prior = self.runs._receipt(
                conn, project_id, origin["task_id"], request.operation_key, body
            )
            if prior is not None:
                return self.runs._view(
                    self.runs._row(conn, project_id, prior["run_id"])
                ), False
            parent = None
            if request.stage == "push":
                local_id = request.origin_run_id
            else:
                parent = self._request(conn, project_id, request.origin_run_id)
                required = "push" if request.stage == "pull" else "pull"
                if (
                    parent["stage"] != required
                    or origin["status"] != "accepted"
                    or not parent["result_json"]
                ):
                    raise RunConflict(
                        "Remote prerequisite is not the exact completed accepted stage"
                    )
                local_id = parent["local_publication_run_id"]
            local, view = self._root(conn, project_id, local_id)
            if (
                conn.execute(
                    "SELECT 1 FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review') LIMIT 1",
                    (project_id, local["task_id"]),
                ).fetchone()
                or conn.execute(
                    "SELECT 1 FROM runtime_peers p JOIN runtime_attempts a ON a.id=p.attempt_id JOIN runtime_runs r ON r.id=a.run_id WHERE r.project_id=? AND r.task_id=? AND p.state!='closed' LIMIT 1",
                    (project_id, local["task_id"]),
                ).fetchone()
            ):
                raise RunConflict("Other task work still owns unresolved authority")
            run_id = str(uuid4())
            now = self.runs.clock()
            if request.stage == "push":
                protocol = RemotePushIntent(
                    run_id,
                    request.remote,
                    request.target_ref,
                    request.expected_target_sha,
                    view.head_sha,
                    view.base_sha,
                )
            elif request.stage == "pull":
                parent_protocol = self._protocol(parent)
                if request.base_sha != view.base_sha:
                    raise RunConflict(
                        "Remote PR base differs from accepted candidate base"
                    )
                protocol = RemotePullIntent(
                    run_id,
                    parent_protocol.remote,
                    parent_protocol.target_ref,
                    request.base_ref,
                    view.head_sha,
                    view.base_sha,
                    request.title,
                    request.body,
                )
            else:
                original = self._protocol(parent)
                result = json.loads(parent["result_json"])["effects"]["pull"]
                if (
                    result.get("candidate_current") is not True
                    or result.get("state") != "created"
                ):
                    raise RunConflict(
                        "Original PR no longer has an exact accepted candidate observation"
                    )
                protocol = {
                    "pull": original,
                    "push": RemotePushIntent(
                        run_id + ":git",
                        original.remote,
                        original.base_ref,
                        view.base_sha,
                        view.head_sha,
                        view.base_sha,
                    ),
                    "number": result["number"],
                }
            self._registration(conn, project_id, view, self._remote(protocol))
            packet = (
                {
                    key: asdict(value) if key in ("pull", "push") else value
                    for key, value in protocol.items()
                }
                if isinstance(protocol, dict)
                else asdict(protocol)
            )
            conn.execute(
                """INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,created_at,updated_at,execution_kind)
                VALUES(?,?,?,'owner-remote-publication',?,?,?,'codex','queued',?,?,'remote_publication')""",
                (
                    run_id,
                    project_id,
                    local["task_id"],
                    local["context_version"],
                    request.operation_key,
                    "Owner remote publication stage: " + request.stage,
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO runtime_remote_publications(run_id,project_id,task_id,local_publication_run_id,origin_run_id,stage,intent_json,protocol_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    project_id,
                    local["task_id"],
                    local_id,
                    request.origin_run_id,
                    request.stage,
                    canonical(body),
                    canonical(packet),
                    now,
                ),
            )
            conn.execute(
                """INSERT INTO runtime_workspace_bindings(run_id,repository_id,repository_name,requested_repository_id,registration_path,workspace,device,inode,created_at)
                SELECT ?,repository_id,repository_name,requested_repository_id,registration_path,workspace,device,inode,? FROM runtime_workspace_bindings WHERE run_id=?""",
                (run_id, now, local_id),
            )
            self.runs._save_receipt(
                conn,
                project_id,
                local["task_id"],
                request.operation_key,
                body,
                {"run_id": run_id},
            )
            self.runs._event(
                conn,
                project_id,
                local["task_id"],
                "remote.publication_requested",
                {
                    "run_id": run_id,
                    "stage": request.stage,
                    "origin_run_id": request.origin_run_id,
                    "local_publication_run_id": local_id,
                },
            )
            return self.runs._view(self.runs._row(conn, project_id, run_id)), True

    def issue(self, lease, effect_name):
        """Reserve one original effect before its network gate; an existing issued/unknown stage is never another dispatch permit."""
        with self.runs._transaction(write=True) as conn:
            run = self.runs._authority(conn, lease)
            from backend.runtime.remote_recovery import RemoteRecovery

            if RemoteRecovery.observation(conn, run) is not None:
                raise RunConflict("Readonly remote observation cannot issue a write")
            row = self._request(conn, lease.project_id, lease.run_id)
            if effect_name not in EFFECTS[row["stage"]]:
                raise RunConflict("Effect is outside the original remote stage")
            existing = conn.execute(
                "SELECT * FROM runtime_remote_effects WHERE run_id=? AND effect_name=?",
                (lease.run_id, effect_name),
            ).fetchone()
            if existing is not None:
                return {
                    "dispatch": False,
                    "operation_id": existing["operation_id"],
                    "state": existing["state"],
                }
            if effect_name == "merge_record":
                git = conn.execute(
                    "SELECT * FROM runtime_remote_effects WHERE run_id=? AND effect_name='merge_git'",
                    (lease.run_id,),
                ).fetchone()
                if (
                    git is None
                    or git["state"] != "observed"
                    or not json.loads(git["outcome_json"]).get("target_current")
                ):
                    raise RunConflict(
                        "Exact original Git merge receipt is required before bookkeeping"
                    )
            operation_id = lease.run_id + ":" + effect_name
            intent = {
                "operation_id": operation_id,
                "effect_name": effect_name,
                "protocol": json.loads(row["protocol_json"]),
                "context_version": run["context_version"],
                "attempt_id": lease.attempt_id,
                "fence": lease.fence,
            }
            conn.execute(
                "INSERT INTO runtime_remote_effects(run_id,effect_name,operation_id,attempt_id,request_json,state,issued_at) VALUES(?,?,?,?,?,'issued',?)",
                (
                    lease.run_id,
                    effect_name,
                    operation_id,
                    lease.attempt_id,
                    canonical(intent),
                    self.runs.clock(),
                ),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "remote.effect_issued",
                {
                    "run_id": lease.run_id,
                    "effect_name": effect_name,
                    "operation_id": operation_id,
                    "attempt_id": lease.attempt_id,
                },
            )
            return {"dispatch": True, "operation_id": operation_id, "state": "issued"}

    @staticmethod
    def _validate(row, effect_name, observation):
        """Match a typed original remote result to its full stored protocol; a positive label alone cannot confirm another candidate or repository."""
        protocol = RemotePublications._protocol(row)
        if effect_name in ("push", "merge_git"):
            expected = protocol["push"] if isinstance(protocol, dict) else protocol
            if (
                not isinstance(observation, RemotePushObservation)
                or observation.state not in ("published", "uncertain")
                or observation.head_sha != expected.head_sha
                or observation.receipt_ref != expected.receipt_ref
                or observation.repository_id != expected.remote.repository_id
                or (observation.state == "published")
                != (observation.observed_marker_sha == expected.head_sha)
                or observation.target_current
                != (
                    observation.state == "published"
                    and observation.observed_target_sha == expected.head_sha
                )
            ):
                raise RunConflict(
                    "Remote push observation differs from original exact intent"
                )
            return observation.state == "published"
        if effect_name == "pull":
            if (
                not isinstance(observation, RemotePullObservation)
                or observation.state not in ("created", "uncertain")
                or observation.marker != protocol.marker
                or observation.repository_id != protocol.remote.repository_id
                or (
                    observation.state == "created"
                    and (type(observation.number) is not int or observation.number <= 0)
                )
                or observation.candidate_current
                != (
                    observation.state == "created"
                    and (observation.observed_head_sha, observation.observed_base_sha)
                    == (protocol.head_sha, protocol.base_sha)
                )
            ):
                raise RunConflict(
                    "Remote PR observation differs from original exact intent"
                )
            return observation.state == "created"
        expected = protocol["push"]
        if (
            not isinstance(observation, RemoteMergeObservation)
            or observation.state not in ("merged", "uncertain")
            or observation.number != protocol["number"]
            or observation.receipt_ref != expected.receipt_ref
            or observation.repository_id != expected.remote.repository_id
            or (
                observation.state == "merged"
                and observation.merge_sha != expected.head_sha
            )
        ):
            raise RunConflict(
                "Remote merge observation differs from original exact intent"
            )
        return observation.state == "merged"

    def observe(self, lease, effect_name, observation, *, client_closed):
        """Preserve original effect evidence after local client closure, including late results after context withdrawal; remote absence stays uncertain."""
        if client_closed is not True:
            raise RunConflict("Original local effect client closure must be proved")
        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            row = self._request(conn, lease.project_id, lease.run_id)
            effect = conn.execute(
                "SELECT * FROM runtime_remote_effects WHERE run_id=? AND effect_name=?",
                (lease.run_id, effect_name),
            ).fetchone()
            if effect is None or effect["attempt_id"] != lease.attempt_id:
                raise RunConflict("No original issued effect for this attempt")
            positive = self._validate(row, effect_name, observation)
            packet = canonical(asdict(observation))
            if effect["state"] == "observed":
                if effect["outcome_json"] != packet:
                    raise RunConflict("Known original remote result is immutable")
                return json.loads(packet)
            key = digest(
                {"result": asdict(observation), "attempt_id": lease.attempt_id}
            )
            added = conn.execute(
                "INSERT OR IGNORE INTO runtime_remote_observations(run_id,effect_name,observation_sha256,result_json,created_at) VALUES(?,?,?,?,?)",
                (lease.run_id, effect_name, key, packet, self.runs.clock()),
            ).rowcount
            conn.execute(
                "UPDATE runtime_remote_effects SET state=?,outcome_json=?,client_closed=1 WHERE run_id=? AND effect_name=?",
                (
                    "observed" if positive else "uncertain",
                    packet,
                    lease.run_id,
                    effect_name,
                ),
            )
            if added:
                self.runs._event(
                    conn,
                    lease.project_id,
                    lease.task_id,
                    "remote.effect_observed",
                    {
                        "run_id": lease.run_id,
                        "effect_name": effect_name,
                        "result": asdict(observation),
                    },
                )
            return json.loads(packet)

    def complete(self, lease, _summary, proof):
        """Atomically finish from recorded original stages after genuine Git-domain/HTTP closure, without accepting unknown or stale remote candidates."""
        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            row = self._request(conn, lease.project_id, lease.run_id)
            if row["result_json"]:
                return json.loads(row["result_json"])
            if (
                conn.execute(
                    "SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=? AND protocol_version=1",
                    (lease.attempt_id,),
                ).fetchone()
                is None
            ):
                raise RunConflict("Original remote host scope is unconfirmed")
            self.runs._closed_peer_proof(conn, lease.attempt_id)
            if (
                row["stage"] in ("push", "merge")
                and proof.get("domain_closed") is not True
            ):
                raise RunConflict("Original Git domain closure is unconfirmed")
            if (
                row["stage"] in ("pull", "merge")
                and proof.get("http_client_closed") is not True
            ):
                raise RunConflict("Original HTTP transport closure is unconfirmed")
            effects = {
                r["effect_name"]: dict(r)
                for r in conn.execute(
                    "SELECT * FROM runtime_remote_effects WHERE run_id=?",
                    (lease.run_id,),
                )
            }
            known = all(
                name in effects
                and effects[name]["state"] == "observed"
                and effects[name]["client_closed"]
                for name in EFFECTS[row["stage"]]
            )
            if (
                known
                and row["stage"] in ("push", "merge")
                and conn.execute(
                    "SELECT 1 FROM runtime_peers WHERE attempt_id=? AND kind='command' AND state='closed'",
                    (lease.attempt_id,),
                ).fetchone()
                is None
            ):
                raise RunConflict(
                    "Successful remote Git result requires original closed command evidence"
                )
            run = self.runs._row(conn, lease.project_id, lease.run_id)
            current = (
                run["status"] == "running"
                and run["fence"] == lease.fence
                and self.runs._context(conn, lease.task_id) == lease.context_version
                and not run["cancel_requested"]
            )
            result = None
            if known:
                values = {
                    name: json.loads(effects[name]["outcome_json"])
                    for name in EFFECTS[row["stage"]]
                }
                if row["stage"] == "pull" and not values["pull"]["candidate_current"]:
                    current = False
                result = {
                    "run_id": lease.run_id,
                    "stage": row["stage"],
                    "local_publication_run_id": row["local_publication_run_id"],
                    "context_version": lease.context_version,
                    "effects": values,
                    "completed_after_withdrawal": not current,
                    "proof_sha256": digest(proof),
                    "recorded_at": self.runs.clock(),
                }
                conn.execute(
                    "UPDATE runtime_remote_publications SET result_json=? WHERE run_id=?",
                    (canonical(result), lease.run_id),
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
                "UPDATE runtime_attempts SET status='finished',ended_at=? WHERE id=?",
                (self.runs.clock(), lease.attempt_id),
            )
            conn.execute(
                "UPDATE runtime_runs SET status=?,updated_at=?,issue_json=? WHERE id=?",
                (
                    status,
                    self.runs.clock(),
                    None if known else canonical(self._issue()),
                    lease.run_id,
                ),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "remote.publication_completed"
                if known
                else "remote.publication_uncertain",
                result
                or {"run_id": lease.run_id, "stage": row["stage"], "replay": False},
            )
            return result

    @staticmethod
    def _issue():
        """Explain uncertainty without claiming that local closure stopped the remote server."""
        return {
            "code": "remote_publication_uncertain",
            "message": "No se confirmó el resultado remoto. El servidor puede haber aplicado el efecto; conservamos la solicitud y no la repetiremos automáticamente.",
            "next_action": "inspect_saved_work",
            "inference_started": False,
        }

    def interrupted(self, lease, *, physically_closed, reason):
        """Keep original issued effects unresolved after interrupted transport; never convert loss of local ownership into another dispatch."""
        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            if physically_closed:
                self.runs._closed_peer_proof(conn, lease.attempt_id)
                conn.execute(
                    "UPDATE runtime_attempts SET status='finished',ended_at=? WHERE id=?",
                    (self.runs.clock(), lease.attempt_id),
                )
            conn.execute(
                "UPDATE runtime_remote_effects SET state='uncertain' WHERE run_id=? AND state='issued'",
                (lease.run_id,),
            )
            conn.execute(
                "UPDATE runtime_runs SET status='reconciling',updated_at=?,issue_json=? WHERE id=?",
                (self.runs.clock(), canonical(self._issue()), lease.run_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "remote.publication_interrupted",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "local_execution_closed": physically_closed,
                    "reason": reason,
                },
            )
