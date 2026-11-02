"""Product factory over original owned peers; the native runtime owns inference."""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from uuid import uuid4

import httpx

from backend.research.models import (
    DEVELOPMENT_PERMISSIONS,
    RESEARCH_PERMISSIONS,
    REVIEW_PERMISSIONS,
)
from backend.runtime.analysis_tools import AnalysisTools
from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.broker_inference import broker_inference
from backend.runtime.broker_stdio import AsyncPeerBroker
from backend.runtime.business_mediation import (
    DEVELOPMENT_NAMES,
    RESEARCH_NAMES,
    REVIEW_NAMES,
    BusinessTools,
)
from backend.runtime.codex_rpc import JsonRpcClient, RpcProtocolError
from backend.runtime.codex_session import CodexSession, ExecutionLimits
from backend.runtime.contracts import RunConflict
from backend.runtime.development_instructions import DEVELOPMENT_INSTRUCTIONS
from backend.runtime.development_state import DevelopmentWorkspaces
from backend.runtime.egress_proxy import EgressPolicy
from backend.runtime.execution_domain import ExecutionDomain
from backend.runtime.git_capsule import GitAsset
from backend.runtime.host_business import host_business
from backend.runtime.native_commands import broker_command_executor
from backend.runtime.native_inference import (
    INSTRUCTIONS,
    InferenceSession,
    _private_control,
)
from backend.runtime.native_state import NativeState
from backend.runtime.peer_broker import PeerBroker
from backend.runtime.review_instructions import REVIEW_INSTRUCTIONS
from backend.runtime.subscription_auth import ExternalChatGPTAuth
from backend.runtime.workspaces import PEER_WORKSPACE


async def _settled(function, *args, **kwargs):
    """Drain owned filesystem/SQL work before closing its journal or peer scope."""
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


async def _drain(reader):
    count = 0
    while chunk := await reader.read(8192):
        count += len(chunk)
        if count > 1048576:
            raise RpcProtocolError("Ken preparation output exceeded its host limit")


class OwnedInferenceSession(InferenceSession):
    """Expose one original owned session and revoke its entire domain on Stop."""

    def __init__(
        self, session, owner, withdraw, *, execution_workspace=None, capture=None
    ):
        """Retain original ownership and the actual execution directory as data, never as an access grant."""
        super().__init__(session.native, session.business, session.active)
        self._session, self._owner, self._withdraw = session, owner, withdraw
        self.execution_workspace = execution_workspace
        self._capture = capture
        self._capture_task = None
        self._running = False
        self._result = None

    @property
    def web_search(self):
        """Return the attested search mode rather than guessing from model text."""
        return self._session.web_search

    async def run(self, text, *, on_event=None, on_started=None):
        """Run one native turn at a time; a started capture permanently seals further generation."""
        if self._capture_task is not None:
            raise RunConflict(
                "Development session is sealed for its original candidate"
            )
        if self._running:
            raise RunConflict("A native turn is already running in this session")
        self._running = True
        self._result = None
        try:
            self._result = await self._session.run(
                text, on_event=on_event, on_started=on_started
            )
            return self._result
        finally:
            self._running = False

    async def capture_candidate(self):
        """Freeze one completed development turn through its host controller; repeats join its original result only."""
        if (
            self._capture is None
            or self._running
            or self._result is None
            or self._result.status != "completed"
        ):
            raise RunConflict("Candidate capture requires a completed development turn")
        if self._capture_task is None:
            self._capture_task = asyncio.create_task(self._capture())
            self._capture_task.add_done_callback(
                lambda done: done.exception() if not done.cancelled() else None
            )
        try:
            return await asyncio.shield(self._capture_task)
        except asyncio.CancelledError:
            await self.cancel()
            await asyncio.gather(self._capture_task, return_exceptions=True)
            raise

    async def cancel(self):
        """Stop physical work before awaiting any interrupted capture's SQL observation."""
        self._withdraw()
        if (
            self._capture_task is not None
            and not self._capture_task.done()
            and not self._capture_task.cancelling()
        ):
            self._capture_task.cancel()
        # Stop the original domain, including startup/Ken/analysis, before SQL.
        await self._owner.aclose()


@dataclass(frozen=True)
class OwnedCodexRuntime:
    """Build subscription-only sessions with required Ken and host-owned private development views."""

    app: object
    research: object
    live_grants: object
    authority: dict
    cgroup_parent: Path
    control_root: Path
    asset: object
    code_host: object
    installation: object
    model_cache: Path
    network: object
    token_source: object
    broker_limits: object
    model: str
    web_search: str = "live"
    _closed_attempts: dict = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self):
        """Reject invalid search configuration before admitting a product attempt."""
        from backend.runtime.native_search import validate_search_mode

        validate_search_mode(self.web_search)

    def consume_closure(self, lease):
        return self._closed_attempts.pop(lease.attempt_id, None) == (
            lease.project_id,
            lease.run_id,
            lease.fence,
            lease.context_version,
        )

    @asynccontextmanager
    async def open(
        self,
        *,
        workspace,
        tool_token,
        active=lambda: True,
        limits=None,
        peer_owner=None,
    ):
        """Admit one original project attempt with required Ken and revocable peers."""
        if (
            peer_owner is None
            or self.app.state.live_grants is not self.live_grants
            or self.app.state.runtime_research_store is not self.research
        ):
            raise ValueError(
                "Owned runtime requires its actual source/application controller"
            )
        registry, lease = peer_owner.registry, peer_owner.lease
        if not os.path.samefile(registry.runs.database, self.research.database):
            raise ValueError("Owned runtime source database differs")
        scope = await _settled(self.research.authorize, tool_token)
        if (scope.project_id, scope.task_id, scope.agent_id, scope.context_version) != (
            lease.project_id,
            lease.task_id,
            lease.actor_id,
            lease.context_version,
        ):
            raise ValueError("Business authority differs from original attempt")
        review = await _settled(
            registry.runs.review_request,
            lease.project_id,
            lease.run_id,
            require_current=True,
        )
        run = await _settled(registry.runs.get, lease.project_id, lease.run_id)
        development = run.execution_kind == "development"
        expected_permissions = (
            DEVELOPMENT_PERMISSIONS
            if development
            else (REVIEW_PERMISSIONS if review is not None else RESEARCH_PERMISSIONS)
        )
        if scope.permissions != expected_permissions:
            raise ValueError(
                "Business capabilities differ from the original admitted execution kind"
            )
        limits = limits or ExecutionLimits(180, 90, 1, 25, 350000)
        workspace = Path(workspace).resolve(strict=True)
        native_peer = peer_owner.ids["native"]
        binding = await _settled(registry.source_binding, native_peer)
        if binding is None or Path(binding.workspace) != workspace:
            raise ValueError("Owned runtime workspace differs from original admission")
        _private_control(self.control_root)
        states = self.control_root / "native-state"
        _private_control(states)
        with WitnessedAuthorityJournal(**self.authority) as journal:
            exported = None
            peer = analysis = None
            broker = None
            path = self.cgroup_parent / ("researcher-owned-" + uuid4().hex)
            path.mkdir(mode=0o700)
            try:
                with ExecutionDomain.open(path) as domain:
                    broker = PeerBroker(journal, domain, limits=self.broker_limits)
                    live = True

                    def admitted():
                        return live and active() and not broker._withdrawn.is_set()

                    def withdraw():
                        nonlocal live
                        live = False
                        self.live_grants.withdraw(scope.grant_id)
                        broker.withdraw()

                    async with AsyncPeerBroker(broker) as owner:

                        async def watch():
                            while admitted():
                                await asyncio.sleep(0.02)
                            withdraw()
                            await owner.aclose()

                        watcher = asyncio.create_task(watch())
                        try:
                            if development:
                                copies = self.control_root / "development"
                                _private_control(copies)
                                view = await DevelopmentWorkspaces(
                                    registry.runs, copies
                                ).prepare(
                                    lease,
                                    owner=owner,
                                    registry=registry,
                                    asset=GitAsset.inspect(Path("/usr/bin/git")),
                                )
                                workspace = Path(view.workspace)
                            state = await _settled(
                                NativeState.provision,
                                journal,
                                registry,
                                native_peer,
                                states / lease.attempt_id,
                            )
                            ken_generation = 0

                            async def prepare_ken():
                                """Prepare/reopen published Ken through original ownership without retaining two model processes."""
                                nonlocal ken_generation
                                suffix = (
                                    ""
                                    if ken_generation == 0
                                    else "-refresh-" + str(ken_generation)
                                )
                                ken_generation += 1
                                prepare_peer = await _settled(
                                    registry.prepare, lease, "ken"
                                )
                                prepare = owner.ken(
                                    registry,
                                    prepare_peer,
                                    operation_key="ken-prepare" + suffix,
                                    installation=self.installation,
                                    model_cache=self.model_cache,
                                    mode="prepare",
                                )
                                async with asyncio.timeout(90):
                                    await prepare.open(limit=65536)
                                    try:
                                        await asyncio.gather(
                                            _drain(prepare.stdout),
                                            _drain(prepare.stderr),
                                        )
                                        if (
                                            await _settled(prepare._raw.wait, timeout=3)
                                            != 0
                                        ):
                                            raise RpcProtocolError(
                                                "Required Ken preparation did not complete"
                                            )
                                    finally:
                                        closed = await prepare.aclose(timeout=5)
                                        if (
                                            not closed
                                            or closed.get("execution_closed")
                                            is not True
                                        ):
                                            raise RpcProtocolError(
                                                "Ken preparation closure is unconfirmed"
                                            )
                                ken_peer = await _settled(
                                    registry.prepare, lease, "ken"
                                )
                                ken = owner.ken(
                                    registry,
                                    ken_peer,
                                    operation_key="ken-mcp" + suffix,
                                    installation=self.installation,
                                    model_cache=self.model_cache,
                                )
                                return ken, prepare._operation

                            ken, prepared_operation = await prepare_ken()
                            endpoint = owner.native(
                                registry,
                                native_peer,
                                operation_key="inference",
                                asset=self.asset,
                                code_host=self.code_host,
                                native_state=state,
                                network=self.network,
                                egress=EgressPolicy(
                                    ("chatgpt.com", "auth.openai.com"),
                                    wall_seconds=min(600, limits.wall_seconds + 120),
                                    idle_seconds=60,
                                ),
                                host_tools=True,
                                web_search=self.web_search,
                            )
                            native = CodexSession(
                                JsonRpcClient(
                                    endpoint, request_timeout=20, max_messages=512
                                ),
                                workspace=PEER_WORKSPACE,
                                model=self.model,
                                limits=limits,
                                developer_instructions=DEVELOPMENT_INSTRUCTIONS
                                if development
                                else (
                                    REVIEW_INSTRUCTIONS
                                    if review is not None
                                    else INSTRUCTIONS
                                ),
                                sandbox="workspace-write"
                                if development
                                else "read-only",
                                subscription_auth=ExternalChatGPTAuth(
                                    self.token_source.tokens, active=admitted
                                ),
                            )
                            async with (
                                host_business(
                                    api_url="http://127.0.0.1",
                                    token=tool_token,
                                    transport=httpx.ASGITransport(app=self.app),
                                    active=admitted,
                                    withdraw=withdraw,
                                    names=DEVELOPMENT_NAMES
                                    if development
                                    else (
                                        REVIEW_NAMES
                                        if review is not None
                                        else RESEARCH_NAMES
                                    ),
                                ) as peer,
                                AnalysisTools(
                                    journal=registry.runs,
                                    lease=lease,
                                    workspace=workspace,
                                    python_executable=Path(sys.executable).resolve(
                                        strict=True
                                    ),
                                    active=admitted,
                                    executor_factory=partial(
                                        broker_command_executor,
                                        owner=owner,
                                        registry=registry,
                                        lease=lease,
                                        workspace=workspace,
                                        asset=self.asset,
                                    ),
                                ) as analysis,
                            ):
                                business = await BusinessTools.connect(
                                    peer, active=admitted
                                )
                                async with broker_inference(
                                    native,
                                    ken,
                                    prepared_operation=prepared_operation,
                                    business=business,
                                    analysis=analysis,
                                    active=admitted,
                                    prepare_ken=prepare_ken if development else None,
                                ) as session:

                                    async def capture():
                                        """Capture under the original live domain after sealing all of this session's writers."""
                                        from backend.runtime.candidate_capture import (
                                            capture_owned_candidate,
                                        )

                                        return await capture_owned_candidate(
                                            lease,
                                            runs=registry.runs,
                                            session=session,
                                            owner=owner,
                                            registry=registry,
                                            asset=GitAsset.inspect(
                                                Path("/usr/bin/git")
                                            ),
                                            settled=_settled,
                                        )

                                    try:
                                        exported = OwnedInferenceSession(
                                            session,
                                            owner,
                                            withdraw,
                                            execution_workspace=workspace,
                                            capture=capture if development else None,
                                        )
                                        yield exported
                                    finally:
                                        withdraw()
                                        if (
                                            exported is not None
                                            and exported._capture_task is not None
                                            and not exported._capture_task.done()
                                        ):
                                            await exported.cancel()
                                            await asyncio.gather(
                                                exported._capture_task,
                                                return_exceptions=True,
                                            )
                        finally:
                            withdraw()
                            watcher.cancel()
                            await asyncio.gather(watcher, return_exceptions=True)
            finally:
                # Before broker creation no process can exist in this fresh leaf.
                # A nonempty/uncertain domain is not silently removed or adopted.
                if path.exists():
                    path.rmdir()
                # Observe closure AFTER scopes exit, never sample inside them.
                grant = (
                    (await _settled(journal.load)).records.get(
                        "broker:grant:" + broker.grant_id, {}
                    )
                    if broker is not None
                    else {}
                )
                physical = broker._physical_closed if broker is not None else None
                closed = (
                    (peer is None or peer.closed)
                    and (analysis is None or analysis.closed)
                    and physical is not None
                    and physical.removed
                    and (
                        not grant
                        or (
                            grant.get("state") == "retired"
                            and grant.get("domain_removed") is True
                        )
                    )
                )
                if closed:
                    self._closed_attempts[lease.attempt_id] = (
                        lease.project_id,
                        lease.run_id,
                        lease.fence,
                        lease.context_version,
                    )
                if exported is not None:
                    exported.peers_closed = closed
