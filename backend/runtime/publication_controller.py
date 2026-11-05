"""Fresh host publication ownership: no model turn, old lease reuse or unowned Git subprocess."""

import asyncio
from pathlib import Path
from uuid import uuid4

from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.broker_stdio import AsyncPeerBroker
from backend.runtime.code_publications import CodePublications
from backend.runtime.execution_domain import ExecutionDomain
from backend.runtime.git_capsule import GitAsset
from backend.runtime.peer_process import PeerUncertain
from backend.runtime.publication_executor import OwnedPublicationGitExecutor
from backend.runtime.publication_git import PublicationRefIntent, publish_candidate_ref


async def execute_owned_publication(runtime, peers, *, active):
    """Publish through a newly owned command domain and return evidence only after its actual physical retirement."""
    registry, lease = peers.registry, peers.lease
    publications = CodePublications(registry.runs)
    with registry.runs._transaction() as conn:
        run = registry.runs._row(conn, lease.project_id, lease.run_id)
        view = publications.current(conn, run)
        request = publications._request(conn, lease.project_id, lease.run_id)
    intent = PublicationRefIntent(
        lease.run_id, request["target_ref"], request["expected_target_sha"]
    )
    path = runtime.cgroup_parent / ("researcher-publication-" + uuid4().hex)
    path.mkdir(mode=0o700)
    broker = executor = None
    with WitnessedAuthorityJournal(**runtime.authority) as journal:
        try:
            with ExecutionDomain.open(path) as domain:
                from backend.runtime.peer_broker import PeerBroker

                broker = PeerBroker(journal, domain, limits=runtime.broker_limits)
                async with AsyncPeerBroker(broker) as owner:

                    async def watch():
                        """Withdraw physical publication capacity when Stop, correction or the original lease ends."""
                        while active() and not broker._withdrawn.is_set():
                            await asyncio.sleep(0.02)
                        broker.withdraw()
                        await owner.aclose()

                    watcher = asyncio.create_task(watch())
                    try:
                        executor = OwnedPublicationGitExecutor(
                            owner=owner,
                            registry=registry,
                            lease=lease,
                            view=view,
                            asset=GitAsset.inspect(Path("/usr/bin/git")),
                        )
                        observed = await publish_candidate_ref(
                            view, intent, executor=executor
                        )
                    finally:
                        broker.withdraw()
                        watcher.cancel()
                        await asyncio.gather(watcher, return_exceptions=True)
        finally:
            if path.exists():
                path.rmdir()
            records = journal.load().records
            grant = records.get("broker:grant:" + broker.grant_id, {}) if broker else {}
            physical = broker._physical_closed if broker else None
            closed = bool(
                physical is not None
                and physical.removed
                and grant.get("state") == "retired"
                and grant.get("domain_removed") is True
            )
            if closed:
                runtime._closed_attempts[lease.attempt_id] = (
                    lease.project_id,
                    lease.run_id,
                    lease.fence,
                    lease.context_version,
                )
        if not closed:
            raise PeerUncertain("Publication physical retirement is unconfirmed")
        operations = []
        for operation_id in executor.operations:
            operation = records["broker:op:" + operation_id]
            operations.append(
                {
                    "operation_id": operation_id,
                    "execution_closed": operation["execution_closed"],
                    "exit_code": operation["exit_code"],
                    "manifest": operation["runtime_manifest"],
                }
            )
        return observed, {
            "grant_id": broker.grant_id,
            "domain_closed": True,
            "operations": operations,
        }
