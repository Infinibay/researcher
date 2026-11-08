"""One local owner composes durable research, development and review with native inference.

No model loop lives here: one admitted request sends at most one native turn.
All native and MCP context managers enter/exit in the same worker task. HTTP
control withdraws live tool authority before waiting for SQLite or native I/O.
"""

import asyncio
import fcntl
import logging
import os
import stat
import time
from contextlib import ExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from backend.research.models import (
    CODE_REVIEW_PERMISSIONS,
    DEVELOPMENT_PERMISSIONS,
    PLANNING_PERMISSIONS,
    RESEARCH_PERMISSIONS,
    REVIEW_PERMISSIONS,
)
from backend.runtime.codex_session import ExecutionLimitExceeded, ExecutionLimits
from backend.runtime.contracts import (
    ProjectBudgetExhausted,
    RunConflict,
    RunNotFound,
    RunSpec,
    StaleAttempt,
    WorkspaceBinding,
    WorkspaceChanged,
    validate_correction,
)
from backend.runtime.failure_diagnostics import failure_sites as _failure_sites
from backend.runtime.peer_registry import AttemptPeers
from backend.runtime.recovery import RunRecovery
from backend.runtime.sqlite_questions import SQLiteQuestionStore
from backend.runtime.task_profiles import DEVELOPMENT_TASK_TYPES, DOCUMENTARY_TASK_TYPES
from backend.runtime.workspaces import WorkspaceRegistry

__all__ = ["RuntimeService", "WorkspaceRegistry"]

logger = logging.getLogger(__name__)


@dataclass
class _Worker:
    """Retain the local handles, live authority and requested outcome of one admitted run; this slot is
    not durable ownership proof.
    """
    spec: object
    workspace: Path
    binding: WorkspaceBinding
    active: bool = True
    grant_id: str | None = None
    attempt_id: str | None = None
    session: object = None
    task: asyncio.Task | None = None
    control: asyncio.Task | None = None
    outcome: str | None = None
    lease_deadline: float = 0
    intent_committed: asyncio.Event = field(default_factory=asyncio.Event)


class RuntimeService:
    """Own native attempts and grant-bound tool closure before durable terminal states."""

    def __init__(
        self,
        store,
        research,
        live_grants,
        runtime,
        *,
        workspaces,
        control_root,
        limits=None,
        max_concurrent=2,
        project_turn_limit=20,
        project_token_limit=4000000,
        legacy_active=None,
        storage_guard=None,
    ):
        """Compose one journal owner, native worker limits and deterministic authorized-plan dispatch; construction starts no work."""
        self.store = store
        self.research = research
        self.questions = SQLiteQuestionStore(store, research)
        self.recovery = RunRecovery(store)
        self.live_grants = live_grants
        self.runtime = runtime
        if legacy_active is not None and not callable(legacy_active):
            raise ValueError("Legacy activity must be an explicit controller observation port")
        self.legacy_active = legacy_active
        self.storage_guard = storage_guard
        self.workspaces = workspaces
        self.control_root = Path(control_root).absolute()
        self.limits = limits or ExecutionLimits(180, 90, 1, 25, 350000)
        if type(max_concurrent) is not int or not 1 <= max_concurrent <= 4:
            raise ValueError("Native concurrency must be between one and four")
        self.max_concurrent = max_concurrent
        self.project_turn_limit = project_turn_limit
        self.project_token_limit = project_token_limit
        self.owner_id = uuid4().hex
        self._lock_fd = None
        self._workers = {}
        self._recovery_jobs = {}
        self._closing = False
        self._admission_lock = asyncio.Lock()
        self._dispatch_lock = asyncio.Lock()
        self._dispatch_wake = asyncio.Event()
        self._dispatcher = None
        self._sources = None
        self._retention = None
        self._source_project_stops = {}

    @contextmanager
    def project_stop_scope(self, project_id, scope):
        """Withdraw exactly read-validated original local handles before the project Stop write; no cached later attempt can inherit this scope."""
        native = []
        for run in scope['runs']:
            slot = self._workers.get(run['run_id'])
            if slot is not None:
                if slot.spec.project_id != project_id or slot.spec.context_version != run['context_version'] or slot.attempt_id != run['attempt_id']:
                    raise RunConflict('El dueño nativo observado cambió; no se retiró otro intento.')
                native.append(slot)
        sources = scope.get('source_operations',[])
        if sources:
            for source in sources:
                self.sources.validate_stop_target(project_id,source['operation_key'],operation_id=source['operation_id'],fence=source['fence'])
        with ExitStack() as cleanup:
            for source in sources:
                cleanup.enter_context(self.sources.stop_scope(project_id,source['operation_key'],operation_id=source['operation_id'],fence=source['fence']))
            try:
                for slot in native:
                    slot.intent_committed.clear()
                    self._withdraw(slot, 'cancelled')
                yield
            finally:
                for slot in native:
                    slot.intent_committed.set()

    @asynccontextmanager
    async def _bodyless_project_stop_scope(self, project_id):
        """Withdraw current project owners before SQL and drain source handoffs under a temporary fuse; later explicit requests are never replayed by this Stop."""
        self._source_project_stops[project_id] = self._source_project_stops.get(project_id,0) + 1
        native = [slot for slot in self._workers.values() if slot.spec.project_id == project_id]
        try:
            for slot in native:
                slot.intent_committed.clear()
                self._withdraw(slot, 'cancelled')
            if self._sources is not None:
                self._sources.withdraw_project(project_id)
                await self._sources.drain_admission()
            yield
        finally:
            for slot in native:
                slot.intent_committed.set()
            remaining = self._source_project_stops[project_id] - 1
            if remaining:
                self._source_project_stops[project_id] = remaining
            else:
                del self._source_project_stops[project_id]

    @property
    def sources(self):
        """Lazily compose administrative source workers from actual owned runtime configuration; construction launches no Git or model work."""
        if self._sources is None:
            from backend.git.source_service import SourceService

            self._sources = SourceService(self)
        return self._sources

    @property
    def retention(self):
        """Compose explicit owner retention over actual authority and configured roots, without starting cleanup on read or startup."""
        if self._retention is None:
            from backend.runtime.retention_service import RetentionService
            self._retention=RetentionService(self)
        return self._retention

    def _acquire(self):
        # The canonical DB path, rather than a configurable control path, owns
        # the lock identity. O_CLOEXEC prevents a native child retaining it.
        """Exclusively lock the canonical business database for this serving owner and recover prior
        owner records; never let children inherit the lock.
        """
        path = Path(self.store.database).resolve()
        fd = os.open(
            str(path) + ".runtime-owner",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise RunConflict("Runtime owner lock must be private and user-owned")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RunConflict("Another runtime owner serves this database") from exc
            self.store.recover_owners(self.owner_id)
            return fd
        except BaseException:
            os.close(fd)
            raise

    async def __aenter__(self):
        """Acquire exclusive journal ownership and observe durable unissued plan work without replaying native attempts."""
        if self._lock_fd is not None:
            raise RunConflict("Runtime owner is already started")
        acquiring = asyncio.create_task(asyncio.to_thread(self._acquire))
        try:
            self._lock_fd = await asyncio.shield(acquiring)
        except BaseException:
            # to_thread keeps running after cancellation. Drain its ownership
            # result and close it rather than leaking a forever-held OS lock.
            try:
                fd = await acquiring
            except Exception:  # noqa: BLE001, S110 — original startup exception is re-raised below
                pass
            else:
                os.close(fd)
            raise
        self._closing = False
        self._dispatcher = asyncio.create_task(self._dispatch_loop(), name="researcher-plan-dispatch")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Drain admissions, native/source closure and original retention threads before releasing the journal owner lock."""
        self._closing = True
        source_closing = asyncio.create_task(self._sources.close(), name='researcher-source-shutdown') if self._sources is not None else None
        retention_closing = asyncio.create_task(self._retention.close(), name='researcher-retention-shutdown') if self._retention is not None else None
        try:
            self._dispatch_wake.set()
            if self._dispatcher is not None:
                await self._dispatcher
                self._dispatcher = None
            workers = list(self._workers.items())
            await asyncio.gather(
                *(self.stop(slot.spec.project_id, run_id) for run_id, slot in workers),
                return_exceptions=True,
            )
            tasks = [slot.task for _, slot in workers]
            if tasks:
                _done, pending = await asyncio.wait(tasks, timeout=10)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            recovery_tasks = [entry[1] for entry in self._recovery_jobs.values()]
            if recovery_tasks:
                await asyncio.gather(*recovery_tasks, return_exceptions=True)
        finally:
            try:
                if source_closing is not None:
                    try:
                        await asyncio.shield(source_closing)
                    except asyncio.CancelledError:
                        try:
                            await source_closing
                        finally:
                            raise
            finally:
                try:
                    if retention_closing is not None:
                        try:await asyncio.shield(retention_closing)
                        except asyncio.CancelledError:
                            try:await retention_closing
                            finally:raise
                finally:
                    if self._lock_fd is not None:
                        os.close(self._lock_fd)
                        self._lock_fd = None

    async def submit(
        self, spec, *, repository_id=None, conversation_thread=None, review=None, prior_code=None
    ):
        """Admit one original owner request, optionally retaining observed prior code as data or a separate finding-review target."""
        self._accepting()
        if spec.runtime != "codex":
            raise RunConflict(
                "This deployment admits only the Codex subscription adapter"
            )
        previous = await asyncio.to_thread(
            self.store.admission_receipt,
            spec,
            conversation_thread=conversation_thread,
            repository_id=repository_id,
            review=review,
            prior_code=prior_code,
        )
        if previous is not None:
            return previous  # Receipt lookup never retries a queued start.
        binding = await asyncio.to_thread(
            self.workspaces.bind, spec.project_id, repository_id
        )
        if self.control_root.resolve().is_relative_to(Path(binding.workspace)):
            raise RunConflict("Repository contains runtime control state")
        context = await asyncio.to_thread(
            self.store.context_snapshot, spec.project_id, spec.task_id
        )
        if context["task"]["type"] not in self.supported_task_types:
            raise RunConflict(
                "Configured runtime does not support this task type; no fallback is permitted"
            )
        if context["context_version"] != spec.context_version:
            raise RunConflict("Request uses an obsolete context version")
        run, admitted = await asyncio.to_thread(
            self.store.admit_once,
            spec,
            conversation_thread=conversation_thread,
            binding=binding,
            review=review,
            prior_code=prior_code,
        )
        return await self._schedule(run) if admitted else run

    def _accepting(self, *, new_work=True):
        """Require the live owner and optional storage headroom only for new work, never Stop."""
        if self._lock_fd is None or self._closing:
            raise RunConflict("Runtime owner is not accepting work")
        if new_work and self.storage_guard is not None:
            self.storage_guard()

    @property
    def supported_task_types(self):
        """Advertise only the configured adapter's supported authoring types; older adapters retain research-only admission."""
        return getattr(self.runtime, "supported_task_types", ("research",))

    async def review_code(self, spec, target):
        """Admit and schedule one owner-observed independent native code review without enabling authoring, acceptance or publication."""
        from backend.runtime.code_reviews import CodeReviews

        self._accepting()
        if spec.runtime != "codex":
            raise RunConflict(
                "This deployment admits only the Codex subscription adapter"
            )
        if "code" not in self.supported_task_types:
            raise RunConflict(
                "Configured runtime does not support isolated code review"
            )
        run, admitted = await asyncio.to_thread(
            CodeReviews(self.store).admit_once, spec, target
        )
        return await self._schedule(run) if admitted else run

    async def publish_code(self, project_id, author_run_id, intent):
        """Admit one explicit owner publication and schedule only its original fresh host attempt."""
        from backend.runtime.code_publications import CodePublications

        self._accepting()
        if not hasattr(self.runtime, "publish_code"):
            raise RunConflict(
                "Configured runtime does not support owned code publication"
            )
        run, admitted = await asyncio.to_thread(
            CodePublications(self.store).admit_once, project_id, author_run_id, intent
        )
        return await self._schedule(run) if admitted else run

    async def start_project_plan(
        self, project_id, *, operation_key=None, prompt=None, repository_id=None
    ):
        """Admit the original native planning task without legacy threads; a repeated start never replays its model turn."""
        from backend.planning.store import ProjectPlans

        self._accepting()
        if "plan" not in self.supported_task_types:
            raise RunConflict(
                "Configure the owned Codex planning runtime before starting this project"
            )
        plans = ProjectPlans(self.store)
        command = {
            "operation_key": operation_key,
            "prompt": prompt,
            "repository_id": repository_id,
        }
        original = await asyncio.to_thread(plans.prepare_start, project_id, **command)
        if original is None:
            binding = await asyncio.to_thread(
                self.workspaces.bind, project_id, repository_id
            )
            if self.control_root.resolve().is_relative_to(Path(binding.workspace)):
                raise RunConflict("Repository contains runtime control state")
            original = await asyncio.to_thread(
                plans.prepare_start, project_id, binding=binding, **command
            )
        spec, binding = original
        receipt = await asyncio.to_thread(
            self.store.admission_receipt,
            spec,
            repository_id=binding.requested_repository_id,
        )
        if receipt is not None:
            return receipt
        await asyncio.to_thread(self.workspaces.validate, project_id, binding)
        run, admitted = await asyncio.to_thread(
            self.store.admit_once, spec, binding=binding
        )
        return await self._schedule(run) if admitted else run

    async def stop_project(self, project_id):
        """Withdraw every active native run in this project; returned states preserve unconfirmed physical closure rather than claiming all work stopped."""

        async with self._bodyless_project_stop_scope(project_id):
            from backend.planning.execution import PlanExecutions

            await asyncio.to_thread(PlanExecutions(self.store).pause_project, project_id)

            from backend.git.source_operations import SourceOperations

            def source_history():
                """Observe administrative history even after this process restarted without reactivating or replaying its worker."""
                with self.store._transaction() as conn:
                    return SourceOperations.has_history(conn.execute('SELECT metadata_json FROM projects WHERE id=?',(project_id,)).fetchone()[0])

            if await asyncio.to_thread(source_history):
                await self.sources.stop_project(project_id)

            def pending():
                """Read durable original active run IDs without admitting or replaying work."""
                with self.store._transaction() as conn:
                    return [
                        r["id"]
                        for r in conn.execute(
                            "SELECT id FROM runtime_runs WHERE project_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')",
                            (project_id,),
                        )
                    ]

            ids = await asyncio.to_thread(pending)
            return [await self.stop(project_id, run_id) for run_id in ids]

    async def execute_plan(self, project_id, plan_run_id, **command):
        """Persist the exact owner execution authorization, then wake the single deterministic dispatcher without awaiting generation."""
        from backend.planning.execution import PlanExecutions

        self._accepting()
        receipt = await asyncio.to_thread(PlanExecutions(self.store).authorize, project_id, plan_run_id, **command)
        self._dispatch_wake.set()
        return receipt

    async def control_plan_execution(self, project_id, execution_id, **command):
        """Persist pause before withdrawing linked peers; resume wakes only still-unissued original deliveries."""
        from backend.planning.execution import PlanExecutions

        self._accepting(new_work=command.get('status') != 'paused')
        receipt = await asyncio.to_thread(PlanExecutions(self.store).control, project_id, execution_id, **command)
        if receipt["status"] == "paused":
            def linked():
                """Resolve exact original run IDs belonging to this execution, without widening Stop to other accepted plans."""
                with self.store._transaction() as conn:
                    return [r[0] for r in conn.execute("SELECT d.run_id FROM runtime_plan_deliveries d JOIN runtime_plan_executions e ON e.id=d.execution_id JOIN runtime_runs r ON r.id=d.run_id WHERE d.execution_id=? AND e.status='paused' AND r.project_id=? AND r.status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review')", (execution_id, project_id))]

            for run_id in await asyncio.to_thread(linked):
                await self.stop(project_id, run_id)
        self._dispatch_wake.set()
        return receipt

    async def _dispatch_loop(self):
        """Recheck durable owner-authorized readiness on wake or bounded polling; this loop performs no inference or chat-based decisions."""
        while not self._closing:
            self._dispatch_wake.clear()
            try:
                await self.dispatch_planned_work()
            except Exception as error:  # noqa: BLE001 -- retain durable work, never replay after an observation failure
                logger.error("Plan dispatch observation failed (%s)", type(error).__name__)
            if not self._closing:
                try:
                    await asyncio.wait_for(self._dispatch_wake.wait(), 1)
                except TimeoutError:
                    pass

    async def continue_plan_delivery(self, project_id, execution_id, delivery_id, **command):
        """Record exact owner authority for a closed delivery's successor, then wake the same dispatcher; no thread, prompt or budget is replayed."""
        from backend.planning.execution import PlanExecutions

        self._accepting()
        receipt = await asyncio.to_thread(PlanExecutions(self.store).continue_delivery, project_id, execution_id, delivery_id, **command)
        self._dispatch_wake.set()
        return receipt

    async def reauthorize_plan(self, project_id, execution_id, **command):
        """Persist the exact corrected owner graph and its closed history; leave dispatch paused until a distinct revision-bound resume."""
        from backend.planning.execution import PlanExecutions

        self._accepting()
        return await asyncio.to_thread(PlanExecutions(self.store).reauthorize, project_id, execution_id, **command)

    async def dispatch_planned_work(self):
        """Admit original ready deliveries and recover only queued runs with no attempt; quotas, closure and native reservation remain owned by the existing run worker."""
        from backend.planning.execution import PlanExecutions

        async with self._dispatch_lock:
            self._accepting()
            executions = PlanExecutions(self.store)
            for delivery in await asyncio.to_thread(executions.pending):
                if self._closing:
                    return
                if self._legacy_controller_active(delivery["project_id"]):
                    await asyncio.to_thread(executions.note_issue, delivery["execution_id"], delivery["task_id"], "legacy_owner_active")
                    continue
                if len(self._workers) >= self.max_concurrent or any(w.spec.project_id == delivery["project_id"] for w in self._workers.values()):
                    continue
                try:
                    prepared = await asyncio.to_thread(executions.prepare, delivery["execution_id"], delivery["task_id"])
                    if prepared is None:
                        continue
                    spec, binding = prepared
                    context = await asyncio.to_thread(self.store.context_snapshot, spec.project_id, spec.task_id)
                    if context["task"]["type"] not in self.supported_task_types:
                        raise RunConflict("Configured native adapter does not support this planned task type")
                    await asyncio.to_thread(self.workspaces.validate, spec.project_id, binding)
                    if self.control_root.resolve().is_relative_to(Path(binding.workspace)):
                        raise WorkspaceChanged("Repository contains runtime control state")
                    run, admitted = await asyncio.to_thread(self.store.admit_once, spec, binding=binding)
                    if admitted or (run.status == "queued" and run.attempt_id is None and (run.issue is None or run.issue.get("code") in ("capacity", "legacy_owner_active"))):
                        await self._schedule(run)
                except (RunConflict, RunNotFound, ValueError) as error:
                    await asyncio.to_thread(executions.note_issue, delivery["execution_id"], delivery["task_id"], type(error).__name__)

    async def preview_remote(self, project_id, local_run_id, target_ref, base_ref):
        """Query the configured adapter for a readonly destination observation; no run or write authority is admitted."""
        self._accepting()
        if getattr(
            self.runtime, "supports_remote_publication", False
        ) is not True or not hasattr(self.runtime, "preview_remote"):
            raise RunConflict(
                "Configured runtime has no owned remote observation transport"
            )
        return await self.runtime.preview_remote(
            self.store, project_id, local_run_id, target_ref, base_ref
        )

    async def publish_remote(self, project_id, request):
        """Admit one exact remote owner action only with a configured owned transport; scoped retry never creates another host effect."""
        from backend.runtime.remote_runtime import RemotePublications

        self._accepting()
        if (
            not hasattr(self.runtime, "publish_remote")
            or getattr(self.runtime, "supports_remote_publication", True) is not True
        ):
            raise RunConflict(
                "Configured runtime has no owned remote publication transport"
            )
        run, admitted = await asyncio.to_thread(
            RemotePublications(self.store).admit_once, project_id, request
        )
        return await self._schedule(run) if admitted else run

    async def reconcile_remote_publication(self, **command):
        """Recover original remote evidence with a new readonly owner; no configuration or request can turn recovery into another write."""
        if getattr(self.runtime, "supports_remote_publication", False) is not True:
            raise RunConflict(
                "Configured runtime has no owned remote observation transport"
            )
        return await self.reconcile_publication(remote=True, **command)

    async def reconcile_publication(self, *, remote=False, **command):
        """Recover one original publication by new readonly observation; an exact completed owner command returns without launching again."""
        from backend.runtime.publication_recovery import PublicationRecovery

        self._accepting()
        from backend.runtime.remote_recovery import RemoteRecovery

        recovery = (
            RemoteRecovery(self.store) if remote else PublicationRecovery(self.store)
        )
        receipt = await asyncio.to_thread(recovery.receipt, **command)
        if receipt is not None:
            return receipt
        key = (command["project_id"], command["run_id"], command["operation_key"])
        intent = recovery.intent(**command)
        existing = self._recovery_jobs.get(key)
        if existing is not None and not existing[1].done():
            if existing[0] != intent:
                raise RunConflict("Recovery key already identifies another request")
            return await asyncio.shield(existing[1])
        self._recovery_jobs = {
            key: entry
            for key, entry in self._recovery_jobs.items()
            if not entry[1].done()
        }
        if len(self._recovery_jobs) >= 128:
            raise RunConflict("Recovery control capacity reached")
        task = asyncio.create_task(
            self._observe_publication_once(command, remote=remote)
        )
        task.add_done_callback(
            lambda done: None if done.cancelled() else done.exception()
        )
        self._recovery_jobs[key] = (intent, task)
        return await asyncio.shield(task)

    async def _observe_publication_once(self, command, *, remote=False):
        """Retire original physical authority, own the fresh observer and save its result only after its separate domain closes."""
        from backend.runtime.publication_recovery import PublicationRecovery
        from backend.runtime.remote_recovery import RemoteRecovery

        recovery = (
            RemoteRecovery(self.store) if remote else PublicationRecovery(self.store)
        )
        slot = self._workers.get(command["run_id"])
        if slot is not None:
            self._withdraw(slot, "failed")
            await asyncio.shield(slot.task)
        close = "close_remote_publication" if remote else "close_publication"
        observe = "observe_remote_publication" if remote else "observe_publication"
        if not hasattr(self.runtime, close) or not hasattr(self.runtime, observe):
            raise RunConflict(
                "Configured runtime cannot perform owned readonly publication recovery"
            )
        proof = await asyncio.to_thread(
            getattr(self.runtime, close),
            self.store,
            command["project_id"],
            command["run_id"],
            command["attempt_id"],
        )
        async with self._admission_lock:
            self._accepting()
            if len(self._workers) >= self.max_concurrent or any(
                w.spec.project_id == command["project_id"]
                for w in self._workers.values()
            ):
                raise RunConflict(
                    "Host capacity occupied; retain this original recovery request"
                )
            lease, peers = await asyncio.to_thread(
                recovery.begin, **command, proof=proof, owner_id=self.owner_id
            )
            run = await asyncio.to_thread(
                self.store.get, lease.project_id, lease.run_id
            )
            binding = await asyncio.to_thread(
                self.store.workspace_binding, lease.project_id, lease.run_id
            )
            slot = _Worker(
                run,
                Path(binding.workspace),
                binding,
                attempt_id=lease.attempt_id,
                task=asyncio.current_task(),
            )
            slot.lease_deadline = time.monotonic() + 30
            slot.intent_committed.set()
            self._workers[lease.run_id] = slot
        heartbeat = asyncio.create_task(self._heartbeat(slot, lease))
        result = None
        try:
            result = await getattr(self.runtime, observe)(
                peers,
                active=lambda: slot.active and time.monotonic() < slot.lease_deadline,
            )
        finally:
            slot.active = False
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            try:
                await peers.aclose()
                closed = self.runtime.consume_closure(lease) is True and peers.closed()
                if result is None or not closed:
                    await asyncio.to_thread(
                        recovery.publications.interrupted,
                        lease,
                        physically_closed=closed,
                        reason="ObservationInterrupted",
                    )
            finally:
                self._workers.pop(lease.run_id, None)
        if not closed:
            raise RunConflict("Readonly observation physical closure remains uncertain")
        return await asyncio.to_thread(recovery.complete, lease, result[0], result[1])

    async def retry_start(self, **command):
        """Schedule only a newly recorded retry of the original queued request; an existing receipt
        returns its run without another scheduling decision.
        """
        self._accepting()
        run, requested = await asyncio.to_thread(self.store.request_start, **command)
        return await self._schedule(run) if requested else run

    def _legacy_controller_active(self, project_id):
        """Observe the serving controller before native work; unknown liveness holds the request, while standalone coordinators explicitly have no legacy-controller port."""
        if self.legacy_active is None:
            return False
        try:
            return self.legacy_active(project_id) is not False
        except Exception as error:  # noqa: BLE001 -- failed observation never grants native execution.
            logger.warning("Legacy closure observation failed for project %s (%s)", project_id, type(error).__name__)
            return True

    async def _schedule(self, run):
        """Schedule an admitted run once after checking its binding and execution profile."""
        async with self._admission_lock:
            self._accepting()
            run = await asyncio.to_thread(self.store.get, run.project_id, run.run_id)
            if run.status != "queued" or run.run_id in self._workers:
                return run
            if self._legacy_controller_active(run.project_id):
                return await self._note_issue(run, "legacy_owner_active", inference_started=False)
            binding = await asyncio.to_thread(
                self.store.workspace_binding, run.project_id, run.run_id
            )
            if binding is None:
                return await self._note_issue(
                    run, "binding_missing", inference_started=None
                )
            context = await asyncio.to_thread(
                self.store.context_snapshot, run.project_id, run.task_id
            )
            expected_types = (
                DEVELOPMENT_TASK_TYPES
                if run.execution_kind
                in (
                    "development",
                    "code_review",
                    "code_publication",
                    "remote_publication",
                )
                else (*DOCUMENTARY_TASK_TYPES, "plan")
            )
            if (
                context["task"]["type"] not in expected_types
                or context["task"]["type"] not in self.supported_task_types
            ):
                return await self._note_issue(run, "task_changed")
            try:
                workspace = await asyncio.to_thread(
                    self.workspaces.validate, run.project_id, binding
                )
                if self.control_root.resolve().is_relative_to(workspace):
                    raise WorkspaceChanged("Repository contains runtime control state")
            except WorkspaceChanged:
                return await self._note_issue(run, "workspace_changed")
            if len(self._workers) >= self.max_concurrent or any(
                w.spec.project_id == run.project_id for w in self._workers.values()
            ):
                return await self._note_issue(run, "capacity")
            spec = RunSpec(
                run.project_id,
                run.task_id,
                run.actor_id,
                run.context_version,
                run.operation_key,
                run.prompt,
                run.runtime,
            )
            # No await between this ownership check and publishing the worker.
            # Shutdown may have completed while validation ran in its thread.
            self._accepting()
            if self._legacy_controller_active(run.project_id):
                return await self._note_issue(run, "legacy_owner_active", inference_started=False)
            slot = _Worker(spec, workspace, binding)
            slot.intent_committed.set()
            self._workers[run.run_id] = slot
            slot.task = asyncio.create_task(
                self._execute_publication(run.run_id, slot)
                if run.execution_kind in ("code_publication", "remote_publication")
                else self._execute(run.run_id, slot),
                name="researcher-run-" + run.run_id,
            )
            return run

    async def _execute_publication(self, run_id, slot):
        """Own one typed host publication without inference and retain unknown effects until its actual local transports close."""
        from backend.runtime.code_publications import CodePublications
        from backend.runtime.remote_runtime import RemotePublications

        publications = CodePublications(self.store)
        lease = peers = heartbeat = result = None
        reason = "PublicationInterrupted"
        try:
            if self.storage_guard is not None:
                await asyncio.to_thread(self.storage_guard)
            run = await asyncio.to_thread(self.store.get, slot.spec.project_id, run_id)
            remote = run.execution_kind == "remote_publication"
            publications = RemotePublications(self.store) if remote else publications
            lease, peers = await asyncio.to_thread(
                AttemptPeers.claim,
                self.store,
                slot.spec.project_id,
                run_id,
                self.owner_id,
            )
            slot.attempt_id = lease.attempt_id
            slot.lease_deadline = time.monotonic() + 30
            heartbeat = asyncio.create_task(self._heartbeat(slot, lease))
            publish = (
                self.runtime.publish_remote if remote else self.runtime.publish_code
            )
            result = await publish(
                peers,
                active=lambda: slot.active and time.monotonic() < slot.lease_deadline,
            )
        except (Exception, asyncio.CancelledError) as error:  # noqa: BLE001 -- host boundary retains partial work and redacts exception details.
            reason = type(error).__name__
            logger.warning("Host publication retained for inspection (%s)", reason)
        finally:
            slot.active = False
            if heartbeat is not None:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            await slot.intent_committed.wait()
            try:
                if peers is not None:
                    await peers.aclose()
                if lease is not None:
                    closed = (
                        self.runtime.consume_closure(lease) is True and peers.closed()
                    )
                    if result is not None and closed:
                        await asyncio.to_thread(
                            publications.complete, lease, result[0], result[1]
                        )
                    else:
                        await asyncio.to_thread(
                            publications.interrupted,
                            lease,
                            physically_closed=closed,
                            reason=reason,
                        )
            except Exception as error:  # noqa: BLE001 -- preserve reconciliation rather than replacing uncertain effects.
                logger.error(
                    "Publication requires reconciliation (%s)", type(error).__name__
                )
            finally:
                self._workers.pop(run_id, None)

    async def _note_issue(self, run, code, *, attempt_id=None, inference_started=False, closure_confirmed=False, limit=None, resources=None, project_budget=None):
        """Persist a safe, actionable owner explanation for this original run."""
        messages = {
            "legacy_owner_active": (
                "El inicio está en espera: no pudimos comprobar que el proyecto esté libre de una ejecución anterior. La solicitud nueva está guardada y no se ha iniciado. Detén cualquier ejecución anterior y vuelve a intentar.",
                "retry_start",
            ),
            "binding_missing": (
                "Esta solicitud antigua no registró su repositorio. Cancélala y crea otra con una selección comprobable.",
                "new_request",
            ),
            "workspace_changed": (
                "El repositorio o la carpeta admitidos cambiaron o no están disponibles. No elegiremos otra carpeta por nuestra cuenta. Restaura la selección original o cancela y crea otra solicitud.",
                "restore_or_new_request",
            ),
            "capacity": (
                "La solicitud está guardada, pero otra ejecución ocupa la capacidad disponible. Puedes volver a intentar su inicio cuando termine.",
                "retry_start",
            ),
            "preparation_failed": (
                "No se pudo preparar el intento. La solicitud sigue guardada y no se inició inferencia. Puedes volver a intentar el inicio o detenerla.",
                "retry_start",
            ),
            "runtime_failed": (
                "No se pudo confirmar el cierre de la ejecución. Conservamos el trabajo y los recibos guardados; revisa qué quedó completo y qué falta. No se repetirá por su cuenta.",
                "inspect_saved_work",
            ),
            "execution_limit": (
                "La ejecución se detuvo al alcanzar un límite. Conservamos el trabajo y los recibos guardados: un borrador puede existir aunque falte la entrega o la explicación final. Revisa la tarea y sus artefactos antes de decidir cómo continuar; este intento no se repetirá por su cuenta.",
                "inspect_saved_work",
            ),
            "project_budget_exhausted": (
                "El presupuesto acumulado del proyecto no permite iniciar esta solicitud. Revisa el presupuesto y sus intentos anteriores antes de continuar; no se repetirá por su cuenta.",
                "inspect_project_budget",
            ),
            "resource_exhaustion": (
                "El sistema registró agotamiento de recursos durante este intento. Conservamos el trabajo y los recibos guardados; revisa los resultados y el límite configurado antes de decidir cómo continuar. No se repetirá automáticamente.",
                "inspect_saved_work",
            ),
            "code_review_unconfirmed": (
                "El revisor terminó su turno, pero no pudimos confirmar la revisión sobre el código observado. Conservamos la propuesta y su evidencia; revisa ese resultado antes de continuar.",
                "inspect_saved_work",
            ),
            "code_candidate_unconfirmed": (
                "El turno terminó, pero no se completó la captura del candidato o sus comprobaciones. Conservamos la evidencia disponible; no se aceptó ni publicó código. Revisa el resultado antes de continuar.",
                "inspect_saved_work",
            ),
            "native_search_unavailable": (
                "El proveedor configurado no admite búsqueda web nativa. No se inició inferencia ni se cambió de proveedor. Revisa la configuración del runtime y las capacidades de la cuenta antes de crear otra solicitud.",
                "review_runtime_configuration",
            ),
            "native_model_unavailable": (
                "El modelo o esfuerzo elegido no está disponible en el catálogo de Codex de esta cuenta. No se envió un turno ni se eligió otro modelo. Revisa la configuración; la solicitud y la elección original se conservan.",
                "review_runtime_configuration",
            ),
            "task_changed": (
                "La tarea cambió a un tipo que este motor todavía no puede ejecutar. La solicitud sigue guardada; revisa la tarea antes de continuar.",
                "inspect_saved_work",
            ),
            "input_too_large": (
                "La tarea o su conversación superan el límite de entrada. No se recortaron instrucciones ni se inició inferencia. Revisa el tamaño del contexto o crea otra tarea/conversación con las condiciones que quieras conservar.",
                "review_context_or_new_conversation",
            ),
        }
        message, action = messages[code]
        details = {}
        if code == "runtime_failed":
            details["closure_confirmed"] = closure_confirmed
            if closure_confirmed:
                if inference_started is False:
                    message = "No se pudo completar la preparación. No se inició inferencia y se comprobó el cierre de los procesos."
                else:
                    message = "La ejecución falló y se comprobó el cierre de sus procesos."
                    if inference_started is None:
                        message += " No se pudo confirmar si se inició inferencia."
                message += " Conservamos el trabajo y los recibos guardados; revisa el intento y su presupuesto antes de continuar. No se repetirá por su cuenta."
        if project_budget is not None:
            message = (
                "No se inició un turno nuevo: el proyecto tiene "
                f"{project_budget['used_turns']} de {project_budget['turn_limit']} solicitudes reservadas y "
                f"{project_budget['accounted_tokens']} de {project_budget['token_limit']} tokens contabilizados; "
                f"esta solicitud necesita reservar {project_budget['requested_tokens']} tokens. "
                "Revisa el presupuesto del proyecto y sus intentos anteriores antes de continuar. "
                "Las mediciones ausentes conservan su reserva; esto no indica la cuota restante de la suscripción."
            )
            details['project_budget'] = project_budget
        if code == "resource_exhaustion" and resources is not None:
            observation = (
                "procesos terminados por falta de memoria"
                if resources.get("memory_oom_kills", 0) > 0
                else "creación de procesos rechazada por alcanzar el límite compartido"
            )
            message = message.replace("agotamiento de recursos", observation)
            details["resource_observation"] = resources
        if limit is not None:
            labels = {"tools": "herramientas", "tokens": "tokens observados",
                      "wall": "tiempo total", "progress": "tiempo sin progreso observable",
                      "output": "tamaño de respuesta", "turns": "turnos"}
            label = labels.get(limit.kind, "recursos")
            message = message.replace("un límite.", f"el límite de {label}.")
            details = {"limit_kind": limit.kind, "execution_budget": limit.budget}
        return await asyncio.to_thread(
            self.store.record_issue,
            run.project_id,
            run.run_id,
            {
                "code": code,
                "message": message,
                "next_action": action,
                "inference_started": inference_started,
                **details,
            },
            attempt_id=attempt_id,
        )

    async def wait(self, run_id):
        """Wait for this owner's existing worker without propagating observer cancellation into it; an
        absent local slot does not prove durable completion.
        """
        slot = self._workers.get(run_id)
        if slot is not None:
            await asyncio.shield(slot.task)

    def _end_tool_authority(self, slot):
        """Immediately disable the local slot and withdraw its live grant before potentially blocking
        persistence or native teardown.
        """
        slot.active = False
        if slot.grant_id:
            self.live_grants.withdraw(slot.grant_id)

    @asynccontextmanager
    async def _tool_authority(self, slot):
        """Ensure live tool authority ends on every exit from the worker scope, including errors and
        deadline cancellation.
        """
        try:
            yield
        finally:
            # End authority before native/MCP teardown can block, including
            # errors and deadline fuses with an HTTP tool still in flight.
            self._end_tool_authority(slot)

    def _withdraw(self, slot, outcome):
        """Retire local tool authority, retain the requested outcome and request one native
        interruption; durable state is recorded separately.
        """
        self._end_tool_authority(slot)
        slot.outcome = outcome
        if slot.session is not None and slot.control is None:
            slot.control = asyncio.create_task(self._interrupt(slot.session))

    @staticmethod
    async def _interrupt(session):
        """Request native cancellation while recording an unavailable receipt by exception type;
        failure to receive a reply is not proof of closure.
        """
        try:
            await session.cancel()
        except Exception as exc:  # noqa: BLE001 — native/AnyIO boundary; redact exception details
            logger.warning(
                "Native interruption receipt unavailable (%s)", type(exc).__name__
            )

    async def stop(self, project_id, run_id):
        """Withdraw the observed local worker before recording cancellation and release its persistence
        gate afterward; no native completion is invented.
        """
        slot = self._workers.get(run_id)
        if slot is not None:
            if slot.spec.project_id != project_id:
                raise RunNotFound("Run not found in this project")
            slot.intent_committed.clear()
            self._withdraw(slot, "cancelled")
        try:
            return await asyncio.to_thread(self.store.cancel, project_id, run_id)
        finally:
            if slot is not None:
                slot.intent_committed.set()

    def question_requested(self, run_id, attempt_id):
        """Retire the exact local peer after the question transaction commits.

        The journal already denies tools. A missing/stale worker cannot be
        declared paused; only its owning finalizer can confirm both closures.
        """
        slot = self._workers.get(run_id)
        if slot is not None and slot.attempt_id == attempt_id:
            self._withdraw(slot, slot.outcome)

    def task_inputs_changed(self, project_id, task_id):
        """Post-commit local notice; durable fencing also covers other writers."""
        for slot in self._workers.values():
            if (slot.spec.project_id, slot.spec.task_id) == (project_id, task_id):
                self._withdraw(slot, "superseded")

    async def reconcile(self, **command):
        """Share one shielded recovery task per exact intent and operation key, rejecting conflicting
        reuse and bounding outstanding local recovery work.
        """
        if self._lock_fd is None or self._closing:
            raise RunConflict("Runtime owner is not accepting recovery controls")
        intent = self.recovery._intent(**command)
        key = (command["project_id"], command["run_id"], command["operation_key"])
        self._recovery_jobs = {
            key: entry
            for key, entry in self._recovery_jobs.items()
            if not entry[1].done()
        }
        existing = self._recovery_jobs.get(key)
        if existing is not None:
            if existing[0] != intent:
                raise RunConflict("Recovery key already identifies another intent")
            return await asyncio.shield(existing[1])
        if len(self._recovery_jobs) >= 128:
            raise RunConflict(
                "Recovery control capacity reached; inspect existing work"
            )
        task = asyncio.create_task(self._reconcile_once(command))
        task.add_done_callback(
            lambda done: None if done.cancelled() else done.exception()
        )
        self._recovery_jobs[key] = (intent, task)
        return await asyncio.shield(task)

    async def _reconcile_once(self, command):
        """Close original peers, tools and witnessed domain before recovery without replay, including rechecks of older local-only receipts."""
        work = await asyncio.to_thread(self.recovery.preflight, **command)
        if work["completed"] is not None:
            await self._close_recovered_domain(command)
            return work["completed"]
        slot = self._workers.get(command["run_id"])
        if slot is not None and slot.attempt_id == command["attempt_id"]:
            self._withdraw(slot, slot.outcome)
        for grant_id in work["tool_grant_ids"]:
            self.live_grants.withdraw(grant_id)
        results = await asyncio.gather(
            asyncio.to_thread(self.recovery.begin, **command),
            *(
                asyncio.to_thread(self.live_grants.wait_closed, grant_id)
                for grant_id in work["tool_grant_ids"]
            ),
            *(
                asyncio.to_thread(self.recovery.peers.close, peer)
                for peer in work["peers"]
            ),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, TimeoutError):
                raise RunConflict(
                    "Host tool closure is unconfirmed; reconcile the original operation again"
                ) from result
            if isinstance(result, BaseException):
                raise result
        if slot is not None and slot.attempt_id == command["attempt_id"] and slot.task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(slot.task), timeout=10)
            except TimeoutError as error:
                raise RunConflict("Original runtime finalizer has not released its domain") from error
        await self._close_recovered_domain(command)
        return await asyncio.to_thread(self.recovery.complete, **command)

    async def _close_recovered_domain(self, command):
        """Use the owning runtime's closure boundary; non-owned test/runtime adapters retain their local protocol."""
        close = getattr(self.runtime, "close_attempt", None)
        if close is not None:
            await asyncio.to_thread(
                close, self.store, command["project_id"], command["run_id"], command["attempt_id"]
            )

    async def correct(self, **command):
        """Record a versioned owner correction and interrupt only still-authorized work.

        Retired workers retain closure ownership, but their original context must
        not reject a later correction while they finish closing. SQLite validates
        the current version; the finalizer derives its outcome from that state.
        """
        validate_correction(**command)
        receipt = await asyncio.to_thread(self.store.correction_receipt, **command)
        if receipt is not None:
            return receipt
        affected = [
            slot
            for slot in self._workers.values()
            if slot.active and (slot.spec.project_id, slot.spec.task_id)
            == (command["project_id"], command["task_id"])
        ]
        for slot in affected:
            if slot.spec.context_version != command["expected_version"]:
                raise RunConflict("Correction refers to an obsolete context version")
        for slot in affected:
            slot.intent_committed.clear()
            self._withdraw(slot, "superseded")
        try:
            return await asyncio.to_thread(self.store.correct_context, **command)
        finally:
            for slot in affected:
                slot.intent_committed.set()

    async def _heartbeat(self, slot, lease):
        """Renew live authority or retire it, distinguishing a committed delivery fence from an unexpected lease loss."""
        while slot.active:
            await asyncio.sleep(5)
            if not slot.active:
                return
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self.store.heartbeat, lease),
                    timeout=max(0.01, slot.lease_deadline - time.monotonic()),
                )
                slot.lease_deadline = time.monotonic() + 30
            except Exception:  # noqa: BLE001 — fail closed on loss of lease renewal
                from backend.planning.store import ProjectPlans

                try:
                    delivered = await asyncio.to_thread(ProjectPlans(self.store).delivery_requested, lease)
                except Exception:  # noqa: BLE001 -- an unreadable receipt cannot excuse lease loss
                    delivered = False
                self._withdraw(slot, slot.outcome if delivered else "failed")
                return

    async def _execute(self, run_id, slot):
        """Own one admitted native turn, then prove peer/tool closure before finalizing it."""
        from backend.planning.store import ProjectPlans

        lease = heartbeat = token = result = peers = None
        error_type = None
        execution_limit = None
        project_budget = None
        resource_observation = None
        closure_confirmed = False
        runtime_opened = False
        dispatch_reserved = native_started = False
        code_review = review_confirmed = False
        development = development_complete = False
        try:
            if self.storage_guard is not None:
                await asyncio.to_thread(self.storage_guard)
            current_run = await asyncio.to_thread(
                self.store.get, slot.spec.project_id, run_id
            )
            code_review = current_run.execution_kind == "code_review"
            development = current_run.execution_kind == "development"
            expected_types = (
                DEVELOPMENT_TASK_TYPES
                if code_review or development
                else DOCUMENTARY_TASK_TYPES
                if current_run.execution_kind == "finding_review"
                else (*DOCUMENTARY_TASK_TYPES, "plan")
            )
            context = await asyncio.to_thread(
                self.store.context_snapshot, slot.spec.project_id, slot.spec.task_id
            )
            if context["task"]["type"] not in expected_types:
                raise RunConflict("Task type changed before native startup")
            await asyncio.to_thread(
                self.workspaces.validate, slot.spec.project_id, slot.binding
            )
            lease, peers = await asyncio.to_thread(
                AttemptPeers.claim,
                self.store,
                slot.spec.project_id,
                run_id,
                self.owner_id,
            )
            slot.attempt_id = lease.attempt_id
            slot.lease_deadline = time.monotonic() + 30
            heartbeat = asyncio.create_task(self._heartbeat(slot, lease))
            review = await asyncio.to_thread(
                self.store.review_request,
                lease.project_id,
                lease.run_id,
                require_current=True,
            )
            if not await asyncio.to_thread(
                self.store.reserve_preparation, lease, limits=self.limits,
                project_turn_limit=self.project_turn_limit,
                project_token_limit=self.project_token_limit,
            ):
                raise RunConflict("Preparation was already reserved; reconcile without replay")
            token = await asyncio.to_thread(
                self.research.issue_grant,
                project_id=lease.project_id,
                task_id=lease.task_id,
                agent_id=lease.actor_id,
                permissions=set(
                    CODE_REVIEW_PERMISSIONS
                    if code_review
                    else DEVELOPMENT_PERMISSIONS
                    if development
                    else REVIEW_PERMISSIONS
                    if review is not None
                    else PLANNING_PERMISSIONS
                    if context["task"]["type"] == "plan"
                    else RESEARCH_PERMISSIONS
                ),
                ttl_seconds=min(3600, self.limits.wall_seconds + 180),
            )
            scope = await asyncio.to_thread(self.research.authorize, token)
            slot.grant_id = scope.grant_id
            await asyncio.to_thread(self.store.bind_grant, lease, scope.grant_id)
            if slot.active:
                self.live_grants.activate(scope.grant_id)
            active = lambda: slot.active and time.monotonic() < slot.lease_deadline
            # Startup has its own deadline; it cannot consume an unbounded lease
            # while waiting for MCP assets/configuration before a native turn.
            async with asyncio.timeout(self.limits.wall_seconds + 120):
                runtime_opened = True
                async with (
                    self.runtime.open(
                        workspace=slot.workspace,
                        tool_token=token,
                        active=active,
                        limits=self.limits,
                        peer_owner=peers,
                    ) as session,
                    self._tool_authority(slot),
                ):
                    slot.session = session
                    if not active():
                        return
                    await asyncio.to_thread(
                        self.store.bind_thread, lease, thread_id=session.thread_id
                    )
                    context = await asyncio.to_thread(
                        self.store.context_snapshot, lease.project_id, lease.task_id
                    )
                    if context["context_version"] != lease.context_version:
                        raise StaleAttempt("Context changed before native dispatch")
                    if context["task"]["type"] not in expected_types:
                        raise RunConflict("Task type changed before native dispatch")
                    await asyncio.to_thread(
                        self.workspaces.validate, slot.spec.project_id, slot.binding
                    )
                    frozen = await asyncio.to_thread(
                        self.store.reserve_input,
                        lease,
                        workspace=str(
                            getattr(session, "execution_workspace", None)
                            or slot.workspace
                        ),
                        catalog_hash=session.catalog_hash,
                        model=session.model,
                        developer_instructions=session.developer_instructions,
                        catalog=session.catalog,
                        limits=self.limits,
                        project_turn_limit=self.project_turn_limit,
                        project_token_limit=self.project_token_limit,
                    )
                    dispatch_reserved = True
                    if frozen is None:
                        raise RunConflict(
                            "Native dispatch was already reserved; reconcile without replay"
                        )
                    if not active():
                        return

                    async def on_started(thread_id, turn_id):
                        """Retain the observed native-start flag and bind the reported thread and turn
                        to the original attempt lease without granting new authority.
                        """
                        nonlocal native_started
                        native_started = True
                        await asyncio.to_thread(
                            self.store.bind_native,
                            lease,
                            thread_id=thread_id,
                            turn_id=turn_id,
                        )

                    async def on_event(event):
                        """Retain bounded original-turn facts without granting effect authority."""
                        method, params = event.get("method"), event.get("params", {})
                        if method == "thread/tokenUsage/updated":
                            await asyncio.to_thread(
                                self.store.note_inference_usage,
                                lease,
                                params["tokenUsage"]["total"]["totalTokens"],
                            )
                            return
                        item = params.get("item", {})
                        if method not in ("item/started", "item/completed") or item.get(
                            "type"
                        ) not in ("mcpToolCall", "dynamicToolCall", "webSearch"):
                            return
                        stage = "started" if method == "item/started" else "completed"
                        payload = {
                            "thread_id": session.thread_id,
                            "item_id": item["id"],
                            "type": item["type"],
                        }
                        if item["type"] == "webSearch":
                            from backend.runtime.native_search import search_observation

                            payload = search_observation(
                                item,
                                mode=getattr(session, "web_search", "disabled"),
                                thread_id=session.thread_id,
                                turn_id=params.get("turnId"),
                            )
                        await asyncio.to_thread(
                            self.store.observe_native,
                            lease,
                            observation_key="tool-" + stage + "-" + item["id"],
                            native_kind="tool." + stage,
                            payload=payload,
                        )

                    result = await session.run(
                        frozen.input_text,
                        on_started=on_started,
                        on_event=on_event,
                    )
                    if development and result.status == "completed":
                        candidate = await session.capture_candidate()
                        if candidate["state"] != "ready":
                            raise RunConflict(
                                "Completed development has no ready exact candidate"
                            )
                        for index, recipe in enumerate(self.runtime.development_checks):
                            await session.run_check(
                                f"host-check-{index + 1}-{recipe.sha256}", recipe
                            )
                        development_complete = True
                    if code_review and result.status == "completed":
                        await session.complete_review()
                        review_confirmed = True
        except asyncio.CancelledError:
            error_type = "WorkerInterrupted"
        except Exception as exc:  # noqa: BLE001 — native/AnyIO boundary; redact exception details
            error_type = type(exc).__name__
            if isinstance(exc, ExecutionLimitExceeded):
                execution_limit = exc
            if isinstance(exc, ProjectBudgetExhausted):
                project_budget = exc.budget
            logger.warning("Research run stopped (%s; locations=%s)", error_type, _failure_sites(exc))
        finally:
            # Both peers have exited their owning worker scope before any final
            # retirement assertion. The grant gate closes even if SQL is busy.
            self._end_tool_authority(slot)
            tools_closed = True
            if slot.grant_id:
                try:
                    await asyncio.to_thread(self.live_grants.wait_closed, slot.grant_id)
                except TimeoutError:
                    tools_closed = False
                    error_type = "ToolWorkerClosureUnconfirmed"
                    logger.warning("Host tool worker closure needs reconciliation")
            if heartbeat is not None:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            if slot.control is not None:
                await slot.control
            await slot.intent_committed.wait()
            try:
                if slot.grant_id:
                    await asyncio.to_thread(self.research.revoke_grant, slot.grant_id)
                peers_closed = False
                if peers is not None:
                    try:
                        await peers.aclose()
                        peers_closed = await asyncio.to_thread(peers.closed)
                    except Exception as exc:  # noqa: BLE001 — retain uncertainty after kernel/DB failure
                        error_type = type(exc).__name__
                        logger.warning(
                            "Peer closure needs reconciliation (%s)", error_type
                        )
                if lease is not None:
                    if result is not None:
                        await asyncio.to_thread(
                            self.store.settle_inference,
                            lease,
                            observed_tokens=result.observed_tokens,
                            native_status=result.status,
                        )
                        await asyncio.to_thread(
                            self.store.observe_native,
                            lease,
                            observation_key="terminal",
                            native_kind="turn." + result.status,
                            payload={
                                "thread_id": result.thread_id,
                                "turn_id": result.turn_id,
                                "status": result.status,
                            },
                        )
                    runtime_closed = not runtime_opened or getattr(slot.session, "peers_closed", False)
                    consume_closure = getattr(self.runtime, "consume_closure", None)
                    consume_resources = getattr(self.runtime, "consume_resources", None)
                    if consume_resources is not None:
                        resource_observation = consume_resources(lease)
                    if consume_closure is not None:
                        runtime_closed = (
                            consume_closure(lease) is True or runtime_closed
                        )
                    closure_confirmed = peers_closed and runtime_closed and tools_closed
                    if not closure_confirmed:
                        await asyncio.to_thread(
                            self.store.uncertain_inference,
                            lease,
                            reason=error_type or "PeerClosureUnconfirmed",
                            native_result={
                                "native_status": result.status,
                                "summary": result.text.strip()
                                or "No hay explicación del runtime.",
                            }
                            if result
                            else None,
                        )
                    elif (
                        await asyncio.to_thread(self.questions.park, lease) is not None
                    ):
                        # Question state derives from durable Stop/context intent
                        # after actual peer closure, regardless of callback order.
                        pass
                    elif (
                        await asyncio.to_thread(self.store.retire_withdrawn, lease)
                        is not None
                    ):
                        # Direct SQL/legacy edits can invalidate inputs without a
                        # local callback. Derive outcome after closure, even when
                        # native completion wins the race with heartbeat polling.
                        pass
                    elif slot.outcome is not None:
                        await asyncio.to_thread(
                            self.store.retire_inference, lease, outcome=slot.outcome
                        )
                    elif await asyncio.to_thread(ProjectPlans(self.store).delivery_requested, lease):
                        if result is not None and error_type is None and result.status in ("completed", "interrupted"):
                            await asyncio.to_thread(ProjectPlans(self.store).finish_delivery, lease, native_status=result.status)
                        else:
                            # A saved artifact survives failure, but cannot hide
                            # a fuse, absent terminal observation or native error.
                            await asyncio.to_thread(self.store.retire_inference, lease, outcome="failed")
                    elif (
                        (
                            (code_review and not review_confirmed)
                            or (development and not development_complete)
                        )
                        and result is not None
                        and result.status == "completed"
                    ):
                        await asyncio.to_thread(
                            self.store.retire_inference, lease, outcome="failed"
                        )
                    elif result is not None:
                        await asyncio.to_thread(
                            self.store.finish,
                            lease,
                            native_status=result.status,
                            summary=result.text.strip()
                            or "El runtime terminó sin una explicación; falta revisar el resultado.",
                        )
                        if result.status != "completed":
                            # All registered peers, including host analysis jobs,
                            # are closed and grants revoked. Missing command exit
                            # receipts remain unknown; closure never invents them.
                            await asyncio.to_thread(
                                self.store.retire_inference, lease, outcome="failed"
                            )
                    else:
                        await asyncio.to_thread(
                            self.store.retire_inference, lease, outcome="failed"
                        )
                        logger.warning(
                            "Research run has no proposal (%s)",
                            error_type or "no_dispatch",
                        )
            except Exception as exc:  # noqa: BLE001 — native/AnyIO boundary; redact exception details
                # Keep durable uncertainty; never replay to repair an error.
                logger.error("Run requires reconciliation (%s)", type(exc).__name__)
            finally:
                try:
                    current = await asyncio.to_thread(
                        self.store.get, slot.spec.project_id, run_id
                    )
                    if (
                        resource_observation is not None
                        and resource_observation.get("observed") is True
                        and (resource_observation.get("memory_oom_kills", 0) > 0 or resource_observation.get("pids_denied", 0) > 0)
                        and current.status in ("failed", "reconciling")
                    ):
                        await self._note_issue(
                            current, "resource_exhaustion", attempt_id=lease.attempt_id,
                            inference_started=True if native_started else None if dispatch_reserved else False,
                            resources=resource_observation,
                        )
                    elif (
                        (
                            (code_review and not review_confirmed)
                            or (development and not development_complete)
                        )
                        and result is not None
                        and result.status == "completed"
                        and error_type is not None
                    ):
                        await self._note_issue(
                            current,
                            "code_review_unconfirmed"
                            if code_review
                            else "code_candidate_unconfirmed",
                            attempt_id=lease.attempt_id,
                            inference_started=True,
                        )
                    elif result is None and error_type is not None:
                        code = (
                            "project_budget_exhausted"
                            if project_budget is not None
                            else "execution_limit"
                            if execution_limit is not None
                            else "native_search_unavailable"
                            if error_type == "NativeSearchUnavailable"
                            else "native_model_unavailable"
                            if error_type == "ModelUnavailable"
                            else "input_too_large"
                            if error_type == "InputTooLarge"
                            else "workspace_changed"
                            if error_type == "WorkspaceChanged"
                            else "preparation_failed"
                            if lease is None
                            else "runtime_failed"
                        )
                        await self._note_issue(
                            current,
                            code,
                            attempt_id=lease.attempt_id if lease else None,
                            inference_started=True
                            if native_started
                            else None
                            if dispatch_reserved
                            else False,
                            closure_confirmed=closure_confirmed,
                            limit=execution_limit,
                            project_budget=project_budget,
                        )
                except Exception as exc:  # noqa: BLE001 -- keep the original failure if its observation cannot commit
                    logger.error(
                        "Run issue could not be recorded (%s)", type(exc).__name__
                    )
                self._workers.pop(run_id, None)
