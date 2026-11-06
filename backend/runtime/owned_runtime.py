"""Product factory over original owned peers; the native runtime owns inference."""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import httpx

from backend.prompts.native import build_instructions
from backend.research.models import (
    CODE_REVIEW_PERMISSIONS,
    DEVELOPMENT_PERMISSIONS,
    PLANNING_PERMISSIONS,
    RESEARCH_PERMISSIONS,
    REVIEW_PERMISSIONS,
)
from backend.runtime.analysis_tools import AnalysisTools
from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.broker_inference import broker_inference
from backend.runtime.broker_stdio import AsyncPeerBroker
from backend.runtime.business_mediation import (
    CODE_REVIEW_NAMES,
    DEVELOPMENT_NAMES,
    INVESTIGATION_NAMES,
    RESEARCH_NAMES,
    REVIEW_NAMES,
    BusinessTools,
    ProjectTools,
)
from backend.runtime.codex_rpc import JsonRpcClient, RpcProtocolError
from backend.runtime.codex_session import CodexSession, ExecutionLimits
from backend.runtime.contracts import RunConflict
from backend.runtime.development_state import DevelopmentWorkspaces
from backend.runtime.egress_proxy import EgressPolicy
from backend.runtime.execution_domain import ExecutionDomain
from backend.runtime.git_capsule import GitAsset
from backend.runtime.host_business import host_business
from backend.runtime.native_commands import broker_command_executor
from backend.runtime.native_inference import (
    InferenceSession,
    _private_control,
)
from backend.runtime.native_state import NativeState
from backend.runtime.peer_broker import PeerBroker
from backend.runtime.subscription_auth import ExternalChatGPTAuth
from backend.runtime.task_profiles import NATIVE_TASK_TYPES
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
        self,
        session,
        owner,
        withdraw,
        *,
        execution_workspace=None,
        capture=None,
        check=None,
        complete_review=None,
    ):
        """Retain original ownership and the actual execution directory as data, never as an access grant."""
        super().__init__(session.native, session.business, session.active)
        self._session, self._owner, self._withdraw = session, owner, withdraw
        self.execution_workspace = execution_workspace
        self._capture = capture
        self._capture_task = None
        self._check = check
        self._check_tasks = {}
        self._complete_review = complete_review
        self._review_task = None
        self._running = False
        self._result = None

    @property
    def web_search(self):
        """Return the attested search mode rather than guessing from model text."""
        return self._session.web_search

    async def run(self, text, *, on_event=None, on_started=None):
        """Run one native turn at a time; a started capture permanently seals further generation."""
        if self._capture_task is not None or self._review_task is not None:
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

    async def run_check(self, operation_key, spec):
        """Run one host recipe only after exact capture; repeated keys join original tasks rather than launching again."""
        from backend.runtime.check_contracts import CheckSpec

        if (
            self._check is None
            or not isinstance(spec, CheckSpec)
            or self._capture_task is None
            or not self._capture_task.done()
            or self._capture_task.cancelled()
        ):
            raise RunConflict("Checks require a captured development candidate")
        if self._capture_task.result()["state"] != "ready":
            raise RunConflict("Checks require a ready exact candidate")
        from backend.runtime.contracts import command_key

        command_key(operation_key)
        existing = self._check_tasks.get(operation_key)
        if existing is not None and existing[0] != spec.sha256:
            raise RunConflict("Check operation already names another recipe")
        if existing is None:
            if (
                self._owner._closing is not None
                or self._owner.broker._withdrawn.is_set()
            ):
                raise RunConflict(
                    "Original check domain retired; inspect saved observations without replay"
                )
            task = asyncio.create_task(self._check(operation_key, spec))
            task.add_done_callback(
                lambda done: done.exception() if not done.cancelled() else None
            )
            self._check_tasks[operation_key] = (spec.sha256, task)
        else:
            task = existing[1]
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await self.cancel()
            await asyncio.gather(task, return_exceptions=True)
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
        for _digest, task in self._check_tasks.values():
            if not task.done() and not task.cancelling():
                task.cancel()
        if (
            self._review_task is not None
            and not self._review_task.done()
            and not self._review_task.cancelling()
        ):
            self._review_task.cancel()
        # Stop the original domain, including startup/Ken/analysis, before SQL.
        await self._owner.aclose()

    async def complete_review(self):
        """Seal one completed reviewer turn and join its original Git/closure confirmation, without accepting or publishing work."""
        if (
            self._complete_review is None
            or self._running
            or self._result is None
            or self._result.status != "completed"
        ):
            raise RunConflict(
                "Review confirmation requires a completed independent native turn"
            )
        if self._review_task is None:
            self._review_task = asyncio.create_task(self._complete_review())
            self._review_task.add_done_callback(
                lambda done: done.exception() if not done.cancelled() else None
            )
        try:
            return await asyncio.shield(self._review_task)
        except asyncio.CancelledError:
            await self.cancel()
            await asyncio.gather(self._review_task, return_exceptions=True)
            raise


@dataclass(frozen=True)
class OwnedCodexRuntime:
    """Build subscription-only sessions with required Ken and host-owned private development views."""

    supported_task_types: ClassVar[tuple[str, ...]] = NATIVE_TASK_TYPES
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
    reasoning_effort: str = "low"
    web_search: str = "live"
    development_checks: tuple = ()
    remote_transport: object = None
    _closed_attempts: dict = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _model_catalog: dict = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self):
        """Reject invalid search configuration before admitting a product attempt."""
        from backend.runtime.native_search import validate_search_mode

        validate_search_mode(self.web_search)
        from backend.runtime.model_settings import model_profile

        model_profile(self.model, self.reasoning_effort)
        from backend.runtime.check_contracts import CheckSpec

        if (
            not isinstance(self.development_checks, tuple)
            or len(self.development_checks) > 8
            or any(
                not isinstance(check, CheckSpec) for check in self.development_checks
            )
        ):
            raise ValueError(
                "Owned development requires immutable bounded host check recipes"
            )

    def consume_closure(self, lease):
        return self._closed_attempts.pop(lease.attempt_id, None) == (
            lease.project_id,
            lease.run_id,
            lease.fence,
            lease.context_version,
        )

    @property
    def supports_remote_publication(self):
        """Expose remote capability only when operator HTTPS/credential configuration was explicitly validated."""
        return self.remote_transport is not None

    async def preview_remote(
        self, store, project_id, local_run_id, target_ref, base_ref
    ):
        """Observe only the registered accepted destination over owned bounded HTTP; this control cannot issue Git or HTTP writes."""
        from backend.runtime.forgejo_publication import ForgejoPublicationClient
        from backend.runtime.remote_destinations import RemoteDestinations

        config = self.remote_transport
        if config is None:
            raise ValueError("Owned remote transport is not configured")
        async with ForgejoPublicationClient(
            config.api_base, config.token(), verify=config.ssl_context()
        ) as client:
            return await RemoteDestinations(store).observe(
                project_id, local_run_id, target_ref, base_ref, client=client
            )

    async def publish_remote(self, peers, *, active):
        """Execute one original remote owner action through owned fixed Git and bounded host HTTP without model inference."""
        from backend.runtime.remote_controller import execute_owned_remote

        return await execute_owned_remote(self, peers, active=active)

    async def observe_remote_publication(self, peers, *, active):
        """Observe original remote effects through new readonly Git/HTTP authority; never resume a write stage."""
        from backend.runtime.remote_controller import execute_owned_remote

        return await execute_owned_remote(self, peers, active=active, observation=True)

    def close_remote_publication(self, store, project_id, run_id, attempt_id):
        """Prove original host HTTP and global Git-domain closure before another readonly remote observer is admitted."""
        from backend.runtime.publication_closure import close_original_publication
        from backend.runtime.remote_clients import RemoteHTTPClients

        http = RemoteHTTPClients(store).closure(project_id, run_id, attempt_id)
        return {
            **close_original_publication(
                self.authority, store, project_id, run_id, attempt_id, remote=True
            ),
            **http,
        }

    async def publish_code(self, peers, *, active):
        """Execute an explicitly admitted host publication under fresh ownership without opening Codex or using the author/reviewer sessions."""
        from backend.runtime.publication_controller import execute_owned_publication

        return await execute_owned_publication(self, peers, active=active)

    async def observe_publication(self, peers, *, active):
        """Observe original ref evidence through a new readonly domain; never reactivate the closed publishing lease."""
        from backend.runtime.publication_controller import execute_owned_publication

        return await execute_owned_publication(
            self, peers, active=active, observation=True
        )

    def close_publication(self, store, project_id, run_id, attempt_id):
        """Prove retirement of this exact original publication's global grants before admitting any new readonly observer."""
        from backend.runtime.publication_closure import close_original_publication

        return close_original_publication(
            self.authority, store, project_id, run_id, attempt_id
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
        from backend.runtime.model_settings import ModelSettings, validate_native_model

        selected_model = await _settled(
            ModelSettings(registry.runs).freeze,
            lease,
            host_model=self.model,
            host_effort=self.reasoning_effort,
        )

        async def verify_model(rpc):
            """Check this frozen original pair against the actual signed-in account catalog before thread creation; never select an alternative."""
            await validate_native_model(rpc, selected_model, self._model_catalog)

        review = await _settled(
            registry.runs.review_request,
            lease.project_id,
            lease.run_id,
            require_current=True,
        )
        run = await _settled(registry.runs.get, lease.project_id, lease.run_id)
        context = await _settled(
            registry.runs.context_snapshot, lease.project_id, lease.task_id
        )
        planning = (
            run.execution_kind == "research" and context["task"]["type"] == "plan"
        )
        audit = run.execution_kind == "research" and context["task"]["type"] == "review"
        investigation = run.execution_kind == "research" and context["task"]["type"] == "investigation"
        development = run.execution_kind == "development"
        code_review = run.execution_kind == "code_review"
        expected_permissions = (
            DEVELOPMENT_PERMISSIONS
            if development
            else (
                CODE_REVIEW_PERMISSIONS
                if code_review
                else (
                    REVIEW_PERMISSIONS
                    if review is not None
                    else PLANNING_PERMISSIONS
                    if planning
                    else RESEARCH_PERMISSIONS
                )
            )
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
            code_tools = review_records = review_executor = None
            material_tools = None
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
                            elif code_review:
                                from backend.runtime.code_review_controller import (
                                    prepare_owned_review,
                                )

                                (
                                    review_records,
                                    review_executor,
                                ) = await prepare_owned_review(
                                    lease,
                                    runs=registry.runs,
                                    owner=owner,
                                    registry=registry,
                                    asset=GitAsset.inspect(Path("/usr/bin/git")),
                                    settled=_settled,
                                )
                                workspace = Path(
                                    (
                                        await _settled(review_records.candidate, lease)
                                    ).workspace
                                )
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
                                model=selected_model['model'],
                                reasoning_effort=selected_model['reasoning_effort'],
                                before_thread=verify_model,
                                limits=limits,
                                developer_instructions=build_instructions(run.execution_kind, context['task']['type'], checks=self.development_checks),
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
                                    if development or planning
                                    else (
                                        CODE_REVIEW_NAMES
                                        if code_review
                                        else REVIEW_NAMES
                                        if review is not None
                                        else INVESTIGATION_NAMES
                                        if investigation
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
                                if code_review:
                                    from backend.runtime.code_review_tools import (
                                        CodeReviewTools,
                                    )

                                    code_tools = CodeReviewTools(
                                        review_records,
                                        lease,
                                        active=admitted,
                                        settled=_settled,
                                    )
                                    business = ProjectTools(business, code_tools)
                                elif planning:
                                    from backend.planning.store import ProjectPlans
                                    from backend.planning.tools import PlanningTools

                                    code_tools = PlanningTools(
                                        ProjectPlans(registry.runs),
                                        lease,
                                        active=admitted,
                                        settled=_settled,
                                    )
                                    business = ProjectTools(business, code_tools)
                                from backend.planning.materials import PredecessorMaterials
                                from backend.runtime.predecessor_tools import PredecessorTools

                                material_records = PredecessorMaterials(registry.runs)
                                if await _settled(material_records.available, lease):
                                    material_tools = PredecessorTools(material_records, lease, active=admitted, settled=_settled)
                                    business = ProjectTools(business, material_tools)

                                async def seal_host_tools():
                                    """Withdraw and drain both role and causal readonly work before the original turn leaves its capability scope."""
                                    for tools in (code_tools, material_tools):
                                        if tools is not None:
                                            await tools.aclose()

                                async with broker_inference(
                                    native,
                                    ken,
                                    prepared_operation=prepared_operation,
                                    business=business,
                                    analysis=analysis,
                                    active=admitted,
                                    prepare_ken=prepare_ken
                                    if development or code_review
                                    else None,
                                    seal_tools=seal_host_tools
                                    if code_tools is not None or material_tools is not None
                                    else None,
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

                                    async def check(operation_key, spec):
                                        """Resolve explicit host environments and keep actual CI execution in original ownership."""
                                        import sysconfig

                                        from backend.runtime.check_capsule import (
                                            CheckEnvironment,
                                        )
                                        from backend.runtime.check_controller import (
                                            execute_owned_check,
                                        )

                                        if spec.environment_id == "system":
                                            environment = CheckEnvironment.system()
                                        elif spec.environment_id == "runtime-python":
                                            environment = CheckEnvironment.capture(
                                                "runtime-python",
                                                Path(sysconfig.get_paths()["purelib"]),
                                            )
                                        else:
                                            raise RunConflict(
                                                "Selected check environment is unavailable; no fallback"
                                            )
                                        return await execute_owned_check(
                                            lease,
                                            operation_key,
                                            spec,
                                            runs=registry.runs,
                                            owner=owner,
                                            registry=registry,
                                            asset=GitAsset.inspect(
                                                Path("/usr/bin/git")
                                            ),
                                            environment=environment,
                                            settled=_settled,
                                        )

                                    async def complete_review():
                                        """Retain the original physical reviewer domain through sealing and exact post-review Git validation."""
                                        from backend.runtime.code_review_controller import (
                                            confirm_owned_review,
                                        )

                                        return await confirm_owned_review(
                                            lease,
                                            records=review_records,
                                            executor=review_executor,
                                            session=session,
                                            owner=owner,
                                            settled=_settled,
                                        )

                                    try:
                                        exported = OwnedInferenceSession(
                                            session,
                                            owner,
                                            withdraw,
                                            execution_workspace=workspace,
                                            capture=capture if development else None,
                                            check=check if development else None,
                                            complete_review=complete_review
                                            if code_review
                                            else None,
                                        )
                                        yield exported
                                    finally:
                                        withdraw()
                                        if exported is not None:
                                            tasks = (
                                                [exported._capture_task]
                                                if exported._capture_task is not None
                                                else []
                                            ) + [
                                                task
                                                for _digest, task in exported._check_tasks.values()
                                            ]
                                            if exported._review_task is not None:
                                                tasks.append(exported._review_task)
                                            if any(not task.done() for task in tasks):
                                                await exported.cancel()
                                            if tasks:
                                                await asyncio.gather(
                                                    *tasks, return_exceptions=True
                                                )
                        finally:
                            withdraw()
                            watcher.cancel()
                            await asyncio.gather(watcher, return_exceptions=True)
                            if material_tools is not None:
                                await material_tools.aclose()
                            if code_review:
                                # Retire physical work before waiting on host
                                # source/SQL work or retaining interruption data.
                                await owner.aclose()
                                if code_tools is not None:
                                    await code_tools.aclose()
                                if review_records is not None:
                                    retained = await _settled(
                                        review_records.get,
                                        lease.project_id,
                                        lease.attempt_id,
                                    )
                                    if retained["state"] in (
                                        "preparing",
                                        "ready",
                                        "proposed",
                                    ):
                                        await _settled(
                                            review_records.observe_failure,
                                            lease,
                                            "Review ownership ended before confirmation",
                                        )
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
