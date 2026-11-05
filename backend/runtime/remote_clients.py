"""Durable original HTTP-client ownership: explicit local closure or same-host process death, never a remote completion claim."""

import os

from backend.runtime.contracts import RunConflict
from backend.runtime.peer_process import boot_id, observer_namespace, start_ticks
from backend.runtime.peer_registry import PeerRegistry


class RemoteHTTPClients:
    """Bind each attempt's host-only HTTP sockets to their original process and database before opening a client."""

    def __init__(self, runs):
        """Reuse the runtime authority transaction; no network or process is opened."""
        self.runs = runs

    @staticmethod
    def _owner():
        """Capture current host process identity in the visible original kernel/PID namespace."""
        return os.getpid(), start_ticks(os.getpid()), boot_id(), observer_namespace()

    def open(self, lease):
        """Register the sole HTTP-client scope before the attempt can release its first HTTP request."""
        with self.runs._transaction(write=True) as conn:
            self.runs._authority(conn, lease)
            conn.execute(
                "INSERT INTO runtime_remote_clients(attempt_id,run_id,database_identity,fence,owner_pid,owner_start_ticks,boot_id,observer_namespace,state,created_at)VALUES(?,?,?,?,?,?,?,?,'open',?)",
                (
                    lease.attempt_id,
                    lease.run_id,
                    PeerRegistry(self.runs)._database_identity(),
                    lease.fence,
                    *self._owner(),
                    self.runs.clock(),
                ),
            )

    def close(self, lease):
        """Record actual controller closure even after authority withdrawal; another process cannot close a live original client by assertion."""
        with self.runs._transaction(write=True) as conn:
            self.runs._original_attempt(conn, lease)
            row = conn.execute(
                "SELECT * FROM runtime_remote_clients WHERE attempt_id=?",
                (lease.attempt_id,),
            ).fetchone()
            if row is None or (
                row["run_id"],
                row["fence"],
                row["database_identity"],
            ) != (
                lease.run_id,
                lease.fence,
                PeerRegistry(self.runs)._database_identity(),
            ):
                raise RunConflict("Original HTTP scope differs")
            if (
                tuple(
                    row[key]
                    for key in (
                        "owner_pid",
                        "owner_start_ticks",
                        "boot_id",
                        "observer_namespace",
                    )
                )
                != self._owner()
            ):
                raise RunConflict("Original HTTP owner differs")
            if row["state"] != "closed":
                conn.execute(
                    "UPDATE runtime_remote_clients SET state='closed',closed_at=? WHERE attempt_id=?",
                    (self.runs.clock(), lease.attempt_id),
                )

    def closure(self, project_id, run_id, attempt_id):
        """Prove original local HTTP closure without signaling the host or inferring that the remote server stopped."""
        with self.runs._transaction() as conn:
            run = self.runs._row(conn, project_id, run_id)
            row = conn.execute(
                "SELECT * FROM runtime_remote_clients WHERE run_id=? AND attempt_id=?",
                (run_id, attempt_id),
            ).fetchone()
            attempt = conn.execute(
                "SELECT fence FROM runtime_attempts WHERE id=? AND run_id=?",
                (attempt_id, run_id),
            ).fetchone()
            if (
                row is None
                or attempt is None
                or (row["database_identity"], row["fence"])
                != (PeerRegistry(self.runs)._database_identity(), attempt["fence"])
                or run["current_attempt_id"] != attempt_id
            ):
                raise RunConflict(
                    "Original HTTP closure identity is missing or changed"
                )
            if row["state"] == "closed":
                return {
                    "http_client_closed": True,
                    "http_attempt_id": attempt_id,
                    "http_closure": "explicit_controller_close",
                }
            if (row["boot_id"], row["observer_namespace"]) != (
                boot_id(),
                observer_namespace(),
            ):
                raise RunConflict("Original HTTP host visibility changed")
            try:
                alive = start_ticks(row["owner_pid"]) == row["owner_start_ticks"]
            except (FileNotFoundError, ProcessLookupError):
                alive = False
            except (OSError, ValueError) as error:
                raise RunConflict("Original HTTP owner remains unconfirmed") from error
            if alive:
                raise RunConflict(
                    "Original HTTP owner is still alive without client closure"
                )
            return {
                "http_client_closed": True,
                "http_attempt_id": attempt_id,
                "http_closure": "original_host_process_absent",
            }
