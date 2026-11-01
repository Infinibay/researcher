"""One local owner composes durable research runs with a native inference adapter.

No model loop lives here: one admitted request sends at most one native turn.
All native and MCP context managers enter/exit in the same worker task. HTTP
control withdraws live tool authority before waiting for SQLite or native I/O.
"""

import asyncio
import fcntl
import json
import logging
import os
import stat
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from backend.db.connection import connect
from backend.research.models import PERMISSIONS
from backend.runtime.codex_session import ExecutionLimits
from backend.runtime.contracts import (
    RunConflict,
    RunNotFound,
    StaleAttempt,
    validate_correction,
)
from backend.runtime.sqlite_questions import SQLiteQuestionStore

logger = logging.getLogger(__name__)


class WorkspaceRegistry:
    """Select a registered repository inside the host-managed source root."""

    def __init__(self, database, root):
        self.database = str(database)
        self.root = Path(root).resolve(strict=True)

    def select(self, project_id, repository_id=None):
        with closing(connect(self.database)) as conn:
            rows = conn.execute(
                "SELECT * FROM repositories WHERE project_id=? AND status='active'",
                (project_id,),
            ).fetchall()
            if repository_id is not None:
                rows = [row for row in rows if row["id"] == repository_id]
            if not rows:
                raise RunNotFound("No active repository in this project")
            if len(rows) != 1:
                raise RunConflict("Select a repository for this request")
            root = Path(rows[0]["local_path"]).resolve(strict=True)
            if (
                not root.is_dir()
                or root == self.root
                or not root.is_relative_to(self.root)
            ):
                raise RunConflict("Repository is outside the managed workspace root")
            if Path(self.database).resolve().is_relative_to(root):
                raise RunConflict("Repository contains the host database")
            others = conn.execute(
                "SELECT local_path FROM repositories WHERE project_id<>? AND status='active'",
                (project_id,),
            ).fetchall()
            for other in others:
                path = Path(other[0]).resolve()
                if root.is_relative_to(path) or path.is_relative_to(root):
                    raise RunConflict("Workspace is shared with another project")
            return root


@dataclass
class _Worker:
    spec: object
    workspace: Path
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
        self._closing = False

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
        finally:
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None

    async def submit(self, spec, *, repository_id=None, conversation_thread=None):
        if self._lock_fd is None or self._closing:
            raise RunConflict("Runtime owner is not accepting work")
        if spec.runtime != "codex":
            raise RunConflict(
                "This deployment admits only the Codex subscription adapter"
            )
        previous = await asyncio.to_thread(
            self.store.admission_receipt, spec, conversation_thread=conversation_thread
        )
        if previous is not None and (
            previous.status != "queued" or previous.run_id in self._workers
        ):
            return previous
        workspace = await asyncio.to_thread(
            self.workspaces.select, spec.project_id, repository_id
        )
        if self.control_root.resolve().is_relative_to(workspace):
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
        run = await asyncio.to_thread(
            self.store.admit, spec, conversation_thread=conversation_thread
        )
        if run.status != "queued" or run.run_id in self._workers:
            return run
        if len(self._workers) >= self.max_concurrent or any(
            w.spec.project_id == spec.project_id for w in self._workers.values()
        ):
            raise RunConflict(
                "Native concurrency is full; admitted request remains queued"
            )
        slot = _Worker(spec, workspace)
        slot.intent_committed.set()
        self._workers[run.run_id] = slot
        slot.task = asyncio.create_task(
            self._execute(run.run_id, slot), name="researcher-run-" + run.run_id
        )
        return run

    async def wait(self, run_id):
        slot = self._workers.get(run_id)
        if slot is not None:
            await asyncio.shield(slot.task)

    def _withdraw(self, slot, outcome):
        slot.active = False
        slot.outcome = outcome
        if slot.grant_id:
            self.live_grants.withdraw(slot.grant_id)
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
        lease = heartbeat = token = result = None
        error_type = None
        try:
            lease = await asyncio.to_thread(
                self.store.claim, slot.spec.project_id, run_id, self.owner_id
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
                async with self.runtime.open(
                    workspace=slot.workspace,
                    tool_token=token,
                    active=active,
                    limits=self.limits,
                ) as session:
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
                    should_send = await asyncio.to_thread(
                        self.store.reserve_inference,
                        lease,
                        workspace=str(slot.workspace),
                        catalog_hash=session.catalog_hash,
                        model=session.model,
                        limits=self.limits,
                        project_turn_limit=self.project_turn_limit,
                        project_token_limit=self.project_token_limit,
                    )
                    if not should_send:
                        raise RunConflict(
                            "Native dispatch was already reserved; reconcile without replay"
                        )
                    if not active():
                        return

                    async def on_started(thread_id, turn_id):
                        await asyncio.to_thread(
                            self.store.bind_native,
                            lease,
                            thread_id=thread_id,
                            turn_id=turn_id,
                        )

                    async def on_event(event):
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
                        ) not in ("mcpToolCall", "dynamicToolCall"):
                            return
                        stage = "started" if method == "item/started" else "completed"
                        await asyncio.to_thread(
                            self.store.observe_native,
                            lease,
                            observation_key="tool-" + stage + "-" + item["id"],
                            native_kind="tool." + stage,
                            payload={
                                "thread_id": session.thread_id,
                                "item_id": item["id"],
                                "type": item["type"],
                            },
                        )

                    result = await session.run(
                        json.dumps(
                            {**context, "request": slot.spec.prompt}, ensure_ascii=False
                        ),
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
            slot.active = False
            if slot.grant_id:
                self.live_grants.withdraw(slot.grant_id)
            if heartbeat is not None:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            if slot.control is not None:
                await slot.control
            await slot.intent_committed.wait()
            try:
                if slot.grant_id:
                    await asyncio.to_thread(self.research.revoke_grant, slot.grant_id)
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
                    if not getattr(slot.session, "peers_closed", False):
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
                            # The research adapter has no native shell effects;
                            # both peers are now closed and grants revoked. The
                            # journal still refuses retirement for unknown jobs.
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
                self._workers.pop(run_id, None)
