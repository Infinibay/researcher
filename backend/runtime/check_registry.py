"""Admit only the reserved check execution copy while retaining its original source concession."""

import json
from dataclasses import dataclass

from backend.runtime.check_contracts import CandidateSubject
from backend.runtime.check_state import CodeChecks
from backend.runtime.contracts import RunConflict, WorkspaceBinding
from backend.runtime.development_workspace import _source_identity
from backend.runtime.git_capsule import PrivateAllocation
from backend.runtime.peer_registry import PeerRegistry


@dataclass(frozen=True)
class CheckExecutionView:
    """Exact writable check copy plus protected metadata and immutable candidate/recipe references."""

    source: WorkspaceBinding
    workspace: str
    device: int
    inode: int
    check_id: str
    subject_sha256: str
    spec_sha256: str
    metadata: PrivateAllocation


class CandidateCheckRegistry(PeerRegistry):
    """Narrow the normal admission/final-binding transactions to one running check and its original peer."""

    def __init__(self, runs, lease, check_id):
        """Keep a fixed host-selected lease/check; model code cannot choose a different view or mount."""
        super().__init__(runs)
        self.lease = lease
        self.check_id = check_id
        self.checks = CodeChecks(runs)

    def _check(self, conn, row, source):
        """Recheck exact scope and both physical identities inside admission and final pre-G binding."""
        candidate, subject = self.checks._current(conn, self.lease)
        check = self.checks._row(conn, self.lease.project_id, self.check_id)
        self.checks._origin(check, self.lease)
        if (
            row["id"] != self.lease.run_id
            or row["execution_kind"] != "development"
            or check["state"] != "running"
        ):
            raise RunConflict(
                "Check execution requires its original running reservation"
            )
        if (
            CandidateSubject(**json.loads(check["subject_json"])) != subject
            or json.loads(candidate["source_json"])["workspace"] != source.workspace
        ):
            raise RunConflict("Check candidate or source concession changed")
        prepared = self.checks.workspace(check)
        _source_identity(prepared.view)
        if PrivateAllocation.capture(prepared.metadata.path) != prepared.metadata:
            raise RunConflict("Check metadata identity changed")
        return check, subject, prepared

    def _validate_development_source(self, conn, row, source):
        """Retain base registration validation and add the check identities at the final gate too."""
        super()._validate_development_source(conn, row, source)
        self._check(conn, row, source)

    def _execution_binding(self, conn, peer, row, source):
        """Select only the recorded command peer's check directory, never the author copy or original source."""
        check, subject, prepared = self._check(conn, row, source)
        if peer["kind"] != "command" or check["peer_id"] != peer["id"]:
            raise RunConflict("Check profile requires its original command peer")
        return CheckExecutionView(
            source,
            prepared.view.workspace,
            prepared.view.device,
            prepared.view.inode,
            self.check_id,
            subject.sha256,
            check["spec_sha256"],
            prepared.metadata,
        )
