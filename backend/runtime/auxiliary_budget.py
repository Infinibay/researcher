"""Durable local-worker admission and exact result recovery, separate from generative token accounting.

Authenticated composition edges bind a project for the synchronous worker call.
Unmeasured or interrupted work retains its full CPU allowance across restarts.
"""

import hashlib
import json
import math
from contextlib import contextmanager
from contextvars import ContextVar

from backend.research.models import ResearchForbidden, SourceUnavailable, WorkerBusy
from backend.runtime.contracts import RunNotFound, identity
from backend.runtime.sqlite_runs import SQLiteRunStore

DEFAULT_POLICY = {'operation_limit': 200, 'cpu_ms_limit': 600000}
ATTEMPT_POLICY = {'operation_limit': 50, 'cpu_ms_limit': 120000}
CURRENT_AUXILIARY_BUDGET = ContextVar('researcher_auxiliary_budget', default=None)


class AuxiliaryBudgetExceeded(WorkerBusy):
    """A local project/attempt cannot reserve the complete requested allowance."""


class AuxiliaryWorkUncertain(SourceUnavailable):
    """Original work has no recoverable result; a read must not silently repeat it."""


def auxiliary_usage(conn, project_id, attempt_id=None):
    """Retain measured CPU or a conservative ceiling, never convert absence to zero."""
    return dict(conn.execute(
        """SELECT COUNT(*) AS used_operations, SUM(observed_cpu_ms) AS observed_cpu_ms,
        COALESCE(SUM(observed_cpu_ms IS NULL),0) AS unknown_operations,
        COALESCE(SUM(status='reserved'),0) AS pending_operations,
        COALESCE(SUM(input_bytes),0) AS input_bytes,
        COALESCE(SUM(COALESCE(observed_cpu_ms,cpu_ceiling_ms)),0) AS accounted_cpu_ms,
        COALESCE(SUM(CASE WHEN observed_cpu_ms IS NULL THEN cpu_ceiling_ms ELSE 0 END),0) AS held_cpu_ms
        FROM runtime_auxiliary_work WHERE project_id=? AND (? IS NULL OR attempt_id=?)""",
        (project_id,attempt_id,attempt_id)).fetchone())


def auxiliary_summary(conn, project_id):
    """Read cumulative project policy and local units without starting a worker or creating state."""
    row=conn.execute('SELECT operation_limit,cpu_ms_limit FROM runtime_auxiliary_policies WHERE project_id=?',(project_id,)).fetchone()
    policy=dict(row) if row else dict(DEFAULT_POLICY)
    usage=auxiliary_usage(conn,project_id)
    return {'policy':policy,'policy_origin':'recorded' if row else 'default',**usage,
            'remaining_operations':max(0,policy['operation_limit']-usage['used_operations']),
            'remaining_cpu_ms':max(0,policy['cpu_ms_limit']-usage['accounted_cpu_ms']),
            'attempt_policy':dict(ATTEMPT_POLICY)}


class AuxiliaryBudget:
    """Serialize local work before process admission and recover only its original completed bytes."""

    def __init__(self, database, project_id, *, research=None, scope=None):
        """Bind owner scope or an existing tool grant without granting any new capability."""
        identity(project_id)
        if (research is None)!=(scope is None) or (scope is not None and scope.project_id!=project_id):
            raise ValueError('Auxiliary authority must belong to the selected project')
        self.runs=SQLiteRunStore(database)
        self.project_id,self.research,self.scope=project_id,research,scope

    @contextmanager
    def bound(self):
        """Limit accounting context to this actual synchronous call and restore it even after failure."""
        token=CURRENT_AUXILIARY_BUDGET.set(self)
        try:yield self
        finally:CURRENT_AUXILIARY_BUDGET.reset(token)

    def _authority(self, conn):
        """Validate current stored/live authority before admission or disclosure; role names confer nothing."""
        if conn.execute('SELECT 1 FROM projects WHERE id=?',(self.project_id,)).fetchone() is None:
            raise RunNotFound('Project not found')
        if self.scope is None:return None
        self.research._check_scope(conn,self.scope)
        return conn.execute('SELECT runtime_attempt_id FROM tool_grants WHERE id=?',(self.scope.grant_id,)).fetchone()[0]

    def summary(self):
        """Expose exact local accounting for a real authorized project, including unknown consumption."""
        with self.runs._transaction() as conn:
            self._authority(conn)
            return auxiliary_summary(conn,self.project_id)

    def execute(self, data, *, kind, fingerprint, cpu_ceiling_ms, execute, on_receipt=None):
        """Reserve once and retain original bytes; optional host metadata distinguishes reused evidence from newly measured work."""
        if not isinstance(data,bytes) or not isinstance(kind,str) or not kind or len(kind)>40:
            raise ValueError('Invalid local operation input')
        if type(cpu_ceiling_ms) is not int or cpu_ceiling_ms<1 or len(fingerprint)!=64:
            raise ValueError('Invalid local operation policy')
        digest=hashlib.sha256(data).hexdigest()
        operation_id=hashlib.sha256(json.dumps([kind,fingerprint,digest,cpu_ceiling_ms]).encode()).hexdigest()
        with self.runs._transaction(write=True) as conn:
            attempt=self._authority(conn)
            prior=conn.execute('SELECT * FROM runtime_auxiliary_work WHERE project_id=? AND operation_id=?',(self.project_id,operation_id)).fetchone()
            if prior:
                if prior['output'] is None:
                    raise AuxiliaryWorkUncertain('Este cálculo local conserva consumo desconocido y no tiene resultado recuperable. No se repitió; conserva su registro para revisar la interrupción.')
                raw=bytes(prior['output'])
                if hashlib.sha256(raw).hexdigest()!=prior['output_sha256']:
                    raise AuxiliaryWorkUncertain('El resultado local guardado cambió; no se repitió el cálculo.')
                if on_receipt:on_receipt({'project_id':self.project_id,'operation_id':operation_id,'reused':True,
                                         'original_attempt_id':prior['attempt_id'],'observed_cpu_ms':prior['observed_cpu_ms'],
                                         'cpu_ceiling_ms':prior['cpu_ceiling_ms'],'measurement_origin':'original_worker'})
                return raw
            state=auxiliary_summary(conn,self.project_id)
            checks=[('proyecto',state['policy'],state)]
            if attempt:checks.append(('intento',ATTEMPT_POLICY,auxiliary_usage(conn,self.project_id,attempt)))
            for label,policy,usage in checks:
                if usage['used_operations']+1>policy['operation_limit'] or usage['accounted_cpu_ms']+cpu_ceiling_ms>policy['cpu_ms_limit']:
                    raise AuxiliaryBudgetExceeded(f'El presupuesto local del {label} no alcanza para otra operación y {cpu_ceiling_ms} ms de CPU reservada. No se inició un proceso; revisa el presupuesto del proyecto.')
            conn.execute('INSERT OR IGNORE INTO runtime_auxiliary_policies VALUES(?,?,?)',(self.project_id,*DEFAULT_POLICY.values()))
            conn.execute('''INSERT INTO runtime_auxiliary_work(project_id,operation_id,kind,fingerprint,input_sha256,input_bytes,attempt_id,grant_id,cpu_ceiling_ms,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,'reserved',?)''',(self.project_id,operation_id,kind,fingerprint,digest,len(data),attempt,self.scope.grant_id if self.scope else None,cpu_ceiling_ms,self.runs.clock()))
        try:
            raw=execute()
            if not isinstance(raw,bytes) or len(raw)>10000000:
                raise ValueError('Invalid local worker receipt')
            measured=self._measurement(raw)
        except BaseException:
            self._finish(operation_id,None,None)
            raise
        self._finish(operation_id,raw,measured)
        with self.runs._transaction() as conn:self._authority(conn)
        if on_receipt:on_receipt({'project_id':self.project_id,'operation_id':operation_id,'reused':False,
                                 'original_attempt_id':attempt,'observed_cpu_ms':measured,
                                 'cpu_ceiling_ms':cpu_ceiling_ms,'measurement_origin':'original_worker'})
        return raw

    @staticmethod
    def _measurement(raw):
        """Extract finite nonnegative worker CPU only; missing or malformed telemetry stays unknown."""
        try:
            result=json.loads(raw)
            observation=result.get('execution') or result.get('provenance',{}).get('execution',{})
            seconds=observation.get('cpu_used_seconds')
            return math.ceil(seconds*1000) if type(seconds) in (int,float) and math.isfinite(seconds) and 0<=seconds<=86400 else None
        except (ValueError,TypeError,AttributeError):return None

    def _finish(self, operation_id, output, observed):
        """Commit resource evidence even after authority withdrawal; failure to persist leaves the original reservation intact."""
        with self.runs._transaction(write=True) as conn:
            updated=conn.execute('''UPDATE runtime_auxiliary_work SET status=?,observed_cpu_ms=?,output=?,output_sha256=?,finished_at=?
                WHERE project_id=? AND operation_id=? AND status='reserved' ''',
                ('settled' if output is not None else 'unknown',observed,output,hashlib.sha256(output).hexdigest() if output is not None else None,self.runs.clock(),self.project_id,operation_id))
            if updated.rowcount!=1:raise AuxiliaryWorkUncertain('El recibo local ya no corresponde a su reserva original.')
