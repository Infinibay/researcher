"""Async host transport over actual broker peers, with reserved Stop capacity.

No launcher/G belongs to the RPC client. Closing one connected endpoint closes
its original namespace; cancelling an uncertain startup withdraws the attempt.
This adapter is not a managed-domain enrollment or a new inference engine.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from backend.runtime.authority_journal import AuthorityBusy, AuthorityConflict


class _WriteProtocol(asyncio.Protocol):
    def __init__(self):
        self.ready = asyncio.Event()
        self.ready.set()
        self.error = None

    def pause_writing(self):
        self.ready.clear()

    def resume_writing(self):
        self.ready.set()

    def connection_lost(self, exc):
        self.error = exc or BrokenPipeError("Broker peer input closed")
        self.ready.set()


class _PipeWriter:
    def __init__(self, transport, protocol):
        self.transport, self.protocol = transport, protocol

    def write(self, data):
        if self.protocol.error is not None:
            raise self.protocol.error
        self.transport.write(data)

    async def drain(self):
        # Let a failed immediate write deliver connection_lost before success.
        await asyncio.sleep(0)
        await self.protocol.ready.wait()
        if self.protocol.error is not None:
            raise self.protocol.error

    def close(self):
        if not self.transport.is_closing():
            self.transport.abort()


class AsyncPeerBroker:
    """One attempt's async composition and bounded launch/control resources.

    One launch worker serializes accepted starts (at most eight pending). Peer
    receipt work cannot occupy the separate worker reserved for whole-attempt
    revocation. IO uses event-loop pipes, not blocking reader threads.
    """

    def __init__(self, broker):
        self.broker = broker
        self._launch_pool = ThreadPoolExecutor(
            1, thread_name_prefix="researcher-launch"
        )
        self._peer_pool = ThreadPoolExecutor(
            1, thread_name_prefix="researcher-peer-close"
        )
        self._stop_pool = ThreadPoolExecutor(1, thread_name_prefix="researcher-stop")
        self._pending = set()
        self._peer_pending = set()
        self._endpoints = []
        self._entered = False
        self._closing = None

    async def __aenter__(self):
        if self._entered or self._closing is not None:
            raise RuntimeError("Async broker scope cannot reopen")
        self._entered = True
        return self

    async def __aexit__(self, *_):
        await self.aclose()

    def peer(self, registry, peer_id, *, operation_key, code):
        return self._endpoint(registry, peer_id, operation_key, code=code)

    def command(self, registry, peer_id, *, operation_key, asset):
        return self._endpoint(
            registry, peer_id, operation_key, asset=asset, command_only=True
        )

    def native(
        self,
        registry,
        peer_id,
        *,
        operation_key,
        asset,
        network=None,
        egress=None,
        host_tools=False,
        code_host=None,
        native_state=None,
    ):
        return self._endpoint(
            registry,
            peer_id,
            operation_key,
            asset=asset,
            network=network,
            egress=egress,
            host_tools=host_tools,
            code_host=code_host,
            native_state=native_state,
        )

    def ken(
        self,
        registry,
        peer_id,
        *,
        operation_key,
        installation,
        model_cache=None,
        mode="mcp",
    ):
        return self._endpoint(
            registry,
            peer_id,
            operation_key,
            ken=installation,
            model_cache=model_cache,
            ken_mode=mode,
        )

    def _endpoint(
        self,
        registry,
        peer_id,
        operation_key,
        *,
        code=None,
        asset=None,
        network=None,
        egress=None,
        ken=None,
        model_cache=None,
        ken_mode="mcp",
        host_tools=False,
        code_host=None,
        native_state=None,
        command_only=False,
    ):
        if not self._entered or self._closing is not None:
            raise AuthorityConflict("Async broker is not admitted")
        if len(self._endpoints) >= 128:
            raise AuthorityBusy("Attempt transport history capacity reached")
        endpoint = BrokerEndpoint(
            self,
            registry,
            peer_id,
            operation_key,
            code,
            asset,
            network,
            egress,
            ken=ken,
            model_cache=model_cache,
            ken_mode=ken_mode,
            host_tools=host_tools,
            code_host=code_host,
            native_state=native_state,
            command_only=command_only,
        )
        self._endpoints.append(endpoint)
        return endpoint

    async def _start(self, endpoint):
        if self._closing is not None:
            raise AuthorityConflict("Async broker admission withdrawn")
        if len(self._pending) >= 8:
            raise AuthorityBusy("Async broker launch queue full")
        loop = asyncio.get_running_loop()
        if endpoint.ken is not None:
            start = self.broker.run_ken
            payload = {
                "installation": endpoint.ken,
                "model_cache": endpoint.model_cache,
                "mode": endpoint.ken_mode,
            }
        elif endpoint.asset is not None:
            start = (
                self.broker.run_command
                if endpoint.command_only
                else self.broker.run_native
            )
            payload = {"asset": endpoint.asset}
        else:
            start = self.broker.run_peer
            payload = {"code": endpoint.code}
        if endpoint.network is not None:
            payload["network"] = endpoint.network
        if endpoint.egress is not None:
            payload["egress"] = endpoint.egress
        if endpoint.host_tools is not False:
            payload["host_tools"] = endpoint.host_tools
        if endpoint.code_host is not None:
            payload["code_host"] = endpoint.code_host
        if endpoint.native_state is not None:
            payload["native_state"] = endpoint.native_state
        future = loop.run_in_executor(
            self._launch_pool,
            lambda: start(
                endpoint.registry,
                endpoint.peer_id,
                operation_key=endpoint.operation_key,
                **payload,
            ),
        )
        self._pending.add(future)

        def observed(done):
            self._pending.discard(done)
            if not done.cancelled():
                done.exception()

        future.add_done_callback(observed)
        try:
            result = await asyncio.shield(future)
        except asyncio.CancelledError:
            # This is memory-only and never waits behind publication or SQL.
            self.broker.withdraw()

            def discard(done):
                # The completion observer may already have removed this future
                # from _pending before cancellation resumes us. No caller can
                # receive these data FDs, even when birth completed successfully.
                if not done.cancelled() and done.exception() is None:
                    child = done.result().child
                    if child is not None:
                        child.close_handles()

            future.add_done_callback(discard)
            await self.aclose()
            raise
        if self._closing is not None:
            if result.child is not None:
                result.child.close_handles()
            raise AuthorityConflict("Async broker withdrew during start")
        return result

    async def _close_peer(self, operation_id):
        if self._closing is not None:
            # The whole-attempt closure covers this peer. Never enqueue onto a
            # retired executor or wait on endpoint tasks from owner shutdown.
            await asyncio.shield(self._closing)
            return

        def close():
            receipt = self.broker.close_peer(operation_id)
            self.broker.project_closed(operation_id=operation_id)
            return receipt

        future = asyncio.get_running_loop().run_in_executor(self._peer_pool, close)
        self._peer_pending.add(future)

        def observed(done):
            self._peer_pending.discard(done)
            if not done.cancelled():
                done.exception()

        future.add_done_callback(observed)
        return await asyncio.shield(future)

    async def aclose(self):
        if self._closing is None:
            self.broker.withdraw()
            self._closing = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._closing)

    async def _shutdown(self):
        pending = list(self._pending)
        error = None
        try:
            try:
                await asyncio.get_running_loop().run_in_executor(
                    self._stop_pool, self.broker.revoke
                )
            except (OSError, RuntimeError, TimeoutError) as exc:
                error = exc
            results = await asyncio.gather(
                *(asyncio.shield(f) for f in (*pending, *self._peer_pending)),
                return_exceptions=True,
            )
            # A start completed during withdrawal may never reach its caller.
            for result in results[: len(pending)]:
                if not isinstance(result, BaseException) and result.child is not None:
                    result.child.close_handles()
            for endpoint in self._endpoints:
                endpoint._close_io()
            if error is not None:
                # Safe receipt/closure retry after constructors drain; never G.
                await asyncio.get_running_loop().run_in_executor(
                    self._stop_pool, self.broker.revoke
                )
            # Source-local SQL is never on the physical Stop path. Derive all
            # reserved operations, including cancelled/undelivered endpoints.
            await asyncio.get_running_loop().run_in_executor(
                self._peer_pool, self.broker.project_closed
            )
        finally:
            for endpoint in self._endpoints:
                endpoint._close_io()
            self._entered = False
            for pool in (self._launch_pool, self._peer_pool, self._stop_pool):
                pool.shutdown(wait=False, cancel_futures=False)


class BrokerEndpoint:
    """A single post-gate connection; cannot reopen or replay a start receipt."""

    def __init__(
        self,
        owner,
        registry,
        peer_id,
        operation_key,
        code,
        asset=None,
        network=None,
        egress=None,
        *,
        ken=None,
        model_cache=None,
        ken_mode="mcp",
        host_tools=False,
        code_host=None,
        native_state=None,
        command_only=False,
    ):
        self.owner, self.registry, self.peer_id = owner, registry, peer_id
        self.operation_key, self.code = operation_key, code
        self.asset = asset
        self.network = network
        self.egress = egress
        self.ken, self.model_cache, self.ken_mode = ken, model_cache, ken_mode
        self.host_tools = host_tools
        self.code_host = code_host
        self.native_state = native_state
        self.command_only = command_only
        self.stdin = self.stdout = self.stderr = None
        self._raw = None
        self._operation = None
        self._opened = False
        self._closing = None
        self._transports = []

    async def open(self, *, limit):
        if self._opened:
            raise RuntimeError("Broker endpoint cannot reopen")
        self._opened = True
        result = await self.owner._start(self)
        if not result.fresh or result.child is None:
            raise AuthorityConflict(
                "Existing start receipt has no new transport; reconcile it"
            )
        self._raw = result.child
        self._operation = result.operation_id
        loop = asyncio.get_running_loop()
        try:
            for name in ("stdout", "stderr"):
                reader = asyncio.StreamReader(limit=limit)
                protocol = asyncio.StreamReaderProtocol(reader)
                stream = getattr(self._raw, name)
                os.set_blocking(stream.fileno(), False)
                transport, _ = await loop.connect_read_pipe(
                    lambda p=protocol: p, stream
                )
                self._transports.append(transport)
                setattr(self, name, reader)
            protocol = _WriteProtocol()
            os.set_blocking(self._raw.stdin.fileno(), False)
            transport, _ = await loop.connect_write_pipe(
                lambda: protocol, self._raw.stdin
            )
            self._transports.append(transport)
            transport.set_write_buffer_limits(high=limit, low=max(1, limit // 2))
            self.stdin = _PipeWriter(transport, protocol)
            return self
        except BaseException:
            await self.aclose(timeout=3)
            raise

    def _close_io(self):
        transports, self._transports = self._transports, []
        for transport in transports:
            if transport.is_closing():
                continue
            if isinstance(transport, asyncio.WriteTransport):
                # A graceful close can leave a pending writer registered. Remove
                # it before releasing the FD, which another file could reuse.
                transport.abort()
            else:
                transport.close()
        if self._raw is not None:
            self._raw.close_handles()

    async def aclose(self, *, timeout):
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
        async with asyncio.timeout(timeout):
            await asyncio.shield(self._closing)

    async def _shutdown(self):
        self._close_io()
        if self._operation is not None:
            return await self.owner._close_peer(self._operation)
