"""Keep published Ken's index aligned with an owned mutable development copy.

Source hashes are computed inside readonly owned peers, never by following
model-controlled host paths. A changed copy closes the old MCP peer before
re-preparing and reopening it, keeping model memory within the shared domain.
This is a retrieval consistency check, not an atomic delivered code candidate.
"""

import asyncio
import json
from contextlib import AsyncExitStack
from functools import partial

import anyio

from backend.runtime.broker_mcp import broker_mcp
from backend.runtime.business_mediation import _failure, catalog_digest
from backend.runtime.ken_mediation import KenNotReady, KenTools

_FINGERPRINT = """import hashlib,json,os,stat,sys
from pathlib import Path
root=Path('/run/researcher-source');digest=hashlib.sha256();count=total=0
def add(value):
 digest.update(len(value).to_bytes(8,'big'));digest.update(value)
try:
 for parent,dirs,files in os.walk(root,followlinks=False):
  if Path(parent)==root:dirs[:]=[name for name in dirs if name not in ('.ken','.git')]
  dirs.sort();files.sort()
  for name in dirs+files:
   path=Path(parent)/name;info=path.lstat();count+=1
   if count>20000:raise ValueError('file budget')
   add(os.fsencode(str(path.relative_to(root))));add(str(info.st_mode).encode())
   if stat.S_ISLNK(info.st_mode):add(os.fsencode(os.readlink(path)))
   elif stat.S_ISREG(info.st_mode):
    size=0;content=hashlib.sha256()
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
     while chunk:=stream.read(65536):
      size+=len(chunk);total+=len(chunk)
      if total>256*1024**2:raise ValueError('byte budget')
      content.update(chunk)
    add(str(size).encode());add(content.digest())
   elif not stat.S_ISDIR(info.st_mode):raise ValueError('special source file')
 print(json.dumps({'sha256':digest.hexdigest(),'entries':count,'bytes':total}))
except BaseException:
 print(json.dumps({'error':'source revision unavailable'}));sys.exit(1)
"""


async def _settled(function, *args):
    """Drain host SQL work before an owning scope can close or retire its attempt."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            with anyio.CancelScope(shield=True):
                await task
        finally:
            raise


class DevelopmentKen:
    """Own MCP refresh and bounded source revisions for one original development attempt."""

    def __init__(self, endpoint, *, prepare, validate, quiet, active):
        """Retain host-only factories; models cannot choose paths, profiles or executables."""
        self.endpoint = endpoint
        self.prepare, self.validate, self.quiet, self.active = (
            prepare,
            validate,
            quiet,
            active,
        )
        self._scope = AsyncExitStack()
        self._lock = asyncio.Lock()
        self._sequence = 0
        self._revision = None
        self.catalog = []
        self._requests = asyncio.Queue(8)
        self._worker = None
        self._closing = None
        self._accepting = False

    async def __aenter__(self):
        """Create the one SDK owner task and await its initial source/catalog admission."""
        self._ready = asyncio.get_running_loop().create_future()
        self._ready.add_done_callback(
            lambda done: done.exception() if not done.cancelled() else None
        )
        self._worker = asyncio.create_task(self._serve())
        try:
            await asyncio.shield(self._ready)
            return self
        except BaseException:
            with anyio.CancelScope(shield=True):
                self.endpoint.owner.broker.withdraw()
                await self.endpoint.owner.aclose()
                await self._shutdown()
            raise

    async def __aexit__(self, *exc):
        """Join original ownership without exiting another task's AnyIO cancel scope."""
        if exc and exc[0] is not None:
            with anyio.CancelScope(shield=True):
                self.endpoint.owner.broker.withdraw()
                await self.endpoint.owner.aclose()
        if self._closing is None:
            self._closing = asyncio.create_task(self._shutdown())
        try:
            await asyncio.shield(self._closing)
        except asyncio.CancelledError:
            with anyio.CancelScope(shield=True):
                self.endpoint.owner.broker.withdraw()
                await self.endpoint.owner.aclose()
                await self._closing
            raise

    async def _shutdown(self):
        """Drain requests and ask the original task to close its own SDK scopes."""
        if self._worker is not None and not self._worker.done():
            await self._requests.put(("close", None, None))
        if self._worker is not None:
            await asyncio.gather(self._worker, return_exceptions=True)

    async def _serve(self):
        """Enter, use, refresh and exit all SDK contexts in the same owning task."""
        try:
            self._peer = await self._scope.enter_async_context(
                broker_mcp(self.endpoint)
            )
            self._tools = await KenTools.connect(self._peer, active=self.active)
            self.catalog = self._tools.catalog
            self._revision = await self._fingerprint()
            self._accepting = True
            self._ready.set_result(None)
            while True:
                kind, arguments, future = await self._requests.get()
                if kind == "close":
                    break
                try:
                    result = (
                        await self._check_ready()
                        if kind == "ready"
                        else await self._call(arguments)
                    )
                except BaseException as error:
                    if not future.done():
                        future.set_exception(
                            KenNotReady("Ken owner interrupted; do not replay effects")
                            if isinstance(error, asyncio.CancelledError)
                            else error
                        )
                    if isinstance(error, asyncio.CancelledError):
                        raise
                else:
                    if not future.done():
                        future.set_result(result)
        except BaseException as error:  # noqa: BLE001 -- hand startup failure to its waiter before draining SDK ownership.
            if not self._ready.done():
                self._ready.set_exception(error)
        finally:
            self._accepting = False
            try:
                await self._scope.aclose()
            finally:
                while not self._requests.empty():
                    _, _, future = self._requests.get_nowait()
                    if future is not None and not future.done():
                        future.set_exception(
                            KenNotReady("Ken owner closed; do not replay effects")
                        )

    async def _request(self, kind, arguments=None):
        """Queue bounded work without moving SDK ownership into a model tool callback."""
        if (
            not self._accepting
            or self._closing is not None
            or self._worker is None
            or self._worker.done()
        ):
            raise KenNotReady("Development Ken owner is closed")
        future = asyncio.get_running_loop().create_future()
        future.add_done_callback(
            lambda done: done.exception() if not done.cancelled() else None
        )
        try:
            self._requests.put_nowait((kind, arguments, future))
        except asyncio.QueueFull:
            raise KenNotReady("Development Ken request capacity reached") from None
        return await asyncio.shield(future)

    @property
    def catalog_hash(self):
        """Return the initial immutable model-visible capability fingerprint."""
        return catalog_digest(self.catalog)

    async def require_ready(self):
        """Keep command read/cancel usable while an active writer prevents code indexing."""
        return await self._request("ready")

    async def _check_ready(self):
        """Check capability availability inside its original SDK task."""
        current = await KenTools.connect(self._peer, active=self.active)
        if current.catalog_hash != self.catalog_hash:
            raise KenNotReady("Development Ken catalog changed")

    async def call(self, params):
        """Request a source-consistent query without retrying unknown or memory-writing effects."""
        return await self._request("call", params)

    async def _fingerprint(self):
        """Hash the actual copy through a bounded readonly kernel peer and require physical closure."""
        if not self.active():
            raise KenNotReady("Attempt ended before source revision")
        owner, registry = self.endpoint.owner, self.endpoint.registry
        lease = await _settled(self._lease)
        peer = await _settled(registry.prepare, lease, "command")
        self._sequence += 1
        endpoint = owner.peer(
            registry,
            peer,
            operation_key="ken-source-revision-" + str(self._sequence),
            code=_FINGERPRINT,
        )
        receipt = None
        try:
            async with asyncio.timeout(10):
                await endpoint.open(limit=4096)
                output, error = await asyncio.gather(
                    endpoint.stdout.read(2048), endpoint.stderr.read(2048)
                )
                await asyncio.get_running_loop().run_in_executor(
                    owner._peer_pool, partial(endpoint._raw.wait, timeout=5)
                )
        finally:
            with anyio.CancelScope(shield=True):
                receipt = await endpoint.aclose(timeout=5)
        if (
            not receipt
            or receipt.get("execution_closed") is not True
            or receipt.get("exit_code") != 0
            or error
        ):
            raise KenNotReady("Private source revision is unavailable or not closed")
        try:
            result = json.loads(output)
            revision = result["sha256"]
            if len(revision) != 64 or any(
                c not in "0123456789abcdef" for c in revision
            ):
                raise ValueError("Invalid revision")
        except (ValueError, KeyError, TypeError):
            raise KenNotReady("Invalid private source revision receipt") from None
        return revision

    def _lease(self):
        """Read the original peer identity off the event loop without treating a replaced DB as authority."""
        registry = self.endpoint.registry
        with registry.runs._transaction() as conn:
            peer = registry._row(conn, self.endpoint.peer_id)
            registry._check_origin(peer)
            return registry._lease(conn, peer)[1]

    async def _call(self, params):
        """Refresh changed source before code queries; never replay memory mutations or unknown transport effects."""
        async with self._lock:
            if not self.active():
                return _failure("Attempt authority ended; do not replay effects")
            if params.get("tool") not in ("ken_find", "ken_read", "ken_related"):
                return await self._tools.call(params)
            if not await self.quiet():
                return _failure(
                    "A private writer is still active. Read or cancel its job before querying code with Ken."
                )
            revision = await self._fingerprint()
            if revision != self._revision:
                await self._scope.aclose()
                endpoint, prepared = await self.prepare()
                if (
                    endpoint.owner is not self.endpoint.owner
                    or endpoint.ken != self.endpoint.ken
                ):
                    raise KenNotReady(
                        "Ken refresh differs from its original owner or installation"
                    )
                await asyncio.to_thread(self.validate, endpoint, prepared)
                self.endpoint = endpoint
                self._peer = await self._scope.enter_async_context(broker_mcp(endpoint))
                current = await KenTools.connect(self._peer, active=self.active)
                if current.catalog_hash != self.catalog_hash:
                    raise KenNotReady("Refreshed Ken catalog changed")
                self._tools = current
                self._revision = revision
            result = await self._tools.call(params)
            if await self._fingerprint() != revision:
                self._revision = None
                return _failure(
                    "The private copy changed during the query. Its result is not a stable code snapshot; read or stop the writer before querying again."
                )
            return result
