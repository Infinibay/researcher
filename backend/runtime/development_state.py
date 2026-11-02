"""Retain private development preparation identity across crashes and context corrections.

The source registration remains the publication precondition. A prepared copy
is a separate execution view, never task acceptance or permission to publish.
Only a current fenced owner can plan or complete preparation; a former owner
may still record an observation against its own original preparation.
"""

import asyncio
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from backend.runtime.contracts import RunConflict, RunNotFound, WorkspaceBinding, text
from backend.runtime.development_workspace import (
    PreparedDevelopmentWorkspace,
    _source_identity,
)
from backend.runtime.git_capsule import PrivateAllocation


@dataclass(frozen=True)
class DevelopmentView:
    """Exact private execution directory, retaining its distinct original source admission."""

    source: WorkspaceBinding
    workspace: str
    device: int
    inode: int
    base_sha: str
    base_tree_sha: str


class DevelopmentWorkspaces:
    """Persist one non-reusable preparation allocation per development attempt."""

    def __init__(self, runs, root):
        """Bind a pre-created private host control directory, without creating or adopting copies."""
        self.runs = runs
        self.root = PrivateAllocation.capture(root)

    @staticmethod
    def _row(conn, project_id, attempt_id):
        """Read an attempt only in its actual project, including historical preparation state."""
        row = conn.execute(
            "SELECT * FROM runtime_development_workspaces WHERE project_id=? AND attempt_id=?",
            (project_id, attempt_id),
        ).fetchone()
        if row is None:
            raise RunNotFound("Development preparation not found")
        return dict(row)

    @staticmethod
    def _origin(row, lease):
        """Prevent a different owner, fence or task from writing an old attempt's observations."""
        fields = (
            "run_id",
            "attempt_id",
            "project_id",
            "task_id",
            "context_version",
            "fence",
            "owner_id",
        )
        if any(row[name] != getattr(lease, name) for name in fields):
            raise RunConflict(
                "Development preparation belongs to another original owner"
            )

    def _source(self, conn, lease):
        """Require live development authority and the unchanged original repository registration."""
        run = self.runs._authority(conn, lease)
        if run["execution_kind"] != "development":
            raise RunConflict("Private preparation requires a development execution")
        binding = conn.execute(
            "SELECT * FROM runtime_workspace_bindings WHERE run_id=?", (lease.run_id,)
        ).fetchone()
        if binding is None:
            raise RunConflict("Development requires an admitted repository")
        source = self.runs._binding_view(binding)
        self.runs._check_registration(conn, lease.project_id, source)
        _source_identity(source)
        return source

    def plan(self, lease):
        """Record allocation before filesystem work; repeats return data without authorizing a reset."""
        with self.runs._transaction(write=True) as conn:
            source = self._source(conn, lease)
            if PrivateAllocation.capture(self.root.path) != self.root:
                raise RunConflict("Private development control directory changed")
            root = Path(self.root.path)
            source_path = Path(source.workspace)
            if root.is_relative_to(source_path) or source_path.is_relative_to(root):
                raise RunConflict("Private preparation root overlaps the source")
            # Host-generated identifiers must remain single path components.
            if any(
                str(UUID(value)) != value for value in (lease.run_id, lease.attempt_id)
            ):
                raise RunConflict("Invalid development allocation identity")
            existing = conn.execute(
                "SELECT 1 FROM runtime_development_workspaces WHERE attempt_id=?",
                (lease.attempt_id,),
            ).fetchone()
            if existing is not None:
                row = self._row(conn, lease.project_id, lease.attempt_id)
                self._origin(row, lease)
                return row, False
            allocation = root / lease.run_id / lease.attempt_id
            now = self.runs.clock()
            conn.execute(
                """INSERT INTO runtime_development_workspaces
                (attempt_id,run_id,project_id,task_id,context_version,fence,owner_id,source_json,allocation,state,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,'preparing',?,?)""",
                (
                    lease.attempt_id,
                    lease.run_id,
                    lease.project_id,
                    lease.task_id,
                    lease.context_version,
                    lease.fence,
                    lease.owner_id,
                    json.dumps(asdict(source), sort_keys=True),
                    str(allocation),
                    now,
                    now,
                ),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "development.preparation_planned",
                {"run_id": lease.run_id, "attempt_id": lease.attempt_id},
            )
            return self._row(conn, lease.project_id, lease.attempt_id), True

    def complete(self, lease, prepared):
        """Persist a closed preparation result only for the live owner and exact planned private child."""
        if not isinstance(prepared, PreparedDevelopmentWorkspace):
            raise TypeError("A prepared development workspace is required")
        with self.runs._transaction(write=True) as conn:
            source = self._source(conn, lease)
            row = self._row(conn, lease.project_id, lease.attempt_id)
            self._origin(row, lease)
            copy = PrivateAllocation.capture(prepared.workspace)
            if (
                json.loads(row["source_json"]) != asdict(source)
                or prepared.repository_id != source.repository_id
                or Path(copy.path) != Path(row["allocation"]) / "repository"
                or (copy.device, copy.inode) != (prepared.device, prepared.inode)
                or any(
                    re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha) is None
                    for sha in (prepared.base_sha, prepared.base_tree_sha)
                )
            ):
                raise RunConflict(
                    "Prepared copy differs from its original allocation or base"
                )
            values = {
                name: getattr(prepared, name)
                for name in (
                    "workspace",
                    "device",
                    "inode",
                    "base_sha",
                    "base_tree_sha",
                )
            }
            if row["state"] == "ready" and all(
                row[key] == value for key, value in values.items()
            ):
                return row
            if row["state"] != "preparing":
                raise RunConflict(
                    "Preparation requires reconciliation before further execution"
                )
            conn.execute(
                """UPDATE runtime_development_workspaces SET state='ready',workspace=?,device=?,inode=?,base_sha=?,base_tree_sha=?,updated_at=? WHERE attempt_id=?""",
                (*values.values(), self.runs.clock(), lease.attempt_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "development.preparation_ready",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "base_sha": prepared.base_sha,
                },
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def observe_failure(self, lease, issue):
        """Retain a former owner's bounded failure observation without restoring business authority."""
        text(issue, "Development preparation issue", 4096)
        with self.runs._transaction(write=True) as conn:
            row = self._row(conn, lease.project_id, lease.attempt_id)
            self._origin(row, lease)
            if row["state"] != "preparing":
                return row
            conn.execute(
                "UPDATE runtime_development_workspaces SET state='reconciling',issue=?,updated_at=? WHERE attempt_id=?",
                (issue, self.runs.clock(), lease.attempt_id),
            )
            self.runs._event(
                conn,
                lease.project_id,
                lease.task_id,
                "development.preparation_interrupted",
                {
                    "run_id": lease.run_id,
                    "attempt_id": lease.attempt_id,
                    "issue": issue,
                },
            )
            return self._row(conn, lease.project_id, lease.attempt_id)

    def inspect(self, project_id, run_id):
        """Return the current attempt's retained preparation, without authorizing its execution."""
        with self.runs._transaction() as conn:
            run = self.runs._row(conn, project_id, run_id)
            return self._row(conn, project_id, run["current_attempt_id"])

    @classmethod
    def read_view(cls, conn, project_id, attempt_id):
        """Read ready identity inside a caller's authority transaction; filesystem is pinned again at spawn."""
        row = cls._row(conn, project_id, attempt_id)
        if row["state"] != "ready":
            raise RunConflict("Development copy is not ready")
        return DevelopmentView(
            WorkspaceBinding(**json.loads(row["source_json"])),
            **{
                key: row[key]
                for key in ("workspace", "device", "inode", "base_sha", "base_tree_sha")
            },
        )

    def view(self, project_id, attempt_id):
        """Return ready data for inspection; peer admission separately verifies the current lease."""
        with self.runs._transaction() as conn:
            return self.read_view(conn, project_id, attempt_id)

    async def prepare(self, lease, *, owner, registry, asset):
        """Prepare once through the actual broker and retain interrupted copies without automatic replay."""
        from backend.runtime.broker_git import OwnedGitExecutor
        from backend.runtime.development_workspace import prepare_workspace

        async def settled(function, *args):
            """Drain host filesystem/SQL work before its owned preparation scope can unwind."""
            task = asyncio.create_task(asyncio.to_thread(function, *args))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                finally:
                    raise

        planned, created = await settled(self.plan, lease)
        if not created:
            raise RunConflict(
                "Original preparation already exists; inspect retained state before a new attempt"
            )
        try:
            parent = Path(planned["allocation"]).parent
            # A run may own more than one historical attempt, but copies are never reused.
            await settled(lambda: parent.mkdir(mode=0o700, exist_ok=True))
            await settled(PrivateAllocation.capture, parent)
            source = WorkspaceBinding(**json.loads(planned["source_json"]))
            executor = OwnedGitExecutor(
                owner=owner,
                registry=registry,
                lease=lease,
                source=source.workspace,
                allocation=planned["allocation"],
                asset=asset,
            )
            prepared = await prepare_workspace(
                source, planned["allocation"], executor=executor
            )
            await settled(self.complete, lease, prepared)
            return await settled(self.view, lease.project_id, lease.attempt_id)
        except BaseException as exc:
            # Record a classification, never raw Git output, credentials or host paths.
            await settled(
                self.observe_failure,
                lease,
                "Development preparation interrupted: " + type(exc).__name__,
            )
            raise
