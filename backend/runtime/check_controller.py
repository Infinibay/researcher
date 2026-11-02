"""Execute a reserved exact candidate check before retiring its original sealed developer domain.

The candidate stays untouched. Each recipe uses its own independent copy and
protected validation metadata; results/events commit only under current authority.
"""

import json
from dataclasses import replace
from pathlib import Path

from backend.runtime import check_execution
from backend.runtime.broker_git import OwnedGitExecutor
from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.check_capsule import CheckLaunch
from backend.runtime.check_contracts import CandidateSubject, CheckObservation
from backend.runtime.check_registry import CandidateCheckRegistry
from backend.runtime.check_state import CodeChecks
from backend.runtime.check_workspace import (
    check_workspace_matches,
    prepare_check_workspace,
)
from backend.runtime.contracts import RunConflict, RunNotFound, WorkspaceBinding
from backend.runtime.git_capsule import PrivateAllocation


async def execute_owned_check(
    lease, operation_key, spec, *, runs, owner, registry, asset, environment, settled
):
    """Reserve before effects, prepare once and retain physical/result evidence without automatic effect replay."""
    checks = CodeChecks(runs)
    check_id = None
    if spec.environment_id != environment.identity:
        raise RunConflict("Check environment is not available under this host policy")
    try:
        row, created = await settled(checks.plan, lease, operation_key, spec)
        check_id = row["id"]
        if not created:
            if row["state"] == "finished":
                return row
            raise RunConflict(
                "Original check reservation exists; inspect it without replay"
            )
        candidate = await settled(
            CodeCandidates(runs).inspect, lease.project_id, lease.run_id
        )
        subject = CandidateSubject(**json.loads(row["subject_json"]))
        source = WorkspaceBinding(**json.loads(candidate["source_json"]))
        snapshot = replace(
            source,
            workspace=candidate["workspace"],
            device=candidate["device"],
            inode=candidate["inode"],
        )
        parent = Path(row["allocation"]).parent
        await settled(lambda: parent.mkdir(mode=0o700, parents=True, exist_ok=True))
        await settled(PrivateAllocation.capture, parent)
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=source.workspace,
            allocation=parent.parent,
            asset=asset,
        )
        prepared = await prepare_check_workspace(
            snapshot,
            row["allocation"],
            head_sha=subject.head_sha,
            tree_sha=subject.tree_sha,
            executor=executor,
        )
        await settled(checks.prepared, lease, check_id, prepared)
        peer = await settled(registry.prepare, lease, "command")
        await settled(checks.bind_peer, lease, check_id, peer)
        view = CandidateCheckRegistry(runs, lease, check_id)
        raw = await check_execution.run_check_worker(
            owner,
            view,
            peer,
            CheckLaunch(check_id, spec, prepared.metadata, environment),
        )
        if raw.subject_sha256 != subject.sha256:
            raise RunConflict(
                "Executed check subject differs from its original candidate"
            )
        matches = await check_workspace_matches(prepared, executor=executor)
        observed = CheckObservation(
            subject,
            spec.sha256,
            raw.payload["exit_code"],
            raw.execution_closed,
            raw.payload["output_complete"],
            matches,
            raw.junit_xml,
        )
        return await settled(
            checks.complete,
            lease,
            check_id,
            observed,
            operation_id=raw.operation_id,
            stdout=raw.stdout,
            stderr=raw.stderr,
            collector_issue=raw.payload.get("error"),
        )
    except BaseException as error:
        owner.broker.withdraw()
        await owner.aclose()
        if check_id is not None:
            try:
                await settled(
                    checks.observe_failure,
                    lease,
                    check_id,
                    "Check interrupted: " + type(error).__name__,
                )
            except RunNotFound:
                pass
        raise
