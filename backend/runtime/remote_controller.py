"""Owned remote Git/HTTP execution: original issued stages, fixed host credentials and actual local closure without another model turn."""

import asyncio
from contextlib import AsyncExitStack, nullcontext
from pathlib import Path
from uuid import uuid4

from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.broker_stdio import AsyncPeerBroker
from backend.runtime.contracts import RunConflict
from backend.runtime.execution_domain import ExecutionDomain
from backend.runtime.forgejo_publication import ForgejoPublicationClient
from backend.runtime.git_capsule import GitAsset
from backend.runtime.peer_broker import PeerBroker
from backend.runtime.peer_process import PeerUncertain
from backend.runtime.remote_executor import OwnedRemoteGitExecutor, OwnedRemoteObserver
from backend.runtime.remote_publication import (
    RemoteEffectUncertain,
    push_candidate_remote,
    reconcile_remote_push,
)
from backend.runtime.remote_runtime import RemotePublications


async def execute_owned_remote(runtime, peers, *, active, observation=False):
    """Execute one explicit remote stage under fresh ownership; retain unknown effects and prove only local client/domain closure."""
    registry, lease = peers.registry, peers.lease
    records = RemotePublications(registry.runs)
    from backend.runtime.remote_clients import RemoteHTTPClients
    from backend.runtime.remote_recovery import RemoteRecovery

    recovery = RemoteRecovery(registry.runs)
    clients = RemoteHTTPClients(registry.runs)
    config = runtime.remote_transport
    if config is None:
        raise RunConflict("Owned remote transport is not configured")
    with registry.runs._transaction() as conn:
        row = registry.runs._row(conn, lease.project_id, lease.run_id)
        request = records._request(conn, lease.project_id, lease.run_id)
        if observation != (recovery.observation(conn, row) is not None):
            raise RunConflict(
                "Remote transport mode differs from original attempt authority"
            )
        view = (
            recovery.subject(conn, row) if observation else records.current(conn, row)
        )
    protocol = records.protocol(lease.project_id, lease.run_id)
    remote = protocol["push"].remote if isinstance(protocol, dict) else protocol.remote
    if remote.api_base != config.api_base:
        raise RunConflict("Remote action differs from configured credential origin")
    stage = request["stage"]
    needs_git = stage in ("push", "merge")
    broker = executor = client = watcher = None
    path = None
    effects = {
        effect["effect_name"]
        for effect in records.request(lease.project_id, lease.run_id)["effects"]
    }
    observations = {}
    http_result = None
    client_registered = False
    proof = None
    current = asyncio.current_task()

    async def live():
        """Validate current lease/acceptance immediately before each HTTP request, independently of prior preflight results."""
        if not active():
            raise RunConflict("Remote attempt authority was withdrawn")

        def check():
            """Open the authority transaction in its owning worker thread, without transferring SQLite connections across threads."""
            with registry.runs._transaction() as conn:
                registry.runs._authority(conn, lease)

        await asyncio.to_thread(check)
        if not active():
            raise RunConflict("Remote attempt authority was withdrawn")

    async def issue_http(method, url, payload):
        """Reserve only the actual original POST at its write boundary, after readonly preflights and before network release."""
        if observation or stage not in ("pull", "merge"):
            raise RunConflict("This remote stage has no HTTP write permission")
        if stage == "pull":
            expected_url = (
                config.api_base + "/repos/" + protocol.remote.full_name + "/pulls"
            )
            expected_payload = {
                "head": protocol.head_ref[len("refs/heads/") :],
                "base": protocol.base_ref[len("refs/heads/") :],
                "title": protocol.title,
                "body": protocol.marked_body,
            }
        else:
            expected_url = (
                config.api_base
                + "/repos/"
                + protocol["pull"].remote.full_name
                + "/pulls/"
                + str(protocol["number"])
                + "/merge"
            )
            expected_payload = {
                "Do": "manually-merged",
                "MergeCommitID": protocol["push"].head_sha,
                "head_commit_id": protocol["push"].head_sha,
                "force_merge": False,
                "delete_branch_after_merge": False,
                "merge_when_checks_succeed": False,
            }
        if method != "POST" or url != expected_url or payload != expected_payload:
            raise RunConflict("HTTP write differs from the original exact remote stage")
        name = "pull" if stage == "pull" else "merge_record"
        reservation = await asyncio.to_thread(records.issue, lease, name)
        if not reservation["dispatch"]:
            raise RemoteEffectUncertain(
                "Original remote HTTP effect already issued; observe without another POST"
            )
        if not active():
            raise RunConflict("Remote attempt ended at the original HTTP gate")

    async def watch():
        """Cancel only this owned attempt and revoke Git gates promptly; remote server completion is still an unknown external effect."""
        while active():
            await asyncio.sleep(0.02)
        closing = None
        if broker is not None:
            broker.withdraw()
            closing = asyncio.create_task(owner.aclose())
        current.cancel()
        if closing is not None:
            await asyncio.shield(closing)

    with (
        WitnessedAuthorityJournal(**runtime.authority)
        if needs_git
        else nullcontext(None) as journal
    ):
        try:
            async with AsyncExitStack() as stack:
                if needs_git:
                    path = runtime.cgroup_parent / ("researcher-remote-" + uuid4().hex)
                    path.mkdir(mode=0o700)
                    domain = stack.enter_context(ExecutionDomain.open(path))
                    broker = PeerBroker(
                        journal,
                        domain,
                        limits=runtime.broker_limits,
                        remote_transport=config,
                    )
                    owner = await stack.enter_async_context(AsyncPeerBroker(broker))
                client = ForgejoPublicationClient(
                    config.api_base,
                    config.token(),
                    verify=config.ssl_context(),
                    before_request=live,
                    before_write=issue_http,
                )
                await asyncio.to_thread(clients.open, lease)
                client_registered = True
                await stack.enter_async_context(client)
                watcher = asyncio.create_task(watch())
                try:
                    if needs_git and (
                        not observation
                        or ("push" if stage == "push" else "merge_git") in effects
                    ):
                        intent = (
                            protocol["push"] if isinstance(protocol, dict) else protocol
                        )
                        executor = (
                            OwnedRemoteObserver
                            if observation
                            else OwnedRemoteGitExecutor
                        )(
                            owner=owner,
                            registry=registry,
                            lease=lease,
                            view=view,
                            asset=GitAsset.inspect(Path("/usr/bin/git")),
                            intent=intent,
                            config=config,
                            client=client,
                            effect_name="push" if stage == "push" else "merge_git",
                        )
                        observed = (
                            await reconcile_remote_push(
                                view,
                                intent,
                                executor=executor,
                                original_client_closed=True,
                            )
                            if observation
                            else await push_candidate_remote(
                                view, intent, executor=executor
                            )
                        )
                        name = "push" if stage == "push" else "merge_git"
                        if observation:
                            observations[name] = observed
                        else:
                            await asyncio.to_thread(
                                records.observe,
                                lease,
                                name,
                                observed,
                                client_closed=True,
                            )
                    if stage == "pull" and (not observation or "pull" in effects):
                        http_result = (
                            await client.reconcile_pull(
                                protocol, original_client_closed=True
                            )
                            if observation
                            else await client.create_pull(protocol)
                        )
                        if observation:
                            observations["pull"] = http_result
                    elif stage == "merge":
                        if observation:
                            if (
                                "merge_record" in effects
                                and observed.state == "published"
                            ):
                                http_result = await client.reconcile_exact_merge(
                                    protocol["pull"],
                                    protocol["number"],
                                    protocol["push"],
                                    observed,
                                    original_client_closed=True,
                                )
                                observations["merge_record"] = http_result
                        else:
                            http_result = await client.record_exact_merge(
                                protocol["pull"],
                                protocol["number"],
                                protocol["push"],
                                observed,
                            )
                finally:
                    if watcher is not None:
                        watcher.cancel()
                        await asyncio.gather(watcher, return_exceptions=True)
                    if broker is not None:
                        broker.withdraw()
        finally:
            if path is not None and path.exists():
                path.rmdir()
            http_closed = client is not None and client._client.is_closed
            domain_closed = not needs_git
            grant_id = None
            operations = []
            if broker is not None:
                snapshot = journal.load().records
                grant = snapshot.get("broker:grant:" + broker.grant_id)
                physical = broker._physical_closed
                domain_closed = bool(
                    physical is not None
                    and physical.removed
                    and (
                        grant is None
                        or (
                            grant.get("state") == "retired"
                            and grant.get("domain_removed") is True
                        )
                    )
                )
                grant_id = broker.grant_id
                if executor is not None:
                    operations = [
                        {"operation_id": key, **snapshot["broker:op:" + key]}
                        for key in executor.operations
                    ]
            if http_closed and client_registered:
                await asyncio.to_thread(clients.close, lease)
            if domain_closed and http_closed:
                runtime._closed_attempts[lease.attempt_id] = (
                    lease.project_id,
                    lease.run_id,
                    lease.fence,
                    lease.context_version,
                )
            if http_result is not None and http_closed and not observation:
                await asyncio.to_thread(
                    records.observe,
                    lease,
                    "pull" if stage == "pull" else "merge_record",
                    http_result,
                    client_closed=True,
                )
            proof = {
                "domain_closed": domain_closed,
                "http_client_closed": http_closed,
                "grant_id": grant_id,
                "operations": [
                    {
                        "operation_id": op.get("operation_id"),
                        "execution_closed": op["execution_closed"],
                        "manifest": op["runtime_manifest"],
                    }
                    for op in operations
                ],
            }
        if not domain_closed or not http_closed:
            raise PeerUncertain("Owned remote local transport closure is unconfirmed")
        return observations if observation else None, proof
