"""Own explicit retention workers through application shutdown; no model execution, timer-based cleanup or startup replay."""

import asyncio

from backend.runtime.contracts import RunConflict, RunNotFound
from backend.runtime.retention_authority import observed_closure
from backend.runtime.workspace_retention import WorkspaceRetention


class RetentionService:
    """Serialize admission per installation and retain each filesystem worker until its original operation settles."""

    def __init__(self, coordinator):
        """Compose only from actual runtime roots and authority, never from request-supplied paths or closure booleans."""
        self.coordinator=coordinator;self._lock=asyncio.Lock();self._jobs={};self._closing=False
        self.store=WorkspaceRetention(coordinator.store,coordinator.control_root,coordinator.workspaces.root,
                                      closed=lambda conn,row:observed_closure(coordinator.runtime.authority,coordinator.store,conn,row))

    @staticmethod
    async def _settled(function,*args,**kwargs):
        """Drain a host thread after client cancellation; durable admission cannot be abandoned mid-transaction."""
        task=asyncio.create_task(asyncio.to_thread(function,*args,**kwargs))
        try:return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:await task
            finally:raise

    def _active(self, attempt_id):
        """Identify only this process's still-running original filesystem worker."""
        task=self._jobs.get(attempt_id)
        return task is not None and not task.done()

    def _schedule(self, operation):
        """Start one pending original decision after commit; an uncertain receipt never selects another operation."""
        if operation['state']=='pending' and not self._active(operation['attempt_id']):
            self._jobs[operation['attempt_id']]=asyncio.create_task(self._settled(self.store.execute,operation['project_id'],operation['operation_key']),name='researcher-retention-'+operation['attempt_id'])

    async def submit(self, project_id, attempt_id, key, kind, **body):
        """Admit an explicit quarantine/removal/restore and return its original identity before bounded background work."""
        async with self._lock:
            self.coordinator._accepting(new_work=kind!='remove')
            if self._closing:raise RunConflict('La conservación está cerrando sus operaciones originales.')
            try:existing=await self._settled(self.store.operation,project_id,key)
            except RunNotFound:existing=None
            if existing is None and self._active(attempt_id):raise RunConflict('Esta copia tiene una operación en curso; espera su recibo antes de otra decisión.')
            if kind=='archive':operation,created=await self._settled(self.store.quarantine,project_id,attempt_id,key,**body)
            else:operation,created=await self._settled(self.store.request,project_id,attempt_id,key,kind,body['archive_sha256'])
            if created:self._schedule(operation)
            return operation

    async def reconcile(self, project_id, key):
        """Explicitly resume only a recorded pending effect; original completed receipts are returned without more I/O."""
        async with self._lock:
            self.coordinator._accepting(new_work=False)
            if self._closing:raise RunConflict('La aplicación está cerrando sus operaciones originales.')
            operation=await self._settled(self.store.operation,project_id,key)
            self._schedule(operation)
            return operation

    async def wait(self, attempt_id):
        """Observe the actual worker handle for tests/shutdown without creating or replaying an operation."""
        task=self._jobs.get(attempt_id)
        if task is not None:await asyncio.shield(task)

    async def close(self):
        """Block new decisions, drain admission and wait for every original thread before releasing the runtime owner lock."""
        self._closing=True
        async with self._lock:tasks=list(self._jobs.values())
        if tasks:
            drained=asyncio.gather(*tasks,return_exceptions=True)
            try:await asyncio.shield(drained)
            except asyncio.CancelledError:
                try:await drained
                finally:raise
