"""Finite owner source workers: explicit requests, scoped Stop and application shutdown reuse the original administrative Git executor."""

import asyncio
import json
from contextlib import contextmanager
from dataclasses import dataclass

from backend.git.source_executor import execute_source, reconcile_source
from backend.git.source_operations import SourceLease, SourceOperations, SourceRequest
from backend.git.source_remote import SourceHTTPControl, execute_remote_source
from backend.runtime.broker_stdio import AsyncPeerBroker
from backend.runtime.contracts import RunConflict
from backend.runtime.owned_runtime import _settled


@dataclass(frozen=True)
class SourceControl:
    """Immutable original administrative lease and actual Git broker or HTTP client, captured before its first effect."""

    lease: SourceLease
    operation_id: str
    owner: AsyncPeerBroker | SourceHTTPControl

    def matches(self, operation_id, fence):
        """A browser observation can withdraw only this original owner; a later observation fence never inherits an older Stop."""
        return self.operation_id == operation_id and self.lease.fence == fence

    def withdraw(self):
        """Reuse the original broker's reserved Stop resources and retirement future; metadata is deliberately outside this physical path."""
        return self.owner.withdraw()


class SourceService:
    """Own actual administrative worker handles without inventing native turns or replaying interrupted writes after restart."""

    def __init__(self, parent):
        """Reuse the serving runtime's original host configuration, store, owner lock and kernel broker boundaries."""
        from backend.runtime.owned_runtime import OwnedCodexRuntime

        if not isinstance(parent.runtime, OwnedCodexRuntime):
            raise RunConflict('La preparación requiere el runtime local con propiedad de procesos configurada.')
        self.parent = parent
        self.records = SourceOperations(parent.store, workspaces=parent.workspaces, control_root=parent.control_root)
        self._workers = {}
        self._owners = {}
        self._pending_stops = {}
        self._lock = asyncio.Lock()
        self._closing = False

    def _configuration(self):
        """Pass only actual host-owned launcher settings; no model, user argv or caller credential supplies execution authority."""
        runtime = self.parent.runtime
        return {'authority':runtime.authority, 'cgroup_parent':runtime.cgroup_parent, 'broker_limits':runtime.broker_limits}

    def _capture_owner(self, project, key, executor):
        """Bind actual executor ownership before G, conditionally withdrawing a late handoff only after its original requested identity matches."""
        control = SourceControl(executor.lease, executor.operation_id, executor.owner)
        if (control.lease.project_id, control.lease.operation_key) != (project, key):
            raise RunConflict('El ejecutor no corresponde a esta preparación original.')
        self._owners[(project,key)] = control
        if self._closing or self.parent._source_project_stops.get(project) or (project,key,control.operation_id,control.lease.fence) in self._pending_stops:
            control.withdraw()
            raise asyncio.CancelledError

    def _withdraw(self, project, key, task):
        """Withdraw the already-captured original owner before cancelling its worker; late owners are held by the same local admission fuse."""
        control = self._owners.get((project,key))
        if control is not None:
            control.withdraw()
        if task is not None and not task.done() and not task.cancelling():
            task.cancel()

    def view(self, project, key):
        """Expose saved phase and actual local worker observation; a stopped local worker never proves remote rollback or fresh Git health."""
        row = self.records.read(project, key)
        value = SourceOperations.summaries(json.dumps({'owner_repository_operations_v1':{key:row}}))[0]
        worker = self._workers.get((project,key))
        closure = row.get('closure') or {}
        value.update(project_id=project, request={'remote_server':None,**row['request']}, issue=row.get('issue'), worker_active=bool(worker and not worker.done()), receipt=row.get('receipt'),
                     local_closure='confirmed' if closure.get('domain_removed') or (row.get('http_client') or {}).get('state')=='closed' or (row['status']=='stopped' and row['owner'] is None) else 'unconfirmed',
                     message='Estado guardado. Una observación Git corresponde a su momento; no comprueba el estado actual. Una carpeta parcial se conserva para revisión.')
        if row['request']['mode'] == 'create_remote':
            value['message'] = 'Crear un remoto vacío es una operación separada. El cierre del cliente local no detiene necesariamente al servidor. Observar sólo consulta la creación original; no vuelve a enviarla. No se creó una carpeta local ni se publicó código.'
        return value

    async def submit(self, project, key, request):
        """Persist exact owner intent before scheduling one bounded worker; an original replay returns history and never restarts a stopped or uncertain effect."""
        async with self._lock:
            self.parent._accepting()
            if self._closing or self.parent._source_project_stops.get(project) or self.parent._legacy_controller_active(project):
                raise RunConflict('El dueño del proyecto no admite nuevas preparaciones; conserva y revisa el trabajo existente.')
            transport = self.parent.runtime.remote_transport
            if request.mode == 'create_remote' and (transport is None or transport.api_base != request.remote_server):
                raise RunConflict('Elige el servidor remoto configurado del host; no se enviaron credenciales ni se creó un remoto en otro servidor.')
            identity = transport.identity if transport is not None and (request.use_configured_auth or request.mode=='create_remote') else None
            row = await _settled(self.records.prepare, project, key, request, remote_identity=identity)
            if row['status'] == 'planned' and (project,key) not in self._workers:
                if sum(not task.done() for task in self._workers.values()) >= 2:
                    raise RunConflict('Hay dos preparaciones activas. La intención se conservó sin iniciar Git; vuelve a consultar antes de iniciarla.')
                self._workers = {k:v for k,v in self._workers.items() if not v.done()}
                self._workers[(project,key)] = asyncio.create_task(self._run(project,key), name='researcher-source-'+row['operation_id'])
            return await _settled(self.view, project, key)

    async def reconcile(self, project, key):
        """Start only explicit readonly reconciliation of the retained operation; no implicit clone, initialization, commit or credentialed write is replayed."""
        async with self._lock:
            self.parent._accepting()
            if self._closing or self.parent._source_project_stops.get(project) or self.parent._legacy_controller_active(project):
                raise RunConflict('El proyecto no admite reconciliación mientras otro dueño conserve actividad.')
            row = await _settled(self.records.read, project, key)
            live = self._workers.get((project,key))
            if live and not live.done():
                raise RunConflict('El trabajador original sigue activo. Obsérvalo o detenlo antes de reconciliar.')
            if row['status'] != 'completed':
                if sum(not task.done() for task in self._workers.values()) >= 2:
                    raise RunConflict('Espera al cierre de otra preparación antes de reconciliar.')
                self._workers[(project,key)] = asyncio.create_task(self._run(project,key,observe=True), name='researcher-source-observe-'+row['operation_id'])
            return await _settled(self.view, project, key)

    async def _run(self, project, key, *, observe=False):
        """Keep executor teardown in its owning task and retain failures as saved uncertainty; raw transport errors and secrets never enter the owner response."""
        try:
            def on_owner(executor):
                """Capture this task's real administrative broker without accepting a caller-supplied grant, PID, namespace or fence."""
                self._capture_owner(project, key, executor)

            row = await _settled(self.records.read, project, key)
            if row['request']['mode'] == 'create_remote':
                await execute_remote_source(self.records, project, key, self.parent.runtime.remote_transport, observe=observe, on_owner=on_owner)
            elif observe:
                await reconcile_source(self.records, project, key, on_owner=on_owner, **self._configuration())
            else:
                runtime = self.parent.runtime
                row = await _settled(self.records.read, project, key)
                transport = runtime.remote_transport
                network = transport.network if row['request']['use_configured_auth'] and transport is not None else runtime.network
                await execute_source(self.records, project, key, source_network=network, source_transport=transport, on_owner=on_owner, **self._configuration())
        except asyncio.CancelledError:
            # Executor records original uncertainty and drains its physical scope.
            # Reading a failed operation never starts another effect.
            pass
        except Exception:
            await _settled(self.records.note_failure, project, key)
        finally:
            try:
                await _settled(self.records.settle_stop, project, key)
            finally:
                self._owners.pop((project,key), None)

    async def wait(self, project, key):
        """Wait for the exact current local handle, without replaying work if its process or application has gone away."""
        task = self._workers.get((project,key))
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if not task.cancelled():
                    raise

    def validate_stop_target(self, project, key, *, operation_id, fence):
        """Reject a mismatching captured original before any physical withdrawal; absent local ownership is not proof of remote or durable closure."""
        control = self._owners.get((project,key))
        if control is not None and not control.matches(operation_id, fence):
            raise RunConflict('El intento observado cambió. Consulta la operación antes de detenerla.')

    @contextmanager
    def stop_scope(self, project, key, *, operation_id, fence):
        """Hold one conditional original Stop through either individual or exact project persistence; it can withdraw only a matching real owner."""
        self.validate_stop_target(project, key, operation_id=operation_id, fence=fence)
        task = self._workers.get((project,key))
        control = self._owners.get((project,key))
        target = (project,key,operation_id,fence)
        pending = task is not None and not task.done()
        if pending and len(self._pending_stops) >= 32 and target not in self._pending_stops:
            raise RunConflict('Hay demasiadas solicitudes Stop pendientes; no se omitió una identidad para continuar.')
        if pending:
            self._pending_stops[target] = self._pending_stops.get(target,0) + 1
        try:
            if control is not None:
                self._withdraw(project, key, task)
            yield
        finally:
            if pending:
                remaining = self._pending_stops[target] - 1
                if remaining:
                    self._pending_stops[target] = remaining
                else:
                    del self._pending_stops[target]

    async def stop(self, project, key, *, operation_id, fence):
        """Withdraw an exact observed original owner before SQL, then persist intent and drain its actual worker without retargeting a new fence."""
        with self.stop_scope(project, key, operation_id=operation_id, fence=fence):
            async with self._lock:
                row = await _settled(self.records.request_stop, project, key, operation_id=operation_id, fence=fence)
                task = self._workers.get((project,key))
                if row.get('stop_requested'):
                    self._withdraw(project, key, task)
            if task is not None:
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    if not task.cancelled():
                        raise
            await _settled(self.records.settle_stop, project, key)
            return await _settled(self.view, project, key)

    def withdraw_project(self, project):
        """Withdraw only this application's actual administrative workers of the selected project before bodyless project Stop can wait on SQL."""
        for (owner_project,key), task in list(self._workers.items()):
            if owner_project == project and not task.done():
                self._withdraw(project, key, task)

    async def drain_admission(self):
        """Drain accepted source handoffs while the project or application fuse keeps late owners from receiving G."""
        async with self._lock:
            pass

    async def stop_project(self, project):
        """Withdraw all currently recorded administrative work for the legacy bodyless project Stop, preserving uncertain original effects when no live handle exists."""
        result = []
        for row in await _settled(self.records.list, project):
            if row['status'] not in ('completed','rejected','stopped'):
                row = await _settled(self.records.request_project_stop, project, row['operation_key'], operation_id=row['operation_id'])
                result.append(await self.stop(project,row['operation_key'],operation_id=row['operation_id'],fence=row['fence']))
        return result

    async def close(self):
        """Withdraw all owned source jobs before the runtime releases its exclusive store owner lock; cancellation is issued once and closure is drained."""
        self._closing = True
        for (project,key), task in list(self._workers.items()):
            self._withdraw(project, key, task)
        async with self._lock:
            workers = list(self._workers.items())
        async def withdraw(project, key, task):
            """Drain the original physical handle even if persistence is unavailable during shutdown; no other job is skipped after an error."""
            try:
                row = await _settled(self.records.read, project, key)
                await self.stop(project, key, operation_id=row['operation_id'], fence=row['fence'])
            finally:
                if not task.done() and not task.cancelling():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        results = await asyncio.gather(*(withdraw(project,key,task) for (project,key),task in workers if not task.done()), return_exceptions=True)
        if any(isinstance(result, BaseException) for result in results):
            raise RunConflict('Se drenaron los trabajadores de fuentes, pero falta reconciliar su registro de cierre.')
