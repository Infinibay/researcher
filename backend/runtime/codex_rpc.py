"""Bounded stdio transport for Codex App Server's JSON-RPC wire format.

Requests are correlated independently of notifications and server requests.
A lost response never causes automatic replay of a potentially applied action.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self


class RpcDisconnected(RuntimeError):
    """The connection can no longer prove delivery or receive a result."""


class RpcProtocolError(RpcDisconnected):
    """A peer supplied an invalid or oversized protocol frame."""


class RpcBackpressure(RpcDisconnected):
    """The consumer must reconcile after exceeding the bounded event buffer."""


class RpcError(RuntimeError):
    """An explicit error response from the peer, not a successful result."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RpcReply:
    result: Any
    preceding_messages: int


class JsonRpcClient:
    """Bounded JSON-RPC over a lifecycle-owned async endpoint.

    The endpoint owns birth/closure. An open failure or cancellation must drain
    its owned launch; the protocol never retries or invents an exit receipt.
    """

    def __init__(
        self,
        endpoint,
        *,
        request_timeout=15,
        close_timeout=2,
        max_messages=256,
        max_message_bytes=1024 * 1024,
        max_pending_requests=32,
    ):
        if (
            min(
                request_timeout,
                close_timeout,
                max_messages,
                max_message_bytes,
                max_pending_requests,
            )
            <= 0
        ):
            raise ValueError("Positive transport limits are required")
        self._endpoint = endpoint
        self.request_timeout = request_timeout
        self.close_timeout = close_timeout
        self.max_message_bytes = max_message_bytes
        self.max_pending_requests = max_pending_requests
        self._messages = asyncio.Queue(maxsize=max_messages)
        self._pending = {}
        self._next_id = 0
        self._message_count = 0
        self._process = None
        self._reader = None
        self._stderr = None
        self._closing = None
        self._failure = None
        self._failed = asyncio.Event()
        self._write_lock = asyncio.Lock()
        self._started = False
        self._private_handlers = {}
        self._private_tasks = set()

    def register_private_request(self, method, handler, *, allowed=None):
        """Host-only connection control, installed before any peer can speak.

        These requests never enter the model/user event queue or its barrier.
        Handlers run independently of pending client requests, at most four.
        """
        if self._started:
            raise RuntimeError("Private handlers must be registered before startup")
        if (
            not isinstance(method, str)
            or not 1 <= len(method) <= 128
            or not callable(handler)
            or allowed is not None
            and not callable(allowed)
            or method in self._private_handlers
            or len(self._private_handlers) >= 4
        ):
            raise ValueError("Invalid or duplicate private control registration")
        self._private_handlers[method] = (handler, allowed)

    async def _serve_private(self, message, registration):
        if self._failure is not None:
            return
        try:
            handler, allowed = registration
            if allowed is not None and not allowed():
                raise RpcDisconnected("Private control authority withdrawn")
            async with asyncio.timeout(self.request_timeout):
                result = await handler(message.get("params", {}))
                await self.respond(message["id"], result, _guard=allowed)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — sanitize secret-bearing host callback failures
            # A credential provider's exception may contain secrets. Never retain
            # it as a public error cause or log it, and never keep using old auth.
            self._fail(RpcDisconnected("Private connection control failed"))
            self._begin_close()

    async def __aenter__(self) -> Self:
        if self._started:
            raise RuntimeError("A connection cannot be started twice")
        self._started = True
        try:
            self._process = await self._endpoint.open(limit=self.max_message_bytes + 1)
            if self._closing is not None:
                raise RpcDisconnected("Connection closed during startup")
        except BaseException as error:
            try:
                await self.aclose()
            except Exception as cleanup_error:
                raise error from cleanup_error
            raise
        self._reader = asyncio.create_task(self._read_messages())
        self._stderr = asyncio.create_task(self._drain_stderr())
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        params: dict | None = None,
        *,
        timeout: float | None = None,
        _guard=None,
    ) -> Any:
        if _guard is None:
            return (await self.request_ordered(method, params, timeout=timeout)).result
        return (
            await self.request_ordered(method, params, timeout=timeout, _guard=_guard)
        ).result

    async def request_ordered(
        self,
        method: str,
        params: dict | None = None,
        *,
        timeout: float | None = None,
        _guard=None,
    ) -> RpcReply:
        """Return a barrier for wire messages preceding this response.

        A separate event consumer may still be processing those notifications;
        streamed output must cross this barrier before its result is persisted.
        """
        self._check_connection()
        if len(self._pending) >= self.max_pending_requests:
            raise RpcBackpressure("Too many pending requests; no request was sent")
        self._next_id += 1
        request_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            async with asyncio.timeout(
                self.request_timeout if timeout is None else timeout
            ):
                message = {"id": request_id, "method": method, "params": params or {}}
                if _guard is None:
                    await self._send(message)
                else:
                    await self._send(message, _guard=_guard)
                return await future
        finally:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    async def notify(self, method: str, params: dict | None = None) -> None:
        message: dict[str, Any] = {"method": method}
        if params is not None:
            message["params"] = params
        await self._send(message)

    async def respond(self, request_id: int | str, result: Any, *, _guard=None) -> None:
        if _guard is None:
            await self._send({"id": request_id, "result": result})
        else:
            await self._send({"id": request_id, "result": result}, _guard=_guard)

    async def next_message(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Read a notification/server request, or expose connection loss promptly."""
        self._check_connection()
        item = asyncio.create_task(self._messages.get())
        failure = asyncio.create_task(self._failed.wait())
        try:
            async with asyncio.timeout(timeout):
                done, _ = await asyncio.wait(
                    (item, failure), return_when=asyncio.FIRST_COMPLETED
                )
                if failure in done:
                    raise self._failure or RpcDisconnected("Connection closed")
                return item.result()
        finally:
            item.cancel()
            failure.cancel()
            await asyncio.gather(item, failure, return_exceptions=True)

    def _check_connection(self) -> None:
        if self._failure is not None:
            raise self._failure
        if self._process is None:
            raise RpcDisconnected("Connection has not started")

    async def _send(self, message: dict[str, Any], *, _guard=None) -> None:
        self._check_connection()
        frame = (
            json.dumps(message, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        )
        if len(frame) > self.max_message_bytes:
            raise RpcProtocolError("Outgoing message exceeds the configured limit")
        async with asyncio.timeout(self.request_timeout), self._write_lock:
            self._check_connection()
            if _guard is not None and not _guard():
                raise RpcDisconnected(
                    "Private control authority withdrawn before write"
                )
            assert self._process is not None and self._process.stdin is not None
            try:
                self._process.stdin.write(frame)
                await self._process.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as exc:
                error = RpcDisconnected("Peer closed its input")
                self._fail(error)
                raise error from exc

    def _fail(self, error: RpcDisconnected) -> None:
        if self._failure is not None:
            return
        self._failure = error
        self._failed.set()
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)

    async def _read_messages(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            while True:
                try:
                    line = await self._process.stdout.readline()
                except ValueError as exc:
                    raise RpcProtocolError(
                        "Incoming message exceeds the configured limit"
                    ) from exc
                if not line:
                    raise RpcDisconnected(
                        "Peer closed its output; reconcile before retrying an action"
                    )
                if len(line) > self.max_message_bytes:
                    raise RpcProtocolError(
                        "Incoming message exceeds the configured limit"
                    )
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise RpcProtocolError("Peer sent invalid JSON") from exc
                if not isinstance(message, dict):
                    raise RpcProtocolError("Expected a protocol object")
                if "method" in message:
                    if not isinstance(message["method"], str):
                        raise RpcProtocolError("Expected a method name")
                    private = self._private_handlers.get(message["method"])
                    if private is not None:
                        request_id = message.get("id")
                        if (
                            not isinstance(request_id, (str, int))
                            or isinstance(request_id, bool)
                            or not isinstance(message.get("params", {}), dict)
                        ):
                            raise RpcProtocolError("Invalid private control request")
                        if self._failure is not None:
                            continue
                        if len(self._private_tasks) >= min(
                            4, self.max_pending_requests
                        ):
                            raise RpcBackpressure(
                                "Private control request capacity reached"
                            )
                        task = asyncio.create_task(
                            self._serve_private(message, private)
                        )
                        self._private_tasks.add(task)
                        task.add_done_callback(self._private_tasks.discard)
                        continue
                    try:
                        self._messages.put_nowait(message)
                        self._message_count += 1
                    except asyncio.QueueFull as exc:
                        raise RpcBackpressure(
                            "Event buffer full; reconnect and reconcile state"
                        ) from exc
                    continue
                request_id = message.get("id")
                if not isinstance(request_id, (str, int)) or isinstance(
                    request_id, bool
                ):
                    raise RpcProtocolError("Expected a response id")
                future = self._pending.get(request_id)
                if future is None or future.done():
                    continue  # Late response: never treat it as another operation's receipt.
                if "error" in message:
                    error = message["error"]
                    if not isinstance(error, dict):
                        raise RpcProtocolError("Expected an error object")
                    future.set_exception(
                        RpcError(
                            error.get("code", -1),
                            str(error.get("message", "Runtime error")),
                        )
                    )
                elif "result" in message:
                    future.set_result(RpcReply(message["result"], self._message_count))
                else:
                    raise RpcProtocolError("Response has neither result nor error")
        except RpcDisconnected as exc:
            self._fail(exc)
        except asyncio.CancelledError:
            self._fail(RpcDisconnected("Connection closed"))
            raise

    async def _drain_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        # Drain rather than log raw provider diagnostics, which may contain secrets.
        while await self._process.stderr.read(8192):
            pass

    async def aclose(self) -> None:
        """Complete one owned shutdown even if an awaiting task is cancelled."""
        if not self._started:
            return
        await asyncio.shield(self._begin_close())

    def _begin_close(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
            self._closing.add_done_callback(
                lambda done: None if done.cancelled() else done.exception()
            )
        return self._closing

    async def _shutdown(self):
        self._fail(RpcDisconnected("Connection closed"))
        try:
            await self._endpoint.aclose(timeout=self.close_timeout)
        finally:
            tasks = [
                task
                for task in (self._reader, self._stderr, *self._private_tasks)
                if task is not None
            ]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._private_handlers.clear()


class _SubprocessEndpoint:
    """Compatibility adapter for the existing CLI/process-group lifetime."""

    def __init__(self, command, cwd, env, process_group_signals):
        self.command = tuple(command)
        self.cwd = cwd
        self.env = dict(env) if env is not None else None
        self.process_group_signals = process_group_signals
        self._process = None
        self._starting = None

    async def open(self, *, limit):
        if self._starting is not None:
            raise RuntimeError("Endpoint already started")
        self._starting = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *self.command,
                cwd=self.cwd,
                env=self.env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                limit=limit,
            )
        )
        self._process = await asyncio.shield(self._starting)
        return self._process

    def _signal(self, sig):
        try:
            if self.process_group_signals:
                os.killpg(self._process.pid, sig)
            elif self._process.returncode is None:
                self._process.send_signal(sig)
        except ProcessLookupError:
            pass

    async def aclose(self, *, timeout):
        if self._starting is None:
            return
        if self._starting.done() and self._starting.exception() is not None:
            return  # Process creation failed; no child was returned to this owner.
        if self._process is None:
            self._process = await asyncio.shield(self._starting)
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
        except TimeoutError:
            self._signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=timeout)
            except TimeoutError:
                self._signal(signal.SIGKILL)
                await self._process.wait()
        finally:
            self._signal(signal.SIGKILL)


class StdioRpcClient(JsonRpcClient):
    """CLI compatibility entry point; broker clients use JsonRpcClient(endpoint)."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        request_timeout=15,
        close_timeout=2,
        max_messages=256,
        max_message_bytes=1024 * 1024,
        max_pending_requests=32,
        process_group_signals=True,
    ):
        if not command:
            raise ValueError("A command is required")
        super().__init__(
            _SubprocessEndpoint(command, cwd, env, process_group_signals),
            request_timeout=request_timeout,
            close_timeout=close_timeout,
            max_messages=max_messages,
            max_message_bytes=max_message_bytes,
            max_pending_requests=max_pending_requests,
        )

    @property
    def command(self):
        return self._endpoint.command

    @command.setter
    def command(self, value):
        self._endpoint.command = tuple(value)

    @property
    def cwd(self):
        return self._endpoint.cwd

    @cwd.setter
    def cwd(self, value):
        self._endpoint.cwd = value

    @property
    def env(self):
        return self._endpoint.env

    @env.setter
    def env(self, value):
        self._endpoint.env = value

    @property
    def process_group_signals(self):
        return self._endpoint.process_group_signals

    @process_group_signals.setter
    def process_group_signals(self, value):
        self._endpoint.process_group_signals = value
