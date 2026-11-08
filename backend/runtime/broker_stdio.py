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
    """Translate pipe backpressure and connection loss into an event that lets writers distinguish
    writable transport from a failed connection.
    """
    def __init__(self):
        """Begin with writable transport state and no observed connection error."""
        self.ready = asyncio.Event()
        self.ready.set()
        self.error = None

    def pause_writing(self):
        """Pause drain observers until the event loop reports that transport buffering is writable
        again.
        """
        self.ready.clear()

    def resume_writing(self):
        """Wake drain observers after transport backpressure subsides."""
        self.ready.set()

    def connection_lost(self, exc):
        """Retain a connection error and wake blocked writers instead of letting a closed input appear
        writable.
        """
        self.error = exc or BrokenPipeError("Broker peer input closed")
        self.ready.set()


class _PipeWriter:
    """Adapt the event-loop write transport to the bounded RPC writer interface without becoming a
    second process owner.
    """
    def __init__(self, transport, protocol):
        """Bind the existing pipe transport to its backpressure/error protocol."""
        self.transport, self.protocol = transport, protocol

    def write(self, data):
        """Reject an already failed input before handing bytes to the event-loop transport; buffering
        is not peer acknowledgement.
        """
        if self.protocol.error is not None:
            raise self.protocol.error
        self.transport.write(data)

    async def drain(self):
        # Let a failed immediate write deliver connection_lost before success.
        """Yield for immediate connection errors, wait for writability and expose transport loss before
        reporting a completed drain.
        """
        await asyncio.sleep(0)
        await self.protocol.ready.wait()
        if self.protocol.error is not None:
            raise self.protocol.error

    def close(self):
        """Abort the write transport so a pending writer cannot retain a descriptor registration after
        owner cleanup.
        """
        if not self.transport.is_closing():
            self.transport.abort()


class AsyncPeerBroker:
    """One attempt's async composition and bounded launch/control resources.

    One launch worker serializes accepted starts (at most eight pending). Peer
    receipt work cannot occupy the separate worker reserved for whole-attempt
    revocation. IO uses event-loop pipes, not blocking reader threads.
    """

    def __init__(self, broker):
        """Configure separate bounded launch, peer-close and whole-attempt Stop executors around the
        original broker without launching actors.
        """
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
        """Enter one async ownership scope and reject reopening after entry or withdrawal."""
        if self._entered or self._closing is not None:
            raise RuntimeError("Async broker scope cannot reopen")
        self._entered = True
        return self

    async def __aexit__(self, *_):
        """Drain the original broker retirement when its async scope exits."""
        await self.aclose()

    def peer(self, registry, peer_id, *, operation_key, code):
        """Describe one analysis endpoint while leaving reservation, spawning and gate release to the
        original broker.
        """
        return self._endpoint(registry, peer_id, operation_key, code=code)

    def git(self, registry, peer_id, *, operation_key, launch):
        """Create a fixed Git endpoint without admitting arbitrary writable model commands."""
        return self._endpoint(registry, peer_id, operation_key, git_launch=launch)

    def check(self, registry, peer_id, *, operation_key, launch):
        """Describe one fixed host check; the original registry/broker still own admission and G."""
        return self._endpoint(registry, peer_id, operation_key, check_launch=launch)

    def command(self, registry, peer_id, *, operation_key, asset):
        """Describe an account-free command endpoint using the selected executable; no command payload
        is released by this factory.
        """
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
        web_search="disabled",
    ):
        """Describe a native peer with a fixed, manifested discovery policy."""
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
            web_search=web_search,
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
        """Describe a Ken endpoint with its selected installation/cache/mode, deferring actual
        preparation and launch to the broker.
        """
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
        web_search="disabled",
        git_launch=None,
        check_launch=None,
    ):
        """Allocate one non-replayable endpoint while its broker remains admitted."""
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
            web_search=web_search,
            git_launch=git_launch,
            check_launch=check_launch,
        )
        self._endpoints.append(endpoint)
        return endpoint

    async def _start(self, endpoint):
        """Forward the original endpoint policy to the bounded launch worker."""
        if self._closing is not None:
            raise AuthorityConflict("Async broker admission withdrawn")
        if len(self._pending) >= 8:
            raise AuthorityBusy("Async broker launch queue full")
        loop = asyncio.get_running_loop()
        if endpoint.check_launch is not None:
            start = self.broker.run_check
            payload = {"launch": endpoint.check_launch}
        elif endpoint.git_launch is not None:
            start = self.broker.run_git
            payload = {"launch": endpoint.git_launch}
        elif endpoint.ken is not None:
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
        if endpoint.web_search != "disabled":
            payload["web_search"] = endpoint.web_search
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
            """Remove a settled constructor future from pending accounting and consume its exception
            without replaying the launch.
            """
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
                """Close unreachable transport handles after a successful birth whose observer was
                cancelled; physical retirement stays with the original broker.
                """
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
        """Close the original operation through the reserved peer-control worker and project its
        receipt afterward; whole-attempt shutdown keeps its existing owner.
        """
        if self._closing is not None:
            # The whole-attempt closure covers this peer. Never enqueue onto a
            # retired executor or wait on endpoint tasks from owner shutdown.
            await asyncio.shield(self._closing)
            return

        def close():
            """Obtain the physical closure receipt before projecting the same original operation into
            local SQL.
            """
            receipt = self.broker.close_peer(operation_id)
            self.broker.project_closed(operation_id=operation_id)
            return receipt

        future = asyncio.get_running_loop().run_in_executor(self._peer_pool, close)
        self._peer_pending.add(future)

        def observed(done):
            """Remove a completed peer-control future and consume its exception without creating a new
            closure owner.
            """
            self._peer_pending.discard(done)
            if not done.cancelled():
                done.exception()

        future.add_done_callback(observed)
        return await asyncio.shield(future)

    def withdraw(self):
        """Withdraw G synchronously on the owning event loop and start the original physical retirement without awaiting source-local SQL."""
        if self._closing is None:
            self.broker.withdraw()
            self._closing = asyncio.create_task(self._shutdown())
        return self._closing

    async def aclose(self):
        """Drain the single original retirement future; caller cancellation cannot transfer or cancel physical ownership."""
        await asyncio.shield(self.withdraw())

    async def _shutdown(self):
        """Coordinate revocation, constructor draining, unused transport cleanup and later SQL closure
        projection; retries concern closure, never payload execution.
        """
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
        web_search="disabled",
        git_launch=None,
        check_launch=None,
    ):
        """Retain launch arguments and handles for exactly one owned connection."""
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
        self.web_search = web_search
        self.git_launch = git_launch
        self.check_launch = check_launch
        self.stdin = self.stdout = self.stderr = None
        self._raw = None
        self._operation = None
        self._opened = False
        self._closing = None
        self._transports = []

    async def open(self, *, limit):
        """Transfer independent pipe descriptors to the loop and release the originals."""
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
                # Loop transports own their descriptors until asynchronous close
                # completes. Owner retirement must not close those same numbers:
                # uvloop can otherwise close an unrelated, newly reused FD.
                original = getattr(self._raw, name)
                stream = os.fdopen(os.dup(original.fileno()), 'rb')
                original.close()
                os.set_blocking(stream.fileno(), False)
                transport, _ = await loop.connect_read_pipe(
                    lambda p=protocol: p, stream
                )
                self._transports.append(transport)
                setattr(self, name, reader)
            protocol = _WriteProtocol()
            input_stream = os.fdopen(os.dup(self._raw.stdin.fileno()), 'wb')
            # Keeping the original writer alive would prevent EOF at the peer.
            self._raw.stdin.close()
            os.set_blocking(input_stream.fileno(), False)
            transport, _ = await loop.connect_write_pipe(
                lambda: protocol, input_stream
            )
            self._transports.append(transport)
            transport.set_write_buffer_limits(high=limit, low=max(1, limit // 2))
            self.stdin = _PipeWriter(transport, protocol)
            return self
        except BaseException:
            await self.aclose(timeout=3)
            raise

    def _close_io(self):
        """Close loop-owned pipes and separate owner handles without descriptor reuse races."""
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
        """Close through the original process owner and return its physical closure receipt."""
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
        async with asyncio.timeout(timeout):
            return await asyncio.shield(self._closing)

    async def _shutdown(self):
        """Close this endpoint's data pipes and ask its original operation owner for physical closure
        when a launch identity exists.
        """
        self._close_io()
        if self._operation is not None:
            return await self.owner._close_peer(self._operation)
