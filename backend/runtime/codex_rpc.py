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


class StdioRpcClient:
    """Own one child process and its connection, with explicit resource bounds."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        request_timeout: float = 15,
        close_timeout: float = 2,
        max_messages: int = 256,
        max_message_bytes: int = 1024 * 1024,
        max_pending_requests: int = 32,
    ) -> None:
        if not command or min(request_timeout, close_timeout, max_messages, max_message_bytes, max_pending_requests) <= 0:
            raise ValueError("A command and positive transport limits are required")
        self.command = tuple(command)
        self.cwd = cwd
        self.env = dict(env) if env is not None else None
        self.request_timeout = request_timeout
        self.close_timeout = close_timeout
        self.max_message_bytes = max_message_bytes
        self.max_pending_requests = max_pending_requests
        self._messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_messages)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._next_id = 0
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task[None] | None = None
        self._stderr: asyncio.Task[None] | None = None
        self._closing: asyncio.Task[None] | None = None
        self._failure: RpcDisconnected | None = None
        self._failed = asyncio.Event()
        self._write_lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        if self._process is not None:
            raise RuntimeError("A connection cannot be started twice")
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            cwd=self.cwd,
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
            limit=self.max_message_bytes + 1,
        )
        self._reader = asyncio.create_task(self._read_messages())
        self._stderr = asyncio.create_task(self._drain_stderr())
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.aclose()

    async def request(self, method: str, params: dict | None = None, *, timeout: float | None = None) -> Any:
        self._check_connection()
        if len(self._pending) >= self.max_pending_requests:
            raise RpcBackpressure("Too many pending requests; no request was sent")
        self._next_id += 1
        request_id = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            async with asyncio.timeout(self.request_timeout if timeout is None else timeout):
                await self._send({"id": request_id, "method": method, "params": params or {}})
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

    async def respond(self, request_id: int | str, result: Any) -> None:
        await self._send({"id": request_id, "result": result})

    async def next_message(self, *, timeout: float | None = None) -> dict[str, Any]:
        """Read a notification/server request, or expose connection loss promptly."""
        self._check_connection()
        item = asyncio.create_task(self._messages.get())
        failure = asyncio.create_task(self._failed.wait())
        try:
            async with asyncio.timeout(timeout):
                done, _ = await asyncio.wait((item, failure), return_when=asyncio.FIRST_COMPLETED)
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

    async def _send(self, message: dict[str, Any]) -> None:
        self._check_connection()
        frame = json.dumps(message, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(frame) > self.max_message_bytes:
            raise RpcProtocolError("Outgoing message exceeds the configured limit")
        async with asyncio.timeout(self.request_timeout), self._write_lock:
            self._check_connection()
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
                    raise RpcProtocolError("Incoming message exceeds the configured limit") from exc
                if not line:
                    raise RpcDisconnected("Peer closed its output; reconcile before retrying an action")
                if len(line) > self.max_message_bytes:
                    raise RpcProtocolError("Incoming message exceeds the configured limit")
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise RpcProtocolError("Peer sent invalid JSON") from exc
                if not isinstance(message, dict):
                    raise RpcProtocolError("Expected a protocol object")
                if "method" in message:
                    if not isinstance(message["method"], str):
                        raise RpcProtocolError("Expected a method name")
                    try:
                        self._messages.put_nowait(message)
                    except asyncio.QueueFull as exc:
                        raise RpcBackpressure("Event buffer full; reconnect and reconcile state") from exc
                    continue
                request_id = message.get("id")
                if not isinstance(request_id, (str, int)) or isinstance(request_id, bool):
                    raise RpcProtocolError("Expected a response id")
                future = self._pending.get(request_id)
                if future is None or future.done():
                    continue  # Late response: never treat it as another operation's receipt.
                if "error" in message:
                    error = message["error"]
                    if not isinstance(error, dict):
                        raise RpcProtocolError("Expected an error object")
                    future.set_exception(RpcError(error.get("code", -1), str(error.get("message", "Runtime error"))))
                elif "result" in message:
                    future.set_result(message["result"])
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

    def _signal_process_group(self, sig: signal.Signals) -> None:
        assert self._process is not None
        try:
            os.killpg(self._process.pid, sig)
        except ProcessLookupError:
            pass

    async def aclose(self) -> None:
        """Complete one owned shutdown even if an awaiting task is cancelled."""
        if self._process is None:
            return
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._closing)

    async def _shutdown(self) -> None:
        """Reap the process and stop only descendants in this owned session."""
        if self._process is None:
            return
        self._fail(RpcDisconnected("Connection closed"))
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=self.close_timeout)
        except TimeoutError:
            self._signal_process_group(signal.SIGTERM)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=self.close_timeout)
            except TimeoutError:
                self._signal_process_group(signal.SIGKILL)
                await self._process.wait()
        finally:
            # The leader may exit while it still has live background descendants.
            self._signal_process_group(signal.SIGKILL)
            tasks = [task for task in (self._reader, self._stderr) if task is not None]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
