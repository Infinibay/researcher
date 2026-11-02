"""Seal an owned developer session and capture its one durable exact code candidate.

The original global broker stays alive through Git capture. All model/command
writers must be physically closed first; no new domain may adopt this attempt.
Failure retains the reservation and bytes, never authorizes replay or acceptance.
"""

import json
from pathlib import Path

from backend.runtime import code_candidate
from backend.runtime.broker_git import OwnedGitExecutor
from backend.runtime.candidate_state import CodeCandidates
from backend.runtime.contracts import RunConflict, RunNotFound, WorkspaceBinding
from backend.runtime.development_workspace import PreparedDevelopmentWorkspace


def closed_writer_proof(owner, lease):
    """Read actual original-domain receipts after sealing; process exit text is insufficient to prove closure."""
    snapshot = owner.broker.journal.load()
    grant = snapshot.records.get(owner.broker._grant_key, {})
    if (
        grant.get("state") != "active"
        or grant.get("attempt_id") != lease.attempt_id
        or grant.get("fence") != lease.fence
        or owner._closing is not None
        or owner.broker._withdrawn.is_set()
    ):
        raise RunConflict("Original candidate domain is no longer active")
    operations = []
    for key, value in snapshot.records.items():
        if (
            key.startswith("broker:op:")
            and value.get("grant_id") == owner.broker.grant_id
        ):
            if value.get("execution_closed") is not True:
                raise RunConflict("Original writer physical closure is unconfirmed")
            operations.append(
                {
                    "operation_id": key.removeprefix("broker:op:"),
                    "execution_closed": True,
                }
            )
    proof = {"grant_id": owner.broker.grant_id, "operations": operations}
    CodeCandidates._proof(proof)
    return proof


async def capture_owned_candidate(
    lease, *, runs, session, owner, registry, asset, settled
):
    """Reserve before effects, seal writers, run exact owned Git and commit only under the unchanged original lease."""
    candidates = CodeCandidates(runs)
    try:
        planned, created = await settled(candidates.plan, lease)
        if not created:
            raise RunConflict(
                "Original candidate reservation already exists; inspect it without replay"
            )
        await session.seal()
        proof = await settled(closed_writer_proof, owner, lease)
        prepared = json.loads(planned["prepared_json"])
        source = WorkspaceBinding(**json.loads(planned["source_json"]))
        author = PreparedDevelopmentWorkspace(
            source.repository_id,
            **{
                name: prepared[name]
                for name in (
                    "workspace",
                    "device",
                    "inode",
                    "base_sha",
                    "base_tree_sha",
                )
            },
        )
        executor = OwnedGitExecutor(
            owner=owner,
            registry=registry,
            lease=lease,
            source=source.workspace,
            allocation=Path(planned["allocation"]).parent,
            asset=asset,
        )
        captured = await code_candidate.capture_candidate(
            source, author, planned["allocation"], executor=executor
        )
        return await settled(candidates.complete, lease, captured, proof)
    except BaseException as error:
        # Physical withdrawal/closure precedes potentially contended source SQL.
        owner.broker.withdraw()
        await owner.aclose()
        try:
            await settled(
                candidates.observe_failure,
                lease,
                "Candidate capture interrupted: " + type(error).__name__,
            )
        except RunNotFound:
            pass  # Cancellation may precede the durable reservation entirely.
        raise
