"""MCP SDK sessions over broker-owned pipes, without a second process launcher."""

import asyncio
import math
from contextlib import asynccontextmanager
from datetime import timedelta

import anyio
from mcp import ClientSession, types
from mcp.shared.exceptions import McpError
from mcp.shared.message import SessionMessage


class McpTransportError(RuntimeError):
    """Delivery/result is uncertain; callers must not automatically replay effects."""


class _Pipes:
    def __init__(self, endpoint, limit, timeout):
        self.endpoint, self.limit, self.timeout = endpoint, limit, timeout
        self.read_send, self.read = anyio.create_memory_object_stream(8)
        self.write, self.write_receive = anyio.create_memory_object_stream(8)
        self.tasks = []
        self.failed = False
        self._closing = None

    async def open(self):
        await self.endpoint.open(limit=self.limit)
        self.tasks = [
            asyncio.create_task(self._reader()),
            asyncio.create_task(self._writer()),
            asyncio.create_task(self._stderr()),
        ]

    async def fail(self):
        self.failed = True
        # Closing the receive channel wakes SDK requests with Connection closed.
        # Do not forward decoder/validation exceptions, which contain raw input.
        self.read_send.close()
        self.write_receive.close()
        if self._closing is None:
            self._closing = asyncio.create_task(self.endpoint.aclose(timeout=3))
        await asyncio.shield(self._closing)

    async def _reader(self):
        try:
            while True:
                line = await self.endpoint.stdout.readline()
                if not line or not line.endswith(b"\n") or len(line) > self.limit:
                    break
                message = types.JSONRPCMessage.model_validate_json(line)
                root = message.root
                # The SDK logs invalid server messages with their raw contents.
                # Validate its typed inputs here, keeping private input out of logs.
                if isinstance(root, types.JSONRPCRequest):
                    types.ServerRequest.model_validate(root.model_dump(by_alias=True))
                elif isinstance(root, types.JSONRPCNotification):
                    types.ServerNotification.model_validate(
                        root.model_dump(by_alias=True)
                    )
                elif type(root.id) is not int or root.id < 0:
                    break
                await self.read_send.send(SessionMessage(message))
        except (
            ValueError,
            OSError,
            anyio.ClosedResourceError,
            anyio.BrokenResourceError,
        ):
            pass
        finally:
            await self.fail()

    async def _writer(self):
        try:
            async for message in self.write_receive:
                data = (
                    message.message.model_dump_json(by_alias=True, exclude_none=True)
                    + "\n"
                ).encode()
                if len(data) > self.limit:
                    break
                async with asyncio.timeout(self.timeout):
                    self.endpoint.stdin.write(data)
                    await self.endpoint.stdin.drain()
        except (
            ValueError,
            OSError,
            TimeoutError,
            anyio.ClosedResourceError,
            anyio.BrokenResourceError,
        ):
            pass
        finally:
            await self.fail()

    async def _stderr(self):
        # Drain/discard diagnostics with fixed chunks; no unbounded capture or log.
        try:
            while await self.endpoint.stderr.read(16384):
                pass
        except (ValueError, OSError):
            pass

    async def close(self):
        # Physical peer closure precedes cancelling protocol IO tasks. The broker
        # retains its original pidfd/receipt ownership even if our wait is cancelled.
        try:
            await self.fail()
        finally:
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            for stream in (self.read_send, self.read, self.write, self.write_receive):
                stream.close()


class _Client:
    def __init__(self, session, pipes):
        self._session, self._pipes = session, pipes
        self._inflight = 0

    async def _run(self, operation):
        if self._pipes.failed:
            raise McpTransportError("MCP peer closed; reconcile before retrying")
        if self._inflight >= 8:
            raise McpTransportError("MCP request capacity reached")
        self._inflight += 1
        try:
            async with asyncio.timeout(self._pipes.timeout):
                return await operation()
        except asyncio.CancelledError:
            with anyio.CancelScope(shield=True):
                await self._pipes.fail()
            raise
        except (
            McpError,
            ValueError,
            OSError,
            TimeoutError,
            anyio.ClosedResourceError,
            anyio.BrokenResourceError,
        ):
            await self._pipes.fail()
            raise McpTransportError(
                "MCP result unavailable; reconcile before retrying"
            ) from None
        finally:
            self._inflight -= 1

    async def list_tools(self, *, cursor=None):
        return await self._run(lambda: self._session.list_tools(cursor=cursor))

    async def call_tool(self, name, arguments):
        return await self._run(lambda: self._session.call_tool(name, arguments))


@asynccontextmanager
async def broker_mcp(endpoint, *, request_timeout=15, max_message_bytes=1_000_000):
    """Initialize one scoped SDK client; sampling/roots/elicitation stay denied.

    The caller enters/exits this scope in the same task, as required by the MCP
    SDK's AnyIO cancel scopes. No subprocess or alternate process ownership exists.
    A tool's isError result remains a normal result; transport failures close this
    peer and never replay the request or withdraw unrelated sibling peers.
    """
    if (
        type(request_timeout) not in (int, float)
        or not math.isfinite(request_timeout)
        or not 0 < request_timeout <= 180
        or type(max_message_bytes) is not int
        or not 1024 <= max_message_bytes <= 1_000_000
    ):
        raise ValueError("Finite bounded MCP transport limits required")
    pipes = _Pipes(endpoint, max_message_bytes, request_timeout)
    body_error = None
    try:
        await pipes.open()
        async with ClientSession(
            pipes.read,
            pipes.write,
            read_timeout_seconds=timedelta(seconds=request_timeout),
            client_info=types.Implementation(name="researcher-host", version="1"),
        ) as session:
            client = _Client(session, pipes)
            try:
                await client._run(session.initialize)
                yield client
            except BaseException as error:  # noqa: BLE001 — preserve caller identity after SDK cancel scopes drain
                body_error = error
            finally:
                with anyio.CancelScope(shield=True):
                    await pipes.close()
        if body_error is not None:
            raise body_error
    finally:
        with anyio.CancelScope(shield=True):
            await pipes.close()
