"""Client-owned native commands with durable dispatch and bounded output.

The RPC peer is dedicated to command execution, not shared with a model event
consumer. The caller supplies a private, account-free, permission-scoped peer.
No command is replayed after losing its native connection or durable receipt.
"""

import asyncio
import base64
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from backend.runtime.codex_rpc import (
    JsonRpcClient,
    RpcDisconnected,
    RpcError,
    RpcProtocolError,
    StdioRpcClient,
)
from backend.runtime.contracts import (
    AttemptLease,
    CommandJob,
    CommandSpec,
    RunConflict,
    RunNotFound,
)
from backend.runtime.peer_registry import PeerRegistry
from backend.runtime.sqlite_runs import SQLiteRunStore


class CommandNeedsReconciliation(RuntimeError):
    """A prior dispatch has no terminal receipt on this owned connection."""


@dataclass
class _Command:
    """Retain one reserved command's bounded output buffers, execution/cancellation tasks and response
    barrier on its original connection.
    """
    lease: AttemptLease
    job: CommandJob
    stdout: bytearray = field(default_factory=bytearray)
    stderr: bytearray = field(default_factory=bytearray)
    output_limited: bool = False
    task: asyncio.Task | None = None
    cancellation: asyncio.Task | None = None
    cancel_intent: asyncio.Task | None = None
    response_settled: asyncio.Event = field(default_factory=asyncio.Event)


class CommandHandle:
    """Observe or cancel one existing command through its original executor; the handle does not grant
    another dispatch.
    """
    def __init__(self, executor, job_id):
        """Bind a lightweight handle to the original executor and durable job identity without
        launching work.
        """
        self._executor = executor
        self.job_id = job_id

    async def wait(self) -> CommandJob:
        """Shield the existing local execution task from observer cancellation, then read the original
        durable receipt instead of restarting it.
        """
        state = self._executor._commands.get(self.job_id)
        if state is not None and state.task is not None:
            await asyncio.shield(state.task)
        return await self._executor._get(self.job_id)

    async def cancel(self) -> CommandJob:
        """Request cancellation through the original executor and return the resulting retained
        receipt.
        """
        return await self._executor.cancel(self.job_id)


class OwnedCommandExecutor:
    """Own one account-free command peer and its original-attempt receipts, separating streamed output,
    cancellation intent and physical peer closure.
    """
    def __init__(
        self,
        rpc: JsonRpcClient,
        *,
        journal: SQLiteRunStore,
        workspace: Path,
        lease: AttemptLease,
        peer_id: str,
        execution_workspace: Path | None = None,
        monitor_interval=0.25,
        cancel_grace=1.0,
    ):
        """Bind journal, workspace and lease only to their own registered command transport; connection
        and account checks occur on async entry.
        """
        if monitor_interval <= 0 or cancel_grace <= 0:
            raise ValueError("Positive command lifecycle limits are required")
        self.rpc = rpc
        self.journal = journal
        self.workspace = workspace.resolve()
        # Journal identity remains the host admission. Only the RPC execution
        # path uses the stable mount inside its dedicated peer namespace.
        self.execution_workspace = execution_workspace or self.workspace
        self.peers = PeerRegistry(journal)
        self.peer_id = peer_id
        peer = self.peers.inspect(peer_id)
        from backend.runtime.broker_stdio import BrokerEndpoint

        endpoint = rpc._endpoint
        self._broker_owned = isinstance(endpoint, BrokerEndpoint)
        if self._broker_owned:
            transport_matches = (
                endpoint.command_only
                and endpoint.peer_id == peer_id
                and endpoint.registry._database_identity()
                == self.peers._database_identity()
                and not endpoint._opened
            )
        else:
            prefix = self.peers.command(peer_id, ["payload"])[:-1]
            transport_matches = (
                isinstance(rpc, StdioRpcClient)
                and tuple(rpc.command[: len(prefix)]) == tuple(prefix)
                and rpc._process is None
            )
        if (
            peer["kind"] != "command"
            or peer["attempt_id"] != lease.attempt_id
            or peer["fence"] != lease.fence
            or not transport_matches
        ):
            raise RunConflict("Command transport must use its own registered peer gate")
        self.peers._check_origin(peer)
        if not self._broker_owned:
            rpc.process_group_signals = False
        self.executor_id = str(uuid4())
        self.monitor_interval = monitor_interval
        self.cancel_grace = cancel_grace
        self._commands: dict[str, _Command] = {}
        self._owner: AttemptLease | None = lease
        self._reader = None
        self._reader_error = None
        self._handled_messages = 0
        self._changed = asyncio.Event()
        self._admission = asyncio.Lock()
        self._closing = None
        self._peer_closing = None
        self._supervisor = None

    async def __aenter__(self):
        """Initialize the dedicated RPC peer, reject an attached account and require its bound identity
        before starting event and authority monitors.
        """
        try:
            await self.rpc.__aenter__()
            await self.rpc.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "researcher-command-worker",
                        "version": "0.1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            await self.rpc.notify("initialized")
            account = await self.rpc.request("account/read", {"refreshToken": False})
            if account.get("account") is not None:
                raise RpcProtocolError(
                    "Command peer must use its own account-free control directory"
                )
            self._reader = asyncio.create_task(self._read_events())
            if (await asyncio.to_thread(self.peers.inspect, self.peer_id))[
                "state"
            ] != "bound":
                raise RpcProtocolError(
                    "Command peer did not bind before initialization"
                )
            self._supervisor = asyncio.create_task(self._watch_owner())
            return self
        except BaseException:
            await self._close_peer()
            raise

    async def __aexit__(self, exc_type, exc, traceback):
        """Await the executor's shared cancellation and peer teardown when its scope exits."""
        await self.aclose()

    async def start(
        self, lease: AttemptLease, operation_key: str, spec: CommandSpec
    ) -> CommandHandle:
        """Reserve one scoped command before its first dispatch, or recover its original
        handle/receipt; an uncertain command from another connection requires reconciliation.
        """
        if (
            self._reader is None
            or self._closing is not None
            or self._reader_error is not None
            or self._peer_closing is not None
        ):
            raise RpcDisconnected("Command executor is not available")
        cwd = (self.workspace / spec.cwd).resolve()
        if not cwd.is_relative_to(self.workspace) or not cwd.is_dir():
            raise ValueError(
                "Command working directory is outside its available workspace"
            )
        async with self._admission:
            names = (
                "project_id",
                "task_id",
                "run_id",
                "attempt_id",
                "actor_id",
                "owner_id",
                "fence",
                "context_version",
            )
            if self._owner is not None and tuple(
                getattr(self._owner, name) for name in names
            ) != tuple(getattr(lease, name) for name in names):
                raise RunConflict(
                    "A native command peer belongs to one attempt; it cannot be shared"
                )
            self._owner = lease
            reservation = await asyncio.to_thread(
                self.journal.reserve_job,
                lease,
                operation_key=operation_key,
                spec=spec,
                workspace=str(self.workspace),
                executor_id=self.executor_id,
                peer_id=self.peer_id,
            )
            job = reservation.job
            if not reservation.should_dispatch:
                if job.job_id not in self._commands and job.status != "exited":
                    raise CommandNeedsReconciliation(
                        f"Command {job.job_id} belongs to a prior connection; it was not replayed"
                    )
                return CommandHandle(self, job.job_id)
            # Keep only bounded active/recent handles; canonical output lives in DB.
            for ident, old in tuple(self._commands.items()):
                if len(self._commands) < 128:
                    break
                if old.task is not None and old.task.done():
                    del self._commands[ident]
            if len(self._commands) >= 128:
                raise RpcProtocolError(
                    "Command handle capacity reached; reconcile reserved dispatch"
                )
            state = _Command(lease, job)
            self._commands[job.job_id] = state
            state.task = asyncio.create_task(self._execute(state, cwd))
            return CommandHandle(self, job.job_id)

    async def _get(self, job_id):
        """Read a retained command only within this executor's admitted run, independently of whether
        that command may still execute.
        """
        if self._owner is None:
            raise RunNotFound("This executor has no admitted attempt")
        record = await asyncio.to_thread(
            self.journal.get_job, self._owner.project_id, job_id
        )
        if record.run_id != self._owner.run_id:
            raise RunNotFound("Job does not belong to this executor's run")
        return record

    async def _read_events(self):
        """Consume command-only notifications and advance the reply barrier; unexpected interactive
        requests or malformed transport trigger peer retirement.
        """
        try:
            while True:
                event = await self.rpc.next_message()
                if "id" in event:
                    raise RpcProtocolError(
                        "Unexpected interactive request on command-only peer"
                    )
                if event.get("method") == "command/exec/outputDelta":
                    self._output(event.get("params", {}))
                self._handled_messages += 1
                self._changed.set()
        except (RpcDisconnected, ValueError, KeyError, TypeError) as exc:
            self._reader_error = exc
            self._changed.set()
            await self._close_peer()

    def _output(self, params):
        """Append decoded bytes only to the matching active command up to its stream limit, requesting
        cancellation when capture reaches its bound.
        """
        if not isinstance(params, dict):
            raise RpcProtocolError("Expected a command output object")
        if (
            not isinstance(params.get("processId"), str)
            or params.get("stream") not in ("stdout", "stderr")
            or type(params.get("capReached")) is not bool
        ):
            raise RpcProtocolError("Malformed command output notification")
        state = self._commands.get(params["processId"])
        if state is None or state.task.done():
            return  # Never attach another or late command's bytes to this one.
        try:
            data = base64.b64decode(params["deltaBase64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise RpcProtocolError("Malformed encoded command output") from exc
        buffer = getattr(state, params["stream"])
        remaining = state.job.spec.output_bytes - len(buffer)
        buffer.extend(data[:remaining])
        if params["capReached"] or len(data) > remaining:
            state.output_limited = True
            self._ensure_cancel(state)

    async def _barrier(self, target):
        """Wait for the event consumer to process every public wire message preceding a command reply,
        exposing reader failures or the bounded wait timeout.
        """
        async with asyncio.timeout(2):
            while self._handled_messages < target:
                if self._reader_error is not None:
                    raise self._reader_error
                self._changed.clear()
                await self._changed.wait()

    async def _execute(self, state, cwd):
        """Dispatch the reserved command once, account for preceding output and persist its recognized
        terminal observation; transport failure closes the peer and retains an unknown exit.
        """
        exit_code, error = None, None
        try:
            if not await asyncio.to_thread(self.journal.attempt_active, state.lease):
                raise RpcDisconnected("Attempt authority ended before native dispatch")
            reply = await self.rpc.request_ordered(
                "command/exec",
                {
                    "command": list(state.job.spec.argv),
                    "cwd": str(
                        self.execution_workspace / cwd.relative_to(self.workspace)
                    ),
                    **(
                        {
                            "sandboxPolicy": {
                                "type": "externalSandbox",
                                "networkAccess": "restricted",
                            }
                        }
                        if self._broker_owned
                        else {"permissionProfile": "researcher_jobs"}
                    ),
                    "processId": state.job.job_id,
                    "streamStdoutStderr": True,
                    "timeoutMs": max(1, int(state.job.spec.timeout_seconds * 1000)),
                    "outputBytesCap": state.job.spec.output_bytes,
                },
                timeout=state.job.spec.timeout_seconds + self.cancel_grace + 2,
            )
            await self._barrier(reply.preceding_messages)
            if type(reply.result.get("exitCode")) is not int:
                raise RpcProtocolError("Command response has no terminal exit code")
            if reply.result.get("stdout") or reply.result.get("stderr"):
                raise RpcProtocolError(
                    "Streamed command unexpectedly returned duplicated buffered output"
                )
            exit_code = reply.result["exitCode"]
        except (RpcDisconnected, RpcError, TimeoutError) as exc:
            error = type(exc).__name__
            await self._close_peer()
        finally:
            state.response_settled.set()
        if state.cancel_intent is not None:
            await asyncio.shield(state.cancel_intent)
        await asyncio.to_thread(
            self.journal.finish_job,
            state.lease,
            state.job.job_id,
            executor_id=self.executor_id,
            exit_code=exit_code,
            stdout=bytes(state.stdout),
            stderr=bytes(state.stderr),
            output_limited=state.output_limited,
            error=error,
        )
        state.stdout.clear()
        state.stderr.clear()

    async def _watch_owner(self):
        """Supervise durable attempt authority and stop active command effects when authority is absent
        or cannot be established.
        """
        while True:
            await asyncio.sleep(self.monitor_interval)
            try:
                active = await asyncio.wait_for(
                    asyncio.to_thread(self.journal.supervise_attempt, self._owner),
                    timeout=max(1.0, self.monitor_interval * 4),
                )
            except Exception:  # noqa: BLE001 -- loss of authority must stop effects.
                active = False  # Cannot establish authority: stop effects, not retry.
            if not active:
                active_jobs = [
                    self._ensure_cancel(state)
                    for state in self._commands.values()
                    if state.task is not None and not state.task.done()
                ]
                try:
                    await asyncio.gather(
                        *(asyncio.shield(job) for job in active_jobs),
                        return_exceptions=True,
                    )
                finally:
                    await self._close_peer()
                return

    def _ensure_cancel(self, state):
        """Create or recover one cancellation task for this command without repeating execution."""
        if state.cancellation is None:
            state.cancellation = asyncio.create_task(self._cancel(state))
        return state.cancellation

    async def cancel(self, job_id) -> CommandJob:
        """Share cancellation for a locally tracked command or inspect an older retained receipt
        without acquiring a new execution owner.
        """
        state = self._commands.get(job_id)
        if state is None:
            return await self._get(job_id)
        await asyncio.shield(self._ensure_cancel(state))
        return await self._get(job_id)

    async def _cancel(self, state):
        """Record cancellation intent and retry only termination control within grace, then cross the
        physical peer closure barrier before collecting the original command outcome.
        """
        if state.task.done():
            return
        if state.response_settled.is_set():
            await self._close_peer()
            await asyncio.shield(state.task)
            return
        state.cancel_intent = asyncio.create_task(
            asyncio.to_thread(
                self.journal.cancel_job,
                state.lease,
                state.job.job_id,
            )
        )
        try:
            async with asyncio.timeout(self.cancel_grace):
                while not state.response_settled.is_set():
                    try:
                        await self.rpc.request(
                            "command/exec/terminate",
                            {"processId": state.job.job_id},
                            timeout=self.cancel_grace,
                        )
                        await state.response_settled.wait()
                    except RpcError:
                        # Termination may race registration; retry control, never execution.
                        await asyncio.sleep(0.02)
        except (RpcDisconnected, TimeoutError):
            pass  # A receipt is optional; the physical closure barrier is not.
        finally:
            await self._close_peer()
        await asyncio.shield(state.cancel_intent)
        await asyncio.shield(state.task)

    async def aclose(self):
        """Await one shared executor shutdown while shielding it from cancellation of an observer."""
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._closing)

    async def _shutdown(self):
        """Request cancellation of active jobs, always close the peer and drain the event reader; peer
        teardown errors remain visible.
        """
        if self._supervisor is not None:
            self._supervisor.cancel()
            await asyncio.gather(self._supervisor, return_exceptions=True)
        active = [
            self._ensure_cancel(state)
            for state in self._commands.values()
            if state.task is not None and not state.task.done()
        ]
        try:
            if active:
                await asyncio.gather(*active, return_exceptions=True)
        finally:
            try:
                await self._close_peer()
            finally:
                if self._reader is not None:
                    self._reader.cancel()
                    await asyncio.gather(self._reader, return_exceptions=True)

    async def _close_peer(self):
        """Create or recover one shielded retirement task for the executor's original peer."""
        if self._peer_closing is None:
            self._peer_closing = asyncio.create_task(self._retire_peer())
        await asyncio.shield(self._peer_closing)

    async def _retire_peer(self):
        """Use broker-owned closure when available; otherwise drain RPC and registered namespace
        closure together and propagate unresolved teardown errors.
        """
        if self._broker_owned:
            # Endpoint closure owns physical Stop and original global→SQL proof.
            await self.rpc.aclose()
            return
        # Physical namespace retirement must not queue behind a writer before
        # stopping effects. PeerRegistry reads a WAL snapshot and kills first.
        results = await asyncio.gather(
            self.rpc.aclose(),
            asyncio.to_thread(self.peers.close, self.peer_id),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result
