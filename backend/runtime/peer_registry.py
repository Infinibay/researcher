"""Host-only durable registration and closure for gated native/MCP peers."""

import asyncio
import hashlib
import os
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

from backend.runtime.contracts import AttemptLease, RunConflict, RunNotFound
from backend.runtime.peer_process import (
    NamespaceIdentity,
    PeerUncertain,
    boot_id,
    close_namespace,
    observer_namespace,
    start_ticks,
)


class PeerRegistry:
    """Register fenced owned peers and distinguish original sources from private execution copies."""

    def __init__(self, runs):
        self.runs = runs

    def _database_identity(self):
        path = Path(self.runs.database).resolve(strict=True)
        info = path.stat()
        return hashlib.sha256(
            (str(path) + "\0" + str(info.st_dev) + ":" + str(info.st_ino)).encode()
        ).hexdigest()

    def _check_origin(self, row):
        if (
            row["database_identity"] is None
            or row["database_identity"] != self._database_identity()
        ):
            raise PeerUncertain(
                "Registered database origin differs; transfer must be reconciled before control"
            )
        if row["state"] != "closed" and (row["boot_id"], row["observer_namespace"]) != (
            boot_id(),
            observer_namespace(),
        ):
            raise PeerUncertain("Registered kernel or observer namespace differs")

    def prepare(self, lease, kind):
        with self.runs._transaction(write=True) as conn:
            return self._prepare(conn, lease, kind)

    def _prepare(self, conn, lease, kind):
        """Register only capabilities allowed by the original execution kind; publication is command-only host work."""
        if kind not in ("native", "business", "command", "ken"):
            raise ValueError("Unknown owned peer kind")
        peer_id = uuid4().hex
        run = self.runs._authority(conn, lease)
        if (
            run["execution_kind"] in ("code_publication", "remote_publication")
            and kind != "command"
        ):
            raise RunConflict("Host publication permits command peers only")
        if (
            kind in ("command", "ken")
            and conn.execute(
                "SELECT 1 FROM runtime_peer_scopes WHERE attempt_id=? AND protocol_version=1",
                (lease.attempt_id,),
            ).fetchone()
            is None
        ):
            raise RunConflict("Command peers require a registered attempt scope")
        counts = conn.execute(
            "SELECT COUNT(*),SUM(state!='closed') FROM runtime_peers WHERE attempt_id=?",
            (lease.attempt_id,),
        ).fetchone()
        # Closing a per-job peer releases physical capacity; keep its immutable
        # receipt for recovery. Also bound total history within one attempt.
        if counts[0] >= 128 or (counts[1] or 0) >= 8:
            raise RunConflict("Attempt peer capacity reached")
        try:
            conn.execute(
                """INSERT INTO runtime_peers(id,attempt_id,kind,protocol_version,state,fence,owner_pid,
                owner_start_ticks,boot_id,observer_namespace,created_at,database_identity) VALUES(?,?,?,1,'prepared',?,?,?,?,?,?,?)""",
                (
                    peer_id,
                    lease.attempt_id,
                    kind,
                    lease.fence,
                    os.getpid(),
                    start_ticks(os.getpid()),
                    boot_id(),
                    observer_namespace(),
                    self.runs.clock(),
                    self._database_identity(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise RunConflict("This attempt already owns that peer") from exc
        return peer_id

    @staticmethod
    def _row(conn, peer_id):
        row = conn.execute(
            "SELECT * FROM runtime_peers WHERE id=?", (peer_id,)
        ).fetchone()
        if row is None:
            raise RunNotFound("Owned peer not found")
        return row

    def inspect(self, peer_id):
        with self.runs._transaction() as conn:
            return dict(self._row(conn, peer_id))

    def source_binding(self, peer_id):
        """Read the immutable original registration, independently of a private execution view."""
        with self.runs._transaction() as conn:
            peer = self._row(conn, peer_id)
            self._check_origin(peer)
            return self._source_binding(conn, peer)

    def _source_binding(self, conn, peer):
        """Read only the original run binding; business transports have no filesystem view."""
        if peer["kind"] not in ("native", "command", "ken"):
            return None
        binding = conn.execute(
            """SELECT b.* FROM runtime_workspace_bindings b
            JOIN runtime_attempts a ON a.run_id=b.run_id WHERE a.id=?""",
            (peer["attempt_id"],),
        ).fetchone()
        return self.runs._binding_view(binding) if binding is not None else None

    def _execution_binding(self, conn, peer, row, source):
        """Select the host-owned ready view; development cannot fall back to the original source."""
        if source is None:
            return None
        if row["execution_kind"] == "development":
            from backend.runtime.development_state import DevelopmentWorkspaces

            view = DevelopmentWorkspaces.read_view(
                conn, row["project_id"], peer["attempt_id"]
            )
            if view.source != source:
                raise RunConflict("Private copy differs from the admitted source")
            return view
        if row["execution_kind"] == "code_review":
            from backend.runtime.code_reviews import CodeReviews

            try:
                view = CodeReviews(self.runs).execution_view(conn, row)
                if peer is not None and peer["kind"] == "native":
                    from backend.runtime.code_review_records import CodeReviewRecords

                    CodeReviewRecords(self.runs).require_preflight(conn, row)
                return view
            except RunNotFound as exc:
                raise RunConflict(
                    "Code review requires an exact candidate snapshot"
                ) from exc
        return source

    def _validate_development_source(self, conn, row, source):
        """Require the original registration and directory to remain current before each private-view gate."""
        if source is not None and row["execution_kind"] in (
            "development",
            "code_review",
        ):
            from backend.runtime.development_workspace import _source_identity

            self.runs._check_registration(conn, row["project_id"], source)
            _source_identity(source)
            if row["execution_kind"] == "code_review":
                self._execution_binding(conn, None, row, source)

    def workspace_binding(self, peer_id):
        """Resolve the execution view; private development copies require a current fenced owner."""
        with self.runs._transaction() as conn:
            peer = self._row(conn, peer_id)
            self._check_origin(peer)
            row, lease = self._lease(conn, peer)
            if row["execution_kind"] in ("development", "code_review"):
                self.runs._authority(conn, lease)
            source = self._source_binding(conn, peer)
            self._validate_development_source(conn, row, source)
            return self._execution_binding(conn, peer, row, source)

    def admission(self, peer_id, *, source_only=False):
        """Revalidate a prepared peer and both views atomically; source_only is reserved for host Git preparation."""
        with self.runs._transaction() as conn:
            peer = self._row(conn, peer_id)
            self._check_origin(peer)
            if peer["state"] != "prepared":
                raise RunConflict("Peer is no longer prepared")
            row, lease = self._lease(conn, peer)
            self.runs._authority(conn, lease)
            result = {
                key: peer[key]
                for key in ("database_identity", "attempt_id", "fence", "kind")
            }
            result.update(
                database_path=str(Path(self.runs.database).resolve(strict=True)),
                project_id=row["project_id"],
                task_id=row["task_id"],
                context_version=lease.context_version,
                execution_kind=row["execution_kind"],
            )
            source = self._source_binding(conn, peer)
            self._validate_development_source(conn, row, source)
            result["source_binding"] = source
            result["binding"] = (
                source
                if source_only
                else self._execution_binding(conn, peer, row, source)
            )
            if row["execution_kind"] == "remote_publication":
                from backend.runtime.remote_runtime import RemotePublications

                remote = RemotePublications(self.runs)
                from backend.runtime.remote_recovery import RemoteRecovery

                recovery = RemoteRecovery(self.runs)
                result["remote_observation"] = (
                    recovery.observation(conn, row) is not None
                )
                result["remote_view"] = (
                    recovery.subject(conn, row)
                    if result["remote_observation"]
                    else remote.current(conn, row)
                )
                result["remote_effects"] = [
                    dict(effect)
                    for effect in conn.execute(
                        "SELECT * FROM runtime_remote_effects WHERE run_id=?",
                        (row["id"],),
                    )
                ]
                result["remote_publication"] = remote._request(
                    conn, row["project_id"], row["id"]
                )
            if row["execution_kind"] == "code_publication":
                from backend.runtime.code_publications import CodePublications
                from backend.runtime.publication_git import PublicationRefIntent

                publications = CodePublications(self.runs)
                from backend.runtime.publication_recovery import PublicationRecovery

                recovery = PublicationRecovery(self.runs)
                result["publication_observation"] = (
                    recovery.observation(conn, row) is not None
                )
                result["publication_view"] = (
                    recovery.subject(conn, row)
                    if result["publication_observation"]
                    else publications.current(conn, row)
                )
                request = publications._request(conn, row["project_id"], row["id"])
                result["publication_ref_intent"] = PublicationRefIntent(
                    row["id"], request["target_ref"], request["expected_target_sha"]
                )
        return result

    @staticmethod
    def _lease(conn, peer):
        row = conn.execute(
            """SELECT r.*,a.id AS attempt_id,a.owner_id,a.lease_expires_at FROM runtime_runs r
            JOIN runtime_attempts a ON a.run_id=r.id WHERE a.id=?""",
            (peer["attempt_id"],),
        ).fetchone()
        lease = AttemptLease(
            row["id"],
            row["attempt_id"],
            row["project_id"],
            row["task_id"],
            row["actor_id"],
            row["context_version"],
            row["owner_id"],
            peer["fence"],
            row["lease_expires_at"],
        )
        return row, lease

    def bind(self, peer_id, identity):
        """Bind a still-gated namespace only while its lease, source registration and directory remain current."""
        # The bootstrap is still gated; capture again immediately before commit.
        if NamespaceIdentity.capture(identity.init_pid) != identity:
            raise RunConflict("Namespace identity changed before binding")
        with self.runs._transaction(write=True) as conn:
            peer = self._row(conn, peer_id)
            self._check_origin(peer)
            if peer["state"] != "prepared":
                raise RunConflict("Peer gate is no longer releasable")
            row, lease = self._lease(conn, peer)
            self.runs._authority(conn, lease)
            self._validate_development_source(
                conn, row, self._source_binding(conn, peer)
            )
            if (identity.boot_id, identity.observer_namespace) != (
                peer["boot_id"],
                peer["observer_namespace"],
            ):
                raise RunConflict(
                    "Owner kernel or PID namespace changed before binding"
                )
            conn.execute(
                "UPDATE runtime_peers SET state='bound',init_pid=?,start_ticks=?,init_namespace=?,bound_at=? WHERE id=?",
                (
                    identity.init_pid,
                    identity.start_ticks,
                    identity.init_namespace,
                    self.runs.clock(),
                    peer_id,
                ),
            )
            self.runs._event(
                conn,
                row["project_id"],
                row["task_id"],
                "peer.bound",
                {
                    "peer_id": peer_id,
                    "attempt_id": peer["attempt_id"],
                    "kind": peer["kind"],
                },
            )

    def close(self, peer_id):
        while True:
            # A WAL read does not wait behind the writer that closure may need
            # to interrupt. Never acquire a write transaction before killing a
            # bound namespace. Prepared->closed remains atomic with bind.
            with self.runs._transaction() as conn:
                row = self._row(conn, peer_id)
                self._check_origin(row)
                if row["state"] == "closed":
                    return dict(row)
                if row["state"] == "bound":
                    identity = NamespaceIdentity.from_record(row)
                    break
            with self.runs._transaction(write=True) as conn:
                row = self._row(conn, peer_id)
                self._check_origin(row)
                if row["state"] == "closed":
                    return dict(row)
                if row["state"] == "prepared":
                    return self._closed(conn, row, "never_released")
        reason = close_namespace(identity)
        with self.runs._transaction(write=True) as conn:
            row = self._row(conn, peer_id)
            self._check_origin(row)
            if row["state"] == "closed":
                return dict(row)
            if NamespaceIdentity.from_record(row) != identity:
                raise RunConflict("Peer binding changed during closure")
            return self._closed(conn, row, reason)

    def _closed(self, conn, row, reason):
        conn.execute(
            "UPDATE runtime_peers SET state='closed',reason=?,closed_at=? WHERE id=?",
            (reason, self.runs.clock(), row["id"]),
        )
        attempt = conn.execute(
            "SELECT r.project_id,r.task_id FROM runtime_runs r JOIN runtime_attempts a ON a.run_id=r.id WHERE a.id=?",
            (row["attempt_id"],),
        ).fetchone()
        self.runs._event(
            conn,
            attempt["project_id"],
            attempt["task_id"],
            "peer.closed",
            {
                "peer_id": row["id"],
                "attempt_id": row["attempt_id"],
                "kind": row["kind"],
                "reason": reason,
            },
        )
        return dict(self._row(conn, row["id"]))

    def command(self, peer_id, command):
        if not command:
            raise ValueError("Owned peer payload command is required")
        self.inspect(peer_id)
        return [
            sys.executable,
            "-I",
            str(Path(__file__).with_name("peer_guard.py")),
            "--database",
            str(Path(self.runs.database).resolve(strict=True)),
            "--peer-id",
            peer_id,
            "--",
            *map(str, command),
        ]


class AttemptPeers:
    """One host scope for all contained peers of an original attempt."""

    def __init__(self, registry, lease, ids):
        self.registry, self.lease, self.ids = registry, lease, ids

    @classmethod
    def claim(cls, runs, project_id, run_id, owner_id, *, lease_seconds=30):
        with runs._transaction(write=True) as conn:
            lease = runs._claim(
                conn, project_id, run_id, owner_id, lease_seconds=lease_seconds
            )
            peers = cls._prepare(conn, runs, lease)
        return lease, peers

    @classmethod
    def prepare(cls, runs, lease):
        with runs._transaction(write=True) as conn:
            return cls._prepare(conn, runs, lease)

    @classmethod
    def _prepare(cls, conn, runs, lease):
        """Create the original peer scope, without fictitious native/business peers for a host-only publication."""
        registry = PeerRegistry(runs)
        ids = {}
        run = runs._authority(conn, lease)
        conn.execute(
            "INSERT INTO runtime_peer_scopes(attempt_id,protocol_version,created_at) VALUES(?,1,?)",
            (lease.attempt_id, runs.clock()),
        )
        for kind in (
            ()
            if run["execution_kind"] in ("code_publication", "remote_publication")
            else ("business", "native")
        ):
            ids[kind] = registry._prepare(conn, lease, kind)
        return cls(registry, lease, ids)

    def command(self, kind, command):
        return self.registry.command(self.ids[kind], command)

    def _rows(self):
        with self.registry.runs._transaction() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM runtime_peers WHERE attempt_id=?",
                    (self.lease.attempt_id,),
                )
            ]

    def closed(self):
        rows = self._rows()
        return set(self.ids.values()) <= {row["id"] for row in rows} and all(
            row["state"] == "closed" for row in rows
        )

    async def aclose(self):
        rows = await asyncio.to_thread(self._rows)
        await asyncio.gather(
            *(asyncio.to_thread(self.registry.close, row["id"]) for row in rows)
        )
