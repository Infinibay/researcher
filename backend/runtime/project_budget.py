"""Owner decisions over lifetime project admission capacity; no inference, refunds, provider changes or automatic resumption."""

import json

from backend.runtime.contracts import RunConflict, RunNotFound, command_key, identity
from backend.runtime.work_budget import project_work_usage

MAX_SAFE_INTEGER = 9007199254740991


class ProjectBudgetPolicies:
    """Serialize explicit policy revisions and immutable operation receipts with the same database lock used by native dispatch admission."""

    def __init__(self, runs):
        """Reuse the serving store's transaction and event ownership without opening native processes."""
        self.runs = runs

    @staticmethod
    def _project(conn, project_id):
        """Require a real scoped project before inspecting or mutating its budget."""
        identity(project_id)
        if conn.execute('SELECT 1 FROM projects WHERE id=?',(project_id,)).fetchone() is None:
            raise RunNotFound('Project not found')

    def receipt(self, project_id, operation_key):
        """Recover the original committed decision by exact operation identity, even after later revisions; absence grants no authority."""
        command_key(operation_key)
        with self.runs._transaction() as conn:
            self._project(conn,project_id)
            row=conn.execute('SELECT receipt_json FROM runtime_project_budget_changes WHERE project_id=? AND operation_key=?',(project_id,operation_key)).fetchone()
            if row is None:raise RunNotFound('No hay un recibo guardado para esta decisión de presupuesto.')
            return json.loads(row[0])

    def update(self, project_id, *, operation_key, expected_revision, turn_limit, token_limit, reason='', auxiliary_operation_limit=None, auxiliary_cpu_ms_limit=None):
        """Compare and atomically record new total limits and their original receipt; replay returns that receipt without applying newer authority or clearing consumption."""
        command_key(operation_key)
        for name,value,minimum in [('revision',expected_revision,0),('turn limit',turn_limit,1),('token limit',token_limit,1)]:
            if type(value) is not int or not minimum<=value<=MAX_SAFE_INTEGER:
                raise ValueError('Invalid '+name)
        if not isinstance(reason,str) or len(reason.encode())>2000:
            raise ValueError('La explicación debe tener como máximo2000bytes.')
        request=dict(expected_revision=expected_revision,turn_limit=turn_limit,token_limit=token_limit,reason=reason)
        if auxiliary_operation_limit is not None or auxiliary_cpu_ms_limit is not None:
            if any(type(v) is not int or not 1<=v<=MAX_SAFE_INTEGER for v in (auxiliary_operation_limit,auxiliary_cpu_ms_limit)):
                raise ValueError('Los dos límites locales deben ser enteros positivos.')
            request.update(auxiliary_operation_limit=auxiliary_operation_limit,auxiliary_cpu_ms_limit=auxiliary_cpu_ms_limit)
        encoded=json.dumps(request,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        with self.runs._transaction(write=True) as conn:
            self._project(conn,project_id)
            previous=conn.execute('SELECT request_json,receipt_json FROM runtime_project_budget_changes WHERE project_id=? AND operation_key=?',(project_id,operation_key)).fetchone()
            if previous:
                if previous['request_json']!=encoded:raise RunConflict('La operación ya identifica otra decisión de presupuesto.')
                return json.loads(previous['receipt_json'])
            row=conn.execute('SELECT turn_limit,token_limit,revision FROM runtime_project_budgets WHERE project_id=?',(project_id,)).fetchone()
            revision=row['revision'] if row else 0
            if revision!=expected_revision:
                raise RunConflict('El presupuesto cambió. Consulta la revisión vigente antes de preparar otra decisión; no se sobrescribió.')
            if revision==MAX_SAFE_INTEGER:raise RunConflict('La revisión excede el rango admitido.')
            receipt=dict(project_id=project_id,operation_key=operation_key,**request,revision=revision+1,
                         previous_policy=dict(row) if row else None,usage_at_decision=project_work_usage(conn,project_id),
                         recorded_at=self.runs.clock(),inference_started=False)
            if auxiliary_operation_limit is not None:
                from backend.runtime.auxiliary_budget import auxiliary_summary
                receipt['previous_auxiliary']=auxiliary_summary(conn,project_id)
                conn.execute('INSERT INTO runtime_auxiliary_policies VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET operation_limit=excluded.operation_limit,cpu_ms_limit=excluded.cpu_ms_limit',
                             (project_id,auxiliary_operation_limit,auxiliary_cpu_ms_limit))
            conn.execute('INSERT INTO runtime_project_budgets(project_id,turn_limit,token_limit,revision) VALUES(?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET turn_limit=excluded.turn_limit,token_limit=excluded.token_limit,revision=excluded.revision',
                         (project_id,turn_limit,token_limit,revision+1))
            conn.execute('INSERT INTO runtime_project_budget_changes VALUES(?,?,?,?)',(project_id,operation_key,encoded,json.dumps(receipt,ensure_ascii=False,separators=(',',':'))))
            self.runs._event(conn,project_id,None,'project.budget_changed',{'operation_key':operation_key,'revision':revision+1,'turn_limit':turn_limit,'token_limit':token_limit,'inference_started':False})
            return receipt
