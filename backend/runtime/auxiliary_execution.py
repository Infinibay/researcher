"""Record bounded local-worker identity before input delivery; observe closure without signaling numeric PIDs.

These are trusted single-process parser/encoder callbacks, not namespace-init
actors. Reuse the kernel identity primitives without claiming a namespace barrier.
"""

import json
import os
import select
from contextlib import contextmanager
from contextvars import ContextVar

from backend.runtime.peer_process import _pidfd, boot_id, observer_namespace, start_ticks

CURRENT_AUXILIARY_EXECUTION = ContextVar('researcher_auxiliary_execution', default=None)


def process_identity(pid):
    """Capture an original process while its creator retains the unreaped child or is the process itself."""
    return {'pid':pid,'start_ticks':start_ticks(pid),'boot_id':boot_id(),'observer_namespace':observer_namespace()}


def process_state(record):
    """Return alive, closed or unknown using same-kernel pidfd observations, never timeout or PID alone."""
    fd=None
    try:
        if (record['boot_id'],record['observer_namespace'])!=(boot_id(),observer_namespace()):return 'unknown'
        if type(record['pid']) is not int or record['pid']<1 or type(record['start_ticks']) is not int:return 'unknown'
        try:fd=_pidfd(record['pid'])
        except ProcessLookupError:return 'closed'
        poller=select.poll();poller.register(fd,select.POLLIN|select.POLLHUP)
        if poller.poll(0):return 'closed'
        try:ticks=start_ticks(record['pid'])
        except (FileNotFoundError,ProcessLookupError):return 'closed' if poller.poll(0) else 'unknown'
        return 'alive' if ticks==record['start_ticks'] else 'closed'
    except (OSError,ValueError,KeyError,TypeError,IndexError):return 'unknown'
    finally:
        if fd is not None:os.close(fd)


class LocalExecution:
    """Carry the existing worker owner's durable identity through admission, IPC and physical reaping."""

    def __init__(self, runs, project_id, operation_id):
        """Bind one exact reservation; construction does not start a worker or acquire another owner."""
        self.runs,self.project_id,self.operation_id=runs,project_id,operation_id

    def register(self, conn):
        """Commit parent identity atomically with the original budget reservation before any callback."""
        conn.execute("INSERT INTO runtime_auxiliary_executions VALUES(?,?,?,'reserved',NULL,NULL)",
                     (self.project_id,self.operation_id,json.dumps(process_identity(os.getpid()))))

    @contextmanager
    def bound(self):
        """Make this registration available only to its synchronous trusted transport callback."""
        token=CURRENT_AUXILIARY_EXECUTION.set(self)
        try:yield self
        finally:CURRENT_AUXILIARY_EXECUTION.reset(token)

    def spawning(self):
        """Record the creation gap before Popen, so a crash cannot be mistaken for proof of no child."""
        with self.runs._transaction(write=True) as conn:
            count=conn.execute("UPDATE runtime_auxiliary_executions SET phase='spawning' WHERE project_id=? AND operation_id=? AND phase='reserved'",(self.project_id,self.operation_id)).rowcount
            if count!=1:raise RuntimeError('Local process admission is no longer original')

    def bind(self, pid):
        """Persist the unreaped original child before releasing any document or query input to it."""
        captured=json.dumps(process_identity(pid))
        with self.runs._transaction(write=True) as conn:
            count=conn.execute("UPDATE runtime_auxiliary_executions SET phase='worker',worker_json=? WHERE project_id=? AND operation_id=? AND phase='spawning'",(captured,self.project_id,self.operation_id)).rowcount
            if count!=1:raise RuntimeError('Local child identity could not be bound')

    def closed(self):
        """Record verified reaping, or failed creation with no child; never call merely because waiting timed out."""
        with self.runs._transaction(write=True) as conn:
            conn.execute("UPDATE runtime_auxiliary_executions SET phase='closed',closed_at=? WHERE project_id=? AND operation_id=? AND phase IN ('spawning','worker')",(self.runs.clock(),self.project_id,self.operation_id))

    def callback_finished(self):
        """Close callbacks that never entered process creation; leave uncertain process stages untouched."""
        with self.runs._transaction(write=True) as conn:
            conn.execute("UPDATE runtime_auxiliary_executions SET phase='closed',closed_at=? WHERE project_id=? AND operation_id=? AND phase='reserved'",(self.runs.clock(),self.project_id,self.operation_id))
