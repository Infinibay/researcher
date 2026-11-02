"""One local owner composes durable research runs with a native inference adapter.

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
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from backend.research.models import PERMISSIONS
from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    RunSpec,
    StaleAttempt,
    WorkspaceBinding,
    WorkspaceChanged,
    validate_correction,
)
from backend.runtime.peer_registry import AttemptPeers
from backend.runtime.recovery import RunRecovery
from backend.runtime.sqlite_questions import SQLiteQuestionStore
from backend.runtime.workspaces import WorkspaceRegistry

__all__ = ["RuntimeService", "WorkspaceRegistry"]

logger = logging.getLogger(__name__)


@dataclass
class _Worker:
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
    ):
        self.store = store
        self.research = research
        self.questions = SQLiteQuestionStore(store, research)
        self.recovery = RunRecovery(store)
        self.live_grants = live_grants
        self.runtime = runtime
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

    def _acquire(self):
        # The canonical DB path, rather than a configurable control path, owns
        # the lock identity. O_CLOEXEC prevents a native child retaining it.
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
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._closing = True
        try:
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
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None

    async def submit(self, spec, *, repository_id=None, conversation_thread=None):
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
        if context["task"]["type"] != "research":
            raise RunConflict(
                "Development capabilities are still being migrated; select a research task"
            )
        if context["context_version"] != spec.context_version:
            raise RunConflict("Request uses an obsolete context version")
        run, admitted = await asyncio.to_thread(
            self.store.admit_once,
            spec,
            conversation_thread=conversation_thread,
            binding=binding,
        )
        return await self._schedule(run) if admitted else run

    def _accepting(self):
        if self._lock_fd is None or self._closing:
            raise RunConflict("Runtime owner is not accepting work")

    async def retry_start(self, **command):
        self._accepting()
        run, requested = await asyncio.to_thread(self.store.request_start, **command)
        return await self._schedule(run) if requested else run

    async def _schedule(self, run):
        async with self._admission_lock:
            self._accepting()
            run = await asyncio.to_thread(self.store.get, run.project_id, run.run_id)
            if run.status != "queued" or run.run_id in self._workers:
                return run
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
            if context["task"]["type"] != "research":
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
            slot = _Worker(spec, workspace, binding)
            slot.intent_committed.set()
            self._workers[run.run_id] = slot
            slot.task = asyncio.create_task(
                self._execute(run.run_id, slot), name="researcher-run-" + run.run_id
            )
            return run

    async def _note_issue(self, run, code, *, attempt_id=None, inference_started=False):
        """Persist a safe, actionable owner explanation for this original run."""
        messages = {
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
                "La ejecución no dejó una propuesta verificable. Conservamos los datos y recibos guardados; no se repetirá por su cuenta.",
                "inspect_saved_work",
            ),
            "native_search_unavailable": (
                "El proveedor configurado no admite búsqueda web nativa. No se inició inferencia ni se cambió de proveedor. Revisa la configuración del runtime y las capacidades de la cuenta antes de crear otra solicitud.",
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
        return await asyncio.to_thread(
            self.store.record_issue,
            run.project_id,
            run.run_id,
            {
                "code": code,
                "message": message,
                "next_action": action,
                "inference_started": inference_started,
            },
            attempt_id=attempt_id,
        )

    async def wait(self, run_id):
        slot = self._workers.get(run_id)
        if slot is not None:
            await asyncio.shield(slot.task)

    def _end_tool_authority(self, slot):
        slot.active = False
        if slot.grant_id:
            self.live_grants.withdraw(slot.grant_id)

    @asynccontextmanager
    async def _tool_authority(self, slot):
        try:
            yield
        finally:
            # End authority before native/MCP teardown can block, including
            # errors and deadline fuses with an HTTP tool still in flight.
            self._end_tool_authority(slot)

    def _withdraw(self, slot, outcome):
        self._end_tool_authority(slot)
        slot.outcome = outcome
        if slot.session is not None and slot.control is None:
            slot.control = asyncio.create_task(self._interrupt(slot.session))

    @staticmethod
    async def _interrupt(session):
        try:
            await session.cancel()
        except Exception as exc:  # noqa: BLE001 — native/AnyIO boundary; redact exception details
            logger.warning(
                "Native interruption receipt unavailable (%s)", type(exc).__name__
            )

    async def stop(self, project_id, run_id):
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
        """Close original peers and grant-bound tools before completing recovery without replay."""
        work = await asyncio.to_thread(self.recovery.preflight, **command)
        if work["completed"] is not None:
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
        return await asyncio.to_thread(self.recovery.complete, **command)

    async def correct(self, **command):
        validate_correction(**command)
        receipt = await asyncio.to_thread(self.store.correction_receipt, **command)
        if receipt is not None:
            return receipt
        affected = [
            slot
            for slot in self._workers.values()
            if (slot.spec.project_id, slot.spec.task_id)
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
                self._withdraw(slot, "failed")
                return

    async def _execute(self, run_id, slot):
        """Own one admitted native turn, then prove peer/tool closure before finalizing it."""
        lease = heartbeat = token = result = peers = None
        error_type = None
        dispatch_reserved = native_started = False
        try:
            context = await asyncio.to_thread(
                self.store.context_snapshot, slot.spec.project_id, slot.spec.task_id
            )
            if context["task"]["type"] != "research":
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
            token = await asyncio.to_thread(
                self.research.issue_grant,
                project_id=lease.project_id,
                task_id=lease.task_id,
                agent_id=lease.actor_id,
                permissions=set(PERMISSIONS),
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
                    if context["task"]["type"] != "research":
                        raise RunConflict("Task type changed before native dispatch")
                    await asyncio.to_thread(
                        self.workspaces.validate, slot.spec.project_id, slot.binding
                    )
                    frozen = await asyncio.to_thread(
                        self.store.reserve_input,
                        lease,
                        workspace=str(slot.workspace),
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
        except asyncio.CancelledError:
            error_type = "WorkerInterrupted"
        except Exception as exc:  # noqa: BLE001 — native/AnyIO boundary; redact exception details
            error_type = type(exc).__name__
            logger.warning("Research run stopped (%s)", error_type)
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
                    runtime_closed = getattr(slot.session, "peers_closed", False)
                    consume_closure = getattr(self.runtime, "consume_closure", None)
                    if consume_closure is not None:
                        runtime_closed = (
                            consume_closure(lease) is True or runtime_closed
                        )
                    if not peers_closed or not runtime_closed or not tools_closed:
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
                    if result is None and error_type is not None:
                        code = (
                            "native_search_unavailable"
                            if error_type == "NativeSearchUnavailable"
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
                        )
                except Exception as exc:  # noqa: BLE001 -- keep the original failure if its observation cannot commit
                    logger.error(
                        "Run issue could not be recorded (%s)", type(exc).__name__
                    )
                self._workers.pop(run_id, None)
