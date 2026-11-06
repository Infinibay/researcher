"""Finite owner source workers: explicit requests, scoped Stop and application shutdown reuse the original administrative Git executor."""

import asyncio
import json

from backend.git.source_executor import execute_source, reconcile_source
from backend.git.source_operations import SourceOperations
from backend.runtime.contracts import RunConflict
from backend.runtime.owned_runtime import _settled


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
        self._lock = asyncio.Lock()
        self._closing = False

    def _configuration(self):
        """Pass only actual host-owned launcher settings; no model, user argv or caller credential supplies execution authority."""
        runtime = self.parent.runtime
        return {'authority':runtime.authority, 'cgroup_parent':runtime.cgroup_parent, 'broker_limits':runtime.broker_limits}

    def view(self, project, key):
        """Expose saved phase and actual local worker observation; a stopped local worker never proves remote rollback or fresh Git health."""
        row = self.records.read(project, key)
        value = SourceOperations.summaries(json.dumps({'owner_repository_operations_v1':{key:row}}))[0]
        worker = self._workers.get((project,key))
        closure = row.get('closure') or {}
        value.update(project_id=project, request=row['request'], issue=row.get('issue'), worker_active=bool(worker and not worker.done()), receipt=row.get('receipt'),
                     local_closure='confirmed' if closure.get('domain_removed') or (row['status']=='stopped' and row['owner'] is None) else 'unconfirmed',
                     message='Estado guardado. Una observación Git corresponde a su momento; no comprueba el estado actual. Una carpeta parcial se conserva para revisión.')
        return value

    async def submit(self, project, key, request):
        """Persist exact owner intent before scheduling one bounded worker; an original replay returns history and never restarts a stopped or uncertain effect."""
        async with self._lock:
            self.parent._accepting()
            if self._closing or self.parent._legacy_controller_active(project):
                raise RunConflict('El dueño del proyecto no admite nuevas preparaciones; conserva y revisa el trabajo existente.')
            if request.mode == 'create_remote':
                raise RunConflict('La creación remota explícita aún no está disponible. No se inicializó ni publicó una fuente como sustitución.')
            transport = self.parent.runtime.remote_transport
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
            if self._closing or self.parent._legacy_controller_active(project):
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
            if observe:
                await reconcile_source(self.records, project, key, **self._configuration())
            else:
                runtime = self.parent.runtime
                row = await _settled(self.records.read, project, key)
                transport = runtime.remote_transport
                network = transport.network if row['request']['use_configured_auth'] and transport is not None else runtime.network
                await execute_source(self.records, project, key, source_network=network, source_transport=transport, **self._configuration())
        except asyncio.CancelledError:
            # Executor records original uncertainty and drains its physical scope.
            # Reading a failed operation never starts another effect.
            pass
        except Exception:
            await _settled(self.records.note_failure, project, key)
        finally:
            await _settled(self.records.settle_stop, project, key)

    async def wait(self, project, key):
        """Wait for the exact current local handle, without replaying work if its process or application has gone away."""
        task = self._workers.get((project,key))
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if not task.cancelled():
                    raise

    async def stop(self, project, key, *, operation_id, fence):
        """Withdraw exact observed admission before cancelling its original local worker; preserve unconfirmed closure if that handle is absent."""
        async with self._lock:
            row = await _settled(self.records.request_stop, project, key, operation_id=operation_id, fence=fence)
            task = self._workers.get((project,key))
            if row.get('stop_requested') and task is not None and not task.done() and not task.cancelling():
                task.cancel()
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if not task.cancelled():
                    raise
        await _settled(self.records.settle_stop, project, key)
        return await _settled(self.view, project, key)

    async def stop_project(self, project):
        """Withdraw all currently recorded administrative work for the legacy bodyless project Stop, preserving uncertain original effects when no live handle exists."""
        result = []
        for row in await _settled(self.records.list, project):
            if row['status'] not in ('completed','rejected','stopped'):
                result.append(await self.stop(project,row['operation_key'],operation_id=row['operation_id'],fence=row['fence']))
        return result

    async def close(self):
        """Withdraw all owned source jobs before the runtime releases its exclusive store owner lock; cancellation is issued once and closure is drained."""
        async with self._lock:
            self._closing = True
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
